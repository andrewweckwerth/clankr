import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

import asyncpg
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from db import (
    create_job,
    dsn,
    get_job_with_steps,
    search_song_fuzzy,
    update_job,
    upsert_song,
)
from services import run_acousti, run_classify, run_demucs, run_whisper
from utils import FRONTEND_ORIGIN, compute_fingerprint_hash, save_uploaded_file
from redis_cache import cache_song_id, find_song_by_fingerprint


logging.basicConfig(level=logging.INFO, format="%(levelname)-9s %(message)s")
logger = logging.getLogger("orchestrator")

STAGE_ORDER = ("identify", "demucs", "whisper", "classify")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
OUTPUT_TO_STAGE = {
    "identify": "identify",
    "stems": "demucs",
    "lyrics": "whisper",
    "classification": "classify",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await asyncpg.create_pool(dsn=dsn)
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await app.state.redis.ping()
        logger.info("Redis cache connected")
    except Exception:
        logger.warning("Redis cache unavailable; PostgreSQL fallback will be used", exc_info=True)
    app.state.stop_event = asyncio.Event()
    worker_count = 3
    app.state.worker_tasks = [
        asyncio.create_task(
            worker_loop(app.state.db_pool, app.state.redis, app.state.stop_event)
        )
        for _ in range(worker_count)
    ]

    try:
        yield
    finally:
        app.state.stop_event.set()
        for task in app.state.worker_tasks:
            task.cancel()
        await asyncio.gather(*app.state.worker_tasks, return_exceptions=True)
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


async def worker_loop(
    pool: asyncpg.Pool,
    redis_client: Redis,
    stop: asyncio.Event,
    poll_interval: float = 0.5,
):
    logger.info("worker_loop starting")
    try:
        while not stop.is_set():
            async with pool.acquire() as conn:
                try:
                    worked = await process_job(conn, redis_client)
                except Exception:
                    await asyncio.sleep(1.0)
                    continue

            if not worked:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("worker_loop exiting")


async def process_job(conn: asyncpg.Connection, redis_client: Redis) -> bool:
    """Claim and execute exactly one queued job step."""
    job = await get_and_claim_job(conn)
    if not job:
        return False

    job_id = job["id"]
    job_step_id = job["job_step_id"]
    stage = job["stage"]
    file_path = job["file_path"]

    try:
        if stage == "identify":
            acousti_out = await run_acousti(file_path)
            matches = acousti_out.get("matches", [])
            match = matches[0] if matches else {}
            fingerprint = acousti_out.get("fingerprint")
            fingerprint_hash = compute_fingerprint_hash(fingerprint) if fingerprint else None
            if not fingerprint_hash:
                raise RuntimeError("Acousti did not produce a fingerprint")

            converted_path = acousti_out.get("file_path")
            await update_job(
                conn,
                job_id,
                title=match.get("title") or job["title"] or "Unknown",
                artist=match.get("artist") or job["artist"],
                duration=acousti_out.get("duration"),
                fingerprint=fingerprint,
                fingerprint_hash=fingerprint_hash,
                file_path=converted_path,
            )

            existing_song = await find_song_by_fingerprint(
                conn,
                redis_client,
                fingerprint_hash,
            )
            if existing_song:
                await reuse_cached_steps(conn, job, existing_song)

            result = {
                "file_path": converted_path,
                "fingerprint": fingerprint,
                "fingerprint_hash": fingerprint_hash,
                "duration": acousti_out.get("duration"),
                "matches": matches,
            }
        elif stage == "demucs":
            demucs_out = await run_demucs(file_path)
            output_path = demucs_out.get("file_path")
            await update_job(
                conn,
                job_id,
                file_path=output_path,
                audio_processed=True,
            )
            result = demucs_out
        elif stage == "whisper":
            whisper_out = await run_whisper(file_path)
            await update_job(conn, job_id, lyrics=whisper_out.get("lyrics"))
            result = whisper_out
        elif stage == "classify":
            classify_out = await run_classify(job["lyrics"])
            await update_job(
                conn,
                job_id,
                classification=classify_out.get("classification"),
                accuracy=classify_out.get("accuracy"),
            )
            result = classify_out
        else:
            raise RuntimeError(f"Unknown job stage: {stage}")

        await complete_job_step(conn, job_step_id, result)
        song_id = await finalize_job_if_ready(conn, job_id)
        if song_id is not None:
            fingerprint_hash = await conn.fetchval(
                "SELECT fingerprint_hash FROM jobs WHERE id = $1",
                job_id,
            )
            await cache_song_id(redis_client, fingerprint_hash, song_id)
        if song_id is None:
            await queue_next_step(conn, job_id)
        logger.info("Completed job step %s for job %s", job_step_id, job_id)
        return True
    except Exception as exc:
        error = str(exc)
        await fail_job_step(conn, job_id, job_step_id, error)
        logger.exception("Job %s failed at step %s", job_id, job_step_id)
        raise


async def reuse_cached_steps(
    conn: asyncpg.Connection,
    job: dict,
    song: asyncpg.Record,
) -> None:
    """Complete later steps that can be reused from an existing song."""
    rows = await conn.fetch(
        """
        SELECT id, stage
        FROM job_steps
        WHERE job_id = $1 AND position > $2 AND status = 'queued'
        ORDER BY position
        """,
        job["id"],
        job["step_position"],
    )

    job_updates = {}
    cached_results = []
    for row in rows:
        if row["stage"] == "demucs":
            cached_path = song["file_path"]
            if cached_path and cached_path.startswith("stems/"):
                job_updates["file_path"] = cached_path
                job_updates["audio_processed"] = True
                cached_results.append((row["id"], {"file_path": cached_path}))
        elif row["stage"] == "whisper" and song["lyrics"] is not None:
            job_updates["lyrics"] = song["lyrics"]
            cached_results.append((row["id"], {"lyrics": song["lyrics"], "cached": True}))
        elif row["stage"] == "classify" and song["classification"] is not None:
            job_updates["classification"] = song["classification"]
            job_updates["accuracy"] = song["accuracy"]
            cached_results.append(
                (
                    row["id"],
                    {
                        "classification": song["classification"],
                        "accuracy": song["accuracy"],
                        "cached": True,
                    },
                )
            )

    if job_updates:
        await update_job(conn, job["id"], **job_updates)
    for step_id, result in cached_results:
        await complete_job_step(conn, step_id, result)


async def complete_job_step(
    conn: asyncpg.Connection,
    job_step_id: int,
    result: Optional[dict],
) -> None:
    import json

    result_json = json.dumps(result) if result is not None else None
    await conn.execute(
        """
        UPDATE job_steps
        SET status = 'completed',
            result = $2::jsonb,
            error = NULL,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """,
        job_step_id,
        result_json,
    )


async def fail_job_step(
    conn: asyncpg.Connection,
    job_id: int,
    job_step_id: int,
    error: str,
) -> None:
    await conn.execute(
        """
        UPDATE job_steps
        SET status = 'failed', error = $2, completed_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """,
        job_step_id,
        error,
    )
    await update_job(
        conn,
        job_id,
        status="failed",
        error=error,
    )


async def queue_next_step(conn: asyncpg.Connection, job_id: int) -> None:
    next_step = await conn.fetchrow(
        """
        SELECT stage
        FROM job_steps
        WHERE job_id = $1 AND status = 'queued'
        ORDER BY position
        LIMIT 1
        """,
        job_id,
    )
    if next_step:
        await update_job(
            conn,
            job_id,
            status="queued",
            current_stage=next_step["stage"],
        )


async def finalize_job_if_ready(
    conn: asyncpg.Connection,
    job_id: int,
) -> Optional[int]:
    """Create/update the song once every requested step has completed."""
    async with conn.transaction():
        job = await conn.fetchrow(
            "SELECT * FROM jobs WHERE id = $1 FOR UPDATE",
            job_id,
        )
        if not job or job["status"] in ("failed", "cancelled", "completed"):
            return None

        has_incomplete = await conn.fetchval(
            """
            SELECT EXISTS(
              SELECT 1 FROM job_steps
              WHERE job_id = $1 AND status <> 'completed'
            )
            """,
            job_id,
        )
        if has_incomplete:
            return None

        song_id = await upsert_song(
            conn,
            title=job["title"],
            artist=job["artist"],
            duration=job["duration"],
            fingerprint=job["fingerprint"],
            fingerprint_hash=job["fingerprint_hash"],
            lyrics=job["lyrics"],
            classification=job["classification"],
            accuracy=float(job["accuracy"]) if job["accuracy"] is not None else None,
            file_path=job["file_path"],
            audio_processed=bool(job["audio_processed"]),
        )
        await update_job(
            conn,
            job_id,
            status="completed",
            current_stage=None,
            song_id=song_id,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            error=None,
        )
        return song_id


async def get_and_claim_job(conn: asyncpg.Connection) -> Optional[dict]:
    """Atomically claim the next queued stage."""
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT j.*, s.id AS job_step_id, s.stage AS stage,
                   s.position AS step_position
            FROM jobs AS j
            JOIN job_steps AS s ON s.job_id = j.id
            WHERE j.status = 'queued' AND s.status = 'queued'
            ORDER BY j.id, s.position
            FOR UPDATE OF j, s SKIP LOCKED
            LIMIT 1
            """
        )
        if not row:
            return None

        await conn.execute(
            """
            UPDATE job_steps
            SET status = 'processing',
                attempts = attempts + 1,
                started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
            WHERE id = $1
            """,
            row["job_step_id"],
        )
        await conn.execute(
            """
            UPDATE jobs
            SET status = 'processing', current_stage = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            row["id"],
            row["stage"],
        )
        return dict(row)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/songs")
async def list_songs(request: Request):
    try:
        async with request.app.state.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM songs ORDER BY created_at DESC")
            return JSONResponse(
                status_code=200,
                content=jsonable_encoder([dict(row) for row in rows]),
            )
    except Exception:
        logger.exception("Database error listing songs")
        return JSONResponse(status_code=500, content={"error": "Database error"})


@app.get("/api/songs/{song_id}")
async def get_song(request: Request, song_id: int):
    try:
        async with request.app.state.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM songs WHERE id = $1", song_id)
            if not row:
                raise HTTPException(status_code=404, detail="Song not found")
            return JSONResponse(status_code=200, content=jsonable_encoder(dict(row)))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error getting song %s", song_id)
        return JSONResponse(status_code=500, content={"error": "Database error"})


@app.get("/api/jobs/{job_id}")
async def get_job(request: Request, job_id: int):
    try:
        job = await get_job_with_steps(request.app.state.db_pool, job_id)
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

        selected_stages = {
            OUTPUT_TO_STAGE[output]
            for output in outputs
            if output in OUTPUT_TO_STAGE
        }
        if input_type == "text":
            selected_stages.discard("identify")
            selected_stages.discard("demucs")
            if not lyrics:
                return {"success": False, "error": "Missing lyrics for text input"}
        elif input_type == "audio":
            if not audio:
                return {"success": False, "error": "Missing audio file for audio input"}
        else:
            return {"success": False, "error": f"Unsupported input type: {input_type}"}

        stages = [stage for stage in STAGE_ORDER if stage in selected_stages]
        if not stages:
            return {"success": False, "error": "At least one valid output is required"}

        file_path = None
        if input_type == "audio":
            file_path = save_uploaded_file(audio)

        async with db_pool.acquire() as conn:
            job_id = await create_job(
                conn,
                stages=stages,
                title=title,
                artist=artist,
                lyrics=lyrics or None,
                input_type=input_type,
                file_path=file_path,
            )
        return {"success": True, "job_id": job_id}
    except Exception as exc:
        logger.exception("Unable to create analysis job")
        return {"success": False, "error": str(exc)}
