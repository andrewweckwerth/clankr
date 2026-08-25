import os
import httpx
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-9s %(message)s",
)
logger = logging.getLogger("orchestrator")

# ------- config -------
ACOUSTI_URL   = os.getenv("ACOUSTI_URL",   "http://acousti:8000")
DEMUCS_URL    = os.getenv("DEMUCS_URL",    "http://demucs:8000")
WHISPER_URL   = os.getenv("WHISPER_URL",   "http://whisper:8000")
CLASSIFY_URL  = os.getenv("CLASSIFY_URL",  "http://classifier:8000")

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
    r = await _client.post(f"{DEMUCS_URL}/separate", data={"file_path": file_path}, timeout=T_DEMUCS)
    if r.status_code != 200:
        await _raise(r, "Demucs")
    return r.json()


async def run_whisper(file_path: str):
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
        r = await _client.post(f"{ACOUSTI_URL}/convert", data={"file_path": file_path},  timeout=T_IDENTIFY)
        
        file_path = r.json()["file_path"]
        
        r = await _client.post(f"{ACOUSTI_URL}/identify", data={"file_path": file_path}, timeout=T_IDENTIFY)
        data = r.json()          # this is the response dict
        data["file_path"] = file_path
        return data
    except Exception as e:
        print(e)
