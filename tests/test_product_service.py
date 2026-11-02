from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.product_service import (
    create_product,
    delete_product,
    get_products,
    update_product,
)


@pytest.mark.asyncio
async def test_get_products_returns_cached_products_on_cache_hit() -> None:
    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock(spec=Redis)
    cached_products = [
        ProductRead(
            id=1,
            name="Keyboard",
            description="Mechanical keyboard",
            price=Decimal("99.90"),
            stock=10,
        )
    ]
    get_cache_mock = AsyncMock(return_value=cached_products)
    get_repository_mock = AsyncMock()
    set_cache_mock = AsyncMock()

    with (
        patch(
            "app.services.product_service.get_cached_products",
            get_cache_mock,
        ),
        patch(
            "app.services.product_service.get_all_products",
            get_repository_mock,
        ),
        patch(
            "app.services.product_service.set_cached_products",
            set_cache_mock,
        ),
    ):
        result = await get_products(db=db, redis=redis)

    assert result is cached_products
    get_cache_mock.assert_awaited_once_with(redis)
    get_repository_mock.assert_not_awaited()
    set_cache_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_products_queries_database_and_caches_on_cache_miss() -> None:
    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock(spec=Redis)
    database_products = [
        Product(
            id=1,
            name="Keyboard",
            description="Mechanical keyboard",
            price=Decimal("99.90"),
            stock=10,
        )
    ]
    get_cache_mock = AsyncMock(return_value=None)
    get_repository_mock = AsyncMock(return_value=database_products)
    set_cache_mock = AsyncMock()

    with (
        patch(
            "app.services.product_service.get_cached_products",
            get_cache_mock,
        ),
        patch(
            "app.services.product_service.get_all_products",
            get_repository_mock,
        ),
        patch(
            "app.services.product_service.set_cached_products",
            set_cache_mock,
        ),
    ):
        result = await get_products(db=db, redis=redis)

    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].name == "Keyboard"
    get_cache_mock.assert_awaited_once_with(redis)
    get_repository_mock.assert_awaited_once_with(db)
    set_cache_mock.assert_awaited_once_with(redis, result)


@pytest.mark.asyncio
async def test_create_product_builds_product_and_calls_repository() -> None:
    db = AsyncMock(spec=AsyncSession)
    product_data = ProductCreate(
        name="Keyboard",
        description="Mechanical keyboard",
        price=Decimal("99.90"),
        stock=10,
    )
    saved_product = Product(
        id=1,
        name="Keyboard",
        description="Mechanical keyboard",
        price=Decimal("99.90"),
        stock=10,
    )

    save_mock = AsyncMock(return_value=saved_product)

    with patch("app.services.product_service.save_product", save_mock):
        result = await create_product(db, product_data)

    assert result is saved_product
    save_mock.assert_awaited_once()

    called_db, called_product = save_mock.await_args.args
    assert called_db is db
    assert isinstance(called_product, Product)
    assert called_product.name == "Keyboard"
    assert called_product.price == Decimal("99.90")
    assert called_product.stock == 10


@pytest.mark.asyncio
async def test_update_product_delegates_to_repository() -> None:
    db = AsyncMock(spec=AsyncSession)
    product_data = ProductUpdate(
        name="Updated keyboard",
        description="Updated description",
        price=Decimal("109.90"),
        stock=12,
    )
    updated_product = Product(
        id=1,
        name="Updated keyboard",
        description="Updated description",
        price=Decimal("109.90"),
        stock=12,
    )

    update_mock = AsyncMock(return_value=updated_product)

    with patch(
        "app.services.product_service.update_product_by_id",
        update_mock,
    ):
        result = await update_product(db, product_id=1, product_data=product_data)

    assert result is updated_product
    update_mock.assert_awaited_once_with(
        db=db,
        product_id=1,
        product_data=product_data,
    )


@pytest.mark.asyncio
async def test_delete_product_returns_repository_result() -> None:
    db = AsyncMock(spec=AsyncSession)
    delete_mock = AsyncMock(return_value=True)

    with patch("app.services.product_service.delete_product_by_id", delete_mock):
        result = await delete_product(db, product_id=1)

    assert result is True
    delete_mock.assert_awaited_once_with(db=db, product_id=1)
