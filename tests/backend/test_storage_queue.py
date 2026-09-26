import io
import json
from unittest.mock import Mock

from starlette.datastructures import UploadFile
from redis.exceptions import ResponseError
import pytest

import redis_queue


async def test_task_uses_current_stage_and_carries_only_input_references(redis):
    task = redis_queue.task_for_job({"id": 42, "current_stage": "whisper", "file_path": "stems/vocals.wav"})
    await redis_queue.enqueue_task(redis, task)
    stream, fields = redis.xadd.await_args.args
    assert stream == redis_queue.STREAMS["whisper"]
    payload = json.loads(fields["payload"])
    assert payload["job_id"] == "42"
    assert payload["file_path"] == "stems/vocals.wav"
    assert payload["stage"] == "whisper"
    assert payload["task_id"] != redis_queue.task_for_job({"id": 42}, "whisper")["task_id"]


def test_task_rejects_unknown_stage():
    with pytest.raises(ValueError):
        redis_queue.task_for_job({"id": 42, "current_stage": "unknown"})


async def test_consumer_group_creation_is_idempotent_but_does_not_hide_other_errors(redis):
    redis.xgroup_create.side_effect = ResponseError("BUSYGROUP Consumer Group name already exists")
    await redis_queue.ensure_consumer_group(redis, "stream", "group")
    redis.xgroup_create.side_effect = ResponseError("permission denied")
    with pytest.raises(ResponseError, match="permission denied"):
        await redis_queue.ensure_consumer_group(redis, "stream", "group")


def test_upload_keeps_raw_key_contract(orchestrator, monkeypatch):
    import utils
    storage = Mock()
    monkeypatch.setattr(utils, "_minio", storage)
    upload = UploadFile(filename="../../track.wav", file=io.BytesIO(b"synthetic"))
    key = utils.save_uploaded_file(upload)
    assert key.startswith("raw/") and key.endswith(".wav")
    assert ".." not in key and key.count("/") == 1
    assert storage.put_object.call_args.args[1] == key


def test_stream_releases_storage_connection_on_early_close(orchestrator, monkeypatch):
    import utils
    response = Mock()
    response.stream.return_value = iter([b"first", b"second"])
    monkeypatch.setattr(utils, "_minio", Mock(get_object=Mock(return_value=response)))
    stream = utils.stream_object("stems/vocals.wav")
    assert next(stream) == b"first"
    stream.close()
    response.close.assert_called_once()
    response.release_conn.assert_called_once()
