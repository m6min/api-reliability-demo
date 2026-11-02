from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.cache.product_cache import (
    PRODUCTS_LIST_CACHE_KEY,
    get_cached_products,
    invalidate_products_cache,
    set_cached_products,
)
from app.core.settings import settings
from app.schemas.product import ProductRead


def make_product_read() -> ProductRead:
    return ProductRead(
        id=1,
        name="Keyboard",
        description="Mechanical keyboard",
        price=Decimal("99.90"),
        stock=10,
    )


@pytest.mark.asyncio
async def test_get_cached_products_returns_none_on_cache_miss() -> None:
    """It returns none when the product list cache does not exist."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)

    result = await get_cached_products(redis)

    assert result is None
    redis.get.assert_awaited_once_with(PRODUCTS_LIST_CACHE_KEY)


@pytest.mark.asyncio
async def test_get_cached_products_deserializes_cached_products() -> None:
    """It converts cached JSON into product response models."""
    redis = AsyncMock()
    redis.get = AsyncMock(
        return_value='[{"id":1,"name":"Keyboard","description":"Mechanical keyboard","price":"99.90","stock":10}]'
    )

    result = await get_cached_products(redis)

    assert result == [make_product_read()]


@pytest.mark.asyncio
async def test_set_cached_products_uses_configured_ttl() -> None:
    """It stores products with the configured cache lifetime."""
    redis = AsyncMock()
    redis.set = AsyncMock()
    products = [make_product_read()]

    await set_cached_products(redis, products)

    redis.set.assert_awaited_once()
    call = redis.set.await_args
    assert call.args[0] == PRODUCTS_LIST_CACHE_KEY
    assert call.kwargs["ex"] == settings.PRODUCTS_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_invalidate_products_cache_deletes_product_list_key() -> None:
    """It deletes the cached product list key."""
    redis = AsyncMock()
    redis.delete = AsyncMock()

    await invalidate_products_cache(redis)

    redis.delete.assert_awaited_once_with(PRODUCTS_LIST_CACHE_KEY)
