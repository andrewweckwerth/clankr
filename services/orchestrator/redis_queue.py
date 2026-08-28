"""Redis Streams helpers shared by the orchestrator's queue lifecycle."""

import json
import os
import socket
import uuid
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RESULT_STREAM = os.getenv("REDIS_RESULT_STREAM", "clankr:events:results")
RESULT_GROUP = os.getenv("REDIS_RESULT_GROUP", "orchestrator")
VISIBILITY_TIMEOUT_MS = int(os.getenv("REDIS_VISIBILITY_TIMEOUT_MS", "3600000"))
STREAMS = {
    "identify": os.getenv("REDIS_IDENTIFY_STREAM", "clankr:queue:identify"),
    "demucs": os.getenv("REDIS_DEMUCS_STREAM", "clankr:queue:demucs"),
    "whisper": os.getenv("REDIS_WHISPER_STREAM", "clankr:queue:whisper"),
    "classify": os.getenv("REDIS_CLASSIFY_STREAM", "clankr:queue:classify"),
}


def new_consumer_name(prefix: str) -> str:
    return f"{prefix}-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


async def ensure_consumer_group(redis: Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(stream, group, id="0-0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def first_requested_stage(job: dict[str, Any]) -> str | None:
    for stage in ("identify", "demucs", "whisper", "classify"):
        if job.get(f"want_{stage}") and not job.get(f"done_{stage}"):
            return stage
    return None


def task_for_job(job: dict[str, Any], stage: str | None = None) -> dict[str, Any]:
    stage = stage or job.get("current_stage") or first_requested_stage(job)
    if stage not in STREAMS:
        raise ValueError(f"Job {job.get('id')} has no valid next stage: {stage}")

    return {
        "task_id": uuid.uuid4().hex,
        "job_id": str(job["id"]),
        "stage": stage,
        "file_path": job.get("file_path"),
        "lyrics": job.get("lyrics"),
        "attempt": "1",
    }


async def enqueue_task(redis: Redis, task: dict[str, Any]) -> str:
    stream = STREAMS[task["stage"]]
    return await redis.xadd(
        stream,
        {"payload": json.dumps(task, separators=(",", ":"))},
        maxlen=10000,
        approximate=True,
    )


async def publish_event(redis: Redis, event: dict[str, Any]) -> str:
    return await redis.xadd(
        RESULT_STREAM,
        {"payload": json.dumps(event, separators=(",", ":"))},
        maxlen=10000,
        approximate=True,
    )


async def reclaim_one(redis: Redis, stream: str, group: str, consumer: str):
    """Return one abandoned task, if available, before waiting for new work."""
    claimed = await redis.xautoclaim(
        stream,
        group,
        consumer,
        min_idle_time=VISIBILITY_TIMEOUT_MS,
        start_id="0-0",
        count=1,
    )
    return claimed[1][0] if len(claimed) > 1 and claimed[1] else None

