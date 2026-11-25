import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import app


ALLOWED_ORIGIN = "https://frontend.example.com"
BLOCKED_ORIGIN = "https://other.example.com"


@pytest.fixture
def cors_client(monkeypatch):
    """It tests the app's CORS configuration with a temporary allowed origin."""
    cors = next(item for item in app.user_middleware if item.cls is CORSMiddleware)
    # Change only the allowed origins; keep the application's other CORS settings.
    monkeypatch.setitem(cors.kwargs, "allow_origins", [ALLOWED_ORIGIN])
    # Rebuild the middleware so the temporary configuration takes effect.
    monkeypatch.setattr(app, "middleware_stack", None)
    with TestClient(app) as client:
        yield client


def test_allowed_origin_can_preflight_authorized_json_request(cors_client):
    """It permits the browser to send a JSON POST with an authorization header."""
    response = cors_client.options("/api/auth/login", headers={
        "Origin": ALLOWED_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    assert "authorization" in response.headers["Access-Control-Allow-Headers"].lower()


def test_blocked_origin_fails_preflight(cors_client):
    """It rejects a preflight from an origin outside the allowlist."""
    response = cors_client.options("/api/auth/login", headers={
        "Origin": BLOCKED_ORIGIN,
        "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 400
    assert "Access-Control-Allow-Origin" not in response.headers


def test_allowed_origin_can_read_retry_after_header(cors_client):
    """It exposes Retry-After without enabling credentialed cross-origin requests."""
    response = cors_client.get("/openapi.json", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    assert "retry-after" in response.headers["Access-Control-Expose-Headers"].lower()
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_blocked_origin_does_not_prevent_simple_request(cors_client):
    """It withholds browser read permission without treating CORS as authentication."""
    response = cors_client.get("/openapi.json", headers={"Origin": BLOCKED_ORIGIN})
    # TestClient is not a browser: it can inspect a response without CORS permission.
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers
