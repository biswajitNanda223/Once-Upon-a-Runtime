import os
import re
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from .redis_client import get_redis, namespaced

app = FastAPI(title="Once Upon a Runtime split API", version="1.0.0")
SAFE_KEY = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")


class CacheValue(BaseModel):
    value: str = Field(min_length=1, max_length=16_384)
    ttl_seconds: int | None = Field(default=None, ge=1, le=86_400)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello(request: Request) -> dict[str, str]:
    return {
        "message": "Hello across two Databricks Apps",
        "email": request.headers.get("x-forwarded-email", "app-or-local-call"),
        "pattern": "split",
    }


@app.get("/api/items/{item_id}")
def item(item_id: int) -> dict[str, int | str]:
    return {"id": item_id, "name": f"Split backend item {item_id}"}


def checked_key(key: str) -> str:
    if not SAFE_KEY.fullmatch(key):
        raise HTTPException(400, "Invalid cache key")
    return namespaced(key)


@app.get("/api/cache/{key}")
def cache_get(key: str) -> dict[str, str | bool]:
    redis_key = checked_key(key)
    try:
        value = get_redis().get(redis_key)
    except RedisError as exc:
        raise HTTPException(503, "Cache temporarily unavailable") from exc
    if value is None:
        raise HTTPException(404, "Cache key not found")
    return {"key": key, "value": cast(str, value), "cached": True}


@app.put("/api/cache/{key}")
def cache_put(key: str, body: CacheValue) -> dict[str, str | int]:
    redis_key = checked_key(key)
    ttl = body.ttl_seconds or int(os.getenv("REDIS_DEFAULT_TTL_SECONDS", "300"))
    try:
        get_redis().set(redis_key, body.value, ex=ttl)
    except RedisError as exc:
        raise HTTPException(503, "Cache temporarily unavailable") from exc
    return {"key": key, "status": "stored", "ttl_seconds": ttl}
