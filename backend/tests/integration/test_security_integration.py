import uuid
from datetime import timedelta

import jwt
import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.database.dependencies import get_db
from app.models import User, WasteScan, ScanObject
from app.utils.security import (
    create_access_token,
    hash_password,
    verify_password,
)



@pytest.fixture
def test_user(db_session):
    user = User(
        name="Security Test User",
        email=f"security_{uuid.uuid4().hex}@example.com",
        password_hash=hash_password("TestPassword@123"),
    )

    db_session.add(user)
    db_session.commit()

    return user


# ------------------------------------------------------------
# 1. Expired JWT rejection
# ------------------------------------------------------------

def test_expired_jwt_rejected(api_client, monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "integration-test-secret-key-123456789",
    )
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    token = create_access_token(
        {"sub": str(uuid.uuid4()), "role": "user"},
        expires_delta=timedelta(seconds=-1),
    )

    response = api_client.get(
        "/scans/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# ------------------------------------------------------------
# 2. Invalid JWT signature rejection
# ------------------------------------------------------------

def test_invalid_jwt_signature_rejected(api_client, monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "correct-integration-secret-123456789",
    )
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "user",
        },
        "incorrect-integration-secret-key-2026",
        algorithm="HS256",
    )

    response = api_client.get(
        "/scans/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# ------------------------------------------------------------
# 3. Missing JWT subject
# ------------------------------------------------------------

def test_missing_jwt_subject_rejected(api_client, monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "integration-test-secret-key-123456789",
    )

    token = create_access_token({"role": "user"})

    response = api_client.get(
        "/scans/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# ------------------------------------------------------------
# 4. Invalid UUID in JWT
# ------------------------------------------------------------

def test_invalid_user_uuid_rejected(api_client, monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "integration-test-secret-key-123456789",
    )

    token = create_access_token({
        "sub": "invalid-uuid",
        "role": "user",
    })

    response = api_client.get(
        "/scans/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# ------------------------------------------------------------
# 5. Deleted user cannot use an old JWT
# ------------------------------------------------------------

def test_deleted_user_token_rejected(
    api_client,
    db_session,
    test_user,
    monkeypatch,
):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "integration-test-secret-key-123456789",
    )

    token = create_access_token({
        "sub": str(test_user.id),
        "role": test_user.role,
    })

    db_session.delete(test_user)
    db_session.commit()

    response = api_client.get(
        "/scans/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User no longer exists"


# ------------------------------------------------------------
# 6. Cross-user scan access prevention
# ------------------------------------------------------------

def test_cross_user_scan_access_rejected(
    api_client,
    db_session,
    test_user,
    monkeypatch,
):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "integration-test-secret-key-123456789",
    )

    scan = WasteScan(
        user_id=test_user.id,
        image_url="https://example.com/security-test.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    attacker = User(
        name="Attacker",
        email=f"attacker_{uuid.uuid4().hex}@example.com",
        password_hash="test-hash",
    )

    db_session.add(attacker)
    db_session.commit()

    token = create_access_token({
        "sub": str(attacker.id),
        "role": attacker.role,
    })

    response = api_client.get(
        f"/scans/{scan.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


# ------------------------------------------------------------
# 7. Password hashing and verification
# ------------------------------------------------------------

def test_registered_password_is_securely_hashed(
    api_client,
    db_session,
):
    email = f"password_{uuid.uuid4().hex}@example.com"
    password = "SecurePassword@123"

    response = api_client.post(
        "/auth/register",
        json={
            "name": "Password Security User",
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 201

    stored_user = db_session.query(User).filter(
        User.email == email
    ).first()

    assert stored_user is not None
    assert stored_user.password_hash != password

    assert verify_password(
        password,
        stored_user.password_hash,
    )

    assert not verify_password(
        "WrongPassword@123",
        stored_user.password_hash,
    )

# ============================================================
# TEST 13: AUTHORIZATION & ACCESS CONTROL
# ============================================================

# 1. JWT claiming admin role cannot elevate a normal user
def test_jwt_admin_claim_cannot_elevate_normal_user(
    api_client,
    test_user,
    monkeypatch,
):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "recycliq-integration-test-secret-key-2026",
    )
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    token = create_access_token({
        "sub": str(test_user.id),
        "role": "admin",
    })

    response = api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    data = response.json()

    # Database role must override the JWT role claim.
    assert data["role"] == "user"


# 2. Database admin role must be reflected despite lower JWT claim
def test_database_role_overrides_jwt_role(
    api_client,
    db_session,
    monkeypatch,
):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "integration-test-secret-key-123456789",
    )

    admin = User(
        name="Database Admin",
        email=f"admin_{uuid.uuid4().hex}@example.com",
        password_hash="test-hash",
        role="admin",
    )

    db_session.add(admin)
    db_session.commit()

    token = create_access_token({
        "sub": str(admin.id),
        "role": "user",
    })

    response = api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


# 3. Tampered JWT must be rejected
def test_tampered_jwt_rejected(
    api_client,
    test_user,
    monkeypatch,
):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "integration-test-secret-key-123456789",
    )

    token = create_access_token({
        "sub": str(test_user.id),
        "role": "user",
    })

    tampered_token = token[:-5] + "xxxxx"

    response = api_client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {tampered_token}"
        },
    )

    assert response.status_code == 401


# 4. Missing authorization header must be rejected
def test_missing_authorization_header_rejected(api_client):
    response = api_client.get("/auth/me")

    assert response.status_code in (401, 403)


# 5. Scan history must only expose the authenticated user's records
def test_scan_history_user_data_isolation(
    api_client,
    db_session,
    test_user,
    monkeypatch,
):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "integration-test-secret-key-123456789",
    )

    another_user = User(
        name="Another User",
        email=f"another_{uuid.uuid4().hex}@example.com",
        password_hash="test-hash",
    )

    db_session.add(another_user)
    db_session.flush()

    own_scan = WasteScan(
        user_id=test_user.id,
        image_url="https://example.com/own.jpg",
        scan_status="completed",
    )

    other_scan = WasteScan(
        user_id=another_user.id,
        image_url="https://example.com/other.jpg",
        scan_status="completed",
    )

    db_session.add_all([own_scan, other_scan])
    db_session.commit()

    token = create_access_token({
        "sub": str(test_user.id),
        "role": "user",
    })

    response = api_client.get(
        "/scans/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_scans"] == 1
    assert len(data["scans"]) == 1

    assert data["scans"][0]["scan_id"] == str(own_scan.id)

    assert data["scans"][0]["scan_id"] != str(other_scan.id)