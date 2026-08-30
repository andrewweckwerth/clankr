import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Dict, Optional, Sequence

import asyncpg


dsn = os.getenv("DATABASE_URL")


@asynccontextmanager
async def lifespan(app):
    app.state.db_pool = await asyncpg.create_pool(dsn=dsn)
    yield
    await app.state.db_pool.close()


async def create_job(
    conn: asyncpg.Connection,
    *,
    user_id: int,
    stages: Sequence[str],
    song_id: Optional[int] = None,
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
) -> int:
    """Create a job and its requested stage rows atomically."""
    if not stages:
        raise ValueError("A job must contain at least one stage")

    async with conn.transaction():
        job_id = await conn.fetchval(
            """
            INSERT INTO jobs (
              user_id, song_id, current_stage, status, input_type,
              title, artist, lyrics, classification, accuracy,
              file_path, duration, fingerprint, fingerprint_hash,
              audio_processed
            ) VALUES (
              $1, $2, $3, 'queued', $4,
              $5, $6, $7, $8, $9,
              $10, $11, $12, $13, $14
            )
            RETURNING id;
            """,
            user_id,
            song_id,
            stages[0],
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
        )

        await conn.executemany(
            """
            INSERT INTO job_steps (job_id, stage, position)
            VALUES ($1, $2, $3)
            """,
            [(job_id, stage, position) for position, stage in enumerate(stages)],
        )

    return job_id


JOB_COLUMNS = {
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
    "error",
    "completed_at",
}


async def update_job(conn: asyncpg.Connection, job_id: int, **fields: Any) -> None:
    if not fields:
        return
    unknown = set(fields) - JOB_COLUMNS
    if unknown:
        raise ValueError(f"Unsupported job fields: {', '.join(sorted(unknown))}")

    columns = list(fields)
    assignments = ", ".join(
        f"{column} = ${index}"
        for index, column in enumerate(columns, start=1)
    )
    assignments += ", updated_at = CURRENT_TIMESTAMP"
    values = [fields[column] for column in columns]
    values.append(job_id)
    await conn.execute(
        f"UPDATE jobs SET {assignments} WHERE id = ${len(values)}",
        *values,
    )


async def get_job_with_steps_for_user(
    pool,
    job_id: int,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT * FROM jobs WHERE id = $1 AND user_id = $2",
            job_id,
            user_id,
        )
        if not job:
            return None
        steps = await conn.fetch(
            """
            SELECT id, job_id, stage, position, status, attempts, result, error,
                   queued_at, started_at, completed_at
            FROM job_steps
            WHERE job_id = $1
            ORDER BY position
            """,
            job_id,
        )
        result = dict(job)
        result["steps"] = [dict(step) for step in steps]
        return result


async def upsert_user(
    pool,
    *,
    auth_user_id: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (auth_user_id, email, display_name, image_url)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (auth_user_id) DO UPDATE SET
              email = COALESCE(EXCLUDED.email, users.email),
              display_name = COALESCE(EXCLUDED.display_name, users.display_name),
              image_url = COALESCE(EXCLUDED.image_url, users.image_url),
              updated_at = CURRENT_TIMESTAMP
            RETURNING id, auth_user_id, email, display_name, image_url;
            """,
            auth_user_id,
            email,
            display_name,
            image_url,
        )
    return dict(row)


async def record_user_song(
    conn: asyncpg.Connection,
    *,
    user_id: int,
    song_id: int,
) -> None:
    await conn.execute(
        """
        INSERT INTO user_songs (user_id, song_id)
        VALUES ($1, $2)
        ON CONFLICT (user_id, song_id) DO UPDATE SET
          last_submitted_at = CURRENT_TIMESTAMP,
          submission_count = user_songs.submission_count + 1
        """,
        user_id,
        song_id,
    )


async def consume_daily_analysis(
    conn: asyncpg.Connection,
    *,
    user_id: int,
    usage_date: date,
    limit: int,
) -> Optional[int]:
    """Atomically consume one analysis from a user's daily quota."""
    return await conn.fetchval(
        """
        INSERT INTO user_daily_usage (user_id, usage_date, analysis_count)
        VALUES ($1, $2, 1)
        ON CONFLICT (user_id, usage_date) DO UPDATE SET
          analysis_count = user_daily_usage.analysis_count + 1
        WHERE user_daily_usage.analysis_count < $3
        RETURNING analysis_count;
        """,
        user_id,
        usage_date,
        limit,
    )


async def upsert_song(
    conn: asyncpg.Connection,
    *,
    title: str,
    artist: Optional[str],
    duration: Optional[float],
    fingerprint: Optional[str],
    fingerprint_hash: Optional[str],
    lyrics: Optional[str],
    classification: Optional[str],
    accuracy: Optional[float],
    file_path: Optional[str],
    audio_processed: bool,
) -> int:
    dur = int(duration) if isinstance(duration, float) else duration

    row = await conn.fetchrow(
        """
        INSERT INTO songs (
            title, artist, duration, fingerprint, fingerprint_hash,
            lyrics, classification, accuracy, file_path, audio_processed
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT (fingerprint_hash) DO UPDATE SET
            title           = COALESCE(EXCLUDED.title, songs.title),
            artist          = COALESCE(EXCLUDED.artist, songs.artist),
            duration        = COALESCE(EXCLUDED.duration, songs.duration),
            fingerprint     = COALESCE(EXCLUDED.fingerprint, songs.fingerprint),
            lyrics          = COALESCE(EXCLUDED.lyrics, songs.lyrics),
            classification  = COALESCE(EXCLUDED.classification, songs.classification),
            accuracy        = COALESCE(EXCLUDED.accuracy, songs.accuracy),
            file_path       = COALESCE(EXCLUDED.file_path, songs.file_path),
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


async def get_song_by_fingerprint_hash(
    conn: asyncpg.Connection,
    fingerprint_hash: str,
) -> Optional[asyncpg.Record]:
    return await conn.fetchrow(
        "SELECT * FROM songs WHERE fingerprint_hash = $1",
        fingerprint_hash,
    )


async def get_song_by_title_artist(pool, title: str, artist: str) -> Optional[int]:
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


async def search_song_fuzzy(
    pool,
    title: str,
    artist: str,
    limit: int = 5,
):
    sql = """
    SELECT id, title, artist,
       similarity(LOWER(title), LOWER($1)) +
       similarity(LOWER(artist), LOWER($2)) AS score
    FROM songs
    ORDER BY (LOWER(title) <-> LOWER($1)) +
             (LOWER(artist) <-> LOWER($2))
    LIMIT $3;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, title, artist, limit)
    return [dict(row) for row in rows]
