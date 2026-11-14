from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.recycling_centre import RecyclingCentre
from app.utils.security import hash_password, create_access_token


# =========================================================
# HELPERS
# =========================================================

def create_test_user(
    db_session: Session,
    role: str = "user",
) -> User:
    user = User(
        name="Admin Centre Test User",
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
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


def create_test_centre(
    db_session: Session,
    owner_id,
    name: str = "Test Recycling Centre",
    city: str = "Kolkata",
    state: str = "West Bengal",
    is_active: bool = True,
):
    centre = RecyclingCentre(
        owner_id=owner_id,
        name=f"{name}-{uuid4().hex[:6]}",
        address="123 Test Road",
        city=city,
        state=state,
        postal_code="700001",
        latitude=22.5726,
        longitude=88.3639,
        contact_number="9876543210",
        is_active=is_active,
    )

    db_session.add(centre)
    db_session.commit()
    db_session.refresh(centre)

    return centre


# =========================================================
# LIST CENTRES
# =========================================================

def test_admin_can_list_all_centres(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    create_test_centre(db_session, recycler.id)
    create_test_centre(db_session, recycler.id)

    response = api_client.get(
        "/admin/centres",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data


def test_admin_can_search_centres(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    centre = create_test_centre(
        db_session,
        recycler.id,
        name="Searchable Centre",
    )

    response = api_client.get(
        "/admin/centres",
        params={"search": centre.name},
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] >= 1
    assert any(
        item["id"] == str(centre.id)
        for item in data["items"]
    )


# =========================================================
# FILTER CENTRES
# =========================================================

def test_admin_can_filter_active_centres(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    active_centre = create_test_centre(
        db_session,
        recycler.id,
        is_active=True,
    )

    create_test_centre(
        db_session,
        recycler.id,
        is_active=False,
    )

    response = api_client.get(
        "/admin/centres",
        params={"is_active": True},
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert all(item["is_active"] is True for item in data["items"])
    assert any(
        item["id"] == str(active_centre.id)
        for item in data["items"]
    )


def test_admin_can_filter_inactive_centres(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    inactive_centre = create_test_centre(
        db_session,
        recycler.id,
        is_active=False,
    )

    response = api_client.get(
        "/admin/centres",
        params={"is_active": False},
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert all(item["is_active"] is False for item in data["items"])
    assert any(
        item["id"] == str(inactive_centre.id)
        for item in data["items"]
    )


# =========================================================
# GET CENTRE DETAILS
# =========================================================

def test_admin_can_get_centre_details(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    centre = create_test_centre(db_session, recycler.id)

    response = api_client.get(
        f"/admin/centres/{centre.id}",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(centre.id)


def test_admin_get_nonexistent_centre_returns_404(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        f"/admin/centres/{uuid4()}",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# =========================================================
# ACTIVATE / DEACTIVATE
# =========================================================

def test_admin_can_activate_centre(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    centre = create_test_centre(
        db_session,
        recycler.id,
        is_active=False,
    )

    response = api_client.patch(
        f"/admin/centres/{centre.id}/activate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_active"] is True


def test_admin_can_deactivate_centre(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    centre = create_test_centre(
        db_session,
        recycler.id,
        is_active=True,
    )

    response = api_client.patch(
        f"/admin/centres/{centre.id}/deactivate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_active"] is False


def test_admin_can_activate_already_active_centre(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    centre = create_test_centre(
        db_session,
        recycler.id,
        is_active=True,
    )

    response = api_client.patch(
        f"/admin/centres/{centre.id}/activate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_active"] is True


def test_admin_can_deactivate_already_inactive_centre(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    centre = create_test_centre(
        db_session,
        recycler.id,
        is_active=False,
    )

    response = api_client.patch(
        f"/admin/centres/{centre.id}/deactivate",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_active"] is False


# =========================================================
# AUTHORIZATION
# =========================================================

def test_non_admin_cannot_list_centres(api_client, db_session):
    user = create_test_user(db_session, role="user")

    response = api_client.get(
        "/admin/centres",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unauthenticated_user_cannot_list_centres(api_client):
    response = api_client.get("/admin/centres")

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_non_admin_cannot_activate_centre(api_client, db_session):
    user = create_test_user(db_session, role="user")
    recycler = create_test_user(db_session, role="recycler")

    centre = create_test_centre(db_session, recycler.id)

    response = api_client.patch(
        f"/admin/centres/{centre.id}/activate",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# =========================================================
# PAGINATION
# =========================================================

def test_admin_centre_pagination(api_client, db_session):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    for _ in range(5):
        create_test_centre(db_session, recycler.id)

    headers = get_auth_headers(admin)

    # First page
    response_1 = api_client.get(
        "/admin/centres",
        params={"page": 1, "page_size": 2},
        headers=headers,
    )

    assert response_1.status_code == status.HTTP_200_OK

    data_1 = response_1.json()

    assert data_1["page"] == 1
    assert data_1["page_size"] == 2
    assert len(data_1["items"]) == 2
    assert data_1["total"] == 5

    # Middle page
    response_2 = api_client.get(
        "/admin/centres",
        params={"page": 2, "page_size": 2},
        headers=headers,
    )

    assert response_2.status_code == status.HTTP_200_OK

    data_2 = response_2.json()

    assert data_2["page"] == 2
    assert len(data_2["items"]) == 2

    # Last page
    response_3 = api_client.get(
        "/admin/centres",
        params={"page": 3, "page_size": 2},
        headers=headers,
    )

    assert response_3.status_code == status.HTTP_200_OK

    data_3 = response_3.json()

    assert data_3["page"] == 3
    assert len(data_3["items"]) == 1

    # No duplicate records across pages
    all_ids = (
        [item["id"] for item in data_1["items"]]
        + [item["id"] for item in data_2["items"]]
        + [item["id"] for item in data_3["items"]]
    )

    assert len(all_ids) == 5
    assert len(set(all_ids)) == 5

def test_admin_centre_pagination_has_stable_tie_breaker(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")
    recycler = create_test_user(db_session, role="recycler")

    centres = [
        create_test_centre(db_session, recycler.id)
        for _ in range(4)
    ]

    # Give every centre exactly the same timestamp.
    shared_timestamp = centres[0].created_at

    for centre in centres:
        centre.created_at = shared_timestamp

    db_session.commit()

    response = api_client.get(
        "/admin/centres",
        params={"page": 1, "page_size": 10},
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    returned_ids = [
        item["id"]
        for item in response.json()["items"]
    ]

    expected_ids = sorted(
        str(centre.id)
        for centre in centres
    )

    assert returned_ids == expected_ids

def test_admin_centre_invalid_pagination_returns_422(
    api_client,
    db_session,
):
    admin = create_test_user(db_session, role="admin")

    response = api_client.get(
        "/admin/centres",
        params={"page": 0},
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT