from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.rate_limit.dependencies import rate_limit
from app.rate_limit.limiter import RATE_LIMIT_SCRIPT, increment_rate_limit


def make_request(client_ip: str = "192.0.2.1") -> Request:
    return Request(
        {
            "type": "http",
            "client": (client_ip, 12345),
            "headers": [],
        }
    )


@pytest.mark.asyncio
async def test_increment_rate_limit_executes_atomic_script() -> None:
    """It executes the rate limit script and returns its count and TTL."""
    redis = AsyncMock()
    redis.eval = AsyncMock(return_value=[4, 42])

    result = await increment_rate_limit(
        redis=redis,
        key="rate_limit:products:list:192.0.2.1",
        window_seconds=60,
    )

    assert result == (4, 42)
    redis.eval.assert_awaited_once_with(
        RATE_LIMIT_SCRIPT,
        1,
        "rate_limit:products:list:192.0.2.1",
        60,
    )


@pytest.mark.asyncio
async def test_rate_limit_allows_request_at_limit() -> None:
    """It allows the request when the counter equals the limit."""
    redis = AsyncMock()
    request = make_request()
    dependency = rate_limit(
        namespace="products:list",
        limit=10,
        window_seconds=60,
    )
    increment_mock = AsyncMock(return_value=(10, 25))

    with patch(
        "app.rate_limit.dependencies.increment_rate_limit",
        increment_mock,
    ):
        result = await dependency(request=request, redis=redis)

    assert result is None
    increment_mock.assert_awaited_once_with(
        redis=redis,
        key="rate_limit:products:list:192.0.2.1",
        window_seconds=60,
    )


@pytest.mark.asyncio
async def test_rate_limit_rejects_request_over_limit() -> None:
    """It rejects the request after the configured limit is exceeded."""
    redis = AsyncMock()
    request = make_request()
    dependency = rate_limit(
        namespace="products:list",
        limit=10,
        window_seconds=60,
    )

    with (
        patch(
            "app.rate_limit.dependencies.increment_rate_limit",
            new=AsyncMock(return_value=(11, 25)),
        ),
        pytest.raises(HTTPException) as exception,
    ):
        await dependency(request=request, redis=redis)

    assert exception.value.status_code == 429
    assert exception.value.headers == {"Retry-After": "25"}


def test_get_products_returns_429_before_service_runs(
    client: TestClient,
) -> None:
    """It blocks the product endpoint before its service is called."""
    service_mock = AsyncMock()

    with (
        patch(
            "app.rate_limit.dependencies.increment_rate_limit",
            new=AsyncMock(return_value=(11, 25)),
        ),
        patch(
            "app.routers.products.get_products_service",
            service_mock,
        ),
    ):
        response = client.get("/api/products/")

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
    assert response.headers["Retry-After"] == "25"
    service_mock.assert_not_awaited()
