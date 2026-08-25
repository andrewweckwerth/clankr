import os
import asyncpg
from contextlib import asynccontextmanager
from typing import Optional
import json
from utils import make_unique_key
from typing import Optional, Dict, Any


dsn = os.getenv("DATABASE_URL")


@asynccontextmanager
async def lifespan(app):
    app.state.db_pool = await asyncpg.create_pool(dsn=dsn)
    yield
    await app.state.db_pool.close()


import asyncpg
from typing import Optional, Dict, Any, Iterable

# ---- CREATE (INSERT) ----
import asyncpg
from typing import Optional


async def create_job(
    conn: asyncpg.Connection,
    *,
    song_id: Optional[int] = None,
    current_stage: Optional[str] = None,
    status: str = "Not Started",
    input_type: Optional[str] = None,
    title: str,
    artist: Optional[str] = None,
    lyrics: Optional[str] = None,
    classification: Optional[str] = None,
    accuracy: Optional[float] = None,
    file_path: Optional[str] = None,
    duration: Optional[int] = None,
    fingerprint: Optional[str] = None,
    fingerprint_hash: Optional[str] = None,
    audio_processed: bool = False,
    want_identify: bool = False,
    want_demucs: bool = False,
    want_whisper: bool = False,
    want_classify: bool = False,
    done_identify: bool = False,
    done_demucs: bool = False,
    done_whisper: bool = False,
    done_classify: bool = False,
) -> int:
    sql = """
    INSERT INTO jobs (
      song_id, current_stage, status, input_type,
      title, artist, lyrics, classification, accuracy,
      file_path, duration, fingerprint, fingerprint_hash,
      audio_processed,
      want_identify, want_demucs, want_whisper, want_classify,
      done_identify, done_demucs, done_whisper, done_classify
    ) VALUES (
      $1,$2,$3,$4,
      $5,$6,$7,$8,$9,
      $10,$11,$12,$13,
      $14,
      $15,$16,$17,$18,
      $19,$20,$21,$22
    )
    RETURNING id;
    """
    return await conn.fetchval(
        sql,
        song_id,
        current_stage,
        status,
        input_type,
        title,
        artist,
        lyrics,
        classification,
        accuracy,
        file_path,
        duration,
        fingerprint,
        fingerprint_hash,
        audio_processed,
        want_identify,
        want_demucs,
        want_whisper,
        want_classify,
        done_identify,
        done_demucs,
        done_whisper,
        done_classify,
    )


async def update_job(conn, job_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ${i}" for i, k in enumerate(fields.keys(), start=1))
    values = list(fields.values()) + [job_id]
    sql = f"UPDATE jobs SET {cols} WHERE id = ${len(values)}"
    await conn.execute(sql, *values)


# ---- UPSERT by fingerprint_hash (idempotent write) ----
# Pass any fields you want to set; None means "don't overwrite existing".
async def upsert_job_by_fingerprint(
    conn: asyncpg.Connection,
    *,
    fingerprint_hash: str,
    # optional fields to set/merge:
    song_id: Optional[int] = None,
    current_stage: Optional[str] = None,
    status: Optional[str] = None,
    input_type: Optional[str] = None,
    title: Optional[str] = None,
    artist: Optional[str] = None,
    lyrics: Optional[str] = None,
    classification: Optional[str] = None,
    accuracy: Optional[float] = None,
    file_path: Optional[str] = None,
    duration: Optional[int] = None,
    fingerprint: Optional[str] = None,
    audio_processed: Optional[bool] = None,
    want_identify: Optional[bool] = None,
    want_demucs: Optional[bool] = None,
    want_whisper: Optional[bool] = None,
    want_classify: Optional[bool] = None,
    done_identify: Optional[bool] = None,
    done_demucs: Optional[bool] = None,
    done_whisper: Optional[bool] = None,
    done_classify: Optional[bool] = None,
) -> int:
    """
    Insert a new job keyed by fingerprint_hash, or update existing row.
    We use COALESCE(EXCLUDED.col, jobs.col) so None won't clobber existing values.
    """
    sql = """
    INSERT INTO jobs (
      fingerprint_hash, song_id, current_stage, status, input_type,
      title, artist, lyrics, classification, accuracy,
      file_path, duration, fingerprint, audio_processed,
      want_identify, want_demucs, want_whisper, want_classify,
      done_identify, done_demucs, done_whisper, done_classify
    ) VALUES (
      $1,$2,$3,$4,$5,
      $6,$7,$8,$9,$10,
      $11,$12,$13,$14,
      $15,$16,$17,$18,
      $19,$20,$21,$22
    )
    ON CONFLICT (fingerprint_hash) DO UPDATE SET
      song_id        = COALESCE(EXCLUDED.song_id,        jobs.song_id),
      current_stage  = COALESCE(EXCLUDED.current_stage,  jobs.current_stage),
      status         = COALESCE(EXCLUDED.status,         jobs.status),
      input_type     = COALESCE(EXCLUDED.input_type,     jobs.input_type),
      title          = COALESCE(EXCLUDED.title,          jobs.title),
      artist         = COALESCE(EXCLUDED.artist,         jobs.artist),
      lyrics         = COALESCE(EXCLUDED.lyrics,         jobs.lyrics),
      classification = COALESCE(EXCLUDED.classification, jobs.classification),
      accuracy       = COALESCE(EXCLUDED.accuracy,       jobs.accuracy),
      file_path      = COALESCE(EXCLUDED.file_path,      jobs.file_path),
      duration       = COALESCE(EXCLUDED.duration,       jobs.duration),
      fingerprint    = COALESCE(EXCLUDED.fingerprint,    jobs.fingerprint),
      audio_processed= COALESCE(EXCLUDED.audio_processed,jobs.audio_processed),
      want_identify  = COALESCE(EXCLUDED.want_identify,  jobs.want_identify),
      want_demucs    = COALESCE(EXCLUDED.want_demucs,    jobs.want_demucs),
      want_whisper   = COALESCE(EXCLUDED.want_whisper,   jobs.want_whisper),
      want_classify  = COALESCE(EXCLUDED.want_classify,  jobs.want_classify),
      done_identify  = COALESCE(EXCLUDED.done_identify,  jobs.done_identify),
      done_demucs    = COALESCE(EXCLUDED.done_demucs,    jobs.done_demucs),
      done_whisper   = COALESCE(EXCLUDED.done_whisper,   jobs.done_whisper),
      done_classify  = COALESCE(EXCLUDED.done_classify,  jobs.done_classify)
    RETURNING id;
    """
    return await conn.fetchval(
        sql,
        fingerprint_hash,
        song_id,
        current_stage,
        status,
        input_type,
        title,
        artist,
        lyrics,
        classification,
        accuracy,
        file_path,
        duration,
        fingerprint,
        audio_processed,
        want_identify,
        want_demucs,
        want_whisper,
        want_classify,
        done_identify,
        done_demucs,
        done_whisper,
        done_classify,
    )


# ---- UPDATE by id (partial/dynamic) ----
async def update_job_fields(
    conn: asyncpg.Connection,
    job_id: int,
    fields: Dict[str, Any],
    *,
    allowed: Iterable[str] = (
        "song_id",
        "current_stage",
        "status",
        "input_type",
        "title",
        "artist",
        "lyrics",
        "classification",
        "accuracy",
        "file_path",
        "duration",
        "fingerprint",
        "fingerprint_hash",
        "audio_processed",
        "want_identify",
        "want_demucs",
        "want_whisper",
        "want_classify",
        "done_identify",
        "done_demucs",
        "done_whisper",
        "done_classify",
    ),
) -> None:
    """
    Dynamically updates only the provided columns.
    Example: await update_job_fields(conn, 42, {"status":"processing","current_stage":"whisper"})
    """
    if not fields:
        return
    sets = []
    values = []
    idx = 1
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"Column not allowed: {k}")
        sets.append(f"{k} = ${idx}")
        values.append(v)
        idx += 1
    values.append(job_id)
    sql = f"UPDATE jobs SET {', '.join(sets)} WHERE id = ${idx};"
    await conn.execute(sql, *values)


async def upsert_song(
    conn: asyncpg.Connection,
    *,
    title: str,
    artist: Optional[str],
    duration: Optional[float],
    fingerprint: Optional[str],
    fingerprint_hash: str,
    lyrics: Optional[str],
    classification: Optional[str],
    accuracy: Optional[float],
    file_path: str,
    audio_processed: bool,
) -> int:
    # normalize
    dur = int(duration) if isinstance(duration, float) else duration

    row = await conn.fetchrow(
        """
        INSERT INTO songs (
            title, artist, duration, fingerprint, fingerprint_hash,
            lyrics, classification, accuracy, file_path, audio_processed
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT (fingerprint_hash) DO UPDATE SET
            title          = COALESCE(EXCLUDED.title, songs.title),
            artist         = COALESCE(EXCLUDED.artist, songs.artist),
            duration       = COALESCE(EXCLUDED.duration, songs.duration),
            fingerprint    = COALESCE(EXCLUDED.fingerprint, songs.fingerprint),
            lyrics         = COALESCE(EXCLUDED.lyrics, songs.lyrics),
            classification = COALESCE(EXCLUDED.classification, songs.classification),
            accuracy       = COALESCE(EXCLUDED.accuracy, songs.accuracy),
            file_path      = COALESCE(EXCLUDED.file_path, songs.file_path),
            -- keep True if either side is True
            audio_processed = (EXCLUDED.audio_processed OR songs.audio_processed)
        RETURNING id;
        """,
        title,
        artist,
        dur,
        fingerprint,
        fingerprint_hash,
        lyrics,
        classification,
        accuracy,
        file_path,
        audio_processed,
    )
    return row["id"]


async def get_song_by_fingerprint_hash(conn, fingerprint_hash: str) -> dict | None:
    
        row = await conn.fetchrow(
            "SELECT * FROM songs WHERE fingerprint_hash = $1", fingerprint_hash
        )
        return row if row else None


# helper
async def get_song_by_title_artist(pool, title, artist) -> int | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id
            FROM songs
            WHERE LOWER(title) = LOWER($1)
              AND LOWER(artist) = LOWER($2)
            LIMIT 1
            """,
            title,
            artist,
        )
        return row["id"] if row else None


async def search_song_fuzzy(pool, title: str, artist: str, limit: int = 5):
    sql = """
    SELECT id, title, artist,
       similarity(LOWER(title),  LOWER($1)) +
       similarity(LOWER(artist), LOWER($2)) AS score
FROM songs
ORDER BY (LOWER(title) <-> LOWER($1)) +
         (LOWER(artist) <-> LOWER($2))
LIMIT $3;

    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, title, artist, limit)
    return [dict(r) for r in rows]



async def get_job(pool, job_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        return dict(row) if row else None


async def setup_db_pool(dsn: str):
    return await asyncpg.create_pool(dsn)
