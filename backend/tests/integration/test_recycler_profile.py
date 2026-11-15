import pytest
from uuid import uuid4
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.database.dependencies import get_db
from app.models.user import User
from app.models.recycler_application import RecyclerApplication
from app.utils.security import hash_password, create_access_token


def create_test_user(db_session, role="recycler"):
    user = User(
        name="Test Recycler",
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def create_approved_recycler(db_session):
    user = create_test_user(db_session, role="recycler")

    application = RecyclerApplication(
        user_id=user.id,
        business_name="Green Earth Recycling",
        contact_number="9876543210",
        business_address="12 Eco Park Road, Kolkata",
        city="Kolkata",
        state="West Bengal",
        postal_code="700001",
        registration_number="REG12345",
        website="https://example.com",
        status="approved",
    )

    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    return user, application


def get_auth_headers(user):
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
        }
    )

    return {"Authorization": f"Bearer {token}"}


def profile_payload(**overrides):
    payload = {
        "business_name": "Updated Green Recycling",
        "contact_number": "9123456789",
        "business_address": "25 New Town Road, Kolkata",
        "city": "Kolkata",
        "state": "West Bengal",
        "postal_code": "700100",
        "registration_number": "NEWREG123",
        "website": "https://greenrecycling.example.com",
    }

    payload.update(overrides)
    return payload


@pytest.fixture
def api_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =========================================================
# GET RECYCLER PROFILE
# =========================================================


def test_recycler_can_retrieve_own_profile(api_client, db_session):
    user, application = create_approved_recycler(db_session)

    response = api_client.get(
        "/recycler/profile",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user_id"] == str(user.id)
    assert response.json()["business_name"] == application.business_name
    


def test_recycler_only_sees_own_profile(api_client, db_session):
    user_one, application_one = create_approved_recycler(db_session)
    user_two, application_two = create_approved_recycler(db_session)

    response_one = api_client.get(
        "/recycler/profile",
        headers=get_auth_headers(user_one),
    )

    response_two = api_client.get(
        "/recycler/profile",
        headers=get_auth_headers(user_two),
    )

    assert response_one.status_code == status.HTTP_200_OK
    assert response_two.status_code == status.HTTP_200_OK

    assert response_one.json()["user_id"] == str(user_one.id)
    assert response_two.json()["user_id"] == str(user_two.id)

    assert response_one.json()["business_name"] == application_one.business_name
    assert response_two.json()["business_name"] == application_two.business_name


def test_recycler_profile_not_found_when_no_approved_application(
    api_client, db_session
):
    user = create_test_user(db_session, role="recycler")

    response = api_client.get(
        "/recycler/profile",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_regular_user_cannot_access_recycler_profile(
    api_client, db_session
):
    user = create_test_user(db_session, role="user")

    response = api_client.get(
        "/recycler/profile",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unauthenticated_user_cannot_access_recycler_profile(api_client):
    response = api_client.get("/recycler/profile")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =========================================================
# UPDATE RECYCLER PROFILE
# =========================================================


def test_recycler_can_update_own_profile(api_client, db_session):
    user, application = create_approved_recycler(db_session)

    response = api_client.put(
        "/recycler/profile",
        json=profile_payload(),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["business_name"] == "Updated Green Recycling"
    assert response.json()["contact_number"] == "9123456789"
    assert response.json()["city"] == "Kolkata"

    db_session.refresh(application)

    assert application.business_name == "Updated Green Recycling"
    assert application.contact_number == "9123456789"


def test_profile_update_does_not_change_approval_status(
    api_client, db_session
):
    user, application = create_approved_recycler(db_session)

    response = api_client.put(
        "/recycler/profile",
        json=profile_payload(),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_200_OK

    db_session.refresh(application)

    assert application.status == "approved"


def test_recycler_cannot_update_profile_without_approved_application(
    api_client, db_session
):
    user = create_test_user(db_session, role="recycler")

    response = api_client.put(
        "/recycler/profile",
        json=profile_payload(),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_regular_user_cannot_update_recycler_profile(
    api_client, db_session
):
    user = create_test_user(db_session, role="user")

    response = api_client.put(
        "/recycler/profile",
        json=profile_payload(),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_invalid_profile_payload_is_rejected(api_client, db_session):
    user, _ = create_approved_recycler(db_session)

    response = api_client.put(
        "/recycler/profile",
        json=profile_payload(business_name="A"),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_unauthenticated_user_cannot_update_recycler_profile(api_client):
    response = api_client.put(
        "/recycler/profile",
        json=profile_payload(),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED