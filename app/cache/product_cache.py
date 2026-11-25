import logging

from pydantic import TypeAdapter
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.settings import settings
from app.schemas.product import ProductRead

logger = logging.getLogger(__name__)

PRODUCTS_LIST_CACHE_KEY = "products:list:v1"

product_list_adapter = TypeAdapter(list[ProductRead])


async def get_cached_products(redis: Redis) -> list[ProductRead] | None:
    try:
        cached_products = await redis.get(PRODUCTS_LIST_CACHE_KEY)
    except (RedisConnectionError, RedisTimeoutError):
        logger.warning(
            "cache=ERROR operation=GET key=%s fallback=postgresql",
            PRODUCTS_LIST_CACHE_KEY,
            exc_info=True,
        )
        return None

    if cached_products is None:
        logger.info(
            "cache=MISS key=%s",
            PRODUCTS_LIST_CACHE_KEY,
        )
        return None

    products = product_list_adapter.validate_json(cached_products)

    logger.info(
        "cache=HIT key=%s",
        PRODUCTS_LIST_CACHE_KEY,
    )

    return products


async def set_cached_products(
    redis: Redis,
    products: list[ProductRead],
) -> None:
    serialized_products = product_list_adapter.dump_json(products)

    try:
        await redis.set(
            PRODUCTS_LIST_CACHE_KEY,
            serialized_products,
            ex=settings.PRODUCTS_CACHE_TTL_SECONDS,
        )
    except (RedisConnectionError, RedisTimeoutError):
        logger.warning(
            "Product cache write failed; returning database result",
            exc_info=True,
        )


async def invalidate_products_cache(redis: Redis) -> None:
    try:
        await redis.delete(PRODUCTS_LIST_CACHE_KEY)
    except (RedisConnectionError, RedisTimeoutError):
        logger.warning(
            "Product cache invalidation failed; cached data may be stale",
            exc_info=True,
        )