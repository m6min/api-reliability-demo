from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from pydantic import SecretStr

from app.core.security import JWT_ALGORITHM, create_access_token
from app.core.settings import settings
from app.models.user import User
from app.services.auth_service import InvalidCredentialsError


@pytest.fixture(autouse=True)
def jwt_test_key(monkeypatch):
    """It uses a test-only signing key without changing the environment file."""
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", SecretStr("test-only-signing-key-for-auth-tests-2026"))


@pytest.fixture
def active_user():
    """It builds an unsaved user for tests that isolate database access."""
    return User(
        id=7,
        email="student@example.com",
        hashed_password="private-hash",
        is_active=True,
        created_at=datetime.now(UTC),
    )


def test_login_token_can_access_current_user(client, active_user):
    """It uses the token returned by login to access the protected endpoint."""
    # Arrange: replace database-dependent authentication, but keep real JWT logic.
    with (
        patch("app.routers.auth.authenticate_user", new=AsyncMock(return_value=active_user)),
        patch("app.api.dependencies.get_user_by_id", new=AsyncMock(return_value=active_user)) as lookup,
    ):
        login = client.post("/api/auth/login", json={
            "email": active_user.email,
            "password": "learning-fastapi-2026",
        })
        assert login.status_code == 200
        assert login.json()["token_type"] == "bearer"

        # Act: send the issued token through the real HTTPBearer dependency.
        token = login.json()["access_token"]
        response = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})

    # Assert: the token selects the correct user and private fields stay hidden.
    assert response.status_code == 200
    assert response.json()["id"] == active_user.id
    assert response.json()["email"] == active_user.email
    assert set(response.json()) == {"id", "email", "is_active", "created_at"}
    lookup.assert_awaited_once()
    assert lookup.await_args.kwargs["user_id"] == active_user.id


@pytest.mark.parametrize("authorization", [None, "Basic abc123", "Bearer"])
def test_missing_bearer_credentials_skip_database(client, authorization):
    """It rejects missing bearer credentials before looking up a user."""
    headers = {} if authorization is None else {"Authorization": authorization}
    with patch("app.api.dependencies.get_user_by_id", new=AsyncMock()) as lookup:
        response = client.get("/api/users/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    lookup.assert_not_awaited()


@pytest.mark.parametrize("case", [
    "malformed", "expired", "wrong_signature", "missing_exp", "invalid_subject",
])
def test_invalid_token_skips_database(client, case):
    """It rejects invalid tokens using real signature and claim validation."""
    now = datetime.now(UTC)
    payload = {"sub": "7", "iat": now - timedelta(minutes=2), "exp": now + timedelta(minutes=5)}
    key = settings.JWT_SECRET_KEY.get_secret_value()
    if case == "expired":
        payload["exp"] = now - timedelta(minutes=1)
    elif case == "wrong_signature":
        key = "different-test-signing-key-at-least-32-characters"
    elif case == "missing_exp":
        del payload["exp"]
    elif case == "invalid_subject":
        payload["sub"] = "not-a-user-id"

    # Arrange: sign the test payload, or use a deliberately malformed token.
    token = "not-a-jwt" if case == "malformed" else jwt.encode(payload, key, algorithm=JWT_ALGORITHM)
    with patch("app.api.dependencies.get_user_by_id", new=AsyncMock()) as lookup:
        response = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    lookup.assert_not_awaited()


@pytest.mark.parametrize("user_state", ["missing", "inactive"])
def test_valid_token_requires_existing_active_user(client, active_user, user_state):
    """It rejects a valid token when its user was deleted or deactivated."""
    token = create_access_token(active_user.id)
    active_user.is_active = False
    user = None if user_state == "missing" else active_user
    with patch("app.api.dependencies.get_user_by_id", new=AsyncMock(return_value=user)) as lookup:
        response = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    lookup.assert_awaited_once()


def test_login_invalid_credentials_returns_401(client):
    """It returns a generic login error without issuing a token."""
    with patch("app.routers.auth.authenticate_user", new=AsyncMock(side_effect=InvalidCredentialsError)):
        response = client.post("/api/auth/login", json={
            "email": "student@example.com", "password": "wrong-password",
        })
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_login_rate_limit_skips_authentication(client, redis_mock):
    """It blocks excessive login attempts before checking the password."""
    redis_mock.eval.return_value = [6, 25]
    with patch("app.routers.auth.authenticate_user", new=AsyncMock()) as authenticate:
        response = client.post("/api/auth/login", json={
            "email": "student@example.com", "password": "learning-fastapi-2026",
        })
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "25"
    authenticate.assert_not_awaited()
