from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.audit_log import AuditLog
from app.utils.security import hash_password, create_access_token
from app.services.audit_log_service import _make_json_safe

# =========================================================
# HELPERS
# =========================================================

def create_test_user(
    db_session: Session,
    role: str = "user",
    email: str | None = None,
) -> User:
    user = User(
        name="Test User",
        email=email or f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def get_auth_headers(user: User) -> dict:
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
    })

    return {"Authorization": f"Bearer {token}"}


def create_audit_log(
    db_session: Session,
    admin: User,
    action: str = "ACTIVATE",
    resource_type: str = "USER",
    resource_id=None,
    created_at: datetime | None = None,
) -> AuditLog:
    log = AuditLog(
        admin_id=admin.id,
        admin_email=admin.email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id or uuid4(),
        old_values={"is_active": False},
        new_values={"is_active": True},
        created_at=created_at or datetime.now(timezone.utc),
    )

    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    return log


# =========================================================
# AUTHORIZATION
# =========================================================

def test_admin_can_access_audit_logs(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        "/admin/audit-logs",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK


def test_regular_user_cannot_access_audit_logs(api_client, db_session):
    user = create_test_user(db_session, role="user")

    response = api_client.get(
        "/admin/audit-logs",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_recycler_cannot_access_audit_logs(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    response = api_client.get(
        "/admin/audit-logs",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unauthenticated_user_cannot_access_audit_logs(api_client):
    response = api_client.get("/admin/audit-logs")

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


# =========================================================
# LISTING AND PAGINATION
# =========================================================

def test_admin_can_list_audit_logs(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    log = create_audit_log(
        db_session,
        admin,
        action="APPROVE",
        resource_type="RECYCLER_APPLICATION",
    )

    response = api_client.get(
        f"/admin/audit-logs?admin_id={admin.id}",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert len(data["logs"]) == 1
    assert data["logs"][0]["id"] == str(log.id)
    assert data["logs"][0]["admin_email"] == admin.email
    assert data["logs"][0]["action"] == "APPROVE"


def test_audit_log_pagination(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    now = datetime.now(timezone.utc)

    for index in range(5):
        create_audit_log(
            db_session,
            admin,
            created_at=now + timedelta(seconds=index),
        )

    response = api_client.get(
        f"/admin/audit-logs?admin_id={admin.id}&page=1&page_size=2",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert len(data["logs"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 3


def test_audit_logs_are_returned_newest_first(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    now = datetime.now(timezone.utc)

    older = create_audit_log(
        db_session,
        admin,
        created_at=now,
    )

    newer = create_audit_log(
        db_session,
        admin,
        created_at=now + timedelta(minutes=5),
    )

    response = api_client.get(
        f"/admin/audit-logs?admin_id={admin.id}",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    logs = response.json()["logs"]

    assert len(logs) == 2
    assert logs[0]["id"] == str(newer.id)
    assert logs[1]["id"] == str(older.id)


# =========================================================
# FILTERING
# =========================================================

def test_filter_audit_logs_by_action(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    create_audit_log(db_session, admin, action="APPROVE")
    create_audit_log(db_session, admin, action="REJECT")

    response = api_client.get(
        f"/admin/audit-logs?admin_id={admin.id}&action=APPROVE",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert all(log["action"] == "APPROVE" for log in data["logs"])


def test_filter_audit_logs_by_resource_type(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    create_audit_log(
        db_session,
        admin,
        resource_type="USER",
    )

    create_audit_log(
        db_session,
        admin,
        resource_type="RECYCLER_APPLICATION",
    )

    response = api_client.get(
        f"/admin/audit-logs?admin_id={admin.id}&resource_type=USER",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert all(
        log["resource_type"] == "USER"
        for log in data["logs"]
    )

def test_filter_audit_logs_by_admin(api_client, db_session):
    admin_one = create_test_user(db_session, role="admin")
    admin_two = create_test_user(db_session, role="admin")

    create_audit_log(db_session, admin_one)
    create_audit_log(db_session, admin_two)

    response = api_client.get(
        f"/admin/audit-logs?admin_id={admin_one.id}",
        headers=get_auth_headers(admin_one),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert data["logs"][0]["admin_id"] == str(admin_one.id)


def test_filter_audit_logs_by_date_range(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    now = datetime.now(timezone.utc)

    create_audit_log(
        db_session,
        admin,
        created_at=now - timedelta(days=5),
    )

    matching_log = create_audit_log(
        db_session,
        admin,
        created_at=now,
    )

    create_audit_log(
        db_session,
        admin,
        created_at=now + timedelta(days=5),
    )

    response = api_client.get(
        "/admin/audit-logs",
        params={
            "admin_id": str(admin.id),
            "start_date": (now - timedelta(hours=1)).isoformat(),
            "end_date": (now + timedelta(hours=1)).isoformat(),
        },
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert data["logs"][0]["id"] == str(matching_log.id)


@pytest.mark.parametrize(
    "query",
    [
        "?page=0",
        "?page_size=0",
        "?page_size=101",
    ],
)
def test_invalid_pagination_is_rejected(api_client, db_session, query):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        f"/admin/audit-logs{query}",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_invalid_date_range_is_rejected(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    now = datetime.now(timezone.utc)

    response = api_client.get(
        "/admin/audit-logs",
        params={
            "start_date": (now + timedelta(days=2)).isoformat(),
            "end_date": now.isoformat(),
        },
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

# =========================================================
# AUDIT SECURITY TESTS
# =========================================================

from app.services.audit_log_service import _make_json_safe


def test_sensitive_fields_are_removed():
    data = {
        "name": "Test User",
        "password": "secret",
        "password_hash": "hashed",
        "access_token": "abc",
        "client_secret": "xyz",
        "api-key": "key",
        "private_key": "private",
        "otp_code": "123456",
    }

    result = _make_json_safe(data)

    assert result == {
        "name": "Test User",
    }


def test_sensitive_fields_are_removed_recursively():
    data = {
        "user": {
            "name": "Test",
            "password": "secret",
        },
        "tokens": [
            {"accessToken": "abc"},
            {"refresh_token": "xyz"},
        ],
    }

    result = _make_json_safe(data)

    assert result == {
        "user": {
            "name": "Test",
        },
        "tokens": [
            {},
            {},
        ],
    }


def test_non_finite_floats_are_json_safe():
    data = {
        "valid": 10.5,
        "nan": float("nan"),
        "positive_infinity": float("inf"),
        "negative_infinity": float("-inf"),
    }

    result = _make_json_safe(data)

    assert result["valid"] == 10.5
    assert result["nan"] is None
    assert result["positive_infinity"] is None
    assert result["negative_infinity"] is None


def test_sensitive_field_matching_is_case_insensitive():
    data = {
        "PASSWORD": "secret",
        "AccessToken": "abc",
        "API_KEY": "key",
        "normal_field": "visible",
    }

    result = _make_json_safe(data)

    assert result == {
        "normal_field": "visible",
    }