import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_login_me_refresh_logout(client: AsyncClient):
    """Test full auth flow: register -> login -> me -> refresh -> logout."""
    import time
    timestamp = int(time.time() * 1000)

    # Register
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": f"newuser_{timestamp}@example.com",
            "phone": f"+7999{timestamp % 10000000:07d}",
            "password": "Password123!",
            "password_confirm": "Password123!",
        },
    )
    assert response.status_code == 201

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": f"newuser_{timestamp}@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Me
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    user = response.json()
    assert user["email"] == f"newuser_{timestamp}@example.com"
    assert user["full_name"] == "Test User"

    # Refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    new_tokens = response.json()
    assert "access_token" in new_tokens

    # Logout (returns 204 No Content)
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_products_crud_pagination_and_soft_delete(
        client: AsyncClient, admin_headers: dict
):
    """Test products CRUD operations with pagination."""
    import time
    timestamp = int(time.time() * 1000)

    # Create products
    for i in range(15):
        response = await client.post(
            "/api/v1/products",
            json={
                "name": f"Product {timestamp}_{i}",
                "price": 100 * (i + 1),
                "is_active": True,
            },
            headers=admin_headers,
        )
        assert response.status_code == 201

    # List with pagination
    response = await client.get(
        "/api/v1/products?page=1&size=10",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["size"] == 10

    # Get product by id
    product_id = data["items"][0]["id"]
    response = await client.get(
        f"/api/v1/products/{product_id}",
        headers=admin_headers,
    )
    assert response.status_code == 200

    # Update product
    response = await client.patch(
        f"/api/v1/products/{product_id}",
        json={"name": "Updated Product", "price": 9999},
        headers=admin_headers,
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Updated Product"
    assert updated["price"] == 9999

    # Soft delete (deactivate)
    response = await client.delete(
        f"/api/v1/products/{product_id}",
        headers=admin_headers,
    )
    assert response.status_code == 200

    # Verify product is inactive
    response = await client.get(
        f"/api/v1/products/{product_id}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_cart_and_order_checkout(
        client: AsyncClient, auth_headers: dict, admin_headers: dict
):
    """Test cart operations and order checkout."""
    import time
    timestamp = int(time.time() * 1000)

    # Create products as admin
    response = await client.post(
        "/api/v1/products",
        json={
            "name": f"Cart Product 1 {timestamp}",
            "price": 1000,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    product1_id = response.json()["id"]

    response = await client.post(
        "/api/v1/products",
        json={
            "name": f"Cart Product 2 {timestamp}",
            "price": 2000,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    product2_id = response.json()["id"]

    # Add to cart
    response = await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {"product_id": product1_id, "quantity": 2},
                {"product_id": product2_id, "quantity": 1},
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200

    # Get cart
    response = await client.get("/api/v1/cart", headers=auth_headers)
    assert response.status_code == 200
    cart = response.json()
    assert len(cart["items"]) == 2
    assert cart["total"] == 4000  # 2*1000 + 1*2000

    # Checkout
    response = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
    )
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "pending_payment"
    assert order["total_amount"] == 4000
    assert len(order["items"]) == 2

    # Pay for order
    response = await client.post(
        f"/api/v1/orders/{order['id']}/pay",
        json={"payment_method": "card"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    paid_order = response.json()
    assert paid_order["status"] == "paid"
    assert paid_order["payment_method"] == "card"

    # Cart should be empty after checkout
    response = await client.get("/api/v1/cart", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0

    # Get orders
    response = await client.get("/api/v1/orders", headers=auth_headers)
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) >= 1
