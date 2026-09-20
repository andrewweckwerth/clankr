import asyncio
import json
import logging
import os
import socket
import subprocess
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from minio import Minio
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from structured_logging import configure_logging, log_event


configure_logging("acousti")
logger = logging.getLogger("acousti")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "clankr")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "change-me")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "clankr-audio")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_STREAM = os.getenv("REDIS_IDENTIFY_STREAM", "clankr:queue:identify")
REDIS_GROUP = os.getenv("REDIS_IDENTIFY_GROUP", "acousti")
REDIS_RESULT_STREAM = os.getenv("REDIS_RESULT_STREAM", "clankr:events:results")
REDIS_VISIBILITY_TIMEOUT_MS = int(os.getenv("REDIS_VISIBILITY_TIMEOUT_MS", "3600000"))

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
)


def download_object(object_key: str, suffix: str = "") -> str:
    fd, path = tempfile.mkstemp(prefix="clankr-", suffix=suffix)
    os.close(fd)
    try:
        minio_client.fget_object(MINIO_BUCKET, object_key, path)
        return path
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise


def upload_object(path: str, object_key: str, content_type: str) -> str:
    minio_client.fput_object(MINIO_BUCKET, object_key, path, content_type=content_type)
    return object_key


def run_fpcalc(file_path: str):
    result = subprocess.run(["fpcalc", file_path], capture_output=True, text=True)
    if "FINGERPRINT=" not in result.stdout or "DURATION=" not in result.stdout:
        raise RuntimeError(f"fpcalc failed: {result.stderr}")

    fingerprint = None
    duration = None
    for line in result.stdout.splitlines():
        if line.startswith("FINGERPRINT="):
            fingerprint = line.split("=", 1)[1]
        elif line.startswith("DURATION="):
            duration = int(float(line.split("=", 1)[1]))

    if not fingerprint or not duration:
        raise RuntimeError("Missing fingerprint or duration")
    return fingerprint, duration


def lookup_acoustid(fingerprint, duration, api_key):
    response = requests.post(
        "https://api.acoustid.org/v2/lookup",
        data={
            "client": api_key,
            "format": "json",
            "fingerprint": fingerprint,
            "duration": duration,
            "meta": "recordings",
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"AcoustID error: {response.text}")
    return response.json()


def convert_audio(object_key: str) -> str:
    suffix = Path(object_key).suffix
    input_path = download_object(object_key, suffix=suffix)
    base = os.path.splitext(os.path.basename(object_key))[0]
    output_path = tempfile.mktemp(prefix="clankr-", suffix=".wav")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", output_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        output_key = f"preprocessed/{base}.wav"
        return upload_object(output_path, output_key, "audio/wav")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg failed: {exc.stderr}") from exc
    finally:
        for path in (input_path, output_path):
            if os.path.exists(path):
                os.remove(path)


def identify_audio(file_path: str) -> dict:
    api_key = os.getenv("ACOUSTID_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ACOUSTID_API_KEY env var")

    local_path = download_object(file_path, suffix=Path(file_path).suffix)
    try:
        fingerprint, duration = run_fpcalc(local_path)
        raw_result = lookup_acoustid(fingerprint, duration, api_key)
        matches = []
        for result in raw_result.get("results", []):
            for recording in result.get("recordings", []):
                title = recording.get("title", "Unknown")
                artist = "Unknown"
                if recording.get("artists"):
                    artist = recording["artists"][0].get("name", "Unknown")
                matches.append({"title": title, "artist": artist})
        return {"file_path": file_path, "fingerprint": fingerprint, "duration": duration, "matches": matches}
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


async def process_task(task: dict) -> dict:
    if task.get("stage") != "identify":
        raise ValueError(f"Acousti cannot process stage {task.get('stage')}")
    if not task.get("file_path"):
        raise ValueError("Identify task is missing file_path")
    preprocessed_path = await asyncio.to_thread(convert_audio, task["file_path"])
    return await asyncio.to_thread(identify_audio, preprocessed_path)


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
    consumer = f"acousti-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
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
            "stage": "identify",
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
            logger.exception("Identify task %s failed", task.get("task_id"))
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
