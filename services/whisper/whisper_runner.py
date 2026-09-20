import asyncio
import json
import logging
import os
import socket
import tempfile
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
from minio import Minio
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from structured_logging import configure_logging, log_event


configure_logging("whisper")
logger = logging.getLogger("whisper")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "clankr")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "change-me")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "clankr-audio")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_STREAM = os.getenv("REDIS_WHISPER_STREAM", "clankr:queue:whisper")
REDIS_GROUP = os.getenv("REDIS_WHISPER_GROUP", "whisper")
REDIS_RESULT_STREAM = os.getenv("REDIS_RESULT_STREAM", "clankr:events:results")
REDIS_VISIBILITY_TIMEOUT_MS = int(os.getenv("REDIS_VISIBILITY_TIMEOUT_MS", "3600000"))

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
)

model = WhisperModel("base", device="cpu", compute_type="int8")


def transcribe_object(file_path: str) -> dict:
    local_path = None
    try:
        fd, local_path = tempfile.mkstemp(prefix="clankr-", suffix=".wav")
        os.close(fd)
        minio_client.fget_object(MINIO_BUCKET, file_path, local_path)
        segments, _ = model.transcribe(local_path, beam_size=5, language="en")
        return {"lyrics": " ".join(segment.text.strip() for segment in segments)}
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)


async def process_task(task: dict) -> dict:
    if task.get("stage") != "whisper":
        raise ValueError(f"Whisper cannot process stage {task.get('stage')}")
    if not task.get("file_path"):
        raise ValueError("Whisper task is missing file_path")
    return await asyncio.to_thread(transcribe_object, task["file_path"])


async def ensure_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(REDIS_STREAM, REDIS_GROUP, id="0-0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def next_message(redis: Redis, consumer: str):
    claimed = await redis.xautoclaim(
        REDIS_STREAM,
        REDIS_GROUP,
        consumer,
        min_idle_time=REDIS_VISIBILITY_TIMEOUT_MS,
        start_id="0-0",
        count=1,
    )
    if len(claimed) > 1 and claimed[1]:
        return claimed[1][0]
    batches = await redis.xreadgroup(
        REDIS_GROUP,
        consumer,
        {REDIS_STREAM: ">"},
        count=1,
        block=5000,
    )
    return batches[0][1][0] if batches and batches[0][1] else None


async def publish_event(redis: Redis, event: dict) -> None:
    await redis.xadd(
        REDIS_RESULT_STREAM,
        {"payload": json.dumps(event, separators=(",", ":"))},
        maxlen=10000,
        approximate=True,
    )


async def worker_loop(redis: Redis, stop: asyncio.Event) -> None:
    consumer = f"whisper-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    log_event(logger, "worker.started", worker_id=consumer, stream=REDIS_STREAM)
    while not stop.is_set():
        message = await next_message(redis, consumer)
        if not message:
            continue
        message_id, fields = message
        task = json.loads(fields["payload"])
        base_event = {
            "task_id": task["task_id"],
            "job_id": task["job_id"],
            "stage": "whisper",
            "worker_id": consumer,
            "attempt": task.get("attempt"),
        }
        if task.get("benchmark_run_id"):
            base_event["benchmark_run_id"] = task["benchmark_run_id"]
        log_event(logger, "task.claimed", **base_event)
        started_at = time.perf_counter()
        try:
            await publish_event(redis, {**base_event, "event": "started"})
            log_event(logger, "stage.started", **base_event)
            result = await process_task(task)
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            await publish_event(redis, {**base_event, "event": "completed", "ok": True, "result": result, "duration_ms": duration_ms})
            log_event(logger, "stage.completed", duration_ms=duration_ms, **base_event)
        except Exception as exc:
            logger.exception("Whisper task %s failed", task.get("task_id"))
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            await publish_event(
                redis,
                {
                    **base_event,
                    "event": "completed",
                    "ok": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "result": {},
                    "duration_ms": duration_ms,
                },
            )
            log_event(logger, "stage.failed", error_type=type(exc).__name__, duration_ms=duration_ms, **base_event)
        await redis.xack(REDIS_STREAM, REDIS_GROUP, message_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    await ensure_group(app.state.redis)
    app.state.stop_event = asyncio.Event()
    app.state.worker_task = asyncio.create_task(worker_loop(app.state.redis, app.state.stop_event))
    try:
        yield
    finally:
        app.state.stop_event.set()
        app.state.worker_task.cancel()
        await asyncio.gather(app.state.worker_task, return_exceptions=True)
        await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    try:
        await app.state.redis.ping()
        if app.state.worker_task.done():
            raise RuntimeError("Redis worker is not running")
        return {"status": "ok", "redis": "ok"}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "unavailable", "error": str(exc)})
