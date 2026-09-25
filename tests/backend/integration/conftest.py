import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from redis.asyncio import Redis


def required_url(name):
    value = os.getenv(name)
    if not value:
        pytest.fail(f"--integration requires {name}; see docs/testing.md")
    return value


@pytest.fixture
async def pool():
    # Each test gets its own schema, including its own sequences. Never truncate
    # shared tables or drop any pre-existing schema.
    admin = await asyncpg.connect(required_url("TEST_DATABASE_URL"))
    schema = "test_" + uuid4().hex
    pool = None
    try:
        await admin.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        pool = await asyncpg.create_pool(
            required_url("TEST_DATABASE_URL"), min_size=1, max_size=10,
            server_settings={"search_path": f"{schema},public"},
        )
        sql = (Path(__file__).resolve().parents[3] / "database/init.sql").read_text()
        async with pool.acquire() as conn:
            await conn.execute(sql)
        yield pool
    finally:
        if pool is not None:
            await pool.close()
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()


@pytest.fixture
async def redis(monkeypatch, orchestrator):
    import redis_cache
    import redis_queue
    prefix = "test:" + uuid4().hex + ":"
    for stage in redis_queue.STREAMS:
        monkeypatch.setitem(redis_queue.STREAMS, stage, prefix + stage)
    monkeypatch.setattr(redis_cache, "SONG_CACHE_PREFIX", prefix + "cache:")
    client = Redis.from_url(required_url("TEST_REDIS_URL"), decode_responses=True)
    try:
        await client.ping()
        yield client
    finally:
        keys = [key async for key in client.scan_iter(match=prefix + "*")]
        if keys:
            await client.delete(*keys)
        await client.aclose()


@pytest.fixture
async def user(pool):
    from db import upsert_user
    return await upsert_user(pool, auth_user_id="test-user", email="test@example.com", display_name="Test User")
