import logging
import os
from typing import Optional

import asyncpg
from redis.asyncio import Redis


logger = logging.getLogger("orchestrator.redis_cache")

SONG_CACHE_PREFIX = os.getenv(
    "SONG_CACHE_PREFIX",
    "clankr:cache:song:fingerprint:",
)
SONG_CACHE_TTL_SECONDS = int(os.getenv("SONG_CACHE_TTL_SECONDS", "86400"))


def song_cache_key(fingerprint_hash: str) -> str:
    return f"{SONG_CACHE_PREFIX}{fingerprint_hash}"


async def find_song_by_fingerprint(
    conn: asyncpg.Connection,
    redis_client: Redis,
    fingerprint_hash: str,
) -> Optional[asyncpg.Record]:
    """Use Redis as a read-through ID cache, with PostgreSQL as the authority."""
    key = song_cache_key(fingerprint_hash)

    try:
        cached_song_id = await redis_client.get(key)
    except Exception:
        logger.warning("Song cache unavailable; falling back to PostgreSQL", exc_info=True)
        cached_song_id = None

    if cached_song_id:
        try:
            song = await conn.fetchrow(
                "SELECT * FROM songs WHERE id = $1",
                int(cached_song_id),
            )
        except (TypeError, ValueError):
            song = None

        if song:
            return song

        # The cache may point to a deleted or invalid row. Remove it and use
        # the authoritative fingerprint lookup below.
        try:
            await redis_client.delete(key)
        except Exception:
            logger.debug("Unable to remove stale song cache key", exc_info=True)

    song = await conn.fetchrow(
        "SELECT * FROM songs WHERE fingerprint_hash = $1",
        fingerprint_hash,
    )
    if song:
        await cache_song_id(redis_client, fingerprint_hash, song["id"])
    return song


async def cache_song_id(
    redis_client: Redis,
    fingerprint_hash: Optional[str],
    song_id: Optional[int],
) -> None:
    if not fingerprint_hash or song_id is None:
        return
    try:
        await redis_client.set(
            song_cache_key(fingerprint_hash),
            str(song_id),
            ex=SONG_CACHE_TTL_SECONDS,
        )
    except Exception:
        # Cache writes must never make a successful PostgreSQL operation fail.
        logger.warning("Unable to refresh song cache", exc_info=True)
