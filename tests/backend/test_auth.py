import base64
import hashlib
import hmac
import json
from unittest.mock import AsyncMock

import auth
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from types import SimpleNamespace


NOW = 1_800_000_000
SECRET = "test-only-internal-secret"


def assertion(payload, secret=SECRET):
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    return encoded + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")


@pytest.fixture
def payload():
    return {"sub": "u1", "email": "user@example.com", "name": "Test User", "iat": NOW, "exp": NOW + 60}


@pytest.fixture
def authenticate(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    monkeypatch.setattr(auth.time, "time", lambda: NOW)
    upsert = AsyncMock(return_value={"id": 1})
    monkeypatch.setattr(auth, "upsert_user", upsert)

    async def call(token):
        headers = [] if token is None else [(b"x-clankr-internal-auth", token)]
        request = Request({"type": "http", "headers": headers, "app": SimpleNamespace(state=SimpleNamespace(db_pool=object()))})
        return await auth.get_current_user(request)

    return call, upsert


async def test_signed_identity_maps_to_local_user(authenticate, payload):
    call, upsert = authenticate
    assert await call(assertion(payload)) == {"id": 1}
    assert upsert.await_args.kwargs == {
        "auth_user_id": "u1", "email": "user@example.com", "display_name": "Test User", "image_url": None,
    }


@pytest.mark.parametrize("token", [None, b"", b"bad", b"a.b.c", b"bad.signature"])
async def test_missing_or_malformed_identity_is_rejected(authenticate, token):
    call, upsert = authenticate
    with pytest.raises(HTTPException) as error:
        await call(token)
    assert error.value.status_code == 401
    upsert.assert_not_awaited()


@pytest.mark.parametrize("changes", [
    {"exp": NOW}, {"iat": NOW + 31}, {"exp": NOW + 91},
    {"sub": ""}, {"email": None}, {"name": 12}, {"exp": "invalid"},
])
async def test_invalid_claims_never_touch_database(authenticate, payload, changes):
    call, upsert = authenticate
    with pytest.raises(HTTPException) as error:
        await call(assertion(payload | changes))
    assert error.value.status_code == 401
    upsert.assert_not_awaited()


async def test_wrong_signing_key_is_rejected(authenticate, payload):
    call, upsert = authenticate
    with pytest.raises(HTTPException) as error:
        await call(assertion(payload, "wrong-secret"))
    assert error.value.status_code == 401
    upsert.assert_not_awaited()


async def test_unconfigured_auth_fails_closed(authenticate, monkeypatch):
    call, upsert = authenticate
    monkeypatch.delenv("INTERNAL_AUTH_SECRET")
    with pytest.raises(HTTPException) as error:
        await call(None)
    assert error.value.status_code == 503
    upsert.assert_not_awaited()
