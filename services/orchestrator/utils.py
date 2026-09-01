import os
import hashlib
import uuid
from collections.abc import Iterable, Iterator
from typing import Any, Dict, Optional

from fastapi import UploadFile
from minio import Minio
from minio.commonconfig import CopySource


MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "clankr")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "change-me")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "clankr-audio")

_minio = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
)


def ensure_bucket() -> None:
    if not _minio.bucket_exists(MINIO_BUCKET):
        _minio.make_bucket(MINIO_BUCKET)


ensure_bucket()

#other os
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")


def compute_fingerprint_hash(fingerprint: str) -> str:
    return hashlib.md5(fingerprint.encode("utf-8")).hexdigest()


def save_uploaded_file(upload_file: UploadFile) -> str:
    ext = os.path.splitext(upload_file.filename or "")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    object_key = f"raw/{filename}"
    upload_file.file.seek(0)
    _minio.put_object(
        MINIO_BUCKET,
        object_key,
        upload_file.file,
        length=-1,
        part_size=10 * 1024 * 1024,
        content_type=upload_file.content_type or "application/octet-stream",
    )
    return object_key


def object_exists(object_key: str) -> bool:
    try:
        _minio.stat_object(MINIO_BUCKET, object_key)
        return True
    except Exception:
        return False


def stream_object(object_key: str) -> Iterator[bytes]:
    response = _minio.get_object(MINIO_BUCKET, object_key)
    try:
        yield from response.stream(amt=64 * 1024)
    finally:
        response.close()
        response.release_conn()


def delete_object_keys(object_keys: Iterable[str]) -> None:
    for object_key in object_keys:
        _minio.remove_object(MINIO_BUCKET, object_key)


def copy_source_object(source_key: str) -> str:
    extension = os.path.splitext(source_key)[1]
    destination_key = f"raw/{uuid.uuid4().hex}{extension}"
    _minio.copy_object(
        MINIO_BUCKET,
        destination_key,
        CopySource(MINIO_BUCKET, source_key),
    )
    return destination_key


def make_unique_key(stage: str, file_name: Optional[str], payload: Dict[str, Any]) -> str:
    fp_hash = payload.get("fingerprint_hash") or ""
    base = f"{stage}|{file_name or ''}|{fp_hash}"
    return hashlib.sha1(base.encode()).hexdigest()
