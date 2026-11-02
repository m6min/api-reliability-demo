from pydantic import TypeAdapter
from redis.asyncio import Redis

from app.core.settings import settings
from app.schemas.product import ProductRead


PRODUCTS_LIST_CACHE_KEY = "products:list:v1"

product_list_adapter = TypeAdapter(list[ProductRead])


async def get_cached_products(redis: Redis) -> list[ProductRead] | None:
    cached_products = await redis.get(PRODUCTS_LIST_CACHE_KEY)

    if cached_products is None:
        return None

    return product_list_adapter.validate_json(cached_products)


async def set_cached_products(
    redis: Redis,
    products: list[ProductRead],
) -> None:
    serialized_products = product_list_adapter.dump_json(products)
    await redis.set(
        PRODUCTS_LIST_CACHE_KEY,
        serialized_products,
        ex=settings.PRODUCTS_CACHE_TTL_SECONDS,
    )
