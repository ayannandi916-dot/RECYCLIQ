
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
) -> User:
    user = User(
        name="Permission Test User",
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
        is_active=is_active,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def get_auth_headers(user: User, token_role: str | None = None) -> dict:
    token = create_access_token({
        "sub": str(user.id),
        "role": token_role or user.role,
    })

    return {"Authorization": f"Bearer {token}"}


# =========================================================
# RECYCLER ROLE
# =========================================================

@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/recycler/centres"),
        ("post", "/recycler/centres"),
    ],
)
def test_regular_user_cannot_access_recycler_centre_routes(
    api_client,
    db_session,
    method,
    path,
):
    user = create_test_user(db_session, role="user")
    headers = get_auth_headers(user)

    if method == "post":
        response = api_client.post(
            path,
            json={},
            headers=headers,
        )
    else:
        response = api_client.get(
            path,
            headers=headers,
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_cannot_use_recycler_centre_routes(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        "/recycler/centres",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_recycler_can_access_recycler_centre_routes(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    response = api_client.get(
        "/recycler/centres",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK


# =========================================================
# ADMIN ROLE
# =========================================================

@pytest.mark.parametrize(
    "path",
    [
        "/admin/centres",
        "/admin/recycler/applications",
    ],
)
@pytest.mark.parametrize("role", ["user", "recycler"])
def test_non_admin_cannot_access_admin_routes(
    api_client,
    db_session,
    path,
    role,
):
    user = create_test_user(db_session, role=role)

    response = api_client.get(
        path,
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_can_access_admin_centre_routes(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        "/admin/centres",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK


# =========================================================
# TOKEN ROLE TAMPERING
# =========================================================

def test_user_cannot_gain_recycler_access_by_changing_token_role(
    api_client,
    db_session,
):
    user = create_test_user(db_session, role="user")

    headers = get_auth_headers(user, token_role="recycler")

    response = api_client.get(
        "/recycler/centres",
        headers=headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_recycler_cannot_gain_admin_access_by_changing_token_role(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    headers = get_auth_headers(recycler, token_role="admin")

    response = api_client.get(
        "/admin/centres",
        headers=headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# =========================================================
# ACCOUNT STATUS
# =========================================================

def test_deactivated_recycler_cannot_access_recycler_routes(
    api_client,
    db_session,
):
    recycler = create_test_user(
        db_session,
        role="recycler",
        is_active=False,
    )

    response = api_client.get(
        "/recycler/centres",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_deactivated_admin_cannot_access_admin_routes(
    api_client,
    db_session,
):
    admin = create_test_user(
        db_session,
        role="admin",
        is_active=False,
    )

    response = api_client.get(
        "/admin/centres",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# =========================================================
# UNAUTHENTICATED ACCESS
# =========================================================

@pytest.mark.parametrize(
    "path",
    [
        "/recycler/centres",
        "/admin/centres",
        "/admin/recycler/applications",
    ],
)
def test_unauthenticated_requests_are_rejected(
    api_client,
    path,
):
    response = api_client.get(path)

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )
