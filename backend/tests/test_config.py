"""Unit tests for application configuration."""
import pytest

from app.core.config import Settings


def make_settings(**overrides):
    data = {
        "secret_key": "x" * 32,
        "database_url": None,
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def test_settings_async_database_url_default():
    s = make_settings(
        postgres_host="db.example.com",
        postgres_db="green",
        postgres_user="root",
        postgres_password="pass",
    )
    url = s.async_database_url
    assert "db.example.com" in url
    assert "/green" in url


def test_settings_async_database_url_explicit():
    explicit = "sqlite+aiosqlite:///./custom.db"
    s = make_settings(database_url=explicit)
    assert s.async_database_url == explicit


def test_settings_required_secret_key():
    with pytest.raises(Exception):
        Settings(_env_file=None, secret_key="short")