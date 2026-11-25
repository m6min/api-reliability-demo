from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from app.core.security import create_access_token
from app.core.settings import settings
from app.models.product import Product
from app.models.user import User


@pytest.mark.parametrize("method,path,service_name,success_status", [
    ("POST", "/api/products/", "create_product_service", 201),
    ("PUT", "/api/products/7", "update_product_service", 200),
    ("DELETE", "/api/products/7", "delete_product_service", 204),
])
@pytest.mark.parametrize("identity", ["anonymous", "user", "admin"])
def test_product_write_permissions(client, monkeypatch, method, path, service_name, success_status, identity):
    """It checks every write endpoint with anonymous, regular, and admin users."""
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", SecretStr("test-only-admin-signing-key-at-least-32-chars"))
    user = User(id=3, is_active=True, is_admin=identity == "admin")
    headers = {} if identity == "anonymous" else {"Authorization": f"Bearer {create_access_token(user.id)}"}
    payload = {"name": "Keyboard", "description": "Test product", "price": "99.90", "stock": 10}
    result = True if method == "DELETE" else Product(id=7, **payload)
    # Keep real JWT and admin checks; replace database and product operations.
    with (
        patch("app.api.dependencies.get_user_by_id", new=AsyncMock(return_value=user)),
        patch(f"app.routers.products.{service_name}", new=AsyncMock(return_value=result)) as service,
    ):
        response = client.request(method, path, headers=headers,
                                  **({} if method == "DELETE" else {"json": payload}))
    expected = success_status if identity == "admin" else (401 if identity == "anonymous" else 403)
    assert response.status_code == expected
    if identity == "admin":
        service.assert_awaited_once()
    else:
        service.assert_not_awaited()


def test_registration_cannot_request_admin_privileges(client):
    """It rejects attempts to grant admin privileges through registration."""
    with patch("app.routers.auth.register_user", new=AsyncMock()) as service:
        response = client.post("/api/auth/register", json={
            "email": "student@example.com",
            "password": "learning-fastapi-2026",
            "is_admin": True,
        })
    assert response.status_code == 422
    service.assert_not_awaited()
