# acoustid-api/main.py
import os
import subprocess
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from pathlib import Path
import tempfile
from minio import Minio

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-9s %(message)s",
)
logger = logging.getLogger("acousti")

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


def download_object(object_key: str, suffix: str = "") -> str:
    fd, path = tempfile.mkstemp(prefix="clankr-", suffix=suffix)
    os.close(fd)
    try:
        minio_client.fget_object(MINIO_BUCKET, object_key, path)
        return path
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise


def upload_object(path: str, object_key: str, content_type: str) -> str:
    minio_client.fput_object(MINIO_BUCKET, object_key, path, content_type=content_type)
    return object_key

app = FastAPI()

# Optional: Allow frontend calls during local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_fpcalc(file_path):
    result = subprocess.run(["fpcalc", file_path], capture_output=True, text=True)

    if "FINGERPRINT=" not in result.stdout or "DURATION=" not in result.stdout:
        raise RuntimeError(f"fpcalc failed: {result.stderr}")

    fingerprint = None
    duration = None

    for line in result.stdout.splitlines():
        if line.startswith("FINGERPRINT="):
            fingerprint = line.split("=", 1)[1]
        elif line.startswith("DURATION="):
            duration = int(float(line.split("=", 1)[1]))

    if not fingerprint or not duration:
        raise RuntimeError("Missing fingerprint or duration")

    return fingerprint, duration


def lookup_acoustid(fingerprint, duration, api_key):
    url = "https://api.acoustid.org/v2/lookup"
    payload = {
        "client": api_key,
        "format": "json",
        "fingerprint": fingerprint,
        "duration": duration,
        "meta": "recordings"
    }

    response = requests.post(url, data=payload)
    if response.status_code != 200:
        raise RuntimeError(f"AcoustID error: {response.text}")

    return response.json()

async def convert_audio(object_key: str) -> str:
    """
    Convert an uploaded audio file to WAV using ffmpeg.
    Returns the path of the converted WAV file.
    Raises subprocess.CalledProcessError on failure.
    """
    suffix = Path(object_key).suffix
    input_path = download_object(object_key, suffix=suffix)
    base = os.path.splitext(os.path.basename(object_key))[0]
    output_path = tempfile.mktemp(prefix="clankr-", suffix=".wav")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                output_path
            ],
            check=True,
            capture_output=True,
            text=True
        )
        output_key = f"preprocessed/{base}.wav"
        upload_object(output_path, output_key, "audio/wav")
        return output_key
    except subprocess.CalledProcessError as e:
        if os.path.exists(input_path):
            os.remove(input_path)
        raise RuntimeError(
            f"FFmpeg failed (stdout={e.stdout}, stderr={e.stderr})"
        )
    finally:
        for path in (input_path, output_path):
            if os.path.exists(path):
                os.remove(path)

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/convert")
async def convert(file_path: str = Form(...)):
    logger.info("🟦Converting")
    try:
        wav_path = await convert_audio(file_path)
        logger.info("🟦Converted Successfully")
        return JSONResponse({"file_path": wav_path})
    except RuntimeError as e:
        logger.info((e))
        logger.error(e)
        return JSONResponse({"error": str(e)}, status_code=500)
      


@app.post("/identify")
async def identify(file_path: str = Form(...)):
    local_path = None
    try:
        logger.info("🟦Identifying")
        
        api_key = os.getenv("ACOUSTID_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ACOUSTID_API_KEY env var")

        local_path = download_object(file_path, suffix=Path(file_path).suffix)
        fingerprint, duration = run_fpcalc(local_path)
        raw_result = lookup_acoustid(fingerprint, duration, api_key)

        matches = []
        for result in raw_result.get("results", []):
            for recording in result.get("recordings", []):
                title = recording.get("title", "Unknown")
                artist = "Unknown"
                if recording.get("artists"):
                    artist = recording["artists"][0].get("name", "Unknown")
                matches.append({"title": title, "artist": artist})
        
        logger.info("🟦Identified Successfully")
        return JSONResponse({
            "fingerprint": fingerprint,
            "duration": duration,
            "matches": matches
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
