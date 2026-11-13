from uuid import uuid4

from fastapi import status
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import (
    hash_password,
    create_access_token,
)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def create_test_user(
    db_session: Session,
    role: str = "user",
) -> User:

    user = User(
        name="Analytics Test User",
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def get_auth_headers(user: User) -> dict:

    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
        }
    )

    return {
        "Authorization": f"Bearer {token}"
    }


# --------------------------------------------------
# AUTHORIZATION TESTS
# --------------------------------------------------

def test_unauthenticated_user_cannot_access_analytics(api_client):

    response = api_client.get(
        "/admin/analytics/overview"
    )

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_regular_user_cannot_access_analytics(
    api_client,
    db_session,
):

    user = create_test_user(
        db_session,
        role="user",
    )

    response = api_client.get(
        "/admin/analytics/overview",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_recycler_cannot_access_analytics(
    api_client,
    db_session,
):

    recycler = create_test_user(
        db_session,
        role="recycler",
    )

    response = api_client.get(
        "/admin/analytics/overview",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# --------------------------------------------------
# ADMIN ACCESS TESTS
# --------------------------------------------------

def test_admin_can_access_overview(
    api_client,
    db_session,
):

    admin = create_test_user(
        db_session,
        role="admin",
    )

    response = api_client.get(
        "/admin/analytics/overview",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert "users" in data
    assert "scans" in data
    assert "centres" in data
    assert "applications" in data


def test_admin_can_access_scan_analytics(
    api_client,
    db_session,
):

    admin = create_test_user(
        db_session,
        role="admin",
    )

    response = api_client.get(
        "/admin/analytics/scans",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert "total" in data
    assert "pending" in data
    assert "completed" in data
    assert "failed" in data


def test_admin_can_access_recycler_analytics(
    api_client,
    db_session,
):

    admin = create_test_user(
        db_session,
        role="admin",
    )

    response = api_client.get(
        "/admin/analytics/recyclers",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert "total_recyclers" in data
    assert "applications" in data


def test_admin_can_access_centre_analytics(
    api_client,
    db_session,
):

    admin = create_test_user(
        db_session,
        role="admin",
    )

    response = api_client.get(
        "/admin/analytics/centres",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert "total" in data
    assert "active" in data
    assert "inactive" in data
    assert "by_state" in data


def test_admin_can_access_object_analytics(
    api_client,
    db_session,
):

    admin = create_test_user(
        db_session,
        role="admin",
    )

    response = api_client.get(
        "/admin/analytics/objects",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert "total_objects" in data
    assert "average_confidence" in data
    assert "by_label" in data


def test_admin_can_access_recent_activity(
    api_client,
    db_session,
):

    admin = create_test_user(
        db_session,
        role="admin",
    )

    response = api_client.get(
        "/admin/analytics/activity",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert "total" in data
    assert "items" in data


def test_activity_limit_is_respected(
    api_client,
    db_session,
):

    admin = create_test_user(
        db_session,
        role="admin",
    )

    response = api_client.get(
        "/admin/analytics/activity?limit=5",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert len(data["items"]) <= 5


def test_activity_rejects_invalid_limit(
    api_client,
    db_session,
):

    admin = create_test_user(
        db_session,
        role="admin",
    )

    response = api_client.get(
        "/admin/analytics/activity?limit=500",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT