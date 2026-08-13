import pytest


def register_payload(**overrides):
    payload = {
        "full_name": "Иван Иванов",
        "email": "new@example.com",
        "phone": "+79991234567",
        "password": "Password$",
        "password_confirm": "Password$",
    }
    payload.update(overrides)
    return payload


async def test_health_and_root(client):
    root_response = await client.get("/")
    health_response = await client.get("/health")

    assert root_response.status_code == 200
    assert root_response.json()["status"] == "ok"

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}


async def test_register_success(client):
    response = await client.post("/api/v1/auth/register", json=register_payload())

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "new@example.com"
    assert data["phone"] == "+79991234567"
    assert data["is_admin"] is False
    assert "password" not in data


async def test_register_password_confirm_mismatch(client):
    response = await client.post(
        "/api/v1/auth/register",
        json=register_payload(password="Password$", password_confirm="OtherPass$"),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "password",
    [
        "short$",
        "noupper$",
        "NOLOWERSPECIAL",
        "Password_",
        "Пароль$$",
    ],
)
async def test_register_invalid_password(client, password):
    response = await client.post(
        "/api/v1/auth/register",
        json=register_payload(password=password, password_confirm=password),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "phone",
    [
        "89991234567",
        "+7999",
        "+799912345678",
        "+19991234567",
    ],
)
async def test_register_invalid_phone(client, phone):
    response = await client.post(
        "/api/v1/auth/register",
        json=register_payload(phone=phone),
    )

    assert response.status_code == 422


async def test_register_duplicate_email(client, create_user):
    await create_user(email="existing@example.com", phone="+79990000001")

    response = await client.post(
        "/api/v1/auth/register",
        json=register_payload(
            email="existing@example.com",
            phone="+79990000002",
        ),
    )

    assert response.status_code == 409


async def test_register_duplicate_phone(client, create_user):
    await create_user(email="existing@example.com", phone="+79990000001")

    response = await client.post(
        "/api/v1/auth/register",
        json=register_payload(
            email="another@example.com",
            phone="+79990000001",
        ),
    )

    assert response.status_code == 409


async def test_login_success_email(client, create_user):
    await create_user(email="user@example.com", phone="+79990000001", password="Password$")

    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": "Password$"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert "access_token" in response.json()


async def test_login_success_phone(client, create_user):
    await create_user(email="user@example.com", phone="+79990000001", password="Password$")

    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "+79990000001", "password": "Password$"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password(client, create_user):
    await create_user(email="user@example.com", password="Password$")

    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": "WrongPass$"},
    )

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Unauthorized"}


async def test_login_user_not_found(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "unknown@example.com", "password": "Password$"},
    )

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Unauthorized"}


async def test_unauthorized_products(client):
    response = await client.get("/api/v1/products")

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Unauthorized"}


async def test_invalid_token(client):
    response = await client.get(
        "/api/v1/products",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Unauthorized"}