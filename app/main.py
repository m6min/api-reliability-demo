import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.api import api_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Test API", version="1.0")

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
