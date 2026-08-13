from app.core.security import create_access_token


async def test_cart_unauthorized(client):
    response = await client.post(
        "/api/v1/cart/items",
        json={"items": [{"product_id": 1, "quantity": 1}]},
    )

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Unauthorized"}


async def test_empty_cart(client, create_user, auth_headers):
    user = await create_user()
    headers = auth_headers(create_access_token(user))

    cart_response = await client.get("/api/v1/cart", headers=headers)
    total_response = await client.get("/api/v1/cart/total", headers=headers)

    assert cart_response.status_code == 200
    assert cart_response.json() == {"items": [], "total": 0}

    assert total_response.status_code == 200
    assert total_response.json() == {"total": 0}


async def test_add_single_item(client, create_user, create_product, auth_headers):
    user = await create_user()
    product = await create_product(price=50)

    headers = auth_headers(create_access_token(user))

    response = await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"items": [{"product_id": product.id, "quantity": 2}]},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == product.id
    assert data["items"][0]["quantity"] == 2
    assert data["total"] == 100

    total_response = await client.get("/api/v1/cart/total", headers=headers)

    assert total_response.status_code == 200
    assert total_response.json() == {"total": 100}


async def test_add_multiple_items_with_duplicates(client, create_user, create_product, auth_headers):
    user = await create_user()
    product_1 = await create_product(name="Product 1", price=10)
    product_2 = await create_product(name="Product 2", price=20)

    headers = auth_headers(create_access_token(user))

    response = await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "items": [
                {"product_id": product_1.id, "quantity": 1},
                {"product_id": product_2.id, "quantity": 3},
                {"product_id": product_1.id, "quantity": 2},
            ]
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["items"]) == 2
    assert data["total"] == 90

    items_by_product_id = {item["product_id"]: item for item in data["items"]}

    assert items_by_product_id[product_1.id]["quantity"] == 3
    assert items_by_product_id[product_2.id]["quantity"] == 3


async def test_add_empty_items_validation(client, create_user, auth_headers):
    user = await create_user()
    headers = auth_headers(create_access_token(user))

    response = await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"items": []},
    )

    assert response.status_code == 422


async def test_remove_item(client, create_user, create_product, auth_headers):
    user = await create_user()
    product_1 = await create_product(name="Product 1", price=10)
    product_2 = await create_product(name="Product 2", price=20)

    headers = auth_headers(create_access_token(user))

    await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "items": [
                {"product_id": product_1.id, "quantity": 1},
                {"product_id": product_2.id, "quantity": 2},
            ]
        },
    )

    delete_response = await client.delete(f"/api/v1/cart/items/{product_1.id}", headers=headers)
    assert delete_response.status_code == 204

    cart_response = await client.get("/api/v1/cart", headers=headers)
    data = cart_response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == product_2.id
    assert data["total"] == 40


async def test_clear_cart(client, create_user, create_product, auth_headers):
    user = await create_user()
    product = await create_product(price=100)

    headers = auth_headers(create_access_token(user))

    await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"items": [{"product_id": product.id, "quantity": 1}]},
    )

    clear_response = await client.delete("/api/v1/cart", headers=headers)
    assert clear_response.status_code == 204

    cart_response = await client.get("/api/v1/cart", headers=headers)
    assert cart_response.json() == {"items": [], "total": 0}


async def test_add_inactive_product(client, create_user, create_product, auth_headers):
    user = await create_user()
    product = await create_product(is_active=False)

    headers = auth_headers(create_access_token(user))

    response = await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"items": [{"product_id": product.id, "quantity": 1}]},
    )

    assert response.status_code == 400


async def test_add_missing_product(client, create_user, auth_headers):
    user = await create_user()
    headers = auth_headers(create_access_token(user))

    response = await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"items": [{"product_id": 9999, "quantity": 1}]},
    )

    assert response.status_code == 400


async def test_remove_missing_item(client, create_user, auth_headers):
    user = await create_user()
    headers = auth_headers(create_access_token(user))

    response = await client.delete("/api/v1/cart/items/9999", headers=headers)

    assert response.status_code == 404