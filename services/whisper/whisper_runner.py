from fastapi import FastAPI, HTTPException, Query, Form
from faster_whisper import WhisperModel
import os
import sys
import json
import traceback
import logging
import tempfile
from minio import Minio

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-9s %(message)s",
)
logger = logging.getLogger("whisper")

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

app = FastAPI()
model = WhisperModel("base", device="cpu", compute_type="int8")

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe(file_path: str = Form(...)):
    logger.info("🟦transcribing vocals")
    local_path = None

    try:
        fd, local_path = tempfile.mkstemp(prefix="clankr-", suffix=".wav")
        os.close(fd)
        minio_client.fget_object(MINIO_BUCKET, file_path, local_path)
        segments, info = model.transcribe(local_path, beam_size=5, language="en")
        transcript = " ".join(segment.text.strip() for segment in segments)
        logger.info("🟦vocals transcribed successfully")
        return {"lyrics": transcript}
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
