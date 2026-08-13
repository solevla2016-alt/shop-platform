from types import SimpleNamespace

import pytest

from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import RateLimiter
from app.core.security import create_access_token


async def test_health(client):
    """Health endpoint should be available."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unauthorized_products(client):
    """Protected endpoint should return standardized 401."""
    response = await client.get("/api/v1/products")

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Unauthorized"}


async def test_register_login_me_refresh_logout(client):
    """Full authentication flow should work."""
    payload = {
        "full_name": "Иван Иванов",
        "email": "user@example.com",
        "phone": "+79991234567",
        "password": "Password$",
        "password_confirm": "Password$",
    }

    register_response = await client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": "Password$"},
    )
    assert login_response.status_code == 200

    tokens = login_response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200

    new_tokens = refresh_response.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout_response.status_code == 204

    refresh_after_logout = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert refresh_after_logout.status_code == 401


async def test_register_validation(client):
    """Registration validation should reject invalid data."""
    payload = {
        "full_name": "Иван Иванов",
        "email": "user@example.com",
        "phone": "89991234567",
        "password": "Password$",
        "password_confirm": "Password$",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422

    payload["phone"] = "+79991234567"
    payload["password"] = "password$"
    payload["password_confirm"] = "password$"

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


async def test_products_crud_pagination_and_soft_delete(
    client,
    create_user,
    create_product,
    auth_headers,
):
    """Products should support pagination, filters and soft delete."""
    admin = await create_user(
        email="admin@example.com",
        phone="+79990000000",
        is_admin=True,
    )
    user = await create_user(
        email="user@example.com",
        phone="+79990000001",
    )

    admin_headers = auth_headers(create_access_token(admin))
    user_headers = auth_headers(create_access_token(user))

    create_response = await client.post(
        "/api/v1/products",
        headers=admin_headers,
        json={"name": "Laptop", "price": 1000, "is_active": True},
    )
    assert create_response.status_code == 201

    await create_product(name="Mouse", price=100)
    await create_product(name="Keyboard", price=200)

    list_response = await client.get(
        "/api/v1/products?page=1&size=2&sort_by=price&sort_order=asc",
        headers=user_headers,
    )

    assert list_response.status_code == 200

    data = list_response.json()

    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["pages"] == 2
    assert data["items"][0]["name"] == "Mouse"

    filtered_response = await client.get(
        "/api/v1/products?name=key",
        headers=user_headers,
    )
    assert filtered_response.json()["total"] == 1

    product_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/products/{product_id}",
        headers=admin_headers,
        json={"price": 900},
    )
    assert update_response.status_code == 200
    assert update_response.json()["price"] == 900

    delete_response = await client.delete(
        f"/api/v1/products/{product_id}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False

    user_list_response = await client.get("/api/v1/products", headers=user_headers)
    assert user_list_response.json()["total"] == 2

    admin_list_response = await client.get(
        "/api/v1/products?include_inactive=true&size=100",
        headers=admin_headers,
    )
    assert admin_list_response.json()["total"] == 3


async def test_cart_and_order_checkout(client, create_user, create_product, auth_headers):
    """Cart and checkout flow should work."""
    user = await create_user()
    product_1 = await create_product(name="Phone", price=100)
    product_2 = await create_product(name="Case", price=50)

    headers = auth_headers(create_access_token(user))

    add_response = await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "items": [
                {"product_id": product_1.id, "quantity": 1},
                {"product_id": product_2.id, "quantity": 2},
            ]
        },
    )

    assert add_response.status_code == 200
    assert add_response.json()["total"] == 200

    total_response = await client.get("/api/v1/cart/total", headers=headers)
    assert total_response.json()["total"] == 200

    checkout_response = await client.post("/api/v1/orders/checkout", headers=headers)
    assert checkout_response.status_code == 201

    order = checkout_response.json()
    assert order["total_amount"] == 200
    assert len(order["items"]) == 2

    cart_after_checkout = await client.get("/api/v1/cart", headers=headers)
    assert cart_after_checkout.json()["total"] == 0

    orders_response = await client.get("/api/v1/orders", headers=headers)
    assert len(orders_response.json()) == 1


async def test_rate_limiter_blocks_after_limit():
    """Rate limiter should raise TooManyRequestsError after limit."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)

    request = SimpleNamespace(
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
    )

    await limiter(request)
    await limiter(request)

    with pytest.raises(TooManyRequestsError):
        await limiter(request)