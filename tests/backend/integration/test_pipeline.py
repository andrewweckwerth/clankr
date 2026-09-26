import asyncio
import json
from datetime import date
from unittest.mock import Mock

import pytest

import db
import redis_queue


pytestmark = [pytest.mark.integration, pytest.mark.allow_hosts(["127.0.0.1", "localhost", "::1"])]


async def submit(client, monkeypatch, orchestrator, audio=True):
    monkeypatch.setattr(orchestrator, "save_uploaded_file", Mock(return_value="raw/test.wav"))
    if audio:
        response = await client.post("/api/analyze", data={"mode": "full"}, files={"audio": ("test.wav", b"test-input", "audio/wav")})
    else:
        response = await client.post("/api/analyze", data={"mode": "standalone", "service": "classifier", "lyrics": "test lyrics"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    return response.json()["job_id"]


async def complete(orchestrator, job_id, stage, result=None, **fields):
    event = {"job_id": str(job_id), "task_id": "test-task", "stage": stage, "event": "completed", "ok": True, "result": result or {}}
    await orchestrator.handle_event(orchestrator.app, event | fields)


async def test_audio_pipeline_sequences_stages_and_creates_one_song(client, pool, redis, user, orchestrator, monkeypatch):
    job_id = await submit(client, monkeypatch, orchestrator)
    results = [
        ("identify", {"matches": [{"title": "Song", "artist": "Artist"}], "fingerprint": "test-fingerprint", "duration": 120, "file_path": "preprocessed/test.wav"}),
        ("demucs", {"file_path": "stems/vocals.wav"}),
        ("whisper", {"lyrics": "transcribed lyrics"}),
        ("classify", {"classification": "Human", "accuracy": 0.9}),
    ]
    for index, (stage, result) in enumerate(results):
        entries = await redis.xrange(redis_queue.STREAMS[stage])
        assert len(entries) == 1
        task = json.loads(entries[0][1]["payload"])
        assert task["job_id"] == str(job_id)
        if stage == "whisper":
            assert task["file_path"] == "stems/vocals.wav"
        if stage == "classify":
            assert task["lyrics"] == "transcribed lyrics"
        await orchestrator.handle_event(orchestrator.app, {**task, "event": "started"})
        assert (await client.get(f"/api/jobs/{job_id}")).json()["status"] == "processing"
        await complete(orchestrator, job_id, stage, result)
        # At-least-once delivery must not enqueue the next task twice.
        await complete(orchestrator, job_id, stage, result)
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        assert job["status"] == ("completed" if index == 3 else "queued")
    assert [step["status"] for step in job["steps"]] == ["completed"] * 4
    assert job["source_file_path"] == "raw/test.wav"
    assert job["file_path"] == "stems/vocals.wav"
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM songs WHERE pipeline_complete") == 1
        assert await conn.fetchval("SELECT submission_count FROM user_songs WHERE user_id=$1", user["id"]) == 1

    # Completed pipeline output is immediately readable without an account.
    monkeypatch.delitem(orchestrator.app.dependency_overrides, orchestrator.get_current_user)
    monkeypatch.delitem(orchestrator.app.dependency_overrides, orchestrator.get_optional_user)
    catalog = (await client.get("/api/songs")).json()
    assert len(catalog) == 1 and catalog[0]["lyrics"] == "transcribed lyrics"
    result = await client.get(f"/api/songs/{job['song_id']}")
    assert result.status_code == 200 and result.json()["classification"] == "Human"


async def test_text_job_completes_without_creating_song(client, pool, redis, orchestrator, monkeypatch):
    job_id = await submit(client, monkeypatch, orchestrator, audio=False)
    task = json.loads((await redis.xrange(redis_queue.STREAMS["classify"]))[0][1]["payload"])
    assert task["lyrics"] == "test lyrics" and task["file_path"] is None
    await complete(orchestrator, job_id, "classify", {"classification": "AI", "accuracy": 0.8})
    job = (await client.get(f"/api/jobs/{job_id}")).json()
    assert job["status"] == "completed" and job["song_id"] is None
    assert job["classification"] == "AI"
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM songs") == 0


async def test_failure_stops_pipeline_and_retry_creates_new_job(client, pool, redis, orchestrator, monkeypatch):
    job_id = await submit(client, monkeypatch, orchestrator, audio=False)
    await complete(orchestrator, job_id, "classify", ok=False, error="model unavailable")
    job = (await client.get(f"/api/jobs/{job_id}")).json()
    assert job["status"] == "failed" and job["steps"][0]["status"] == "failed"
    assert job["error"] == "model unavailable"
    response = await client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 200
    retry_id = response.json()["job_id"]
    assert retry_id != job_id
    retry = (await client.get(f"/api/jobs/{retry_id}")).json()
    assert retry["status"] == "queued" and retry["lyrics"] == "test lyrics"
    assert (await client.post(f"/api/jobs/{retry_id}/retry")).status_code == 409


async def test_failed_audio_stage_does_not_enqueue_next_stage(client, pool, redis, orchestrator, monkeypatch):
    job_id = await submit(client, monkeypatch, orchestrator)
    await complete(orchestrator, job_id, "identify", ok=False, error="invalid audio")
    # A duplicate failure cannot start more work or change the terminal state.
    await complete(orchestrator, job_id, "identify", ok=False, error="invalid audio")
    job = (await client.get(f"/api/jobs/{job_id}")).json()
    assert job["status"] == "failed"
    assert job["steps"][0]["status"] == "failed"
    assert await redis.xlen(redis_queue.STREAMS["demucs"]) == 0
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM songs") == 0


async def test_fingerprint_cache_skips_remaining_stages(client, pool, redis, user, orchestrator, monkeypatch):
    fingerprint = "cached-fingerprint"
    async with pool.acquire() as conn:
        song_id = await db.upsert_song(conn, title="Cached song", artist="Artist", duration=120,
            fingerprint=fingerprint, fingerprint_hash=orchestrator.compute_fingerprint_hash(fingerprint),
            lyrics="cached lyrics", classification="Human", accuracy=0.9, file_path="stems/cached.wav", audio_processed=True)
    job_id = await submit(client, monkeypatch, orchestrator)
    await complete(orchestrator, job_id, "identify", {"fingerprint": fingerprint, "file_path": "preprocessed/test.wav"})
    job = (await client.get(f"/api/jobs/{job_id}")).json()
    assert job["status"] == "completed" and job["cache_hit"] is True
    assert job["song_id"] == song_id and job["lyrics"] == "cached lyrics"
    assert [step["status"] for step in job["steps"]] == ["completed", "cancelled", "cancelled", "cancelled"]
    assert await redis.xlen(redis_queue.STREAMS["demucs"]) == 0


async def test_concurrent_quota_cannot_exceed_daily_limit(pool, user):
    async def consume():
        async with pool.acquire() as conn:
            return await db.consume_daily_analysis(conn, user_id=user["id"], usage_date=date(2026, 1, 1), limit=10)
    results = await asyncio.gather(*(consume() for _ in range(20)))
    assert sorted(value for value in results if value is not None) == list(range(1, 11))
    assert results.count(None) == 10


async def test_private_job_and_shared_queue_redaction(client, pool, user, orchestrator, monkeypatch):
    other = await db.upsert_user(pool, auth_user_id="other-user", display_name="Other")
    async with pool.acquire() as conn:
        job_id = await db.create_job(conn, user_id=other["id"], job_type="classifier", stages=("classify",), title="Private title", lyrics="Private lyrics")
    assert (await client.get(f"/api/jobs/{job_id}")).status_code == 404
    assert (await client.delete(f"/api/jobs/{job_id}")).status_code == 404
    assert (await client.post(f"/api/jobs/{job_id}/retry")).status_code == 404
    response = await client.get("/api/jobs?view=active")
    shared = next(job for job in response.json() if job["id"] == job_id)
    assert shared["is_owner"] is False and shared["title"] is None
    assert "Private lyrics" not in response.text and "Private title" not in response.text


async def test_guest_queue_and_completed_feed_hide_personal_data(guest_client, pool, user):
    async with pool.acquire() as conn:
        job_id = await db.create_job(conn, user_id=user["id"], job_type="classifier", stages=("classify",), title="Private title", lyrics="Private lyrics")
    for view, status in [("active", "queued"), ("all", "completed")]:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE jobs SET status=$1 WHERE id=$2", status, job_id)
        response = await guest_client.get(f"/api/jobs?view={view}")
        assert response.status_code == 200
        job = response.json()[0]
        assert job["id"] == job_id and job["is_owner"] is False
        assert job["title"] is None and job["song_id"] is None
        assert "Private title" not in response.text and "Private lyrics" not in response.text
        assert "user_id" not in job and "email" not in job


async def test_public_catalog_excludes_incomplete_songs(guest_client, pool):
    async with pool.acquire() as conn:
        song_id = await conn.fetchval("INSERT INTO songs (title, file_path) VALUES ('Partial', 'raw/private.wav') RETURNING id")
    assert (await guest_client.get("/api/songs")).json() == []
    assert (await guest_client.get(f"/api/songs/{song_id}")).status_code == 404
    assert (await guest_client.get(f"/api/songs/{song_id}/artifact")).status_code == 404


async def test_redis_consumer_group_delivery_reclaim_and_ack(redis, monkeypatch):
    stream = redis_queue.STREAMS["classify"]
    await redis_queue.ensure_consumer_group(redis, stream, "test-group")
    await redis_queue.ensure_consumer_group(redis, stream, "test-group")
    task = redis_queue.task_for_job({"id": 42, "lyrics": "text"}, "classify")
    message_id = await redis_queue.enqueue_task(redis, task)
    messages = await redis.xreadgroup("test-group", "worker1", {stream: ">"}, count=1)
    assert json.loads(messages[0][1][0][1]["payload"]) == task
    monkeypatch.setattr(redis_queue, "VISIBILITY_TIMEOUT_MS", 0)
    reclaimed_id, fields = await redis_queue.reclaim_one(redis, stream, "test-group", "worker2")
    assert reclaimed_id == message_id
    assert json.loads(fields["payload"]) == task
    await redis.xack(stream, "test-group", message_id)
    assert (await redis.xpending(stream, "test-group"))["pending"] == 0
