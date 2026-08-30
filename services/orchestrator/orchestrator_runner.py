import asyncio
import json
import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import asyncpg
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from auth import get_current_user
from db import (
    consume_daily_analysis,
    create_job,
    dsn,
    get_job_with_steps_for_user,
    record_user_song,
    search_song_fuzzy,
    update_job,
    upsert_song,
)
from redis_cache import cache_song_id
from redis_queue import REDIS_URL, RESULT_GROUP, RESULT_STREAM, STREAMS, enqueue_task, ensure_consumer_group, new_consumer_name, reclaim_one, task_for_job
from utils import FRONTEND_ORIGIN, compute_fingerprint_hash, save_uploaded_file

logging.basicConfig(level=logging.INFO, format="%(levelname)-9s %(message)s")
logger = logging.getLogger("orchestrator")
STAGE_ORDER = ("identify", "demucs", "whisper", "classify")
OUTPUT_TO_STAGE = {"identify": "identify", "stems": "demucs", "lyrics": "whisper", "classification": "classify"}
DAILY_ANALYSIS_LIMIT = 10


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
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


async def result_loop(app: FastAPI) -> None:
    redis = app.state.redis
    consumer = new_consumer_name("orchestrator")
    try:
        while not app.state.stop_event.is_set():
            message = await reclaim_one(redis, RESULT_STREAM, RESULT_GROUP, consumer)
            if message is None:
                batches = await redis.xreadgroup(RESULT_GROUP, consumer, {RESULT_STREAM: ">"}, count=10, block=5000)
                messages = batches[0][1] if batches else []
            else:
                messages = [message]
            for message_id, fields in messages:
                try:
                    await handle_event(app, json.loads(fields["payload"]))
                    await redis.xack(RESULT_STREAM, RESULT_GROUP, message_id)
                except Exception:
                    logger.exception("Unable to process Redis result event %s", message_id)
    except asyncio.CancelledError:
        pass


async def handle_event(app: FastAPI, event: dict[str, Any]) -> None:
    job_id = int(event["job_id"])
    stage = event["stage"]
    if stage not in STREAMS:
        raise ValueError(f"Unknown result stage: {stage}")
    pool = app.state.db_pool
    redis = app.state.redis
    next_task = None
    async with pool.acquire() as conn:
        async with conn.transaction():
            job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1 FOR UPDATE", job_id)
            step = await conn.fetchrow("SELECT * FROM job_steps WHERE job_id = $1 AND stage = $2 FOR UPDATE", job_id, stage)
            if not job or not step:
                logger.warning("Ignoring result for missing job/step %s/%s", job_id, stage)
                return
            if event.get("event") == "started":
                await conn.execute("UPDATE job_steps SET status = 'processing', started_at = COALESCE(started_at, CURRENT_TIMESTAMP) WHERE id = $1 AND status = 'queued'", step["id"])
                await update_job(conn, job_id, status="processing", current_stage=stage)
                return
            if event.get("event") != "completed":
                raise ValueError(f"Unknown Redis result event: {event.get('event')}")
            if step["status"] == "completed":
                return
            if not event.get("ok", False):
                error = event.get("error", "stage failed")
                await conn.execute("UPDATE job_steps SET status = 'failed', error = $2, completed_at = CURRENT_TIMESTAMP WHERE id = $1", step["id"], error)
                await update_job(conn, job_id, status="failed", current_stage=stage, error=error)
                return
            result = event.get("result") or {}
            await update_job(conn, job_id, **stage_updates(stage, result))
            await conn.execute("UPDATE job_steps SET status = 'completed', result = $2::jsonb, error = NULL, completed_at = CURRENT_TIMESTAMP WHERE id = $1", step["id"], json.dumps(result))
            next_step = await conn.fetchrow("SELECT stage FROM job_steps WHERE job_id = $1 AND status = 'queued' ORDER BY position LIMIT 1", job_id)
            if next_step:
                await update_job(conn, job_id, status="queued", current_stage=next_step["stage"])
                updated = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
                next_task = task_for_job(dict(updated), next_step["stage"])
            else:
                song_id = await upsert_song(conn, title=job["title"], artist=job["artist"], duration=job["duration"], fingerprint=job["fingerprint"], fingerprint_hash=job["fingerprint_hash"], lyrics=job["lyrics"], classification=job["classification"], accuracy=job["accuracy"], file_path=job["file_path"], audio_processed=job["audio_processed"])
                await update_job(conn, job_id, status="completed", current_stage=None, song_id=song_id, completed_at=datetime.now(timezone.utc).replace(tzinfo=None), error=None)
                if job["user_id"] is not None:
                    await record_user_song(conn, user_id=job["user_id"], song_id=song_id)
                await cache_song_id(redis, job["fingerprint_hash"], song_id)
    if next_task:
        await enqueue_task(redis, next_task)


def stage_updates(stage: str, result: dict[str, Any]) -> dict[str, Any]:
    if stage == "identify":
        match = (result.get("matches") or [{}])[0]
        fingerprint = result.get("fingerprint")
        return {"title": match.get("title") or "Unknown", "artist": match.get("artist") or "Unknown", "duration": result.get("duration"), "fingerprint": fingerprint, "fingerprint_hash": compute_fingerprint_hash(fingerprint) if fingerprint else None, "file_path": result.get("file_path")}
    if stage == "demucs":
        return {"file_path": result.get("file_path"), "audio_processed": True}
    if stage == "whisper":
        return {"lyrics": result.get("lyrics")}
    if stage == "classify":
        return {"classification": result.get("classification"), "accuracy": result.get("accuracy")}
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
async def list_songs(request: Request, user: dict = Depends(get_current_user)):
    try:
        async with request.app.state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT songs.*
                FROM songs
                ORDER BY songs.updated_at DESC NULLS LAST, songs.id DESC
                """,
            )
        return JSONResponse(status_code=200, content=jsonable_encoder([dict(row) for row in rows]))
    except Exception:
        logger.exception("Database error listing songs")
        return JSONResponse(status_code=500, content={"error": "Database error"})


@app.get("/api/songs/mine")
async def list_my_songs(request: Request, user: dict = Depends(get_current_user)):
    try:
        async with request.app.state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT songs.*, user_songs.first_submitted_at,
                       user_songs.last_submitted_at, user_songs.submission_count
                FROM songs
                JOIN user_songs ON user_songs.song_id = songs.id
                WHERE user_songs.user_id = $1
                ORDER BY user_songs.last_submitted_at DESC, songs.id DESC
                """,
                user["id"],
            )
        return JSONResponse(status_code=200, content=jsonable_encoder([dict(row) for row in rows]))
    except Exception:
        logger.exception("Database error listing the user's songs")
        return JSONResponse(status_code=500, content={"error": "Database error"})


@app.get("/api/songs/{song_id}")
async def get_song(request: Request, song_id: int, user: dict = Depends(get_current_user)):
    try:
        async with request.app.state.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT songs.*
                FROM songs
                WHERE songs.id = $1
                """,
                song_id,
            )
        if not row:
            raise HTTPException(status_code=404, detail="Song not found")
        return JSONResponse(status_code=200, content=jsonable_encoder(dict(row)))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error getting song %s", song_id)
        return JSONResponse(status_code=500, content={"error": "Database error"})


@app.get("/api/jobs/{job_id}")
async def get_job(request: Request, job_id: int, user: dict = Depends(get_current_user)):
    try:
        job = await get_job_with_steps_for_user(request.app.state.db_pool, job_id, user["id"])
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JSONResponse(status_code=200, content=jsonable_encoder(job))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error getting job %s", job_id)
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
    user: dict = Depends(get_current_user),
):
    try:
        db_pool = request.app.state.db_pool
        if input_type == "search":
            if not title or not artist:
                return {"success": False, "error": "Missing title or artist for search input"}
            matches = await search_song_fuzzy(db_pool, title, artist)
            if matches and matches[0].get("score", 0) >= 0.3:
                return {"success": True, "song_id": matches[0]["id"], "match": matches[0]}
            return {"success": False, "error": "Not found", "status": 404}
        selected = {OUTPUT_TO_STAGE[out] for out in outputs if out in OUTPUT_TO_STAGE}
        if input_type == "text":
            selected -= {"identify", "demucs"}
            if not lyrics.strip():
                return {"success": False, "error": "Missing lyrics for text input"}
        elif input_type == "audio":
            if not audio:
                return {"success": False, "error": "Missing audio file for audio input"}
        else:
            return {"success": False, "error": f"Unsupported input type: {input_type}"}
        stages = [stage for stage in STAGE_ORDER if stage in selected]
        if not stages:
            return {"success": False, "error": "At least one valid output is required"}

        async with db_pool.acquire() as conn:
            usage_count = await consume_daily_analysis(
                conn,
                user_id=user["id"],
                usage_date=datetime.now(timezone.utc).date(),
                limit=DAILY_ANALYSIS_LIMIT,
            )
        if usage_count is None:
            reset_at = datetime.combine(
                datetime.now(timezone.utc).date(),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            reset_at += timedelta(days=1)
            retry_after = max(1, int((reset_at - datetime.now(timezone.utc)).total_seconds()))
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Daily analysis limit reached",
                    "limit": DAILY_ANALYSIS_LIMIT,
                    "reset_at": reset_at.isoformat(),
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(DAILY_ANALYSIS_LIMIT),
                    "X-RateLimit-Remaining": "0",
                },
            )

        file_path = save_uploaded_file(audio) if input_type == "audio" else None
        async with db_pool.acquire() as conn:
            job_id = await create_job(conn, user_id=user["id"], stages=stages, title=title or "Untitled", artist=artist, lyrics=lyrics or None, input_type=input_type, file_path=file_path)
            job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        await enqueue_task(request.app.state.redis, task_for_job(dict(job), stages[0]))
        return {
            "success": True,
            "job_id": job_id,
            "rate_limit": {
                "limit": DAILY_ANALYSIS_LIMIT,
                "remaining": DAILY_ANALYSIS_LIMIT - usage_count,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unable to create analysis job")
        line = traceback.extract_tb(exc.__traceback__)[-1].lineno if exc.__traceback__ else "unknown"
        return {"success": False, "error": f"{exc} (line {line})"}
