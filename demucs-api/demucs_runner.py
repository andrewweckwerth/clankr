from fastapi import FastAPI, UploadFile, File, Form
import os
from pathlib import Path
import traceback
import tempfile
from minio import Minio
import soundfile as sf
from fastapi.responses import JSONResponse
from demucs.apply import apply_model
from demucs.pretrained import get_model
from demucs.audio import AudioFile

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-9s %(message)s",
)
logger = logging.getLogger("demucs")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "clankr")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "change-me")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "clankr-audio")
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
)


def download_object(object_key: str) -> str:
    suffix = Path(object_key).suffix
    fd, path = tempfile.mkstemp(prefix="clankr-", suffix=suffix)
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

app = FastAPI()
MODEL = get_model(name="htdemucs")


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

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/separate")
async def separate(file_path: str = Form(...)):
    logger.info("🟦Separating Stems")
    base = os.path.splitext(os.path.basename(file_path))[0]
    input_path = None
    output_path = tempfile.mktemp(prefix="clankr-", suffix=".wav")

    try:
        input_path = download_object(file_path)
        success = separate_vocals(input_path, output_path)

        if success:
            output_key = f"stems/{base}.wav"
            upload_object(output_path, output_key)
            logger.info("🟦Stems Separated Successfuly")
            return JSONResponse({"file_path": output_key})
        else:
            return {"status": "error", "message": "No vocals stem found."}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        for path in (input_path, output_path):
            if path and os.path.exists(path):
                os.remove(path)
