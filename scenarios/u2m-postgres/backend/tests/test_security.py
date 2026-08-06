import hashlib
import hmac
import time

import pytest
from starlette.requests import Request

from app.config import Settings
from app.security import verify_internal_request


def request(headers: dict[str, str]) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": raw})


def test_signed_local_request_is_accepted() -> None:
    body = b'{"external_user_id":"user-1"}'
    timestamp = str(int(time.time()))
    secret = "a" * 32
    signature = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    settings = Settings(auth_mode="local", database_url="postgresql+psycopg://unused", internal_identity_hmac_secret=secret)
    value = verify_internal_request(request({"x-internal-timestamp": timestamp, "x-internal-signature": f"sha256={signature}"}), body, settings)
    assert value == "unknown"


def test_unsigned_request_is_rejected() -> None:
    settings = Settings(auth_mode="local", database_url="postgresql+psycopg://unused", internal_identity_hmac_secret="a" * 32)
    with pytest.raises(Exception):
        verify_internal_request(request({}), b"{}", settings)
