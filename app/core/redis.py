from fastapi import Request
from redis.asyncio import Redis

from app.core.settings import settings


def create_redis_client() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


def get_redis(request: Request) -> Redis:
    return request.app.state.redis
