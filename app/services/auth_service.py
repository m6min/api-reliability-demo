from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import get_user_by_email, save_user
from app.schemas.user import UserCreate, UserLogin


class EmailAlreadyRegisteredError(Exception):
    pass

async def register_user(db: AsyncSession, user_data: UserCreate) -> User:
    """Registers user with UserCreate schema, hashes password with threadpool
    Raises IntegrityError if fails
    """
    email = str(user_data.email).lower()
    existing_user = await get_user_by_email(db, email)
    if existing_user is not None:
        raise EmailAlreadyRegisteredError()
    hashed_password = await run_in_threadpool(
        hash_password,
        user_data.password.get_secret_value()
    )
    user = User(
        email = email,
        hashed_password = hashed_password
    )
    try:
        return await save_user(db, user)
    except IntegrityError as exc:
        existing_user = await get_user_by_email(db=db, email=email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError() from exc
        raise

class InvalidCredentialsError(Exception):
    pass

async def authenticate_user(
    db: AsyncSession,
    login_data: UserLogin) -> User:
    email = str(login_data.email).lower()
    user = await get_user_by_email(db, email)

    stored_hash = (
        user.hashed_password
        if user is not None
        else DUMMY_PASSWORD_HASH
    )

    password_matches = await run_in_threadpool(
        verify_password,
        login_data.password.get_secret_value(),
        stored_hash,
    )

    if user is None or not password_matches:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise InvalidCredentialsError()

    return user
