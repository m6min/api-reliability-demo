from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.rate_limit.dependencies import rate_limit
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import (
    EmailAlreadyRegisteredError,
    register_user,
)

router = APIRouter()

@router.post("/register",
            response_model=UserRead,
            status_code=status.HTTP_201_CREATED, dependencies=[
                Depends(rate_limit(namespace="auth:register",limit=5,window_seconds=60))
            ])
async def register(user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    try:
        return await register_user(db=db, user_data=user_data)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Email is already registered") from exc