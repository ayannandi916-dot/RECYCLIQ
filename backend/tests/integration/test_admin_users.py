from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import hash_password, create_access_token


# =========================================================
# HELPERS
# =========================================================

def create_test_user(
    db_session: Session,
    role: str = "user",
    is_active: bool = True,
    email: str | None = None,
) -> User:
    user = User(
        name="Test User",
        email=email or f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
        is_active=is_active,
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


# =========================================================
# AUTHORIZATION
# =========================================================

def test_admin_can_access_user_list(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        "/admin/users",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK


def test_regular_user_cannot_access_user_list(api_client, db_session):
    user = create_test_user(db_session, role="user")

    response = api_client.get(
        "/admin/users",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_recycler_cannot_access_user_list(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    response = api_client.get(
        "/admin/users",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unauthenticated_user_cannot_access_user_list(api_client):
    response = api_client.get("/admin/users")

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


# =========================================================
# USER LISTING
# =========================================================

def test_admin_can_list_users(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    # Record existing users before adding test users.
    baseline = api_client.get(
        "/admin/users",
        headers=get_auth_headers(admin),
    ).json()["total"]

    create_test_user(db_session, role="user")
    create_test_user(db_session, role="recycler")

    response = api_client.get(
        "/admin/users",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == baseline + 2
    assert len(data["users"]) == min(baseline + 2, 20)

def test_user_list_pagination(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    baseline = api_client.get(
        "/admin/users",
        headers=get_auth_headers(admin),
    ).json()["total"]

    for _ in range(5):
        create_test_user(db_session)

    response = api_client.get(
        "/admin/users?page=1&page_size=2",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    expected_total = baseline + 5

    assert len(data["users"]) == 2
    assert data["total"] == expected_total
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == (expected_total + 1) // 2

def test_user_list_role_filter(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    create_test_user(db_session, role="user")
    create_test_user(db_session, role="recycler")

    response = api_client.get(
        "/admin/users?role=recycler",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert all(user["role"] == "recycler" for user in data["users"])


def test_user_list_search(api_client, db_session):
    admin = create_test_user(
        db_session,
        role="admin",
        email="admin-search@example.com",
    )

    matching_user = User(
        name="UniqueSearchName",
        email="unique-search@example.com",
        password_hash=hash_password("TestPassword123!"),
        role="user",
        is_active=True,
    )

    db_session.add(matching_user)
    db_session.commit()

    response = api_client.get(
        "/admin/users?search=UniqueSearchName",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert data["users"][0]["name"] == "UniqueSearchName"


def test_invalid_pagination_rejected(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        "/admin/users?page=0",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =========================================================
# USER DETAILS
# =========================================================

def test_admin_can_get_user_details(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    user = create_test_user(db_session)

    response = api_client.get(
        f"/admin/users/{user.id}",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(user.id)
    assert response.json()["email"] == user.email


def test_nonexistent_user_returns_404(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        f"/admin/users/{uuid4()}",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_regular_user_cannot_get_user_details(api_client, db_session):
    user = create_test_user(db_session)
    target = create_test_user(db_session)

    response = api_client.get(
        f"/admin/users/{target.id}",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# =========================================================
# ACTIVATION
# =========================================================

def test_admin_can_activate_user(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    user = create_test_user(db_session, is_active=False)

    response = api_client.patch(
        f"/admin/users/{user.id}/activate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user"]["is_active"] is True

    db_session.refresh(user)
    assert user.is_active is True


def test_admin_can_deactivate_user(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    user = create_test_user(db_session)

    response = api_client.patch(
        f"/admin/users/{user.id}/deactivate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user"]["is_active"] is False

    db_session.refresh(user)
    assert user.is_active is False


def test_deactivated_user_cannot_use_existing_token(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")
    user = create_test_user(db_session)

    old_headers = get_auth_headers(user)

    deactivate_response = api_client.patch(
        f"/admin/users/{user.id}/deactivate",
        headers=get_auth_headers(admin),
    )

    assert deactivate_response.status_code == status.HTTP_200_OK

    response = api_client.get(
        "/auth/me",
        headers=old_headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_cannot_deactivate_own_account(api_client, db_session):
    admin = create_test_user(db_session, role="admin")

    response = api_client.patch(
        f"/admin/users/{admin.id}/deactivate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST

    db_session.refresh(admin)
    assert admin.is_active is True


def test_admin_cannot_deactivate_last_active_admin(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")

    another_admin = create_test_user(
        db_session,
        role="admin",
    )

    # Deactivate the first admin.
    first_response = api_client.patch(
        f"/admin/users/{admin.id}/deactivate",
        headers=get_auth_headers(another_admin),
    )

    assert first_response.status_code == status.HTTP_200_OK

    # The remaining active admin cannot be deactivated.
    second_response = api_client.patch(
        f"/admin/users/{another_admin.id}/deactivate",
        headers=get_auth_headers(another_admin),
    )

    assert second_response.status_code == status.HTTP_400_BAD_REQUEST


def test_admin_can_activate_already_active_user(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    user = create_test_user(db_session, is_active=True)

    response = api_client.patch(
        f"/admin/users/{user.id}/activate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user"]["is_active"] is True


def test_admin_can_deactivate_already_inactive_user(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")
    user = create_test_user(db_session, is_active=False)

    response = api_client.patch(
        f"/admin/users/{user.id}/deactivate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user"]["is_active"] is False