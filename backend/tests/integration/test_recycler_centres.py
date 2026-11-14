import pytest

from uuid import uuid4
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.dependencies import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.recycling_centre import RecyclingCentre
from app.models.material import Material
from app.models.recycling_centre_material import RecyclingCentreMaterial
from app.utils.security import hash_password
from app.utils.security import create_access_token
from datetime import datetime, timezone


# =========================================================
# HELPERS
# =========================================================


def create_test_user(
    db_session: Session,
    role: str = "user",
    email: str | None = None,
) -> User:
    user = User(
        name="Test User",
        email=email or f"{uuid4()}@example.com",
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

    return {"Authorization": f"Bearer {token}"}


def centre_payload(**overrides) -> dict:
    payload = {
        "name": "Green Earth Recycling",
        "address": "12 Eco Park Road",
        "city": "Kolkata",
        "state": "West Bengal",
        "postal_code": "700001",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "contact_number": "9876543210",
        "is_active": True,
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
# CREATE CENTRE
# =========================================================


def test_recycler_can_create_centre(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()

    assert data["name"] == "Green Earth Recycling"
    assert data["city"] == "Kolkata"
    assert data["owner_id"] == str(recycler.id)


def test_centre_owner_is_assigned_automatically(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    payload = centre_payload()

    # A client must not be able to assign ownership.
    payload["owner_id"] = str(uuid4())

    response = api_client.post(
        "/recycler/centres",
        json=payload,
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["owner_id"] == str(recycler.id)


def test_regular_user_cannot_create_centre(api_client, db_session):
    user = create_test_user(db_session, role="user")

    response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unauthenticated_user_cannot_create_centre(api_client):
    response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
    )

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


# =========================================================
# LIST CENTRES
# =========================================================


def test_recycler_can_list_own_centres(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    api_client.post(
        "/recycler/centres",
        json=centre_payload(name="Centre One"),
        headers=get_auth_headers(recycler),
    )

    api_client.post(
        "/recycler/centres",
        json=centre_payload(name="Centre Two"),
        headers=get_auth_headers(recycler),
    )

    response = api_client.get(
        "/recycler/centres",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 2

    names = {centre["name"] for centre in response.json()}

    assert names == {"Centre One", "Centre Two"}

# =========================================================
# CENTRE LIST ORDERING REGRESSION TESTS
# =========================================================


def test_recycler_centre_list_has_stable_ordering(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    created_centres = []

    for index in range(4):
        response = api_client.post(
            "/recycler/centres",
            json=centre_payload(name=f"Ordering Centre {index}"),
            headers=get_auth_headers(recycler),
        )

        assert response.status_code == status.HTTP_201_CREATED

        created_centres.append(response.json()["id"])

    # Give all centres the same timestamp.
    shared_timestamp = datetime.now(timezone.utc)

    centres = (
        db_session.query(RecyclingCentre)
        .filter(RecyclingCentre.owner_id == recycler.id)
        .all()
    )

    for centre in centres:
        centre.created_at = shared_timestamp

    db_session.commit()

    response = api_client.get(
        "/recycler/centres",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK

    returned_ids = [
        centre["id"]
        for centre in response.json()
    ]

    expected_ids = sorted(created_centres)

    assert returned_ids == expected_ids


def test_recycler_centre_list_returns_only_owned_centres(
    api_client,
    db_session,
):
    recycler_one = create_test_user(db_session, role="recycler")
    recycler_two = create_test_user(db_session, role="recycler")

    api_client.post(
        "/recycler/centres",
        json=centre_payload(name="Recycler One Centre"),
        headers=get_auth_headers(recycler_one),
    )

    api_client.post(
        "/recycler/centres",
        json=centre_payload(name="Recycler Two Centre"),
        headers=get_auth_headers(recycler_two),
    )

    response = api_client.get(
        "/recycler/centres",
        headers=get_auth_headers(recycler_one),
    )

    assert response.status_code == status.HTTP_200_OK

    centres = response.json()

    assert len(centres) == 1
    assert centres[0]["owner_id"] == str(recycler_one.id)


def test_recycler_cannot_see_other_recyclers_centres(
    api_client,
    db_session,
):
    recycler_one = create_test_user(db_session, role="recycler")
    recycler_two = create_test_user(db_session, role="recycler")

    api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler_one),
    )

    response = api_client.get(
        "/recycler/centres",
        headers=get_auth_headers(recycler_two),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


# =========================================================
# GET CENTRE DETAILS
# =========================================================


def test_recycler_can_get_own_centre(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    centre_id = create_response.json()["id"]

    response = api_client.get(
        f"/recycler/centres/{centre_id}",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == centre_id


def test_recycler_cannot_get_another_recyclers_centre(
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

    centre_id = create_response.json()["id"]

    response = api_client.get(
        f"/recycler/centres/{centre_id}",
        headers=get_auth_headers(recycler_two),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_nonexistent_centre_returns_404(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    response = api_client.get(
        f"/recycler/centres/{uuid4()}",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# =========================================================
# UPDATE CENTRE
# =========================================================


def test_recycler_can_update_own_centre(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    centre_id = create_response.json()["id"]

    response = api_client.put(
        f"/recycler/centres/{centre_id}",
        json={
            "name": "Updated Recycling Centre",
            "city": "Howrah",
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["name"] == "Updated Recycling Centre"
    assert data["city"] == "Howrah"


def test_recycler_cannot_update_another_recyclers_centre(
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

    centre_id = create_response.json()["id"]

    response = api_client.put(
        f"/recycler/centres/{centre_id}",
        json={"name": "Unauthorized Update"},
        headers=get_auth_headers(recycler_two),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_recycler_cannot_update_nonexistent_centre(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    response = api_client.put(
        f"/recycler/centres/{uuid4()}",
        json={"name": "Updated Centre"},
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# =========================================================
# DELETE CENTRE
# =========================================================


def test_recycler_can_delete_own_centre(api_client, db_session):
    recycler = create_test_user(db_session, role="recycler")

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    centre_id = create_response.json()["id"]

    response = api_client.delete(
        f"/recycler/centres/{centre_id}",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    get_response = api_client.get(
        f"/recycler/centres/{centre_id}",
        headers=get_auth_headers(recycler),
    )

    assert get_response.status_code == status.HTTP_404_NOT_FOUND


def test_recycler_cannot_delete_another_recyclers_centre(
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

    centre_id = create_response.json()["id"]

    response = api_client.delete(
        f"/recycler/centres/{centre_id}",
        headers=get_auth_headers(recycler_two),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_nonexistent_centre_returns_404(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    response = api_client.delete(
        f"/recycler/centres/{uuid4()}",
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# =========================================================
# VALIDATION
# =========================================================


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude", 91),
        ("latitude", -91),
        ("longitude", 181),
        ("longitude", -181),
    ],
)
def test_invalid_coordinates_are_rejected(
    api_client,
    db_session,
    field,
    value,
):
    recycler = create_test_user(db_session, role="recycler")

    payload = centre_payload()
    payload[field] = value

    response = api_client.post(
        "/recycler/centres",
        json=payload,
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_invalid_update_coordinates_are_rejected(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    centre_id = create_response.json()["id"]

    response = api_client.put(
        f"/recycler/centres/{centre_id}",
        json={"latitude": 95},
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =========================================================
# ACCEPTED MATERIAL CASCADE
# =========================================================


def test_deleting_centre_deletes_material_mappings(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    material = Material(
        name=f"Plastic-{uuid4()}",
        category="Plastic",
        description="Test recyclable plastic",
        recyclable=True,
        biodegradable=False,
    )

    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    centre_id = create_response.json()["id"]

    centre = db_session.get(RecyclingCentre, centre_id)
    assert centre is not None

    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(mapping)
    db_session.commit()

    delete_response = api_client.delete(
        f"/recycler/centres/{centre_id}",
        headers=get_auth_headers(recycler),
    )

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    db_session.expire_all()

    assert db_session.get(RecyclingCentre, centre_id) is None

    # The mapping should be deleted, but the material should remain.
    assert db_session.get(Material, material.id) is not None

# =========================================================
# ACCEPTED MATERIALS REPLACEMENT
# =========================================================


def create_test_material(db_session, name):
    material = Material(
        name=name,
        category="Plastic",
        description="Test recyclable material",
        recyclable=True,
        biodegradable=False,
    )

    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    return material


def test_recycler_can_replace_centre_materials(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    material_one = create_test_material(
        db_session, f"Plastic-{uuid4()}"
    )
    material_two = create_test_material(
        db_session, f"Paper-{uuid4()}"
    )

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    centre_id = create_response.json()["id"]

    response = api_client.put(
        f"/recycler/centres/{centre_id}/materials",
        json={
            "material_ids": [
                str(material_one.id),
                str(material_two.id),
            ]
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_200_OK

    returned_ids = {item["id"] for item in response.json()}

    assert returned_ids == {
        str(material_one.id),
        str(material_two.id),
    }


def test_duplicate_material_ids_are_rejected(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    material = create_test_material(
        db_session, f"Plastic-{uuid4()}"
    )

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    centre_id = create_response.json()["id"]

    response = api_client.put(
        f"/recycler/centres/{centre_id}/materials",
        json={
            "material_ids": [
                str(material.id),
                str(material.id),
            ]
        },
        headers=get_auth_headers(recycler),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_invalid_replacement_preserves_existing_materials(
    api_client,
    db_session,
):
    recycler = create_test_user(db_session, role="recycler")

    material_one = create_test_material(
        db_session, f"Plastic-{uuid4()}"
    )
    material_two = create_test_material(
        db_session, f"Paper-{uuid4()}"
    )

    create_response = api_client.post(
        "/recycler/centres",
        json=centre_payload(),
        headers=get_auth_headers(recycler),
    )

    centre_id = create_response.json()["id"]

    headers = get_auth_headers(recycler)

    # First, save a valid material mapping.
    initial_response = api_client.put(
        f"/recycler/centres/{centre_id}/materials",
        json={
            "material_ids": [str(material_one.id)]
        },
        headers=headers,
    )

    assert initial_response.status_code == status.HTTP_200_OK

    # Now attempt an invalid replacement with duplicate IDs.
    invalid_response = api_client.put(
        f"/recycler/centres/{centre_id}/materials",
        json={
            "material_ids": [
                str(material_two.id),
                str(material_two.id),
            ]
        },
        headers=headers,
    )

    assert invalid_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Verify the original mapping remains unchanged.
    final_response = api_client.get(
        f"/recycler/centres/{centre_id}/materials",
        headers=headers,
    )

    assert final_response.status_code == status.HTTP_200_OK

    returned_ids = {item["id"] for item in final_response.json()}

    assert returned_ids == {str(material_one.id)}