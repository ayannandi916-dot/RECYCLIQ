import pytest
from uuid import uuid4
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.database.dependencies import get_db
from app.models.user import User
from app.models.recycler_application import RecyclerApplication
from app.utils.security import hash_password, create_access_token


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


def create_application(db_session, user, application_status="pending"):
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
        status=application_status,
    )

    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


def get_auth_headers(user):
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def rejection_payload():
    return {"reason": "Application does not meet the requirements."}


@pytest.fixture
def api_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =========================================================
# NONEXISTENT APPLICATION HANDLING
# =========================================================

def test_approving_nonexistent_application_returns_404(
    api_client, db_session
):
    admin = create_test_user(db_session, role="admin")

    response = api_client.post(
        f"/admin/recycler/applications/{uuid4()}/approve",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_rejecting_nonexistent_application_returns_404(
    api_client, db_session
):
    admin = create_test_user(db_session, role="admin")

    response = api_client.post(
        f"/admin/recycler/applications/{uuid4()}/reject",
        json=rejection_payload(),
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# =========================================================
# INVALID STATUS TRANSITIONS
# =========================================================

def test_rejected_application_cannot_be_approved(
    api_client, db_session
):
    admin = create_test_user(db_session, role="admin")
    applicant = create_test_user(db_session)

    application = create_application(
        db_session,
        applicant,
        application_status="rejected",
    )

    response = api_client.post(
        f"/admin/recycler/applications/{application.id}/approve",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_409_CONFLICT

    db_session.refresh(application)
    db_session.refresh(applicant)

    assert application.status == "rejected"
    assert applicant.role == "user"


def test_rejected_application_cannot_be_rejected_again(
    api_client, db_session
):
    admin = create_test_user(db_session, role="admin")
    applicant = create_test_user(db_session)

    application = create_application(
        db_session,
        applicant,
        application_status="rejected",
    )

    response = api_client.post(
        f"/admin/recycler/applications/{application.id}/reject",
        json=rejection_payload(),
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_approved_application_cannot_be_rejected(
    api_client, db_session
):
    admin = create_test_user(db_session, role="admin")
    applicant = create_test_user(db_session, role="recycler")

    application = create_application(
        db_session,
        applicant,
        application_status="approved",
    )

    response = api_client.post(
        f"/admin/recycler/applications/{application.id}/reject",
        json=rejection_payload(),
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_409_CONFLICT

    db_session.refresh(application)

    assert application.status == "approved"


# =========================================================
# REVIEW METADATA AND ROLE CONSISTENCY
# =========================================================

def test_rejection_preserves_applicant_role_and_records_review(
    api_client, db_session
):
    admin = create_test_user(db_session, role="admin")
    applicant = create_test_user(db_session)

    application = create_application(db_session, applicant)

    response = api_client.post(
        f"/admin/recycler/applications/{application.id}/reject",
        json=rejection_payload(),
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    db_session.refresh(application)
    db_session.refresh(applicant)

    assert application.status == "rejected"
    assert application.reviewed_by == admin.id
    assert application.reviewed_at is not None
    assert application.rejection_reason == rejection_payload()["reason"]
    assert applicant.role == "user"


def test_approval_records_reviewer_and_timestamp(
    api_client, db_session
):
    admin = create_test_user(db_session, role="admin")
    applicant = create_test_user(db_session)

    application = create_application(db_session, applicant)

    response = api_client.post(
        f"/admin/recycler/applications/{application.id}/approve",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == status.HTTP_200_OK

    db_session.refresh(application)
    db_session.refresh(applicant)

    assert application.status == "approved"
    assert application.reviewed_by == admin.id
    assert application.reviewed_at is not None
    assert application.rejection_reason is None
    assert applicant.role == "recycler"