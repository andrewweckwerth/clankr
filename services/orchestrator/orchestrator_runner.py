import asyncio
import json
import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import asyncpg
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis

from auth import get_current_user
from db import (
    consume_daily_analysis,
    create_job,
    dsn,
    get_daily_analysis_usage,
    get_job_with_steps_for_user,
    list_jobs_for_user,
    record_user_song,
    update_job,
    upsert_song,
)
from redis_cache import cache_song_id, find_song_by_fingerprint
from redis_queue import REDIS_URL, RESULT_GROUP, RESULT_STREAM, STREAMS, enqueue_task, ensure_consumer_group, new_consumer_name, reclaim_one, task_for_job
from utils import FRONTEND_ORIGIN, compute_fingerprint_hash, copy_source_object, delete_object_keys, object_exists, save_uploaded_file, stream_object

logging.basicConfig(level=logging.INFO, format="%(levelname)-9s %(message)s")
logger = logging.getLogger("orchestrator")
STAGE_ORDER = ("identify", "demucs", "whisper", "classify")
JOB_TYPE_STAGES = {
    "full": STAGE_ORDER,
    "acousti": ("identify",),
    "demucs": ("demucs",),
    "whisper": ("whisper",),
    "classifier": ("classify",),
}
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
                if job["status"] in ("completed", "failed", "cancelled") or step["status"] != "queued":
                    return
                await conn.execute("UPDATE job_steps SET status = 'processing', started_at = COALESCE(started_at, CURRENT_TIMESTAMP) WHERE id = $1 AND status = 'queued'", step["id"])
                await update_job(conn, job_id, status="processing", current_stage=stage)
                return
            if event.get("event") != "completed":
                raise ValueError(f"Unknown Redis result event: {event.get('event')}")
            if step["status"] in ("completed", "failed", "cancelled"):
                return
            if not event.get("ok", False):
                error = event.get("error", "stage failed")
                await conn.execute("UPDATE job_steps SET status = 'failed', error = $2, completed_at = CURRENT_TIMESTAMP WHERE id = $1", step["id"], error)
                await update_job(conn, job_id, status="failed", current_stage=stage, error=error)
                return
            result = event.get("result") or {}
            await update_job(conn, job_id, **stage_updates(stage, result))
            await conn.execute("UPDATE job_steps SET status = 'completed', result = $2::jsonb, error = NULL, completed_at = CURRENT_TIMESTAMP WHERE id = $1", step["id"], json.dumps(result))
            updated_job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)

            if (
                stage == "identify"
                and updated_job["job_type"] in ("full", "acousti")
                and updated_job["fingerprint_hash"]
            ):
                cached_song = await find_song_by_fingerprint(
                    conn,
                    redis,
                    updated_job["fingerprint_hash"],
                )
                if cached_song:
                    await conn.execute(
                        """
                        UPDATE job_steps
                        SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP
                        WHERE job_id = $1 AND status = 'queued'
                        """,
                        job_id,
                    )
                    await record_user_song(
                        conn,
                        user_id=updated_job["user_id"],
                        song_id=cached_song["id"],
                    )
                    await update_job(
                        conn,
                        job_id,
                        status="completed",
                        current_stage=None,
                        song_id=cached_song["id"],
                        cache_hit=True,
                        title=cached_song["title"],
                        artist=cached_song["artist"],
                        lyrics=cached_song["lyrics"],
                        classification=cached_song["classification"],
                        accuracy=cached_song["accuracy"],
                        file_path=cached_song["file_path"],
                        audio_processed=cached_song["audio_processed"],
                        completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        error=None,
                    )
                    return

            next_step = await conn.fetchrow("SELECT stage FROM job_steps WHERE job_id = $1 AND status = 'queued' ORDER BY position LIMIT 1", job_id)
            if next_step:
                await update_job(conn, job_id, status="queued", current_stage=next_step["stage"])
                updated = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
                next_task = task_for_job(dict(updated), next_step["stage"])
            elif updated_job["job_type"] == "full":
                song_id = await upsert_song(conn, title=updated_job["title"], artist=updated_job["artist"], duration=updated_job["duration"], fingerprint=updated_job["fingerprint"], fingerprint_hash=updated_job["fingerprint_hash"], lyrics=updated_job["lyrics"], classification=updated_job["classification"], accuracy=updated_job["accuracy"], file_path=updated_job["file_path"], audio_processed=updated_job["audio_processed"])
                await update_job(conn, job_id, status="completed", current_stage=None, song_id=song_id, completed_at=datetime.now(timezone.utc).replace(tzinfo=None), error=None)
                await record_user_song(conn, user_id=updated_job["user_id"], song_id=song_id)
                await cache_song_id(redis, updated_job["fingerprint_hash"], song_id)
            else:
                await update_job(
                    conn,
                    job_id,
                    status="completed",
                    current_stage=None,
                    completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    error=None,
                )
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


async def consume_quota_or_raise(pool, user_id: int) -> int:
    async with pool.acquire() as conn:
        usage_count = await consume_daily_analysis(
            conn,
            user_id=user_id,
            usage_date=datetime.now(timezone.utc).date(),
            limit=DAILY_ANALYSIS_LIMIT,
        )
    if usage_count is not None:
        return usage_count

    reset_at = datetime.combine(
        datetime.now(timezone.utc).date(),
        datetime.min.time(),
        tzinfo=timezone.utc,
    ) + timedelta(days=1)
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


@app.get("/health")
async def health(request: Request):
    try:
        await request.app.state.redis.ping()
        if request.app.state.result_task.done():
            raise RuntimeError("Redis result consumer is not running")
        return {"status": "ok", "redis": "ok"}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "unavailable", "error": str(exc)})


@app.get("/api/usage")
async def get_usage(request: Request, user: dict = Depends(get_current_user)):
    usage_date = datetime.now(timezone.utc).date()
    async with request.app.state.db_pool.acquire() as conn:
        used = await get_daily_analysis_usage(
            conn,
            user_id=user["id"],
            usage_date=usage_date,
        )
    used = min(used, DAILY_ANALYSIS_LIMIT)
    return {
        "date": usage_date.isoformat(),
        "limit": DAILY_ANALYSIS_LIMIT,
        "used": used,
        "remaining": DAILY_ANALYSIS_LIMIT - used,
    }


@app.get("/api/songs")
async def list_songs(request: Request, user: dict = Depends(get_current_user)):
    try:
        async with request.app.state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT songs.*
                FROM songs
                WHERE songs.pipeline_complete IS TRUE
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
                  AND songs.pipeline_complete IS TRUE
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
                WHERE songs.id = $1 AND songs.pipeline_complete IS TRUE
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


@app.delete("/api/songs/{song_id}")
async def remove_song_from_library(
    request: Request,
    song_id: int,
    user: dict = Depends(get_current_user),
):
    async with request.app.state.db_pool.acquire() as conn:
        removed = await conn.fetchval(
            """
            DELETE FROM user_songs
            WHERE user_id = $1 AND song_id = $2
            RETURNING song_id
            """,
            user["id"],
            song_id,
        )
    if removed is None:
        raise HTTPException(status_code=404, detail="Song is not in your library")
    return {"success": True}


@app.get("/api/songs/{song_id}/artifact")
async def download_song_artifact(
    request: Request,
    song_id: int,
    user: dict = Depends(get_current_user),
):
    async with request.app.state.db_pool.acquire() as conn:
        song = await conn.fetchrow(
            """
            SELECT file_path FROM songs
            WHERE id = $1 AND pipeline_complete IS TRUE
            """,
            song_id,
        )
    if not song or not song["file_path"]:
        raise HTTPException(status_code=404, detail="Song artifact not found")
    if not await asyncio.to_thread(object_exists, song["file_path"]):
        raise HTTPException(status_code=404, detail="Song artifact not found")
    filename = Path(song["file_path"]).name
    return StreamingResponse(
        stream_object(song["file_path"]),
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/jobs")
async def list_jobs(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    jobs = await list_jobs_for_user(
        request.app.state.db_pool,
        user["id"],
        limit=limit,
    )
    return JSONResponse(status_code=200, content=jsonable_encoder(jobs))


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


@app.get("/api/jobs/{job_id}/artifact")
async def download_job_artifact(
    request: Request,
    job_id: int,
    user: dict = Depends(get_current_user),
):
    job = await get_job_with_steps_for_user(
        request.app.state.db_pool,
        job_id,
        user["id"],
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed" or job["job_type"] != "demucs" or not job["file_path"]:
        raise HTTPException(status_code=404, detail="Job artifact not found")
    if not await asyncio.to_thread(object_exists, job["file_path"]):
        raise HTTPException(status_code=404, detail="Job artifact not found")
    filename = Path(job["file_path"]).name
    return StreamingResponse(
        stream_object(job["file_path"]),
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(
    request: Request,
    job_id: int,
    user: dict = Depends(get_current_user),
):
    original = await get_job_with_steps_for_user(
        request.app.state.db_pool,
        job_id,
        user["id"],
    )
    if not original:
        raise HTTPException(status_code=404, detail="Job not found")
    if original["status"] != "failed":
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")

    job_type = original["job_type"]
    stages = JOB_TYPE_STAGES.get(job_type)
    if not stages:
        raise HTTPException(status_code=409, detail="This job type cannot be retried")
    source_file_path = original["source_file_path"]
    if original["input_type"] == "audio" and not source_file_path:
        raise HTTPException(status_code=409, detail="The original upload is unavailable")

    usage_count = await consume_quota_or_raise(request.app.state.db_pool, user["id"])
    retry_source_file_path = (
        await asyncio.to_thread(copy_source_object, source_file_path)
        if source_file_path
        else None
    )
    async with request.app.state.db_pool.acquire() as conn:
        new_job_id = await create_job(
            conn,
            user_id=user["id"],
            job_type=job_type,
            stages=stages,
            input_type=original["input_type"],
            title=original["title"],
            artist=original["artist"],
            lyrics=original["lyrics"] if job_type == "classifier" else None,
            source_file_path=retry_source_file_path,
            file_path=retry_source_file_path,
        )
        new_job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", new_job_id)
    await enqueue_task(request.app.state.redis, task_for_job(dict(new_job), stages[0]))
    return {
        "success": True,
        "job_id": new_job_id,
        "rate_limit": {
            "limit": DAILY_ANALYSIS_LIMIT,
            "remaining": DAILY_ANALYSIS_LIMIT - usage_count,
        },
    }


@app.delete("/api/jobs/{job_id}")
async def delete_job(
    request: Request,
    job_id: int,
    user: dict = Depends(get_current_user),
):
    job = await get_job_with_steps_for_user(
        request.app.state.db_pool,
        job_id,
        user["id"],
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="Active jobs cannot be deleted")

    object_keys = {job.get("source_file_path")}
    for step in job["steps"]:
        result = step.get("result") or {}
        if isinstance(result, dict):
            object_keys.add(result.get("file_path"))
    if job.get("song_id"):
        async with request.app.state.db_pool.acquire() as conn:
            song_path = await conn.fetchval(
                "SELECT file_path FROM songs WHERE id = $1",
                job["song_id"],
            )
        object_keys.discard(song_path)

    async with request.app.state.db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM jobs WHERE id = $1 AND user_id = $2",
            job_id,
            user["id"],
        )
    try:
        await asyncio.to_thread(delete_object_keys, {key for key in object_keys if key})
    except Exception:
        logger.warning("Unable to delete all objects for job %s", job_id, exc_info=True)
    return {"success": True}


@app.post("/api/analyze")
async def analyze(
    request: Request,
    mode: str = Form(...),
    service: str = Form(""),
    audio: Optional[UploadFile] = File(None),
    title: str = Form(""),
    artist: str = Form(""),
    lyrics: str = Form(""),
    user: dict = Depends(get_current_user),
):
    try:
        db_pool = request.app.state.db_pool
        if mode == "full":
            job_type = "full"
        elif mode == "standalone" and service in JOB_TYPE_STAGES and service != "full":
            job_type = service
        else:
            raise HTTPException(status_code=400, detail="Choose a valid analysis mode and service")

        stages = JOB_TYPE_STAGES[job_type]
        input_type = "text" if job_type == "classifier" else "audio"
        if input_type == "audio" and not audio:
            raise HTTPException(status_code=400, detail="An audio file is required")
        if input_type == "text" and not lyrics.strip():
            raise HTTPException(status_code=400, detail="Text is required")

        usage_count = await consume_quota_or_raise(db_pool, user["id"])
        source_file_path = save_uploaded_file(audio) if audio else None
        display_title = title.strip()
        if not display_title and audio and audio.filename:
            display_title = Path(audio.filename).stem
        if not display_title:
            display_title = "Text classification" if job_type == "classifier" else "Untitled"

        async with db_pool.acquire() as conn:
            job_id = await create_job(
                conn,
                user_id=user["id"],
                job_type=job_type,
                stages=stages,
                title=display_title,
                artist=artist.strip() or None,
                lyrics=lyrics.strip() or None,
                input_type=input_type,
                source_file_path=source_file_path,
                file_path=source_file_path,
            )
            job = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        await enqueue_task(request.app.state.redis, task_for_job(dict(job), stages[0]))
        return {
            "success": True,
            "job_id": job_id,
            "job_type": job_type,
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
