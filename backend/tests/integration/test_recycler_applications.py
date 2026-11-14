import pytest
from uuid import uuid4
from fastapi import status

from app.models.recycler_application import RecyclerApplication
from app.models.user import User
from app.utils.security import hash_password, create_access_token
from unittest.mock import Mock
from sqlalchemy.exc import IntegrityError

from app.services.recycler_service import submit_application
from app.schemas.recycler import RecyclerApplicationCreate


def create_test_user(db_session, role="user"):
    user = User(
        name="Test User",
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def get_auth_headers(user):
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def application_payload(**overrides):
    payload = {
        "business_name": "Green Earth Recycling",
        "contact_number": "9876543210",
        "business_address": "12 Eco Park Road, Kolkata",
        "city": "Kolkata",
        "state": "West Bengal",
        "postal_code": "700001",
        "registration_number": "REG12345",
        "website": "https://example.com",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def api_client(db_session):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database.dependencies import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_user_can_submit_application(api_client, db_session):
    user = create_test_user(db_session)

    response = api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["user_id"] == str(user.id)
    assert response.json()["status"] == "pending"


def test_user_can_retrieve_own_application(api_client, db_session):
    user = create_test_user(db_session)

    api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=get_auth_headers(user),
    )

    response = api_client.get(
        "/recycler/application",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user_id"] == str(user.id)


def test_user_cannot_retrieve_another_users_application(
    api_client, db_session
):
    user_one = create_test_user(db_session)
    user_two = create_test_user(db_session)

    api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=get_auth_headers(user_one),
    )

    response = api_client.get(
        "/recycler/application",
        headers=get_auth_headers(user_two),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_user_cannot_edit_another_users_application(
    api_client, db_session
):
    user_one = create_test_user(db_session)
    user_two = create_test_user(db_session)

    api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=get_auth_headers(user_one),
    )

    response = api_client.put(
        "/recycler/application",
        json=application_payload(
            business_name="Unauthorized Business"
        ),
        headers=get_auth_headers(user_two),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_pending_application_cannot_be_edited(api_client, db_session):
    user = create_test_user(db_session)

    api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=get_auth_headers(user),
    )

    response = api_client.put(
        "/recycler/application",
        json=application_payload(
            business_name="Updated Business"
        ),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_duplicate_pending_application_is_rejected(
    api_client, db_session
):
    user = create_test_user(db_session)

    first_response = api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=get_auth_headers(user),
    )

    second_response = api_client.post(
        "/recycler/apply",
        json=application_payload(
            business_name="Another Business"
        ),
        headers=get_auth_headers(user),
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_409_CONFLICT


def test_invalid_application_payload_is_rejected(
    api_client, db_session
):
    user = create_test_user(db_session)

    response = api_client.post(
        "/recycler/apply",
        json=application_payload(business_name="A"),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_non_user_cannot_submit_application(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    response = api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN

def test_concurrent_application_integrity_error_returns_409():
    user = Mock()
    user.id = uuid4()
    user.role = "user"

    data = RecyclerApplicationCreate(**application_payload())

    db = Mock()

    # First query: no existing application.
    # Second query: another request has created one.
    db.scalar.side_effect = [None, Mock()]

    db.commit.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("Unique constraint violation"),
    )

    with pytest.raises(Exception) as exc_info:
        submit_application(db, user, data)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    db.rollback.assert_called_once()
    assert db.scalar.call_count == 2