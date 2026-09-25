"""Fast tests never start service lifespans or connect to external services."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from minio import Minio


def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", help="Enable PostgreSQL/Redis tests")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Use --integration with disposable services"))


@pytest.fixture(scope="session")
def orchestrator():
    # utils currently probes MinIO at import time. Keep production startup intact
    # and stub only that probe; all subsequent storage calls get per-test mocks.
    with patch.object(Minio, "bucket_exists", return_value=True):
        return importlib.import_module("orchestrator_runner")


@pytest.fixture
def connection():
    conn = AsyncMock()
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__.return_value = conn
    return conn


@pytest.fixture
def pool(connection):
    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = connection
    return pool


@pytest.fixture
def redis():
    return AsyncMock()


@pytest.fixture
def user():
    return {"id": 7, "auth_user_id": "test-user", "email": "test@example.com"}


@pytest.fixture
async def client(orchestrator, pool, redis, user, monkeypatch):
    monkeypatch.setattr(orchestrator.app.state, "db_pool", pool, raising=False)
    monkeypatch.setattr(orchestrator.app.state, "redis", redis, raising=False)
    monkeypatch.setitem(orchestrator.app.dependency_overrides, orchestrator.get_current_user, lambda: user)
    # ASGITransport exercises real routing/validation without starting consumers.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=orchestrator.app), base_url="http://test"
    ) as client:
        yield client
