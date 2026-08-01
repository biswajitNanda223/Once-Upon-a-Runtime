import os
from functools import lru_cache

import redis
from redis_entraid.cred_provider import create_from_default_azure_credential


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    """Create one thread-safe Redis connection pool per backend process."""
    provider = create_from_default_azure_credential(
        ("https://redis.azure.com/.default",),
    )
    return redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.getenv("REDIS_PORT", "10000")),
        ssl=True,
        decode_responses=True,
        credential_provider=provider,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
        retry_on_timeout=True,
    )


def namespaced(key: str) -> str:
    """Keep this application inside the Redis ACL key namespace."""
    return f"{os.getenv('REDIS_KEY_PREFIX', 'runtime:')}{key}"
