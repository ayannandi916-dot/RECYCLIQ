import pytest

from uuid import uuid4

from fastapi import status

from app.models.user import User
from app.models.material import Material
from app.models.recycling_centre import RecyclingCentre
from app.models.recycling_centre_material import RecyclingCentreMaterial

from app.utils.security import hash_password, create_access_token


# =========================================================
# HELPERS
# =========================================================


def create_test_user(db_session, role="user"):
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


def get_auth_headers(user):
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
        }
    )

    return {
        "Authorization": f"Bearer {token}"
    }


def create_test_material(db_session, name=None):
    # Every material gets a unique name because Material.name is unique.
    unique_name = f"{name or 'Material'}-{uuid4()}"

    material = Material(
        name=unique_name,
        category="Plastic",
        description="Test recyclable material",
        recyclable=True,
        biodegradable=False,
    )

    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    return material


def create_test_centre(db_session, recycler):
    centre = RecyclingCentre(
        owner_id=recycler.id,
        name="Green Earth Recycling",
        address="12 Eco Park Road",
        city="Kolkata",
        state="West Bengal",
        postal_code="700001",
        latitude=22.5726,
        longitude=88.3639,
        contact_number="9876543210",
        is_active=True,
    )

    db_session.add(centre)
    db_session.commit()
    db_session.refresh(centre)

    return centre


def assign_material(db_session, centre, material):
    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(mapping)
    db_session.commit()

    return mapping


# =========================================================
# GET ACCEPTED MATERIALS
# =========================================================


def test_recycler_can_get_accepted_materials(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    material_one = create_test_material(db_session, "Plastic")
    material_two = create_test_material(db_session, "Glass")

    assign_material(db_session, centre, material_one)
    assign_material(db_session, centre, material_two)

    response = api_client.get(
        f"/recycler/centres/{centre.id}/materials",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert len(data) == 2

    returned_ids = {
        material["id"] for material in data
    }

    assert returned_ids == {
        str(material_one.id),
        str(material_two.id),
    }


def test_recycler_gets_empty_material_list(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    response = api_client.get(
        f"/recycler/centres/{centre.id}/materials",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_recycler_cannot_get_another_recyclers_materials(
    api_client,
    db_session,
):
    recycler_one = create_test_user(db_session, role="recycler")
    recycler_two = create_test_user(db_session, role="recycler")

    centre = create_test_centre(db_session, recycler_one)

    response = api_client.get(
        f"/recycler/centres/{centre.id}/materials",
        headers=get_auth_headers(recycler_two),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# =========================================================
# ADD ACCEPTED MATERIALS
# =========================================================


def test_recycler_can_add_accepted_materials(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    material_one = create_test_material(db_session, "Plastic")
    material_two = create_test_material(db_session, "Glass")

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={
            "material_ids": [
                str(material_one.id),
                str(material_two.id),
            ]
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert len(data) == 2

    returned_ids = {
        material["id"] for material in data
    }

    assert returned_ids == {
        str(material_one.id),
        str(material_two.id),
    }


# =========================================================
# REPLACE ACCEPTED MATERIALS
# =========================================================


def test_recycler_can_replace_accepted_materials(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    plastic = create_test_material(db_session, "Plastic")
    glass = create_test_material(db_session, "Glass")
    metal = create_test_material(db_session, "Metal")

    assign_material(db_session, centre, plastic)
    assign_material(db_session, centre, glass)

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={
            "material_ids": [str(metal.id)]
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == str(metal.id)


def test_replacement_removes_old_mappings(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    plastic = create_test_material(db_session, "Plastic")
    glass = create_test_material(db_session, "Glass")

    assign_material(db_session, centre, plastic)

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={
            "material_ids": [str(glass.id)]
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK

    db_session.expire_all()

    mappings = (
        db_session.query(RecyclingCentreMaterial)
        .filter_by(recycling_centre_id=centre.id)
        .all()
    )

    assert len(mappings) == 1
    assert mappings[0].material_id == glass.id


# =========================================================
# CLEAR ACCEPTED MATERIALS
# =========================================================


def test_recycler_can_clear_accepted_materials(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    plastic = create_test_material(db_session, "Plastic")
    glass = create_test_material(db_session, "Glass")

    assign_material(db_session, centre, plastic)
    assign_material(db_session, centre, glass)

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={
            "material_ids": []
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []

    db_session.expire_all()

    mappings = (
        db_session.query(RecyclingCentreMaterial)
        .filter_by(recycling_centre_id=centre.id)
        .all()
    )

    assert mappings == []


# =========================================================
# VALIDATION
# =========================================================


def test_duplicate_material_ids_are_rejected(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    plastic = create_test_material(db_session, "Plastic")

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={
            "material_ids": [
                str(plastic.id),
                str(plastic.id),
            ]
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_nonexistent_material_id_is_rejected(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={
            "material_ids": [str(uuid4())]
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_invalid_request_preserves_existing_materials(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    plastic = create_test_material(db_session, "Plastic")

    assign_material(db_session, centre, plastic)

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={
            "material_ids": [str(uuid4())]
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

    db_session.expire_all()

    mappings = (
        db_session.query(RecyclingCentreMaterial)
        .filter_by(recycling_centre_id=centre.id)
        .all()
    )

    assert len(mappings) == 1
    assert mappings[0].material_id == plastic.id


# =========================================================
# ACCESS CONTROL
# =========================================================


def test_regular_user_cannot_get_centre_materials(
    api_client,
    db_session,
):
    user = create_test_user(db_session, role="user")
    centre = create_test_centre(db_session, user)

    response = api_client.get(
        f"/recycler/centres/{centre.id}/materials",
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_regular_user_cannot_update_centre_materials(
    api_client,
    db_session,
):
    user = create_test_user(db_session, role="user")
    centre = create_test_centre(db_session, user)

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={"material_ids": []},
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unauthenticated_user_cannot_get_materials(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")
    centre = create_test_centre(db_session, recycler)

    response = api_client.get(
        f"/recycler/centres/{centre.id}/materials"
    )

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_recycler_cannot_update_another_recyclers_materials(
    api_client,
    db_session,
):
    recycler_one = create_test_user(db_session, role="recycler")
    recycler_two = create_test_user(db_session, role="recycler")

    centre = create_test_centre(db_session, recycler_one)
    material = create_test_material(db_session, "Plastic")

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={
            "material_ids": [str(material.id)]
        },
        headers=get_auth_headers(recycler_two),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND