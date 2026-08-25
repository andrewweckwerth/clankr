import os
import uuid
import hashlib
from minio import Minio
from fastapi import UploadFile
from typing import Optional, Dict, Any


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
    ext = os.path.splitext(upload_file.filename)[1]
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

def make_unique_key(stage: str, file_name: Optional[str], payload: Dict[str,Any]) -> str:
    fp_hash = payload.get("fingerprint_hash") or ""
    base = f"{stage}|{file_name or ''}|{fp_hash}"
    return hashlib.sha1(base.encode()).hexdigest()
