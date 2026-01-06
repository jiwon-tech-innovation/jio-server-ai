import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()

def get_redis_client() -> redis.Redis:
    """
    Returns an async Redis client.
    """
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=int(settings.REDIS_PORT),
        password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
        decode_responses=True # Returns strings instead of bytes
    )
