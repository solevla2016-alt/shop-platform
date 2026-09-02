"""Unit tests for validation schemas."""
import pytest

from app.schemas.auth import validate_password
from app.schemas.user import UserCreate


def make_user(**overrides):
    data = {
        "full_name": "Иван Иванов",
        "email": "ivan@example.com",
        "phone": "+79991234567",
        "password": "Sup3r$ecret",
        "password_confirm": "Sup3r$ecret",
    }
    data.update(overrides)
    return UserCreate(**data)


def test_validate_password_valid():
    assert validate_password("Sup3r$ecret") == "Sup3r$ecret"
    assert validate_password("Abcdefg!1") == "Abcdefg!1"


def test_validate_password_too_short():
    with pytest.raises(ValueError):
        validate_password("A!1")


def test_validate_password_illegal_characters():
    with pytest.raises(ValueError):
        validate_password("пароль!A1" * 5)


def test_validate_password_missing_uppercase():
    with pytest.raises(ValueError):
        validate_password("abcdefg!12345")


def test_validate_password_missing_special():
    with pytest.raises(ValueError):
        validate_password("Abcdefg12345")


def test_user_create_valid():
    user = make_user()
    assert user.full_name == "Иван Иванов"
    assert user.email == "ivan@example.com"


def test_user_create_full_name_too_short():
    with pytest.raises(ValueError):
        make_user(full_name="  X  ")


def test_user_create_email_none():
    with pytest.raises(ValueError):
        make_user(email=None)


def test_user_create_email_empty():
    with pytest.raises(ValueError):
        make_user(email="   ")


def test_user_create_password_no_fullmatch():
    with pytest.raises(ValueError):
        make_user(password="Неправильный!A1", password_confirm="Неправильный!A1")


def test_user_create_password_no_uppercase():
    with pytest.raises(ValueError):
        make_user(password="abcdefg!12345", password_confirm="abcdefg!12345")


def test_user_create_password_no_special():
    with pytest.raises(ValueError):
        make_user(password="Abcdefg12345", password_confirm="Abcdefg12345")


def test_user_create_passwords_mismatch():
    with pytest.raises(ValueError):
        make_user(password_confirm="OtherPassword!1")
