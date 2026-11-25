import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.redis import get_redis
from app.core.settings import settings
from app.rate_limit.limiter import increment_rate_limit

logger = logging.getLogger(__name__)


def rate_limit(
    namespace: str,
    limit: int = settings.RATE_LIMIT_REQUESTS,
    window_seconds: int = settings.RATE_LIMIT_WINDOW_SECONDS,
    *,
    fail_open: bool = False,
) -> Callable[..., Awaitable[None]]:
    async def dependency(
        request: Request,
        redis: Annotated[Redis, Depends(get_redis)],
    ) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{namespace}:{client_ip}"

        try:
            count, ttl = await increment_rate_limit(
                redis=redis,
                key=key,
                window_seconds=window_seconds,
            )
        except (RedisConnectionError, RedisTimeoutError) as exc:
            logger.warning(
                "Rate limiter unavailable: namespace=%s fail_open=%s",
                namespace,
                fail_open,
                exc_info=True,
            )

            if fail_open:
                return

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable",
                headers={"Retry-After": "5"},
            ) from exc

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(max(ttl, 0))},
            )

    return dependency