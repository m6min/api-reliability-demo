import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.api import api_router
from app.core.redis import create_redis_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    redis_client = create_redis_client()
    app.state.redis = redis_client

    try:
        yield
    finally:
        await redis_client.aclose()


app = FastAPI(
    title="API Reliability Demo",
    version="1.0",
    lifespan=lifespan
)

@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception(
        "Database error on %s %s",
        request.method,
        request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal database error"},
    )

app.include_router(api_router, prefix="/api")
