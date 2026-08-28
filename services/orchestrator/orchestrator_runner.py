import asyncio
import json
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Any, List, Optional

import asyncpg
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from db import create_job, dsn, search_song_fuzzy, update_job, upsert_song
from redis_queue import (
    REDIS_URL,
    RESULT_GROUP,
    RESULT_STREAM,
    STREAMS,
    enqueue_task,
    ensure_consumer_group,
    first_requested_stage,
    new_consumer_name,
    reclaim_one,
    task_for_job,
)
from utils import FRONTEND_ORIGIN, compute_fingerprint_hash, save_uploaded_file


logging.basicConfig(level=logging.INFO, format="%(levelname)-9s %(message)s")
logger = logging.getLogger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await asyncpg.create_pool(dsn=dsn)
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    await ensure_consumer_group(app.state.redis, RESULT_STREAM, RESULT_GROUP)

    app.state.stop_event = asyncio.Event()
    app.state.result_task = asyncio.create_task(result_loop(app))

    try:
        yield
    finally:
        app.state.stop_event.set()
        app.state.result_task.cancel()
        await asyncio.gather(app.state.result_task, return_exceptions=True)
        await app.state.redis.aclose()
        await app.state.db_pool.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def result_loop(app: FastAPI) -> None:
    redis: Redis = app.state.redis
    stop: asyncio.Event = app.state.stop_event
    consumer = new_consumer_name("orchestrator")

    logger.info("Redis result consumer starting: %s", consumer)
    try:
        while not stop.is_set():
            message = await reclaim_one(redis, RESULT_STREAM, RESULT_GROUP, consumer)
            if message is None:
                batches = await redis.xreadgroup(
                    RESULT_GROUP,
                    consumer,
                    {RESULT_STREAM: ">"},
                    count=10,
                    block=5000,
                )
                messages = batches[0][1] if batches else []
            else:
                messages = [message]

            for message_id, fields in messages:
                try:
                    event = json.loads(fields["payload"])
                    await handle_event(app, event)
                    await redis.xack(RESULT_STREAM, RESULT_GROUP, message_id)
                except Exception:
                    logger.exception("Unable to process Redis result event %s", message_id)
                    # Leave the message pending so a later consumer can reclaim it.
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Redis result consumer exiting")


async def handle_event(app: FastAPI, event: dict[str, Any]) -> None:
    event_type = event.get("event")
    job_id = int(event["job_id"])
    stage = event["stage"]

    if stage not in STREAMS:
        raise ValueError(f"Unknown result stage: {stage}")

    pool: asyncpg.Pool = app.state.db_pool
    redis: Redis = app.state.redis

    if event_type == "started":
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'In Progress', current_stage = $2
                WHERE id = $1 AND current_stage = $2 AND status <> 'Completed'
                """,
                job_id,
                stage,
            )
        return

    if event_type != "completed":
        raise ValueError(f"Unknown Redis result event: {event_type}")

    next_task: dict[str, Any] | None = None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1 FOR UPDATE", job_id)
            if not row:
                logger.warning("Ignoring result for missing job %s", job_id)
                return

            if row[f"done_{stage}"]:
                logger.info("Ignoring duplicate %s result for job %s", stage, job_id)
                return

            if not event.get("ok", False):
                await conn.execute(
                    "UPDATE jobs SET status = 'Failed', current_stage = $2 WHERE id = $1",
                    job_id,
                    stage,
                )
                logger.error("Job %s failed at %s: %s", job_id, stage, event.get("error"))
                return

            result = event.get("result") or {}
            await update_job(conn, job_id, **stage_updates(stage, result))

            updated = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1 FOR UPDATE", job_id)
            next_stage = first_requested_stage(dict(updated))
            if next_stage:
                await conn.execute(
                    "UPDATE jobs SET status = 'Queued', current_stage = $2 WHERE id = $1",
                    job_id,
                    next_stage,
                )
                updated = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
                next_task = task_for_job(dict(updated), next_stage)
            else:
                song_id = await upsert_song(
                    conn,
                    title=updated["title"],
                    artist=updated["artist"],
                    duration=updated["duration"],
                    fingerprint=updated["fingerprint"],
                    fingerprint_hash=updated["fingerprint_hash"],
                    lyrics=updated["lyrics"],
                    classification=updated["classification"],
                    accuracy=updated["accuracy"],
                    file_path=updated["file_path"],
                    audio_processed=updated["audio_processed"],
                )
                await conn.execute(
                    "UPDATE jobs SET status = 'Completed', song_id = $2 WHERE id = $1",
                    job_id,
                    song_id,
                )

    if next_task:
        await enqueue_task(redis, next_task)
        logger.info("Queued job %s for %s", job_id, next_task["stage"])
    else:
        logger.info("Job %s completed", job_id)


def stage_updates(stage: str, result: dict[str, Any]) -> dict[str, Any]:
    if stage == "identify":
        matches = result.get("matches") or []
        first_match = matches[0] if matches else {}
        fingerprint = result.get("fingerprint")
        return {
            "title": first_match.get("title") or "Unknown",
            "artist": first_match.get("artist") or "Unknown",
            "duration": result.get("duration"),
            "fingerprint": fingerprint,
            "fingerprint_hash": compute_fingerprint_hash(fingerprint) if fingerprint else None,
            "file_path": result.get("file_path"),
            "done_identify": True,
        }
    if stage == "demucs":
        return {
            "file_path": result.get("file_path"),
            "audio_processed": True,
            "done_demucs": True,
        }
    if stage == "whisper":
        return {"lyrics": result.get("lyrics"), "done_whisper": True}
    if stage == "classify":
        return {
            "classification": result.get("classification"),
            "accuracy": result.get("accuracy"),
            "done_classify": True,
        }
    raise ValueError(f"Unknown stage: {stage}")


@app.get("/health")
async def health(request: Request):
    try:
        await request.app.state.redis.ping()
        if request.app.state.result_task.done():
            raise RuntimeError("Redis result consumer is not running")
        return {"status": "ok", "redis": "ok"}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "unavailable", "error": str(exc)})


@app.get("/api/songs")
async def list_songs(request: Request):
    try:
        pool = request.app.state.db_pool
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM songs ORDER BY created_at DESC")
            return JSONResponse(status_code=200, content=jsonable_encoder([dict(row) for row in rows]))
    except Exception:
        logger.exception("DB error in GET /songs")
        return JSONResponse(status_code=500, content={"error": "Database error"})


@app.get("/api/songs/{song_id}")
async def get_song(request: Request, song_id: int):
    try:
        pool = request.app.state.db_pool
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM songs WHERE id = $1", song_id)
            if not row:
                raise HTTPException(status_code=404, detail="Song not found")
            return JSONResponse(status_code=200, content=jsonable_encoder(dict(row)))
    except HTTPException:
        raise
    except Exception:
        logger.exception("DB error in GET /song/%s", song_id)
        return JSONResponse(status_code=500, content={"error": "Database error"})


@app.get("/api/jobs/{job_id}")
async def get_job(request: Request, job_id: int):
    try:
        pool = request.app.state.db_pool
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
            return JSONResponse(status_code=200, content=jsonable_encoder(dict(row)))
    except HTTPException:
        raise
    except Exception:
        logger.exception("DB error in GET /job/%s", job_id)
        return JSONResponse(status_code=500, content={"error": "Database error"})


@app.post("/api/analyze")
async def analyze(
    request: Request,
    input_type: str = Form(...),
    audio: Optional[UploadFile] = File(None),
    outputs: List[str] = Form(...),
    title: str = Form(""),
    artist: str = Form(""),
    lyrics: str = Form(""),
):
    try:
        if input_type not in {"audio", "text", "search"}:
            return {"success": False, "error": "Unsupported input type"}

        db_pool = request.app.state.db_pool
        requested = {
            "want_identify": "identify" in outputs,
            "want_demucs": "stems" in outputs,
            "want_whisper": "lyrics" in outputs,
            "want_classify": "classification" in outputs,
        }

        if input_type == "audio":
            if not audio:
                return {"success": False, "error": "Missing audio file for input_type 'audio'"}
            file_path = save_uploaded_file(audio)
        elif input_type == "text":
            if not lyrics.strip():
                return {"success": False, "error": "Missing lyrics for text input"}
            file_path = None
        else:
            if not title or not artist:
                return {"success": False, "error": "Missing title or artist for search input"}
            matches = await search_song_fuzzy(db_pool, title, artist)
            if matches and matches[0].get("score", 0) >= 0.3:
                return {"success": True, "song_id": matches[0]["id"], "match": matches[0]}
            return {"success": False, "error": "Not found", "status": 404}

        if not any(requested.values()):
            return {"success": False, "error": "Select at least one output"}

        initial_stage = next(
            stage for stage in ("identify", "demucs", "whisper", "classify")
            if requested[f"want_{stage}"]
        )

        async with db_pool.acquire() as conn:
            job_id = await create_job(
                conn,
                title=title or "Untitled",
                artist=artist,
                lyrics=lyrics or None,
                input_type=input_type,
                current_stage=initial_stage,
                status="Queued",
                file_path=file_path,
                **requested,
            )
            job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)

        try:
            await enqueue_task(request.app.state.redis, task_for_job(dict(job), initial_stage))
        except Exception:
            async with db_pool.acquire() as conn:
                await update_job(conn, job_id, status="Failed")
            raise

        logger.info("Queued job %s for %s", job_id, initial_stage)
        return {"success": True, "job_id": job_id}
    except Exception as exc:
        logger.exception("Unable to create analysis job")
        tb = traceback.extract_tb(exc.__traceback__)
        line = tb[-1].lineno if tb else "unknown"
        return {"success": False, "error": f"{exc} (line {line})"}
