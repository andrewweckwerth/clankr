from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.parametrize("data,detail", [
    ({"mode": "bad"}, "Choose a valid analysis mode and service"),
    ({"mode": "standalone", "service": "unknown"}, "Choose a valid analysis mode and service"),
    ({"mode": "full"}, "An audio file is required"),
    ({"mode": "standalone", "service": "whisper"}, "An audio file is required"),
    ({"mode": "standalone", "service": "classifier", "lyrics": "  "}, "Text is required"),
])
async def test_invalid_submission_does_not_consume_quota(client, connection, redis, data, detail):
    response = await client.post("/api/analyze", data=data)
    assert response.status_code == 400
    assert response.json()["detail"] == detail
    connection.fetchval.assert_not_awaited()
    redis.xadd.assert_not_awaited()


async def test_missing_form_fields_use_fastapi_validation(client):
    assert (await client.post("/api/analyze")).status_code == 422


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/jobs"), ("GET", "/api/jobs?view=mine"),
    ("GET", "/api/jobs/1"), ("GET", "/api/jobs/1/artifact"),
    ("POST", "/api/jobs/1/retry"), ("DELETE", "/api/jobs/1"),
    ("POST", "/api/analyze"), ("GET", "/api/usage"),
    ("GET", "/api/songs/mine"), ("DELETE", "/api/songs/1"),
])
async def test_guest_cannot_access_personal_data_or_mutate(guest_client, method, path):
    assert (await guest_client.request(method, path)).status_code == 401


@pytest.mark.parametrize("view", ["active", "all"])
async def test_guest_can_read_shared_jobs(guest_client, orchestrator, monkeypatch, view):
    lookup = AsyncMock(return_value=[{"id": 1, "is_owner": False}])
    monkeypatch.setattr(orchestrator, "list_shared_jobs", lookup)
    response = await guest_client.get(f"/api/jobs?view={view}")
    assert response.status_code == 200
    assert lookup.await_args.args[1] is None
    assert lookup.await_args.kwargs == {"view": view, "limit": 100}


async def test_guest_cannot_forge_identity_on_shared_jobs(guest_client):
    response = await guest_client.get("/api/jobs?view=active", headers={"x-clankr-internal-auth": "bad.signature"})
    assert response.status_code == 401


async def test_guest_can_read_song_results_and_download_stem(guest_client, connection, orchestrator, monkeypatch):
    song = {"id": 1, "title": "Public song", "lyrics": "Public lyrics", "classification": "Human", "file_path": "stems/test.wav"}
    connection.fetch.return_value = [song]
    connection.fetchrow.return_value = song
    assert (await guest_client.get("/api/songs")).json() == [song]
    assert (await guest_client.get("/api/songs/1")).json() == song
    monkeypatch.setattr(orchestrator, "object_exists", Mock(return_value=True))
    monkeypatch.setattr(orchestrator, "stream_object", Mock(return_value=iter([b"test-stem"])))
    response = await guest_client.get("/api/songs/1/artifact")
    assert response.status_code == 200
    assert response.content == b"test-stem"
    assert response.headers["content-type"] == "audio/wav"


@pytest.mark.parametrize("path", ["/api/songs/1", "/api/songs/1/artifact"])
async def test_missing_public_song_returns_not_found(guest_client, connection, path):
    connection.fetchrow.return_value = None
    assert (await guest_client.get(path)).status_code == 404


async def test_unauthenticated_request_is_rejected(client, orchestrator, monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", "test-only")
    monkeypatch.delitem(orchestrator.app.dependency_overrides, orchestrator.get_current_user)
    assert (await client.get("/api/jobs")).status_code == 401


async def test_quota_exhaustion_returns_retry_headers(client, connection, redis):
    connection.fetchval.return_value = None
    response = await client.post("/api/analyze", data={"mode": "standalone", "service": "classifier", "lyrics": "text"})
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert response.headers["X-RateLimit-Remaining"] == "0"
    redis.xadd.assert_not_awaited()


@pytest.mark.parametrize("audio", [False, True])
async def test_valid_submission_creates_job_and_enqueues_first_stage(client, orchestrator, connection, monkeypatch, audio):
    create = AsyncMock(return_value=42)
    enqueue = AsyncMock()
    save = Mock(return_value="raw/input.wav")
    monkeypatch.setattr(orchestrator, "create_job", create)
    monkeypatch.setattr(orchestrator, "enqueue_task", enqueue)
    monkeypatch.setattr(orchestrator, "save_uploaded_file", save)
    connection.fetchval.return_value = 1
    connection.fetchrow.return_value = {"id": 42, "file_path": "raw/input.wav" if audio else None, "lyrics": None if audio else "text"}
    data = {"mode": "full"} if audio else {"mode": "standalone", "service": "classifier", "lyrics": "  text  "}
    files = {"audio": ("input.wav", b"synthetic-upload", "audio/wav")} if audio else None
    response = await client.post("/api/analyze", data=data, files=files)
    assert response.status_code == 200
    assert response.json()["job_id"] == 42
    assert response.json()["rate_limit"]["remaining"] == 9
    assert create.await_args.kwargs["stages"] == (orchestrator.STAGE_ORDER if audio else ("classify",))
    task = enqueue.await_args.args[1]
    assert task["job_id"] == "42"
    assert task["stage"] == ("identify" if audio else "classify")
    assert task["file_path"] == ("raw/input.wav" if audio else None)
    if not audio:
        assert task["lyrics"] == "text"
        save.assert_not_called()


async def test_other_users_job_is_not_exposed(client, orchestrator, monkeypatch):
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(orchestrator, "get_job_with_steps_for_user", lookup)
    assert (await client.get("/api/jobs/99")).status_code == 404
    assert lookup.await_args.args[1:] == (99, 7)


@pytest.mark.parametrize("redis_down,stopped", [(False, False), (True, False), (False, True)])
async def test_health_checks_redis_and_consumer(client, orchestrator, redis, monkeypatch, redis_down, stopped):
    monkeypatch.setattr(orchestrator.app.state, "result_task", Mock(done=Mock(return_value=stopped)), raising=False)
    if redis_down:
        redis.ping.side_effect = ConnectionError("unavailable")
    response = await client.get("/health")
    assert response.status_code == (503 if redis_down or stopped else 200)
