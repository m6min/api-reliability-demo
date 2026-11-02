from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.product_cache import (
    get_cached_products,
    invalidate_products_cache,
    set_cached_products,
)
from app.models.product import Product
from app.repositories.product_repository import (
    delete_product_by_id,
    get_all_products,
    save_product,
    update_product_by_id,
)
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate


async def get_products(db: AsyncSession, redis: Redis) -> list[ProductRead]:
    cached_products = await get_cached_products(redis)

    if cached_products is not None:
        return cached_products

    products = await get_all_products(db)
    product_response = [
        ProductRead.model_validate(product) for product in products
    ]
    await set_cached_products(redis, product_response)

    return product_response


async def create_product(db: AsyncSession, redis: Redis , product_data: ProductCreate) -> Product:
    """Create a 'Product' object on database"""
    product = Product(**product_data.model_dump())
    saved_product = await save_product(db, product)
    await invalidate_products_cache(redis)
    return saved_product

async def update_product(db: AsyncSession, product_id: int, product_data: ProductUpdate, redis: Redis) -> Product | None:
    updated_product = await update_product_by_id(
        db=db,
        product_id=product_id,
        product_data=product_data,
    )
    if updated_product is not None:
        await invalidate_products_cache(redis)
    return updated_product

async def delete_product(db: AsyncSession, product_id: int, redis: Redis) -> bool:
    deleted = await delete_product_by_id(
        db=db,
        product_id=product_id
    )
    if deleted:
        await invalidate_products_cache(redis)
    return deleted

