import os
import time
import asyncio
import httpx
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-9s %(message)s",
)
logger = logging.getLogger("orchestrator")

# ------- config -------
SHARED_PATH = "/shared_data"
STEMS_PATH = os.path.join(SHARED_PATH, "stems")
RAW_PATH = os.path.join(SHARED_PATH, "raw")
PREPROCESSED_PATH = os.path.join(SHARED_PATH, "preprocessed")

ACOUSTI_URL   = os.getenv("ACOUSTI_URL",   "http://acousti_api:8000")
DEMUCS_URL    = os.getenv("DEMUCS_URL",    "http://demucs_api:8000")
WHISPER_URL   = os.getenv("WHISPER_URL",   "http://whisper_api:8000")
CLASSIFY_URL  = os.getenv("CLASSIFY_URL",  "http://classifier_api:8000")

# Timeouts (connect, read)
T_IDENTIFY   = (5.0, 120.0)
T_CONVERT    = (5.0, 120.0)
T_DEMUCS     = (5.0, 900.0)
T_WHISPER    = (5.0, 600.0)
T_CLASSIFIER = (5.0, 60.0)

# ------- global async client -------
_client = httpx.AsyncClient(timeout=None)  # we set per-request timeouts below


async def _raise(resp: httpx.Response, ctx: str):
    try:
        msg = resp.json()
    except Exception:
        msg = resp.text
    raise RuntimeError(f"{ctx} failed: HTTP {resp.status_code} - {msg}")


# ------- async helpers -------
async def run_demucs(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio not found for Demucs: {file_path}")

    r = await _client.post(f"{DEMUCS_URL}/separate", data={"file_path": file_path}, timeout=T_DEMUCS)
    if r.status_code != 200:
        await _raise(r, "Demucs")
    return r.json()


async def run_whisper(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio not found for Whisper: {file_path}")
    
    r = await _client.post(f"{WHISPER_URL}/transcribe", data={"file_path": file_path}, timeout=T_WHISPER)
    if r.status_code != 200:
        await _raise(r, "Whisper")
    return r.json()


async def run_classify(lyrics: str):
    r = await _client.post(f"{CLASSIFY_URL}/classify", data={"lyrics": lyrics}, timeout=T_CLASSIFIER)
    if r.status_code != 200:
        await _raise(r, "Classifier")
    return r.json()


async def run_acousti(file_path: str):
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio not found for Acousti: {file_path}")
        r = await _client.post(f"{ACOUSTI_URL}/convert", data={"file_path": file_path},  timeout=T_IDENTIFY)
        
        file_path = r.json()["file_path"]
        
        r = await _client.post(f"{ACOUSTI_URL}/identify", data={"file_path": file_path}, timeout=T_IDENTIFY)
        data = r.json()          # this is the response dict
        data["file_path"] = file_path   # inject your own field
        return data
    except Exception as e:
        print(e)

async def preprocess(file_name: str) -> str:
    
    ext = Path(file_name).suffix.lower()

    if ext == ".wav":
        return file_name
    
    input_path = os.path.join(RAW_PATH, file_name)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found for convert: {input_path}")

    with open(input_path, "rb") as f:
        files = {'file': (file_name, f)}
        try:
            r = await _client.post(f"{ACOUSTI_URL}/convert", files=files, timeout=T_CONVERT)
        except httpx.RequestError as e:
            raise RuntimeError(f"Connect to /convert failed: {e}")

    if r.status_code != 200:
        await _raise(r, "Conversion")

    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Convert returned non-JSON: {r.text}")

    converted_name = data.get("filename")
    if not converted_name:
        raise RuntimeError("Conversion response missing 'filename'")

    try:
        os.remove(input_path)
    except FileNotFoundError:
        pass

    return converted_name
