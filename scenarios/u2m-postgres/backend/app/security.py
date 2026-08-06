import hashlib
import hmac
import time

from fastapi import HTTPException, Request, status

from .config import Settings


def verify_internal_request(request: Request, body: bytes, settings: Settings) -> str:
    # Databricks authenticates/authorizes the Bearer token at the App gateway.
    # The HMAC binds the user payload to this server-to-server request.
    timestamp_text = request.headers.get("x-internal-timestamp", "")
    supplied = request.headers.get("x-internal-signature", "")
    try:
        timestamp = int(timestamp_text)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request signature") from error
    if abs(int(time.time()) - timestamp) > settings.signature_max_age_seconds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Request signature expired")
    expected = "sha256=" + hmac.new(
        settings.internal_identity_hmac_secret.encode(), timestamp_text.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request signature")
    return request.headers.get("x-request-id", "unknown")
