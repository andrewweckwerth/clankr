import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict

from fastapi import HTTPException, Request, status

from db import upsert_user

INTERNAL_AUTH_HEADER = "x-clankr-internal-auth"


def _decode_payload(encoded_payload: str) -> Dict[str, Any]:
    padding = "=" * (-len(encoded_payload) % 4)
    decoded = base64.urlsafe_b64decode(encoded_payload + padding)
    payload = json.loads(decoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Auth payload must be an object")
    return payload


async def get_current_user(request: Request) -> Dict[str, Any]:
    """Validate the short-lived identity assertion issued by the frontend."""
    secret = os.getenv("INTERNAL_AUTH_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    assertion = request.headers.get(INTERNAL_AUTH_HEADER)
    if not assertion or assertion.count(".") != 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    encoded_payload, encoded_signature = assertion.split(".", 1)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    padding = "=" * (-len(encoded_signature) % 4)
    try:
        actual_signature = base64.urlsafe_b64decode(encoded_signature + padding)
    except (ValueError, UnicodeError, binascii.Error):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication")

    if not hmac.compare_digest(actual_signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication")

    try:
        payload = _decode_payload(encoded_payload)
        subject = payload["sub"]
        email = payload["email"]
        name = payload["name"]
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication")

    now = int(time.time())
    if (
        not isinstance(subject, str)
        or not subject
        or not isinstance(email, str)
        or not email
        or not isinstance(name, str)
        or not name
        or issued_at > now + 30
        or expires_at <= now
        or expires_at - issued_at > 90
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired authentication")

    image = payload.get("image")
    if image is not None and not isinstance(image, str):
        image = None

    return await upsert_user(
        request.app.state.db_pool,
        auth_user_id=subject,
        email=email,
        display_name=name,
        image_url=image,
    )
