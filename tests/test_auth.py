from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.auth_service import EmailAlreadyRegisteredError, register_user


PAYLOAD = {"email": "student@example.com", "password": "learning-fastapi-2026"}


def test_password_hash_verifies_only_correct_password():
    """It verifies a password without storing its plain text."""
    hashed = hash_password(PAYLOAD["password"])
    assert hashed != PAYLOAD["password"]
    assert verify_password(PAYLOAD["password"], hashed)
    assert not verify_password("wrong-password", hashed)


def test_register_returns_public_fields_only(client):
    """It creates a public response without exposing the password hash."""
    # Arrange: return an ORM object that includes a private password hash.
    user = User(id=1, email=PAYLOAD["email"], hashed_password="private-hash",
                is_active=True, created_at=datetime.now(UTC))
    with patch("app.routers.auth.register_user", new=AsyncMock(return_value=user)):
        # Act: send a real HTTP request through the test client.
        response = client.post("/api/auth/register", json=PAYLOAD)
    # Assert: response_model must filter out private fields.
    assert response.status_code == 201
    assert set(response.json()) == {"id", "email", "is_active", "created_at"}
    assert response.json()["email"] == PAYLOAD["email"]


def test_register_duplicate_returns_409(client):
    """It translates the duplicate email error into HTTP 409."""
    with patch("app.routers.auth.register_user", new=AsyncMock(side_effect=EmailAlreadyRegisteredError)):
        response = client.post("/api/auth/register", json=PAYLOAD)
    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already registered"}


@pytest.mark.parametrize("changes", [{"password": "short"}, {"email": "invalid"}, {"is_active": False}])
def test_register_rejects_invalid_input(client, changes):
    """It rejects invalid or forbidden input before calling the service."""
    with patch("app.routers.auth.register_user", new=AsyncMock()) as service:
        response = client.post("/api/auth/register", json=PAYLOAD | changes)
    assert response.status_code == 422
    service.assert_not_awaited()


def test_register_rate_limit_blocks_service(client, redis_mock):
    """It blocks the sixth registration attempt in the active window."""
    redis_mock.eval.return_value = [6, 25]
    with patch("app.routers.auth.register_user", new=AsyncMock()) as service:
        response = client.post("/api/auth/register", json=PAYLOAD)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "25"
    service.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_normalizes_email_and_saves_hash():
    """It saves the normalized email and the hash returned by the worker."""
    db = AsyncMock()
    data = UserCreate(**(PAYLOAD | {"email": "Student@example.com"}))
    # Arrange: isolate database access and the expensive hash operation.
    with (
        patch("app.services.auth_service.get_user_by_email", new=AsyncMock(return_value=None)),
        patch("app.services.auth_service.run_in_threadpool", new=AsyncMock(return_value="encoded-hash")) as worker,
        patch("app.services.auth_service.save_user", new=AsyncMock()) as save,
    ):
        result = await register_user(db, data)
    saved_user = save.await_args.args[1]
    assert saved_user.email == "student@example.com"
    assert saved_user.hashed_password == "encoded-hash"
    worker.assert_awaited_once_with(hash_password, PAYLOAD["password"])
    assert result is save.return_value


@pytest.mark.asyncio
async def test_existing_email_skips_hash_and_save():
    """It rejects an existing email before hashing or saving."""
    with (
        patch("app.services.auth_service.get_user_by_email", new=AsyncMock(return_value=User())),
        patch("app.services.auth_service.run_in_threadpool", new=AsyncMock()) as worker,
        patch("app.services.auth_service.save_user", new=AsyncMock()) as save,
        pytest.raises(EmailAlreadyRegisteredError),
    ):
        await register_user(AsyncMock(), UserCreate(**PAYLOAD))
    worker.assert_not_awaited()
    save.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate", [True, False])
async def test_integrity_error_checks_for_concurrent_registration(duplicate):
    """It distinguishes a concurrent registration from other integrity errors."""
    error = IntegrityError("INSERT", {}, Exception("constraint failure"))
    # Arrange: the first lookup finds nothing; another request may save later.
    lookup = AsyncMock(side_effect=[None, User() if duplicate else None])
    with (
        patch("app.services.auth_service.get_user_by_email", lookup),
        patch("app.services.auth_service.run_in_threadpool", new=AsyncMock(return_value="hash")),
        patch("app.services.auth_service.save_user", new=AsyncMock(side_effect=error)),
        pytest.raises(EmailAlreadyRegisteredError if duplicate else IntegrityError) as caught,
    ):
        await register_user(AsyncMock(), UserCreate(**PAYLOAD))
    assert lookup.await_count == 2
    if not duplicate:
        assert caught.value is error
