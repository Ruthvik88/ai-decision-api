"""
Tests for authentication: registration, login, password hashing, token rejection.

Uses FastAPI TestClient with an in-memory SQLite database.
"""

import pytest

from src.auth import hash_password, verify_password
from tests.conftest import client


# ---------------------------------------------------------------------------
# Password hashing tests
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_and_verify(self):
        plain = "mysecretpassword"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)

    def test_wrong_password(self):
        hashed = hash_password("correctpassword")
        assert not verify_password("wrongpassword", hashed)

    def test_different_hashes_for_same_password(self):
        """bcrypt should produce different salts each time."""
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_success(self):
        resp = client.post(
            "/register", json={"email": "alice@example.com", "password": "pass123"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "alice@example.com"
        assert "id" in data
        # Password should NOT be in the response
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_duplicate_email(self):
        client.post(
            "/register", json={"email": "dupe@example.com", "password": "pass123"}
        )
        resp = client.post(
            "/register", json={"email": "dupe@example.com", "password": "pass456"}
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success(self):
        client.post(
            "/register", json={"email": "login@example.com", "password": "pass123"}
        )
        resp = client.post(
            "/login", json={"email": "login@example.com", "password": "pass123"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self):
        client.post(
            "/register", json={"email": "login2@example.com", "password": "pass123"}
        )
        resp = client.post(
            "/login", json={"email": "login2@example.com", "password": "wrongpass"}
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self):
        resp = client.post(
            "/login", json={"email": "noone@example.com", "password": "pass123"}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token tests
# ---------------------------------------------------------------------------


class TestTokenValidation:
    def test_invalid_token_rejected(self):
        resp = client.get(
            "/me", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401

    def test_missing_token_rejected(self):
        resp = client.get("/me")
        assert resp.status_code == 401

    def test_valid_token_accepted(self):
        client.post(
            "/register", json={"email": "valid@example.com", "password": "pass123"}
        )
        login_resp = client.post(
            "/login", json={"email": "valid@example.com", "password": "pass123"}
        )
        token = login_resp.json()["access_token"]
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "valid@example.com"
