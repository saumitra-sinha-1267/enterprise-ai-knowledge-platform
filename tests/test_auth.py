"""Unit and integration tests for Authentication and Identity.
"""

import pytest
from app.auth.security import create_access_token, decode_access_token, verify_password, get_password_hash


def test_password_hashing():
    """Verify bcrypt password hashing and verification."""
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_cycle():
    """Verify JWT encoding, claim retention, and decoding."""
    token = create_access_token(
        subject="alice",
        user_id=42,
        role="employee",
        department="general",
    )
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "alice"
    assert payload["user_id"] == 42
    assert payload["role"] == "employee"
    assert payload["department"] == "general"


def test_login_success(client, test_users):
    """Verify successful authentication with valid credentials."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "hr_user", "password": "TestPassword123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == "hr_user"
    assert data["role"] == "hr"
    assert data["department"] == "hr"


def test_login_failure_wrong_password(client, test_users):
    """Verify authentication rejection for incorrect credentials."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "hr_user", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_nonexistent_user(client, test_users):
    """Verify rejection of unknown users."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent_ghost", "password": "SomePassword123!"},
    )
    assert response.status_code == 401


def test_get_current_user_profile(client, auth_headers):
    """Verify /me profile endpoint returns verified claims."""
    response = client.get("/api/v1/auth/me", headers=auth_headers["finance_user"])
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "finance_user"
    assert data["role"] == "finance"
    assert data["department"] == "finance"
    assert "finance" in data["authorized_scopes"]["departments"]
    assert "general" in data["authorized_scopes"]["departments"]


def test_access_protected_endpoint_without_token(client):
    """Verify unauthenticated requests are rejected with 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
