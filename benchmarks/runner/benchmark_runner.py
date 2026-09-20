"""Submit, observe, and report isolated Demucs benchmark runs."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
from minio import Minio
from minio.commonconfig import CopySource
from redis.asyncio import Redis


POSTGRES_DSN = os.environ["POSTGRES_DSN"]
REDIS_URL = os.environ["REDIS_URL"]
MINIO_BUCKET = os.environ["MINIO_BUCKET"]
MINIO_STREAM = os.getenv("REDIS_DEMUCS_STREAM", "clankr:queue:demucs")

SCHEMA = """
CREATE TABLE IF NOT EXISTS benchmark_runs (
  run_id TEXT PRIMARY KEY,
  scenario TEXT NOT NULL,
  status TEXT NOT NULL,
  submitted_job_count INTEGER NOT NULL,
  config JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS benchmark_jobs (
  run_id TEXT NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
  job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  PRIMARY KEY (run_id, job_id),
  UNIQUE (run_id, ordinal)
);

CREATE TABLE IF NOT EXISTS benchmark_events (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
  observed_at TIMESTAMPTZ,
  service TEXT,
  container TEXT,
  event TEXT,
  level TEXT,
  job_id BIGINT,
  task_id TEXT,
  stage TEXT,
  duration_ms BIGINT,
  payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_benchmark_events_run_event
  ON benchmark_events(run_id, event);
"""


def emit(event: str, **fields: Any) -> None:
    print(
        json.dumps(
            {
                "schema_version": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "service": "benchmark-runner",
                "benchmark_run_id": fields.pop("run_id", None),
                **fields,
            },
            separators=(",", ":"),
        ),
        flush=True,
    )


def minio_client() -> Minio:
    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def ensure_schema(conn: asyncpg.Connection) -> None:
    await conn.execute(SCHEMA)


async def submit(args: argparse.Namespace) -> None:
    audio_path = Path(args.audio)
    if not audio_path.is_file():
        raise ValueError(f"Benchmark audio is not available in the runner: {audio_path}")
    if args.jobs < 1:
        raise ValueError("--jobs must be at least 1")

    client = minio_client()
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)

    run_id = args.run_id
    suffix = audio_path.suffix or ".wav"
    source_key = f"raw/benchmarks/{run_id}/source{suffix}"
    client.fput_object(MINIO_BUCKET, source_key, str(audio_path), content_type="audio/*")
    input_keys = [f"raw/benchmarks/{run_id}/{ordinal:06d}{suffix}" for ordinal in range(1, args.jobs + 1)]
    for key in input_keys:
        client.copy_object(MINIO_BUCKET, key, CopySource(MINIO_BUCKET, source_key))

    config = {
        "demucs_replicas": args.demucs_replicas,
        "audio_filename": audio_path.name,
        "audio_sha256": sha256_file(audio_path),
        "input_object_prefix": f"raw/benchmarks/{run_id}/",
    }
    conn = await asyncpg.connect(POSTGRES_DSN)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await ensure_schema(conn)
        async with conn.transaction():
            exists = await conn.fetchval("SELECT 1 FROM benchmark_runs WHERE run_id = $1", run_id)
            if exists:
                raise ValueError(f"Benchmark run already exists: {run_id}")
            user_id = await conn.fetchval(
                """
                INSERT INTO users (auth_user_id, email, display_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (auth_user_id) DO UPDATE SET display_name = EXCLUDED.display_name
                RETURNING id
                """,
                f"benchmark:{run_id}",
                f"benchmark+{run_id}@invalid.local",
                "Benchmark runner",
            )
            await conn.execute(
                """
                INSERT INTO benchmark_runs (run_id, scenario, status, submitted_job_count, config)
                VALUES ($1, 'demucs', 'submitting', $2, $3::jsonb)
                """,
                run_id,
                args.jobs,
                json.dumps(config),
            )
            jobs: list[tuple[int, str]] = []
            for ordinal, object_key in enumerate(input_keys, start=1):
                job_id = await conn.fetchval(
                    """
                    INSERT INTO jobs (
                      user_id, job_type, current_stage, status, input_type, title,
                      source_file_path, file_path
                    ) VALUES ($1, 'demucs', 'demucs', 'queued', 'audio', $2, $3, $3)
                    RETURNING id
                    """,
                    user_id,
                    f"Benchmark Demucs {ordinal}",
                    object_key,
                )
                await conn.execute(
                    "INSERT INTO job_steps (job_id, stage, position) VALUES ($1, 'demucs', 0)",
                    job_id,
                )
                await conn.execute(
                    "INSERT INTO benchmark_jobs (run_id, job_id, ordinal) VALUES ($1, $2, $3)",
                    run_id,
                    job_id,
                    ordinal,
                )
                jobs.append((job_id, object_key))

        for job_id, object_key in jobs:
            task = {
                "task_id": uuid.uuid4().hex,
                "job_id": str(job_id),
                "stage": "demucs",
                "file_path": object_key,
                "lyrics": None,
                "attempt": "1",
                "benchmark_run_id": run_id,
            }
            await redis.xadd(MINIO_STREAM, {"payload": json.dumps(task, separators=(",", ":"))}, maxlen=10000, approximate=True)
        await conn.execute(
            "UPDATE benchmark_runs SET status = 'running' WHERE run_id = $1",
            run_id,
        )
        emit("benchmark.submitted", run_id=run_id, jobs=args.jobs, demucs_replicas=args.demucs_replicas)
    finally:
        await redis.aclose()
        await conn.close()


async def wait_for_completion(args: argparse.Namespace) -> None:
    deadline = time.monotonic() + args.timeout_seconds
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await ensure_schema(conn)
        while True:
            counts = await conn.fetchrow(
                """
                SELECT
                  count(*)::integer AS total,
                  count(*) FILTER (WHERE j.status = 'completed')::integer AS completed,
                  count(*) FILTER (WHERE j.status = 'failed')::integer AS failed,
                  count(*) FILTER (WHERE j.status IN ('queued', 'processing'))::integer AS active
                FROM benchmark_jobs bj
                JOIN jobs j ON j.id = bj.job_id
                WHERE bj.run_id = $1
                """,
                args.run_id,
            )
            if counts["total"] == 0:
                raise ValueError(f"No jobs exist for benchmark run {args.run_id}")
            emit("benchmark.progress", run_id=args.run_id, **dict(counts))
            if counts["active"] == 0:
                status = "completed" if counts["failed"] == 0 else "completed_with_failures"
                await conn.execute(
                    "UPDATE benchmark_runs SET status = $2, finished_at = CURRENT_TIMESTAMP WHERE run_id = $1",
                    args.run_id,
                    status,
                )
                return
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for benchmark run {args.run_id}")
            await asyncio.sleep(args.poll_seconds)
    finally:
        await conn.close()


def parse_log_line(line: str) -> tuple[datetime | None, dict[str, Any]] | None:
    if line.startswith("{"):
        try:
            payload = json.loads(line)
            timestamp = payload.get("timestamp")
            observed_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else None
        except (json.JSONDecodeError, ValueError, AttributeError):
            return None
        return (observed_at, payload) if payload.get("schema_version") == 1 else None
    timestamp_text, separator, message = line.rstrip("\n").partition(" ")
    if not separator:
        return None
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return None
    if payload.get("schema_version") != 1:
        return None
    try:
        observed_at = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        observed_at = None
    return observed_at, payload


async def import_events(args: argparse.Namespace) -> None:
    logs_path = Path(args.logs)
    if not logs_path.is_dir():
        raise ValueError(f"Log directory is not available in the runner: {logs_path}")
    rows: list[tuple[Any, ...]] = []
    for path in sorted(logs_path.glob("*.log")):
        for line in path.read_text(errors="replace").splitlines():
            parsed = parse_log_line(line)
            if not parsed:
                continue
            observed_at, payload = parsed
            job_id = payload.get("job_id")
            try:
                job_id = int(job_id) if job_id is not None else None
            except (TypeError, ValueError):
                job_id = None
            rows.append(
                (
                    args.run_id,
                    observed_at,
                    payload.get("service"),
                    payload.get("container"),
                    payload.get("event"),
                    payload.get("level"),
                    job_id,
                    payload.get("task_id"),
                    payload.get("stage"),
                    payload.get("duration_ms"),
                    json.dumps(payload),
                )
            )
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await ensure_schema(conn)
        async with conn.transaction():
            await conn.execute("DELETE FROM benchmark_events WHERE run_id = $1", args.run_id)
            if rows:
                await conn.executemany(
                    """
                    INSERT INTO benchmark_events (
                      run_id, observed_at, service, container, event, level, job_id,
                      task_id, stage, duration_ms, payload
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
                    """,
                    rows,
                )
        emit("benchmark.events_imported", run_id=args.run_id, event_count=len(rows))
    finally:
        await conn.close()


def milliseconds(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    return round((end - start).total_seconds() * 1000, 3)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 3)


async def report(args: argparse.Namespace) -> None:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        run = await conn.fetchrow("SELECT * FROM benchmark_runs WHERE run_id = $1", args.run_id)
        if not run:
            raise ValueError(f"Benchmark run does not exist: {args.run_id}")
        rows = await conn.fetch(
            """
            SELECT
              bj.ordinal, j.id AS job_id, j.status, j.created_at, j.completed_at, j.error,
              js.queued_at, js.started_at, js.completed_at AS step_completed_at
            FROM benchmark_jobs bj
            JOIN jobs j ON j.id = bj.job_id
            JOIN job_steps js ON js.job_id = j.id AND js.stage = 'demucs'
            WHERE bj.run_id = $1
            ORDER BY bj.ordinal
            """,
            args.run_id,
        )
    finally:
        await conn.close()

    jobs = []
    queue_waits: list[float] = []
    stage_durations: list[float] = []
    job_durations: list[float] = []
    completed_times: list[datetime] = []
    created_times: list[datetime] = []
    for row in rows:
        queue_wait = milliseconds(row["queued_at"], row["started_at"])
        stage_duration = milliseconds(row["started_at"], row["step_completed_at"])
        job_duration = milliseconds(row["created_at"], row["completed_at"])
        if queue_wait is not None:
            queue_waits.append(queue_wait)
        if stage_duration is not None:
            stage_durations.append(stage_duration)
        if job_duration is not None:
            job_durations.append(job_duration)
        if row["completed_at"]:
            completed_times.append(row["completed_at"])
        if row["created_at"]:
            created_times.append(row["created_at"])
        jobs.append(
            {
                "ordinal": row["ordinal"],
                "job_id": row["job_id"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "queued_at": row["queued_at"].isoformat() if row["queued_at"] else None,
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                "queue_wait_ms": queue_wait,
                "stage_duration_ms": stage_duration,
                "job_duration_ms": job_duration,
                "error": row["error"],
            }
        )

    elapsed_seconds = None
    if created_times and completed_times:
        elapsed_seconds = (max(completed_times) - min(created_times)).total_seconds()
    completed = sum(job["status"] == "completed" for job in jobs)
    summary = {
        "run_id": args.run_id,
        "scenario": run["scenario"],
        "status": run["status"],
        "config": json.loads(run["config"]) if isinstance(run["config"], str) else run["config"],
        "submitted_jobs": len(jobs),
        "completed_jobs": completed,
        "failed_jobs": sum(job["status"] == "failed" for job in jobs),
        "throughput_jobs_per_second": round(completed / elapsed_seconds, 4) if elapsed_seconds else None,
        "queue_wait_ms": {"p50": percentile(queue_waits, 0.5), "p95": percentile(queue_waits, 0.95), "max": max(queue_waits, default=None)},
        "stage_duration_ms": {"p50": percentile(stage_durations, 0.5), "p95": percentile(stage_durations, 0.95), "max": max(stage_durations, default=None)},
        "job_duration_ms": {"p50": percentile(job_durations, 0.5), "p95": percentile(job_durations, 0.95), "max": max(job_durations, default=None)},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (output / "jobs.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(jobs[0]) if jobs else ["ordinal", "job_id", "status"])
        writer.writeheader()
        writer.writerows(jobs)
    report_lines = [
        f"# Demucs benchmark: {args.run_id}",
        "",
        f"- Jobs: {completed}/{len(jobs)} completed; {summary['failed_jobs']} failed",
        f"- Demucs replicas: {summary['config'].get('demucs_replicas')}",
        f"- Throughput: {summary['throughput_jobs_per_second']} jobs/s",
        f"- Queue wait: p50 {summary['queue_wait_ms']['p50']} ms; p95 {summary['queue_wait_ms']['p95']} ms",
        f"- Demucs duration: p50 {summary['stage_duration_ms']['p50']} ms; p95 {summary['stage_duration_ms']['p95']} ms",
        f"- End-to-end job duration: p50 {summary['job_duration_ms']['p50']} ms; p95 {summary['job_duration_ms']['p95']} ms",
        "",
        "See `jobs.csv`, `summary.json`, `docker-stats.ndjson`, and `logs/` for the raw evidence.",
    ]
    (output / "report.md").write_text("\n".join(report_lines) + "\n")
    emit("benchmark.report_written", run_id=args.run_id, output=str(output))


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser()
    commands = command_parser.add_subparsers(dest="command", required=True)
    submit_parser = commands.add_parser("submit")
    submit_parser.add_argument("--run-id", required=True)
    submit_parser.add_argument("--audio", required=True)
    submit_parser.add_argument("--jobs", type=int, required=True)
    submit_parser.add_argument("--demucs-replicas", type=int, required=True)
    wait_parser = commands.add_parser("wait")
    wait_parser.add_argument("--run-id", required=True)
    wait_parser.add_argument("--timeout-seconds", type=int, default=7200)
    wait_parser.add_argument("--poll-seconds", type=int, default=10)
    import_parser = commands.add_parser("import-events")
    import_parser.add_argument("--run-id", required=True)
    import_parser.add_argument("--logs", required=True)
    report_parser = commands.add_parser("report")
    report_parser.add_argument("--run-id", required=True)
    report_parser.add_argument("--output", required=True)
    return command_parser


async def main() -> None:
    args = parser().parse_args()
    handlers = {
        "submit": submit,
        "wait": wait_for_completion,
        "import-events": import_events,
        "report": report,
    }
    await handlers[args.command](args)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(json.dumps({"event": "benchmark.error", "error_type": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise
