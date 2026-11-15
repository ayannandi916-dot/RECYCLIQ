
from uuid import uuid4

from fastapi import status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.material import Material
from app.models.recycler_application import RecyclerApplication

from app.utils.security import hash_password, create_access_token


# =========================================================
# HELPERS
# =========================================================

def create_test_user(
    db_session: Session,
    role: str = "user",
) -> User:
    user = User(
        name="Workflow Test User",
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

    return {
        "Authorization": f"Bearer {token}"
    }


def application_payload():
    return {
        "business_name": "Green Earth Recycling",
        "contact_number": "9876543210",
        "business_address": "12 Eco Park Road, Kolkata",
        "city": "Kolkata",
        "state": "West Bengal",
        "postal_code": "700001",
        "registration_number": f"REG-{uuid4().hex[:8]}",
        "website": "https://example.com",
    }


def centre_payload():
    return {
        "name": "Green Earth Recycling Centre",
        "address": "12 Eco Park Road",
        "city": "Kolkata",
        "state": "West Bengal",
        "postal_code": "700001",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "contact_number": "9876543210",
    }


def create_test_material(db_session):
    material = Material(
        name=f"Workflow Plastic {uuid4()}",
        category="Plastic",
        description="Recyclable plastic",
        recyclable=True,
        biodegradable=False,
    )

    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    return material


# =========================================================
# COMPLETE RECYCLER ONBOARDING WORKFLOW
# =========================================================

def test_complete_recycler_onboarding_workflow(
    api_client,
    db_session,
):
    # 1. Create a regular user and an admin.
    user = create_test_user(db_session, role="user")
    admin = create_test_user(db_session, role="admin")

    user_headers = get_auth_headers(user)
    admin_headers = get_auth_headers(admin)

    # 2. User submits recycler application.
    application_response = api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=user_headers,
    )

    assert application_response.status_code == status.HTTP_201_CREATED

    application_data = application_response.json()

    application_id = application_data["id"]

    assert application_data["status"] == "pending"
    assert application_data["user_id"] == str(user.id)

    # 3. Admin retrieves pending applications.
    list_response = api_client.get(
        "/admin/recycler/applications",
        params={"application_status": "pending"},
        headers=admin_headers,
    )

    assert list_response.status_code == status.HTTP_200_OK

    assert any(
        item["id"] == application_id
        for item in list_response.json()
    )

    # 4. Admin approves the application.
    approval_response = api_client.post(
        f"/admin/recycler/applications/{application_id}/approve",
        headers=admin_headers,
    )

    assert approval_response.status_code == status.HTTP_200_OK
    assert approval_response.json()["status"] == "approved"

    # 5. Verify the user's database role changed.
    db_session.refresh(user)

    assert user.role == "recycler"

    # Generate a fresh token after the role transition.
    recycler_headers = get_auth_headers(user)

    # 6. Approved recycler creates a recycling centre.
    centre_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=recycler_headers,
    )

    assert centre_response.status_code == status.HTTP_201_CREATED

    centre_data = centre_response.json()
    centre_id = centre_data["id"]

    assert centre_data["owner_id"] == str(user.id)
    assert centre_data["name"] == "Green Earth Recycling Centre"

    # 7. Recycler adds an accepted material.
    material = create_test_material(db_session)

    material_response = api_client.put(
        f"/recycler/centres/{centre_id}/materials",
        json={
            "material_ids": [str(material.id)]
        },
        headers=recycler_headers,
    )

    assert material_response.status_code == status.HTTP_200_OK

    assert any(
        item["id"] == str(material.id)
        for item in material_response.json()
    )

    # 8. Verify centre appears in public discovery.
    public_response = api_client.get(
        "/public/centres",
        params={"city": "Kolkata"},
    )

    assert public_response.status_code == status.HTTP_200_OK

    public_centres = public_response.json()

    visible_centre = next(
        (
            centre
            for centre in public_centres
            if centre["id"] == centre_id
        ),
        None,
    )

    assert visible_centre is not None

    assert any(
        item["id"] == str(material.id)
        for item in visible_centre["accepted_materials"]
    )

    # 9. Admin deactivates the centre.
    deactivate_response = api_client.patch(
        f"/admin/centres/{centre_id}/deactivate",
        headers=admin_headers,
    )

    assert deactivate_response.status_code == status.HTTP_200_OK
    assert deactivate_response.json()["is_active"] is False

    # 10. Inactive centre must disappear from public discovery.
    hidden_response = api_client.get(
        "/public/centres",
        params={"city": "Kolkata"},
    )

    assert hidden_response.status_code == status.HTTP_200_OK

    assert not any(
        centre["id"] == centre_id
        for centre in hidden_response.json()
    )

    # 11. Admin activates the centre again.
    activate_response = api_client.patch(
        f"/admin/centres/{centre_id}/activate",
        headers=admin_headers,
    )

    assert activate_response.status_code == status.HTTP_200_OK
    assert activate_response.json()["is_active"] is True

    # 12. Verify centre is publicly visible again.
    final_response = api_client.get(
        "/public/centres",
        params={"city": "Kolkata"},
    )

    assert final_response.status_code == status.HTTP_200_OK

    assert any(
        centre["id"] == centre_id
        for centre in final_response.json()
    )


# =========================================================
# PENDING APPLICATION RESTRICTIONS
# =========================================================

def test_pending_applicant_cannot_create_recycling_centre(
    api_client,
    db_session,
):
    user = create_test_user(db_session, role="user")

    application_response = api_client.post(
        "/recycler/apply",
        json=application_payload(),
        headers=get_auth_headers(user),
    )

    assert application_response.status_code == status.HTTP_201_CREATED

    response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# =========================================================
# RECYCLER CENTRE OWNERSHIP WORKFLOW
# =========================================================

def test_recycler_cannot_modify_another_recyclers_centre(
    api_client,
    db_session,
):
    recycler_one = create_test_user(db_session, role="recycler")
    recycler_two = create_test_user(db_session, role="recycler")

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler_one),
    )

    assert create_response.status_code == status.HTTP_201_CREATED

    centre_id = create_response.json()["id"]

    # Recycler two attempts to modify recycler one's centre.
    update_response = api_client.put(
        f"/recycler/centres/{centre_id}",
        json={"name": "Unauthorized Modification"},
        headers=get_auth_headers(recycler_two),
    )

    assert update_response.status_code == status.HTTP_404_NOT_FOUND

    # Recycler two attempts to delete the centre.
    delete_response = api_client.delete(
        f"/recycler/centres/{centre_id}",
        headers=get_auth_headers(recycler_two),
    )

    assert delete_response.status_code == status.HTTP_404_NOT_FOUND

    # Original owner must still be able to retrieve it.
    owner_response = api_client.get(
        f"/recycler/centres/{centre_id}",
        headers=get_auth_headers(recycler_one),
    )

    assert owner_response.status_code == status.HTTP_200_OK

    assert owner_response.json()["name"] == "Green Earth Recycling Centre"
