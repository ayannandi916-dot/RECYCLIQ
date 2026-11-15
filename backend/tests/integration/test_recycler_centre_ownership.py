import pytest
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.database.dependencies import get_db
from app.models.user import User
from app.models.recycling_centre import RecyclingCentre
from app.models.material import Material
from app.models.recycling_centre_material import RecyclingCentreMaterial
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


def create_test_centre(db_session, owner):
    centre = RecyclingCentre(
        owner_id=owner.id,
        name="Green Earth Recycling",
        address="12 Eco Park Road",
        city="Kolkata",
        state="West Bengal",
        postal_code="700001",
        latitude=22.5726,
        longitude=88.3639,
        contact_number="9876543210",
    )

    db_session.add(centre)
    db_session.commit()
    db_session.refresh(centre)

    return centre


def create_test_material(db_session):
    material = Material(
        name=f"Plastic-{uuid4()}",
        category="Plastic",
        description="Test recyclable material",
        recyclable=True,
        biodegradable=False,
    )

    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    return material


def get_auth_headers(user):
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
        }
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =========================================================
# OWNERSHIP IMMUTABILITY
# =========================================================

def test_recycler_cannot_transfer_centre_ownership(
    api_client,
    db_session,
):
    owner = create_test_user(db_session)
    another_recycler = create_test_user(db_session)

    centre = create_test_centre(db_session, owner)

    response = api_client.put(
        f"/recycler/centres/{centre.id}",
        json={
            "name": "Updated Centre",
            "owner_id": str(another_recycler.id),
        },
        headers=get_auth_headers(owner),
    )

    assert response.status_code == status.HTTP_200_OK

    db_session.refresh(centre)

    assert centre.owner_id == owner.id
    assert centre.name == "Updated Centre"


# =========================================================
# UNAUTHORIZED UPDATE INTEGRITY
# =========================================================

def test_unauthorized_update_does_not_modify_centre(
    api_client,
    db_session,
):
    owner = create_test_user(db_session)
    attacker = create_test_user(db_session)

    centre = create_test_centre(db_session, owner)

    original_name = centre.name
    original_city = centre.city

    response = api_client.put(
        f"/recycler/centres/{centre.id}",
        json={
            "name": "Unauthorized Modification",
            "city": "Unauthorized City",
        },
        headers=get_auth_headers(attacker),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

    db_session.refresh(centre)

    assert centre.name == original_name
    assert centre.city == original_city
    assert centre.owner_id == owner.id


# =========================================================
# UNAUTHORIZED DELETE INTEGRITY
# =========================================================

def test_unauthorized_delete_does_not_remove_centre(
    api_client,
    db_session,
):
    owner = create_test_user(db_session)
    attacker = create_test_user(db_session)

    centre = create_test_centre(db_session, owner)

    response = api_client.delete(
        f"/recycler/centres/{centre.id}",
        headers=get_auth_headers(attacker),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

    db_session.expire_all()

    existing_centre = db_session.get(
        RecyclingCentre,
        centre.id,
    )

    assert existing_centre is not None
    assert existing_centre.owner_id == owner.id


# =========================================================
# UNAUTHORIZED MATERIAL MODIFICATION
# =========================================================

def test_unauthorized_material_replacement_preserves_mappings(
    api_client,
    db_session,
):
    owner = create_test_user(db_session)
    attacker = create_test_user(db_session)

    centre = create_test_centre(db_session, owner)
    material = create_test_material(db_session)

    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(mapping)
    db_session.commit()

    response = api_client.put(
        f"/recycler/centres/{centre.id}/materials",
        json={"material_ids": []},
        headers=get_auth_headers(attacker),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

    db_session.expire_all()

    mappings = (
        db_session.query(RecyclingCentreMaterial)
        .filter_by(recycling_centre_id=centre.id)
        .all()
    )

    assert len(mappings) == 1
    assert mappings[0].material_id == material.id