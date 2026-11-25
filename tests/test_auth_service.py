from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import DUMMY_PASSWORD_HASH, hash_password
from app.models.user import User
from app.schemas.user import UserLogin
from app.services.auth_service import InvalidCredentialsError, authenticate_user


@pytest.fixture(scope="module")
def password_hash():
    """It computes one real password hash for the authentication scenarios."""
    return hash_password("learning-fastapi-2026")


@pytest.mark.asyncio
async def test_authentication_returns_active_user(password_hash):
    """It normalizes the email and verifies the real password hash."""
    user = User(id=1, email="student@example.com", hashed_password=password_hash, is_active=True)
    db = AsyncMock()
    data = UserLogin(email="Student@example.com", password="learning-fastapi-2026")
    # Replace only the lookup; real password verification runs in the thread pool.
    with patch("app.services.auth_service.get_user_by_email", new=AsyncMock(return_value=user)) as lookup:
        result = await authenticate_user(db, data)
    assert result is user
    lookup.assert_awaited_once_with(db, "student@example.com")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["wrong_password", "inactive_user", "missing_user"])
async def test_authentication_rejects_invalid_credentials(password_hash, case):
    """It rejects wrong passwords, inactive accounts, and unknown emails."""
    user = User(id=1, hashed_password=password_hash, is_active=case != "inactive_user")
    if case == "missing_user":
        user = None
    password = "wrong-password" if case == "wrong_password" else "learning-fastapi-2026"
    with (
        patch("app.services.auth_service.get_user_by_email", new=AsyncMock(return_value=user)),
        pytest.raises(InvalidCredentialsError),
    ):
        await authenticate_user(AsyncMock(), UserLogin(email="student@example.com", password=password))


@pytest.mark.asyncio
async def test_unknown_user_still_runs_password_verification():
    """It verifies against the dummy hash even when the account is missing."""
    from app.services.auth_service import verify_password

    with (
        patch("app.services.auth_service.get_user_by_email", new=AsyncMock(return_value=None)),
        patch("app.services.auth_service.run_in_threadpool", new=AsyncMock(return_value=False)) as worker,
        pytest.raises(InvalidCredentialsError),
    ):
        await authenticate_user(AsyncMock(), UserLogin(email="missing@example.com", password="some-password"))
    worker.assert_awaited_once_with(verify_password, "some-password", DUMMY_PASSWORD_HASH)
