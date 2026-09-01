import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_invalid_login_and_phone_login(
    client: AsyncClient,
    regular_user,
):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": regular_user.email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": regular_user.phone,
            "password": "Password123!",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_invalid_access_token_and_missing_user(
    client: AsyncClient,
):
    response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": "Bearer not-a-token"
        },
    )

    assert response.status_code == 401

    from app.core.security import create_access_token
    from app.models.user import User

    fake_user = User(
        id=999999,
        is_admin=False,
    )

    token = create_access_token(fake_user)

    response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_route_forbidden_for_regular_user(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Forbidden",
            "price": 100,
            "sku": "FORBIDDEN-SKU",
            "category_id": 1,
        },
        headers=auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_refresh_token_reuse_and_logout_invalid_token(
    client: AsyncClient,
    regular_user,
):
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": regular_user.email,
            "password": "Password123!",
        },
    )

    assert login.status_code == 200

    old_refresh = login.json()["refresh_token"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": old_refresh
        },
    )

    assert refreshed.status_code == 200

    response = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": old_refresh
        },
    )

    assert response.status_code == 401

    response = await client.post(
        "/api/v1/auth/logout",
        json={
            "refresh_token": "x" * 20
        },
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_password_reset_unknown_email_and_same_password(
    client: AsyncClient,
    regular_user,
    monkeypatch,
):
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={
            "email": "missing@example.com"
        },
    )

    assert response.status_code == 200

    sent = {}

    async def fake_send(recipient, token):
        sent["token"] = token

    monkeypatch.setattr(
        "app.api.v1.auth.send_password_reset_email",
        fake_send,
    )

    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={
            "email": regular_user.email
        },
    )

    assert response.status_code == 200
    assert "token" in sent

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": sent["token"],
            "new_password": "Password123!",
        },
    )

    assert response.status_code == 400

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "x" * 20,
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_categories_list_duplicate_not_found_and_delete_with_products(
    client: AsyncClient,
    admin_headers: dict,
    test_product,
):
    response = await client.get(
        "/api/v1/categories"
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)

    response = await client.post(
        "/api/v1/categories",
        json={
            "name": "Unique Category",
            "slug": "unique-category",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201

    created_id = response.json()["id"]

    response = await client.get(
        f"/api/v1/categories/{created_id}",
    )

    assert response.status_code == 200
    assert response.json()["slug"] == "unique-category"

    response = await client.get(
        "/api/v1/categories/999999",
    )

    assert response.status_code == 404

    response = await client.post(
        "/api/v1/categories",
        json={
            "name": "Unique Category",
            "slug": "another-category",
        },
        headers=admin_headers,
    )

    assert response.status_code == 409

    response = await client.patch(
        "/api/v1/categories/999999",
        json={
            "name": "Missing"
        },
        headers=admin_headers,
    )

    assert response.status_code == 404

    response = await client.delete(
        "/api/v1/categories/1",
        headers=admin_headers,
    )

    assert response.status_code == 400

    response = await client.delete(
        "/api/v1/categories/999999",
        headers=admin_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_products_filters_sorting_inactive_and_conflicts(
    client: AsyncClient,
    admin_headers: dict,
    auth_headers: dict,
    test_product,
):
    import time

    # Сохраняем значения до запросов, которые могут вызвать rollback().
    # После rollback() SQLAlchemy может инвалидировать состояние ORM-объектов.
    test_product_id = test_product.id
    test_product_sku = test_product.sku

    timestamp = time.time_ns()

    response = await client.post(
        "/api/v1/products",
        json={
            "name": "ZZZ Product",
            "price": 500,
            "is_active": False,
            "sku": f"INACTIVE-{timestamp}",
            "category_id": 1,
        },
        headers=admin_headers,
    )

    assert response.status_code == 201

    inactive_id = response.json()["id"]

    response = await client.get(
        "/api/v1/products"
        "?include_inactive=true"
        "&sort_by=price"
        "&sort_order=asc",
        headers=admin_headers,
    )

    assert response.status_code == 200

    assert any(
        item["id"] == inactive_id
        for item in response.json()["items"]
    )

    response = await client.get(
        "/api/v1/products"
        "?include_inactive=true"
        "&name=ZZZ",
        headers=auth_headers,
    )

    assert response.status_code == 200

    assert all(
        item["is_active"]
        for item in response.json()["items"]
    )

    response = await client.get(
        "/api/v1/products"
        "?min_price=500"
        "&max_price=1500",
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.get(
        f"/api/v1/products/{inactive_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404

    response = await client.get(
        f"/api/v1/products/{inactive_id}",
        headers=admin_headers,
    )

    assert response.status_code == 200

    duplicate = await client.post(
        "/api/v1/products",
        json={
            "name": "Duplicate SKU",
            "price": 100,
            "sku": test_product_sku,
            "category_id": 1,
        },
        headers=admin_headers,
    )

    assert duplicate.status_code == 409

    response = await client.put(
        f"/api/v1/products/{test_product_id}",
        json={
            "description": "Full update",
            "size": "M",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["size"] == "M"

    response = await client.delete(
        "/api/v1/products/999999",
        headers=admin_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cart_empty_and_unavailable_product(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.get(
        "/api/v1/cart",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
    }

    response = await client.get(
        "/api/v1/cart/total",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0

    response = await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {
                    "product_id": 999999,
                    "quantity": 1,
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 400

    response = await client.delete(
        "/api/v1/cart/items/999999",
        headers=auth_headers,
    )

    assert response.status_code == 404

    response = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_order_access_and_state_errors(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_product,
):
    await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {
                    "product_id": test_product.id,
                    "quantity": 1,
                }
            ]
        },
        headers=auth_headers,
    )

    order = (
        await client.post(
            "/api/v1/orders/checkout",
            headers=auth_headers,
        )
    ).json()

    order_id = order["id"]

    response = await client.get(
        "/api/v1/orders/999999",
        headers=auth_headers,
    )

    assert response.status_code == 404

    response = await client.post(
        f"/api/v1/orders/{order_id}/pay",
        json={
            "payment_method": "card"
        },
        headers=admin_headers,
    )

    assert response.status_code == 200

    response = await client.post(
        f"/api/v1/orders/{order_id}/pay",
        json={
            "payment_method": "card"
        },
        headers=auth_headers,
    )

    assert response.status_code == 400

    response = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=auth_headers,
    )

    assert response.status_code == 400

    response = await client.patch(
        "/api/v1/orders/admin/999999/status",
        json={
            "status": "paid"
        },
        headers=admin_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_and_reset_password_page(
    client: AsyncClient,
):
    response = await client.get(
        "/health"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    response = await client.get(
        "/reset-password"
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_optional_auth_ignores_invalid_token_and_forwarded_ip(
    client: AsyncClient,
):
    response = await client.get(
        "/api/v1/products",
        headers={
            "Authorization": "Bearer invalid-token",
            "X-Forwarded-For": "203.0.113.10, 10.0.0.1",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_access_token_payload_without_sub_is_rejected(
    client: AsyncClient,
):
    import jwt

    from app.core.config import settings

    token = jwt.encode(
        {"type": "access"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_order_permissions(
    client: AsyncClient,
    auth_headers: dict,
    second_user_headers: dict,
    test_product,
):
    await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {
                    "product_id": test_product.id,
                    "quantity": 1,
                }
            ]
        },
        headers=auth_headers,
    )

    order = (
        await client.post(
            "/api/v1/orders/checkout",
            headers=auth_headers,
        )
    ).json()

    order_id = order["id"]

    response = await client.get(
        f"/api/v1/orders/{order_id}",
        headers=second_user_headers,
    )

    assert response.status_code == 404

    response = await client.post(
        f"/api/v1/orders/{order_id}/pay",
        json={
            "payment_method": "card"
        },
        headers=second_user_headers,
    )

    assert response.status_code == 404

    response = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=second_user_headers,
    )

    assert response.status_code == 404

    response = await client.get(
        "/api/v1/orders/admin/all",
        headers=second_user_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_security_helpers(
    client: AsyncClient,
    regular_user,
):
    from app.core.security import (
        create_refresh_token,
        decode_access_token,
        decode_refresh_token,
        hash_password,
        verify_password,
    )

    password_hash = hash_password(
        "Secret123!"
    )

    assert verify_password(
        "Secret123!",
        password_hash,
    )

    assert not verify_password(
        "wrong",
        password_hash,
    )

    assert not verify_password(
        "wrong",
        "not-a-valid-hash",
    )

    refresh_token, _, _ = create_refresh_token(
        regular_user
    )

    with pytest.raises(Exception):
        decode_access_token(
            refresh_token
        )

    with pytest.raises(Exception):
        decode_refresh_token(
            "not-a-token"
        )

    response = await client.get(
        "/api/v1/products"
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_registration_duplicate_phone(client: AsyncClient, regular_user):
    import time

    timestamp = time.time_ns()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Another User",
            "email": f"phone_conflict_{timestamp}@example.com",
            "phone": regular_user.phone,
            "password": "Password123!",
            "password_confirm": "Password123!",
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_auth_invalid_refresh_and_logout_valid_token(
    client: AsyncClient,
    regular_user,
):
    response = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": "x" * 20,
        },
    )

    assert response.status_code == 401

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": regular_user.email,
            "password": "Password123!",
        },
    )

    assert login.status_code == 200

    refresh_token = login.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/logout",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert response.status_code == 204

    response = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_optional_auth_with_valid_and_missing_user_token(
    client: AsyncClient,
    regular_user,
):
    from app.core.security import create_access_token
    from app.models.user import User

    token = create_access_token(regular_user)

    response = await client.get(
        "/api/v1/products",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    fake_user = User(
        id=999998,
        is_admin=False,
    )

    fake_token = create_access_token(fake_user)

    response = await client.get(
        "/api/v1/products",
        headers={
            "Authorization": f"Bearer {fake_token}",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_categories_update_conflict(
    client: AsyncClient,
    admin_headers: dict,
):
    first = await client.post(
        "/api/v1/categories",
        json={
            "name": "Coverage Category A",
            "slug": "coverage-category-a",
        },
        headers=admin_headers,
    )

    second = await client.post(
        "/api/v1/categories",
        json={
            "name": "Coverage Category B",
            "slug": "coverage-category-b",
        },
        headers=admin_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = await client.patch(
        f"/api/v1/categories/{second.json()['id']}",
        json={
            "name": "Coverage Category A",
        },
        headers=admin_headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_categories_update_success_and_delete(
    client: AsyncClient,
    admin_headers: dict,
):
    created = await client.post(
        "/api/v1/categories",
        json={
            "name": "Update Me",
            "slug": "update-me",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    category_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/categories/{category_id}",
        json={
            "name": "Updated Name",
            "icon": "🌿",
            "description": "Обновлено",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
    assert response.json()["icon"] == "🌿"

    fetched = await client.get(
        f"/api/v1/categories/{category_id}",
    )
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Updated Name"

    deleted = await client.delete(
        f"/api/v1/categories/{category_id}",
        headers=admin_headers,
    )
    assert deleted.status_code == 204

    not_found = await client.get(
        f"/api/v1/categories/{category_id}",
    )
    assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_product_create_invalid_category_and_put(
    client: AsyncClient,
    admin_headers: dict,
    test_product,
):
    import time

    timestamp = time.time_ns()

    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Invalid Category Product",
            "price": 100,
            "sku": f"INVALID-CATEGORY-{timestamp}",
            "category_id": 999999,
        },
        headers=admin_headers,
    )

    assert response.status_code == 400

    response = await client.put(
        f"/api/v1/products/{test_product.id}",
        json={
            "name": "PUT Product",
            "price": 1234,
            "description": "Updated by PUT",
            "size": "L",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "PUT Product"
    assert data["price"] == 1234
    assert data["size"] == "L"


@pytest.mark.asyncio
async def test_product_inactive_hidden_from_guest(
    client: AsyncClient,
    admin_headers: dict,
    test_product,
):
    response = await client.patch(
        f"/api/v1/products/{test_product.id}",
        json={
            "is_active": False,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200

    response = await client.get(
        f"/api/v1/products/{test_product.id}",
    )

    assert response.status_code == 404

    response = await client.patch(
        f"/api/v1/products/{test_product.id}",
        json={
            "is_active": True,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cart_existing_item_updates_quantity(
    client: AsyncClient,
    auth_headers: dict,
    test_product,
):
    response = await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {
                    "product_id": test_product.id,
                    "quantity": 2,
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {
                    "product_id": test_product.id,
                    "quantity": 3,
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    item = next(
        item
        for item in response.json()["items"]
        if item["product_id"] == test_product.id
    )

    assert item["quantity"] == 5
    assert item["subtotal"] == 5000


@pytest.mark.asyncio
async def test_cart_remove_without_cart_and_checkout_empty(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.delete(
        "/api/v1/cart/items/999998",
        headers=auth_headers,
    )

    assert response.status_code == 404

    response = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_checkout_rejects_inactive_product(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_product,
):
    response = await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {
                    "product_id": test_product.id,
                    "quantity": 1,
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.patch(
        f"/api/v1/products/{test_product.id}",
        json={
            "is_active": False,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200

    response = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
    )

    assert response.status_code == 400

    await client.delete(
        "/api/v1/cart",
        headers=auth_headers,
    )

    await client.patch(
        f"/api/v1/products/{test_product.id}",
        json={
            "is_active": True,
        },
        headers=admin_headers,
    )


@pytest.mark.asyncio
async def test_checkout_with_selected_products(
    client: AsyncClient,
    auth_headers: dict,
    test_product,
    db_session,
):
    from app.models.product import Product

    second_product = Product(
        name="Second Checkout Product",
        price=2000,
        is_active=True,
        category_id=1,
        sku="SECOND-CHECKOUT-PRODUCT",
    )
    db_session.add(second_product)
    await db_session.commit()
    await db_session.refresh(second_product)

    cart = await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {"product_id": test_product.id, "quantity": 1},
                {"product_id": second_product.id, "quantity": 1},
            ]
        },
        headers=auth_headers,
    )
    assert cart.status_code == 200

    checkout = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
        json={"product_ids": [test_product.id]},
    )

    assert checkout.status_code == 201
    assert checkout.json()["total_amount"] == 1000

    item_ids = {
        item["product_id"]
        for item in checkout.json()["items"]
    }
    assert item_ids == {test_product.id}

    remaining = await client.get(
        "/api/v1/cart",
        headers=auth_headers,
    )
    remaining_ids = {
        item["product_id"]
        for item in remaining.json()["items"]
    }
    assert remaining_ids == {second_product.id}

    await client.delete(
        "/api/v1/cart",
        headers=auth_headers,
    )


@pytest.mark.asyncio
async def test_checkout_with_unknown_product_ids_rejected(
    client: AsyncClient,
    auth_headers: dict,
    test_product,
):
    await client.post(
        "/api/v1/cart/items",
        json={
            "items": [{"product_id": test_product.id, "quantity": 1}]
        },
        headers=auth_headers,
    )

    result = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
        json={"product_ids": [999999]},
    )

    assert result.status_code == 400

    await client.delete(
        "/api/v1/cart",
        headers=auth_headers,
    )


@pytest.mark.asyncio
async def test_checkout_with_delivery(
    client: AsyncClient,
    auth_headers: dict,
    test_product,
):
    await client.post(
        "/api/v1/cart/items",
        json={
            "items": [{"product_id": test_product.id, "quantity": 1}]
        },
        headers=auth_headers,
    )

    result = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
        json={
            "product_ids": [test_product.id],
            "delivery_method": "delivery",
            "delivery_cost": 500,
            "delivery_address": "г. Москва, ул. Ленина, д. 1",
            "recipient_name": "Иванов Иван Иванович",
        },
    )

    assert result.status_code == 201

    data = result.json()

    assert data["delivery_method"] == "delivery"
    assert data["delivery_cost"] == 500
    assert data["recipient_name"] == "Иванов Иван Иванович"
    assert data["total_amount"] == 1000 + 500


@pytest.mark.asyncio
async def test_checkout_delivery_requires_address_and_name(
    client: AsyncClient,
    auth_headers: dict,
    test_product,
):
    await client.post(
        "/api/v1/cart/items",
        json={
            "items": [{"product_id": test_product.id, "quantity": 1}]
        },
        headers=auth_headers,
    )

    result = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
        json={
            "product_ids": [test_product.id],
            "delivery_method": "delivery",
        },
    )

    assert result.status_code == 400

    await client.delete(
        "/api/v1/cart",
        headers=auth_headers,
    )


@pytest.mark.asyncio
async def test_checkout_pickup_resets_delivery(
    client: AsyncClient,
    auth_headers: dict,
    test_product,
):
    await client.post(
        "/api/v1/cart/items",
        json={
            "items": [{"product_id": test_product.id, "quantity": 1}]
        },
        headers=auth_headers,
    )

    result = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
        json={
            "product_ids": [test_product.id],
            "delivery_method": "pickup",
            "delivery_cost": 500,
            "delivery_address": "г. Москва, ул. Ленина, д. 1",
            "recipient_name": "Иванов Иван Иванович",
        },
    )

    assert result.status_code == 201

    data = result.json()

    assert data["delivery_method"] == "pickup"
    assert data["delivery_cost"] == 0
    assert data["delivery_address"] is None
    assert data["total_amount"] == 1000

    await client.delete(
        "/api/v1/cart",
        headers=auth_headers,
    )


@pytest.mark.asyncio
async def test_checkout_function_direct_selected(
    db_session,
    regular_user,
):
    from app.api.v1.orders import checkout
    from app.models.cart import Cart, CartItem
    from app.models.product import Product
    from app.schemas.order import CheckoutRequest
    from sqlalchemy import select

    first = Product(
        name="Direct First",
        price=500,
        is_active=True,
        category_id=1,
        sku="DIRECT-FIRST",
    )
    second = Product(
        name="Direct Second",
        price=300,
        is_active=True,
        category_id=1,
        sku="DIRECT-SECOND",
    )
    db_session.add_all([first, second])
    await db_session.flush()
    cart = Cart(user_id=regular_user.id)
    db_session.add(cart)
    await db_session.flush()
    db_session.add_all([
        CartItem(cart_id=cart.id, product_id=first.id, quantity=2),
        CartItem(cart_id=cart.id, product_id=second.id, quantity=1),
    ])
    await db_session.commit()

    order = await checkout(
        CheckoutRequest(product_ids=[first.id]),
        regular_user,
        db_session,
    )

    assert order.total_amount == 1000
    assert len(order.items) == 1
    assert order.items[0].product_name == "Direct First"

    remaining = await db_session.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    assert remaining is not None
    assert remaining.product_id == second.id


@pytest.mark.asyncio
async def test_checkout_function_direct_no_selection_keeps_full_cart(
    db_session,
    regular_user,
):
    from app.api.v1.orders import checkout
    from app.models.cart import Cart, CartItem
    from app.models.product import Product
    from app.schemas.order import CheckoutRequest
    from app.core.exceptions import BadRequestError
    from sqlalchemy import select

    product = Product(
        name="Direct Only",
        price=100,
        is_active=True,
        category_id=1,
        sku="DIRECT-ONLY",
    )
    db_session.add(product)
    await db_session.flush()
    cart = Cart(user_id=regular_user.id)
    db_session.add(cart)
    await db_session.flush()
    db_session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1))
    await db_session.commit()

    order = await checkout(
        CheckoutRequest(product_ids=None),
        regular_user,
        db_session,
    )

    assert order.total_amount == 100
    assert len(order.items) == 1

    remaining = await db_session.scalars(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    assert len(remaining.all()) == 0

    with pytest.raises(BadRequestError):
        await checkout(
            CheckoutRequest(product_ids=[]),
            regular_user,
            db_session,
        )


@pytest.mark.asyncio
async def test_order_cancelled_order_cannot_be_cancelled_again(
    client: AsyncClient,
    auth_headers: dict,
    test_product,
):
    await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {
                    "product_id": test_product.id,
                    "quantity": 1,
                }
            ]
        },
        headers=auth_headers,
    )

    checkout = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
    )

    assert checkout.status_code == 201

    order_id = checkout.json()["id"]

    response = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_order_status_clears_payment_data(
    client: AsyncClient,
    auth_headers: dict,
    admin_headers: dict,
    test_product,
):
    await client.post(
        "/api/v1/cart/items",
        json={
            "items": [
                {
                    "product_id": test_product.id,
                    "quantity": 1,
                }
            ]
        },
        headers=auth_headers,
    )

    checkout = await client.post(
        "/api/v1/orders/checkout",
        headers=auth_headers,
    )

    assert checkout.status_code == 201

    order_id = checkout.json()["id"]

    response = await client.post(
        f"/api/v1/orders/{order_id}/pay",
        json={
            "payment_method": "cash",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.patch(
        f"/api/v1/orders/admin/{order_id}/status",
        json={
            "status": "pending_payment",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "pending_payment"
    assert data["paid_at"] is None
    assert data["payment_method"] is None


@pytest.mark.asyncio
async def test_security_helpers_invalid_and_expired_tokens(
    client: AsyncClient,
):
    import jwt
    from datetime import datetime, timedelta, timezone

    from app.core.config import settings
    from app.core.security import (
        decode_access_token,
        decode_refresh_token,
    )

    with pytest.raises(Exception):
        decode_access_token("not-a-jwt")

    wrong_type = jwt.encode(
        {
            "sub": "1",
            "type": "refresh",
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    with pytest.raises(Exception):
        decode_access_token(wrong_type)

    expired = jwt.encode(
        {
            "sub": "1",
            "type": "refresh",
            "exp": datetime.now(timezone.utc)
            - timedelta(minutes=1),
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    with pytest.raises(Exception):
        decode_refresh_token(expired)


@pytest.mark.asyncio
async def test_password_schema_and_registration_validation(
    client: AsyncClient,
):
    import time

    timestamp = time.time_ns()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Valid User",
            "email": f"badphone_{timestamp}@example.com",
            "phone": "123",
            "password": "Password123!",
            "password_confirm": "Password123!",
        },
    )

    assert response.status_code == 422

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Valid User",
            "email": f"mismatch_{timestamp}@example.com",
            "phone": f"+7999{timestamp % 10000000:07d}",
            "password": "Password123!",
            "password_confirm": "Different123!",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_main_validation_handler_returns_json(
    client: AsyncClient,
    admin_headers,
):
    response = await client.post(
        "/api/v1/products",
        headers=admin_headers,
        json={
            "name": "",
            "price": -1,
            "sku": "",
            "category_id": 0,
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert data["code"] == 422
    assert data["message"] == "Ошибка валидации"
    assert isinstance(data["details"], list)


@pytest.mark.asyncio
async def test_auth_rate_limiter_forwarded_ip_and_limit(
    client: AsyncClient,
    monkeypatch,
):
    from starlette.requests import Request

    from app.api import deps
    from app.core.config import settings

    deps._rate_limit_store.clear()

    monkeypatch.setattr(
        settings,
        "rate_limit_auth_requests",
        1,
    )

    monkeypatch.setattr(
        settings,
        "rate_limit_auth_window_seconds",
        60,
    )

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [
                (
                    b"x-forwarded-for",
                    b"203.0.113.10, 10.0.0.1",
                ),
            ],
            "client": (
                "127.0.0.1",
                12345,
            ),
        }
    )

    assert deps._get_client_ip(request) == "203.0.113.10"

    await deps.auth_rate_limiter(request)

    with pytest.raises(Exception) as exc_info:
        await deps.auth_rate_limiter(request)

    assert getattr(exc_info.value, "status_code", None) == 429

    no_client_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "client": None,
        }
    )

    assert deps._get_client_ip(no_client_request) == "unknown"


@pytest.mark.asyncio
async def test_health_check_database_failure(
    client: AsyncClient,
    db_session,
):
    from app.db.session import get_db
    from app.main import app

    class BrokenSession:
        async def execute(self, statement):
            raise RuntimeError("database down")

    async def broken_get_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_get_db

    try:
        response = await client.get("/health")
    finally:
        app.dependency_overrides[get_db] = lambda: db_session

    assert response.status_code == 503
    assert response.json()["database"] == "disconnected"


@pytest.mark.asyncio
async def test_products_list_validation_errors(
    client: AsyncClient,
):
    response = await client.get(
        "/api/v1/products?page=0"
    )
    assert response.status_code == 422

    response = await client.get(
        "/api/v1/products?size=101"
    )
    assert response.status_code == 422

    response = await client.get(
        "/api/v1/products?name="
    )
    assert response.status_code == 422

    response = await client.get(
        "/api/v1/products?min_price=-1"
    )
    assert response.status_code == 422

    response = await client.get(
        "/api/v1/products?sort_by=invalid"
    )
    assert response.status_code == 422

    response = await client.get(
        "/api/v1/products?sort_order=invalid"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_products_invalid_price_range(
    client: AsyncClient,
):
    response = await client.get(
        "/api/v1/products"
        "?min_price=1000"
        "&max_price=500"
    )

    assert response.status_code == 400

    data = response.json()

    assert data["code"] == 400
    assert "min_price" in data["message"]


@pytest.mark.asyncio
async def test_products_sorting_and_pagination(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
):
    from app.models.product import Product

    import time

    timestamp = time.time_ns()

    first = Product(
        name=f"AAA Product {timestamp}",
        price=300,
        is_active=True,
        category_id=1,
        sku=f"AAA-{timestamp}",
    )

    second = Product(
        name=f"BBB Product {timestamp}",
        price=700,
        is_active=True,
        category_id=1,
        sku=f"BBB-{timestamp}",
    )

    third = Product(
        name=f"CCC Product {timestamp}",
        price=500,
        is_active=True,
        category_id=1,
        sku=f"CCC-{timestamp}",
    )

    db_session.add_all([first, second, third])
    await db_session.commit()

    response = await client.get(
        "/api/v1/products"
        "?sort_by=price"
        "&sort_order=asc"
        "&size=100"
    )

    assert response.status_code == 200

    items = response.json()["items"]

    prices = [item["price"] for item in items]

    assert prices == sorted(prices)

    response = await client.get(
        "/api/v1/products"
        "?sort_by=price"
        "&sort_order=desc"
        "&size=1"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["size"] == 1
    assert len(data["items"]) == 1
    assert data["pages"] >= 1


@pytest.mark.asyncio
async def test_products_filter_by_category(
    client: AsyncClient,
    db_session,
):
    from app.models.category import Category
    from app.models.product import Product

    import time

    timestamp = time.time_ns()

    extra_category = Category(
        name=f"Extra {timestamp}",
        slug=f"extra-{timestamp}",
        description="Extra",
        icon="🪴",
    )
    db_session.add(extra_category)
    await db_session.commit()
    await db_session.refresh(extra_category)

    db_session.add_all([
        Product(
            name=f"Cat A {timestamp}",
            price=100,
            is_active=True,
            category_id=1,
            sku=f"CATA-{timestamp}",
        ),
        Product(
            name=f"Cat B {timestamp}",
            price=200,
            is_active=True,
            category_id=extra_category.id,
            sku=f"CATB-{timestamp}",
        ),
    ])
    await db_session.commit()

    response = await client.get(
        "/api/v1/products"
        f"?category_id={extra_category.id}"
        "&size=50"
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert items, "expected products to be returned"
    assert all(
        item["category_id"] == extra_category.id
        for item in items
    )


@pytest.mark.asyncio
async def test_product_get_not_found(
    client: AsyncClient,
):
    response = await client.get(
        "/api/v1/products/999999"
    )

    assert response.status_code == 404

    data = response.json()

    assert data["code"] == 404


@pytest.mark.asyncio
async def test_product_update_and_delete_not_found(
    client: AsyncClient,
    admin_headers: dict,
):
    response = await client.put(
        "/api/v1/products/999999",
        json={
            "name": "Missing",
            "price": 100,
        },
        headers=admin_headers,
    )

    assert response.status_code == 404

    response = await client.patch(
        "/api/v1/products/999999",
        json={
            "name": "Missing",
        },
        headers=admin_headers,
    )

    assert response.status_code == 404

    response = await client.delete(
        "/api/v1/products/999999",
        headers=admin_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_product_patch(
    client: AsyncClient,
    admin_headers: dict,
    test_product,
):
    response = await client.patch(
        f"/api/v1/products/{test_product.id}",
        json={
            "name": "Patched Product",
            "price": 1500,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Patched Product"
    assert data["price"] == 1500


@pytest.mark.asyncio
async def test_product_delete(
    client: AsyncClient,
    admin_headers: dict,
    test_product,
):
    response = await client.delete(
        f"/api/v1/products/{test_product.id}",
        headers=admin_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == test_product.id
    assert data["is_active"] is False

    response = await client.get(
        f"/api/v1/products/{test_product.id}"
    )

    assert response.status_code == 404

    response = await client.get(
        f"/api/v1/products/{test_product.id}",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_product_create_duplicate_sku(
    client: AsyncClient,
    admin_headers: dict,
    test_product,
):
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Duplicate",
            "price": 500,
            "sku": test_product.sku,
            "category_id": 1,
        },
        headers=admin_headers,
    )

    assert response.status_code == 409

    data = response.json()

    assert data["code"] == 409


@pytest.mark.asyncio
async def test_product_create_without_admin(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Forbidden Product",
            "price": 100,
            "sku": "FORBIDDEN-NEW-SKU",
            "category_id": 1,
        },
        headers=auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_product_update_without_admin(
    client: AsyncClient,
    auth_headers: dict,
    test_product,
):
    response = await client.patch(
        f"/api/v1/products/{test_product.id}",
        json={
            "name": "Forbidden Update",
        },
        headers=auth_headers,
    )

    assert response.status_code == 403

    response = await client.delete(
        f"/api/v1/products/{test_product.id}",
        headers=auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_main_not_found_handler(
    client: AsyncClient,
):
    response = await client.get(
        "/this-route-does-not-exist"
    )

    assert response.status_code == 404

    data = response.json()

    assert data["code"] == 404
    assert "message" in data


@pytest.mark.asyncio
async def test_products_invalid_page_returns_validation_json(
    client: AsyncClient,
):
    response = await client.get(
        "/api/v1/products?page=invalid"
    )

    assert response.status_code == 422

    data = response.json()

    assert data["code"] == 422
    assert data["message"] == "Ошибка валидации"
    assert "details" in data
    assert isinstance(data["details"], list)


@pytest.mark.asyncio
async def test_health_response(
    client: AsyncClient,
):
    response = await client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_upload_image_success(
    client: AsyncClient,
    admin_headers: dict,
):
    response = await client.post(
        "/api/v1/uploads",
        headers=admin_headers,
        data={"folder": "categories"},
        files={
            "file": (
                "test-photo.jpg",
                b"\xff\xd8\xff\xe0fake-jpeg-bytes",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "url" in data
    assert data["url"].startswith(
        "/uploads/categories/"
    )
    assert data["url"].endswith(".jpg")


@pytest.mark.asyncio
async def test_upload_image_wrong_folder(
    client: AsyncClient,
    admin_headers: dict,
):
    response = await client.post(
        "/api/v1/uploads",
        headers=admin_headers,
        data={"folder": "avatars"},
        files={
            "file": (
                "pic.jpg",
                b"\xff\xd8\xff\xe0fake",
                "image/jpeg",
            )
        },
    )

    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_upload_image_bad_extension(
    client: AsyncClient,
    admin_headers: dict,
):
    response = await client.post(
        "/api/v1/uploads",
        headers=admin_headers,
        data={"folder": "products"},
        files={
            "file": (
                "evil.txt",
                b"hello world",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_image_without_admin(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.post(
        "/api/v1/uploads",
        headers=auth_headers,
        data={"folder": "products"},
        files={
            "file": (
                "pic.jpg",
                b"\xff\xd8\xff\xe0fake",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_image_empty_file(
    client: AsyncClient,
    admin_headers: dict,
):
    response = await client.post(
        "/api/v1/uploads",
        headers=admin_headers,
        data={"folder": "categories"},
        files={
            "file": (
                "empty.jpg",
                b"",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_image_too_large(
    client: AsyncClient,
    admin_headers: dict,
):
    from app.core.config import settings

    max_bytes = settings.max_upload_size_bytes
    big_file = b"\xff\xd8\xff\xe0" + b"0" * (max_bytes + 1)

    response = await client.post(
        "/api/v1/uploads",
        headers=admin_headers,
        data={"folder": "products"},
        files={
            "file": (
                "big.jpg",
                big_file,
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_image_without_auth(
    client: AsyncClient,
):
    response = await client.post(
        "/api/v1/uploads",
        data={"folder": "products"},
        files={
            "file": (
                "pic.jpg",
                b"\xff\xd8\xff\xe0fake",
                "image/jpeg",
            )
        },
    )

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_db_dependency_yields_session():
    from app.db.session import get_db

    async for session in get_db():
        from app.db.base import Base

        assert Base is not None
        assert session is not None
        break
