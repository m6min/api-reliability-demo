from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.settings import settings
from app.models.product import Product


@pytest.fixture(params=[RedisConnectionError, RedisTimeoutError])
def redis_failure(request):
    """It runs each dependent test for a connection error and a timeout."""
    return request.param("Redis is unavailable")


@pytest.fixture
def product():
    """It provides an unsaved product as the simulated database result."""
    return Product(id=7, name="Keyboard", description="Mechanical keyboard",
                   price=Decimal("99.90"), stock=10)


def test_product_list_survives_redis_outage(client, redis_mock, redis_failure, product, monkeypatch, caplog):
    """It returns database products when both rate limiting and caching fail."""
    monkeypatch.setattr(settings, "PRODUCTS_CACHE_ENABLED", True)
    # Arrange: fail Redis operations, but keep real service and cache functions.
    redis_mock.eval.side_effect = redis_failure
    redis_mock.get.side_effect = redis_failure
    redis_mock.set.side_effect = redis_failure
    with patch("app.services.product_service.get_all_products", new=AsyncMock(return_value=[product])) as lookup:
        response = client.get("/api/products/")
    assert response.status_code == 200
    assert response.json()[0]["id"] == product.id
    lookup.assert_awaited_once()
    redis_mock.eval.assert_awaited_once()
    redis_mock.get.assert_awaited_once()
    redis_mock.set.assert_awaited_once()
    assert "Rate limiter unavailable" in caplog.text
    assert "cache=ERROR operation=GET" in caplog.text
    assert "fallback=postgresql" in caplog.text
    assert "Product cache write failed" in caplog.text


@pytest.mark.parametrize("endpoint,service_name", [
    ("login", "authenticate_user"),
    ("register", "register_user"),
])
def test_auth_stops_when_rate_limiter_is_unavailable(client, redis_mock, redis_failure, endpoint, service_name):
    """It returns 503 before running authentication or registration."""
    redis_mock.eval.side_effect = redis_failure
    with patch(f"app.routers.auth.{service_name}", new=AsyncMock()) as service:
        response = client.post(f"/api/auth/{endpoint}", json={
            "email": "student@example.com", "password": "learning-fastapi-2026",
        })
    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}
    assert response.headers["Retry-After"] == "5"
    service.assert_not_awaited()


@pytest.mark.parametrize("method,path,repository_name,expected_status", [
    ("POST", "/api/products/", "save_product", 201),
    ("PUT", "/api/products/7", "update_product_by_id", 200),
    ("DELETE", "/api/products/7", "delete_product_by_id", 204),
])
def test_cache_invalidation_failure_preserves_success(client, redis_mock, redis_failure, product, caplog,
                                                     method, path, repository_name, expected_status):
    """It preserves a successful database result when cache deletion fails."""
    # Arrange: the repository succeeds; only the later Redis deletion fails.
    redis_mock.delete.side_effect = redis_failure
    result = True if method == "DELETE" else product
    payload = {"name": "Keyboard", "description": "Mechanical keyboard", "price": "99.90", "stock": 10}
    with patch(f"app.services.product_service.{repository_name}", new=AsyncMock(return_value=result)) as repository:
        response = client.request(method, path, **({} if method == "DELETE" else {"json": payload}))
    assert response.status_code == expected_status
    repository.assert_awaited_once()
    redis_mock.delete.assert_awaited_once()
    assert "Product cache invalidation failed" in caplog.text
    if method == "DELETE":
        assert response.content == b""
    else:
        assert response.json()["id"] == product.id


def test_rate_limiter_does_not_hide_programming_errors(client, redis_mock):
    """It propagates unrelated errors instead of bypassing the limiter."""
    redis_mock.eval.side_effect = ValueError("Unexpected counter format")
    with (
        patch("app.routers.products.get_products_service", new=AsyncMock()) as service,
        pytest.raises(ValueError, match="Unexpected counter format"),
    ):
        client.get("/api/products/")
    service.assert_not_awaited()
