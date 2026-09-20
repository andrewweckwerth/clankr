import asyncio
import json
import logging
import os
import socket
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import soundfile as sf
from demucs.apply import apply_model
from demucs.audio import AudioFile
from demucs.pretrained import get_model
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from minio import Minio
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from structured_logging import configure_logging, log_event


configure_logging("demucs")
logger = logging.getLogger("demucs")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "clankr")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "change-me")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "clankr-audio")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_STREAM = os.getenv("REDIS_DEMUCS_STREAM", "clankr:queue:demucs")
REDIS_GROUP = os.getenv("REDIS_DEMUCS_GROUP", "demucs")
REDIS_RESULT_STREAM = os.getenv("REDIS_RESULT_STREAM", "clankr:events:results")
REDIS_VISIBILITY_TIMEOUT_MS = int(os.getenv("REDIS_VISIBILITY_TIMEOUT_MS", "3600000"))

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
)

MODEL = get_model(name="htdemucs")


def download_object(object_key: str) -> str:
    fd, path = tempfile.mkstemp(prefix="clankr-", suffix=Path(object_key).suffix)
    os.close(fd)
    try:
        minio_client.fget_object(MINIO_BUCKET, object_key, path)
        return path
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise


def upload_object(path: str, object_key: str) -> str:
    minio_client.fput_object(MINIO_BUCKET, object_key, path, content_type="audio/wav")
    return object_key


def separate_vocals(file_path: str, output_path: str):
    ref = AudioFile(file_path).read(streams=0, samplerate=MODEL.samplerate)
    ref = ref.unsqueeze(0)
    sources = apply_model(MODEL, ref, split=True, overlap=0.25)[0]

    for idx, name in enumerate(MODEL.sources):
        if name == "vocals":
            stem = sources[idx].squeeze(0) if sources[idx].ndim == 3 else sources[idx]
            sf.write(output_path, stem.T.cpu().numpy(), MODEL.samplerate)
            return True
    return False


def separate_from_object(file_path: str) -> dict:
    base = os.path.splitext(os.path.basename(file_path))[0]
    input_path = download_object(file_path)
    output_path = tempfile.mktemp(prefix="clankr-", suffix=".wav")
    try:
        if not separate_vocals(input_path, output_path):
            raise RuntimeError("No vocals stem found")
        return {"file_path": upload_object(output_path, f"stems/{base}.wav")}
    finally:
        for path in (input_path, output_path):
            if path and os.path.exists(path):
                os.remove(path)


async def process_task(task: dict) -> dict:
    if task.get("stage") != "demucs":
        raise ValueError(f"Demucs cannot process stage {task.get('stage')}")
    if not task.get("file_path"):
        raise ValueError("Demucs task is missing file_path")
    return await asyncio.to_thread(separate_from_object, task["file_path"])


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
    consumer = f"demucs-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
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
            "stage": "demucs",
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
            logger.exception("Demucs task %s failed", task.get("task_id"))
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
