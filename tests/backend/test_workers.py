"""Exercise all four Redis workers without importing ML runtimes or weights."""

import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest


@pytest.fixture(params=[("acousti", "identify"), ("demucs", "demucs"), ("whisper", "whisper"), ("classifier", "classify")])
def worker(request):
    name, stage = request.param
    stubs = {}
    for module_name, attributes in {
        "soundfile": ["write"], "demucs": [], "demucs.apply": ["apply_model"],
        "demucs.audio": ["AudioFile"], "demucs.pretrained": ["get_model"],
        "faster_whisper": ["WhisperModel"],
    }.items():
        stub = ModuleType(module_name)
        for attribute in attributes:
            setattr(stub, attribute, Mock())
        stubs[module_name] = stub
    path = Path(__file__).resolve().parents[2] / "services" / name / f"{name}_runner.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}_worker", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", stubs):
        spec.loader.exec_module(module)
    return module, stage


async def test_worker_rejects_wrong_stage(worker):
    module, _ = worker
    with pytest.raises(ValueError, match="cannot process stage"):
        await module.process_task({"stage": "unknown"})


async def test_worker_rejects_missing_input(worker):
    module, stage = worker
    with pytest.raises(ValueError, match="missing"):
        await module.process_task({"stage": stage})


@pytest.mark.parametrize("fails", [False, True])
async def test_worker_publishes_result_before_acknowledging(worker, monkeypatch, fails):
    module, stage = worker
    stop = asyncio.Event()
    task = {"job_id": "42", "task_id": "t1", "stage": stage, "attempt": "1", "file_path": "raw/input.wav", "lyrics": "text"}
    monkeypatch.setattr(module, "next_message", AsyncMock(return_value=("1-0", {"payload": json.dumps(task)})))
    process = AsyncMock(return_value={"output": "result"}, side_effect=ValueError("bad input") if fails else None)
    monkeypatch.setattr(module, "process_task", process)
    redis = AsyncMock()

    async def acknowledge(*args):
        assert redis.xadd.await_count == 2
        stop.set()

    redis.xack.side_effect = acknowledge
    await asyncio.wait_for(module.worker_loop(redis, stop), timeout=2)
    events = [json.loads(call.args[1]["payload"]) for call in redis.xadd.await_args_list]
    assert [event["event"] for event in events] == ["started", "completed"]
    assert all(event["job_id"] == "42" and event["task_id"] == "t1" and event["stage"] == stage for event in events)
    assert events[-1]["ok"] is not fails
    if fails:
        assert events[-1]["error_type"] == "ValueError"
        assert events[-1]["error"] == "bad input"
    else:
        assert events[-1]["result"] == {"output": "result"}
    redis.xack.assert_awaited_once_with(module.REDIS_STREAM, module.REDIS_GROUP, "1-0")


@pytest.mark.parametrize("stopped", [False, True])
async def test_worker_health_detects_stopped_consumer(worker, stopped):
    module, _ = worker
    module.app.state.redis = AsyncMock()
    module.app.state.worker_task = Mock(done=Mock(return_value=stopped))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == (503 if stopped else 200)
