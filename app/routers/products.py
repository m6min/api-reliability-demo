from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db
from app.models.product import Product
from app.repositories.product_repository import get_product_by_id
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.product_service import (
    create_product as create_product_service,
)
from app.services.product_service import (
    delete_product as delete_product_service,
)
from app.services.product_service import get_products as get_products_service
from app.services.product_service import (
    update_product as update_product_service,
)

router = APIRouter()

@router.get("/", response_model=list[ProductRead],
            summary="Get all products from database in a list")
async def get_products(db: Annotated[AsyncSession,
                                    Depends(get_db)], redis: Annotated[Redis, Depends(get_redis)]) -> list[ProductRead]:
    return await get_products_service(db=db, redis=redis)

@router.post("/", response_model=ProductRead,
            status_code=status.HTTP_201_CREATED, summary="Create a new product into database")
async def create_product(product_data: ProductCreate,
                        db: Annotated[AsyncSession, Depends(get_db)],
                        redis: Annotated[Redis, Depends(get_redis)]):
    return await create_product_service(db=db, redis=redis, product_data=product_data)

@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> Product:
    product = await get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No matched product for id of {product_id}")
    return product

@router.put("/{product_id}",
            response_model=ProductRead, summary="Update a product with id")
async def update_product(product_id: int, product_data: ProductUpdate,
                        db: Annotated[AsyncSession, Depends(get_db)],  redis: Annotated[Redis, Depends(get_redis)]) -> Product:
    product = await update_product_service(
        db=db,
        product_id=product_id,
        product_data=product_data,
        redis=redis
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No matched product for id of {product_id}",
        )

    return product

@router.delete("/{product_id}",
            status_code=status.HTTP_204_NO_CONTENT, summary="Delete your product with id")
async def delete_product(product_id: int,
                        db: Annotated[AsyncSession, Depends(get_db)],  redis: Annotated[Redis, Depends(get_redis)]) -> None:
    result = await delete_product_service(db=db, product_id=product_id, redis=redis)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No matched product for id of {product_id}")
