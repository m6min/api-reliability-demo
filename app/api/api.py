from fastapi import APIRouter

from app.routers import auth, products

api_router = APIRouter()

api_router.include_router(products.router, prefix="/products", tags=["Product Actions"])

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
