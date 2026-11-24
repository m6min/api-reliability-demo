from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_email(db: AsyncSession,
                            email:str) -> User | None:
    try:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except SQLAlchemyError:
        await db.rollback()
        raise

async def save_user(db: AsyncSession,
                    user: User) -> User:
    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except SQLAlchemyError:
        await db.rollback()
        raise

async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    try:
        return await db.get(User, user_id)
    except SQLAlchemyError:
        await db.rollback()
        raise
