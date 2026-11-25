import logging
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.parametrize("path,status_code", [
    ("/openapi.json", 200),
    ("/api/users/me", 401),
])
def test_request_log_records_status_and_duration(client, caplog, path, status_code):
    """It records both successful and rejected requests with elapsed time."""
    caplog.set_level(logging.INFO, logger="app.main")
    # Control the clock so the test does not depend on computer speed.
    with patch("app.main.perf_counter", side_effect=[10.0, 10.025]):
        response = client.get(path)
    assert response.status_code == status_code
    messages = [record.getMessage() for record in caplog.records if record.name == "app.main"]
    assert messages == [f"method=GET path={path} status={status_code} duration_ms=25.00"]


def test_request_log_excludes_credentials_and_query(client, caplog):
    """It omits the request body, authorization header, and query parameters."""
    caplog.set_level(logging.INFO, logger="app.main")
    response = client.post(
        "/api/auth/login?debug=private-query-value",
        headers={"Authorization": "Bearer private-token-value"},
        json={"email": "invalid-email", "password": "private-password-value"},
    )
    assert response.status_code == 422
    # Inspect our logger, not unrelated libraries that may log request URLs.
    messages = [record.getMessage() for record in caplog.records if record.name == "app.main"]
    assert len(messages) == 1
    assert "method=POST path=/api/auth/login status=422" in messages[0]
    for secret in ("private-query-value", "private-token-value", "private-password-value"):
        assert secret not in messages[0]


def test_unhandled_error_is_logged_and_reraised(client, caplog):
    """It logs an unexpected failure without hiding the original exception."""
    error = RuntimeError("Simulated service failure")
    with (
        patch("app.routers.products.get_products_service", new=AsyncMock(side_effect=error)),
        patch("app.main.perf_counter", side_effect=[20.0, 20.05]),
        pytest.raises(RuntimeError) as caught,
    ):
        client.get("/api/products/")
    assert caught.value is error
    records = [record for record in caplog.records if record.name == "app.main"]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].getMessage() == "method=GET path=/api/products/ status=500 duration_ms=50.00"
