from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.models.product import Product


def make_product() -> Product:
    return Product(
        id=1,
        name="Keyboard",
        description="Mechanical keyboard",
        price=Decimal("99.90"),
        stock=10,
    )


def test_get_products_returns_product_list(client: TestClient) -> None:
    products = [make_product()]

    with patch(
        "app.routers.products.get_products_service",
        new=AsyncMock(return_value=products),
    ):
        response = client.get("/api/products/")

    assert response.status_code == 200
    assert response.json()[0]["id"] == 1
    assert response.json()[0]["name"] == "Keyboard"


def test_get_product_returns_404_when_product_does_not_exist(
    client: TestClient,
) -> None:
    with patch(
        "app.routers.products.get_product_by_id",
        new=AsyncMock(return_value=None),
    ):
        response = client.get("/api/products/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "No matched product for id of 999"


def test_get_product_returns_product(client: TestClient) -> None:
    with patch(
        "app.routers.products.get_product_by_id",
        new=AsyncMock(return_value=make_product()),
    ):
        response = client.get("/api/products/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["name"] == "Keyboard"


def test_create_product_returns_201(client: TestClient) -> None:
    with patch(
        "app.routers.products.create_product_service",
        new=AsyncMock(return_value=make_product()),
    ):
        response = client.post(
            "/api/products/",
            json={
                "name": "Keyboard",
                "description": "Mechanical keyboard",
                "price": "99.90",
                "stock": 10,
            },
        )

    assert response.status_code == 201
    assert response.json()["id"] == 1
    assert response.json()["name"] == "Keyboard"


def test_create_product_returns_422_for_invalid_price(client: TestClient) -> None:
    create_mock = AsyncMock()

    with patch(
        "app.routers.products.create_product_service",
        new=create_mock,
    ):
        response = client.post(
            "/api/products/",
            json={
                "name": "Keyboard",
                "description": "Mechanical keyboard",
                "price": "not-a-number",
                "stock": 10,
            },
        )

    assert response.status_code == 422
    create_mock.assert_not_awaited()


def test_update_product_returns_200(client: TestClient) -> None:
    with patch(
        "app.routers.products.update_product_service",
        new=AsyncMock(return_value=make_product()),
    ):
        response = client.put(
            "/api/products/1",
            json={
                "name": "Updated keyboard",
                "description": "Updated description",
                "price": "109.90",
                "stock": 12,
            },
        )

    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_update_product_returns_404_when_product_does_not_exist(
    client: TestClient,
) -> None:
    with patch(
        "app.routers.products.update_product_service",
        new=AsyncMock(return_value=None),
    ):
        response = client.put(
            "/api/products/999",
            json={
                "name": "Updated keyboard",
                "description": "Updated description",
                "price": "109.90",
                "stock": 12,
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "No matched product for id of 999"


def test_delete_product_returns_204(client: TestClient) -> None:
    with patch(
        "app.routers.products.delete_product_service",
        new=AsyncMock(return_value=True),
    ):
        response = client.delete("/api/products/1")

    assert response.status_code == 204
    assert response.content == b""


def test_delete_product_returns_404_when_product_does_not_exist(
    client: TestClient,
) -> None:
    with patch(
        "app.routers.products.delete_product_service",
        new=AsyncMock(return_value=False),
    ):
        response = client.delete("/api/products/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "No matched product for id of 999"
