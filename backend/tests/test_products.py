from app.core.security import create_access_token


async def test_products_unauthorized(client):
    response = await client.get("/api/v1/products")

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Unauthorized"}


async def test_list_only_active_products(client, create_user, create_product, auth_headers):
    user = await create_user()
    await create_product(name="Active", is_active=True)
    await create_product(name="Inactive", is_active=False)

    headers = auth_headers(create_access_token(user))
    response = await client.get("/api/v1/products", headers=headers)

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Active"


async def test_non_admin_cannot_create_product(client, create_user, auth_headers):
    user = await create_user()
    headers = auth_headers(create_access_token(user))

    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Laptop", "price": 1000, "is_active": True},
    )

    assert response.status_code == 403


async def test_admin_create_product(client, create_user, auth_headers):
    admin = await create_user(
        email="admin@example.com",
        phone="+79990000000",
        is_admin=True,
    )
    headers = auth_headers(create_access_token(admin))

    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Laptop", "price": 1000, "is_active": True},
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Laptop"
    assert data["price"] == 1000
    assert data["is_active"] is True


async def test_admin_create_product_validation(client, create_user, auth_headers):
    admin = await create_user(
        email="admin@example.com",
        phone="+79990000000",
        is_admin=True,
    )
    headers = auth_headers(create_access_token(admin))

    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "", "price": -5},
    )

    assert response.status_code == 422


async def test_admin_update_product(client, create_user, create_product, auth_headers):
    admin = await create_user(
        email="admin@example.com",
        phone="+79990000000",
        is_admin=True,
    )
    product = await create_product(price=100)

    headers = auth_headers(create_access_token(admin))

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        headers=headers,
        json={"price": 250},
    )

    assert response.status_code == 200
    assert response.json()["price"] == 250


async def test_admin_can_get_inactive_product(client, create_user, create_product, auth_headers):
    admin = await create_user(
        email="admin@example.com",
        phone="+79990000000",
        is_admin=True,
    )
    product = await create_product(is_active=False)

    headers = auth_headers(create_access_token(admin))

    response = await client.get(f"/api/v1/products/{product.id}", headers=headers)

    assert response.status_code == 200


async def test_user_cannot_get_inactive_product(client, create_user, create_product, auth_headers):
    user = await create_user()
    product = await create_product(is_active=False)

    headers = auth_headers(create_access_token(user))

    response = await client.get(f"/api/v1/products/{product.id}", headers=headers)

    assert response.status_code == 404


async def test_admin_delete_product(client, create_user, create_product, auth_headers):
    admin = await create_user(
        email="admin@example.com",
        phone="+79990000000",
        is_admin=True,
    )
    product = await create_product()

    headers = auth_headers(create_access_token(admin))

    delete_response = await client.delete(f"/api/v1/products/{product.id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/products/{product.id}", headers=headers)
    assert get_response.status_code == 404


async def test_non_admin_cannot_delete_product(client, create_user, create_product, auth_headers):
    user = await create_user()
    product = await create_product()

    headers = auth_headers(create_access_token(user))

    response = await client.delete(f"/api/v1/products/{product.id}", headers=headers)

    assert response.status_code == 403