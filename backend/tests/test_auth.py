import uuid

import pytest

from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user
from app.database.dependencies import get_db
from app.models import User
from app.utils.security import hash_password, create_access_token


# Mock database
@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_user():
    user = MagicMock(spec=User)

    user.id = uuid.uuid4()
    user.name = "Test User"
    user.email = "test@recycliq.com"
    user.role = "user"
    user.password_hash = hash_password("TestPassword@123")

    return user


# 1. Successful registration
def test_successful_registration(client, mock_db):

    mock_db.query.return_value.filter.return_value.first.return_value = None

    response = client.post(
        "/auth/register",
        json={
            "name": "Test User",
            "email": "newuser@recycliq.com",
            "password": "TestPassword@123"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Test User"
    assert data["email"] == "newuser@recycliq.com"
    assert data["role"] == "user"

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


# 2. Duplicate email registration
def test_duplicate_email_registration(client, mock_db, sample_user):

    mock_db.query.return_value.filter.return_value.first.return_value = sample_user

    response = client.post(
        "/auth/register",
        json={
            "name": "Another User",
            "email": "test@recycliq.com",
            "password": "TestPassword@123"
        }
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email is already registered!"


# 3. Successful login
def test_successful_login(client, mock_db, sample_user):

    mock_db.query.return_value.filter.return_value.first.return_value = sample_user

    response = client.post(
        "/auth/login",
        json={
            "email": "test@recycliq.com",
            "password": "TestPassword@123"
        }
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


# 4. Login with incorrect password
def test_login_wrong_password(client, mock_db, sample_user):

    mock_db.query.return_value.filter.return_value.first.return_value = sample_user

    response = client.post(
        "/auth/login",
        json={
            "email": "test@recycliq.com",
            "password": "WrongPassword@123"
        }
    )

    assert response.status_code == 401


# 5. Login with nonexistent email
def test_login_nonexistent_email(client, mock_db):

    mock_db.query.return_value.filter.return_value.first.return_value = None

    response = client.post(
        "/auth/login",
        json={
            "email": "unknown@recycliq.com",
            "password": "TestPassword@123"
        }
    )

    assert response.status_code == 401


# 6. Access /auth/me without authentication
def test_auth_me_without_token(client):

    response = client.get("/auth/me")

    assert response.status_code in (401, 403)


# 7. Access /auth/me with valid JWT
def test_auth_me_with_valid_token(client, mock_db, sample_user):

    mock_db.query.return_value.filter.return_value.first.return_value = sample_user

    token = create_access_token({
        "sub": str(sample_user.id),
        "role": "user"
    })

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "test@recycliq.com"


# 8. Invalid JWT
def test_auth_me_with_invalid_token(client):

    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"}
    )

    assert response.status_code == 401


# 9. Valid JWT but nonexistent user
def test_auth_me_user_not_found(client, mock_db):

    mock_db.query.return_value.filter.return_value.first.return_value = None

    user_id = uuid.uuid4()

    token = create_access_token({
        "sub": str(user_id),
        "role": "user"
    })

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


# 10. Invalid UUID in JWT subject
def test_auth_me_invalid_user_id(client):

    token = create_access_token({
        "sub": "not-a-valid-uuid",
        "role": "user"
    })

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401

def test_missing_subject_in_token(client, monkeypatch):
    from app.api import dependencies

    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda token: {"role": "user"}
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer fake-token"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid authentication token"
    )