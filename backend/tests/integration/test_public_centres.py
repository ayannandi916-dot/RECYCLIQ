from uuid import uuid4

from fastapi import status

from app.models.user import User
from app.models.recycling_centre import RecyclingCentre
from app.models.material import Material
from app.models.recycling_centre_material import RecyclingCentreMaterial

from app.utils.security import hash_password


def create_user(db_session):
    user = User(
        name="Public Centre Test",
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role="recycler",
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def create_centre(
    db_session,
    owner,
    name="Test Recycling Centre",
    city="Kolkata",
    state="West Bengal",
    is_active=True,
):
    centre = RecyclingCentre(
        owner_id=owner.id,
        name=name,
        address="12 Eco Park Road",
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


def test_public_users_can_list_active_centres(
    api_client,
    db_session,
):
    recycler = create_user(db_session)

    centre = create_centre(db_session, recycler)

    response = api_client.get("/public/centres")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert any(
        item["id"] == str(centre.id)
        for item in data
    )


def test_public_listing_hides_inactive_centres(
    api_client,
    db_session,
):
    recycler = create_user(db_session)

    active = create_centre(
        db_session,
        recycler,
        name="Active Centre",
    )

    inactive = create_centre(
        db_session,
        recycler,
        name="Inactive Centre",
        is_active=False,
    )

    response = api_client.get("/public/centres")

    assert response.status_code == status.HTTP_200_OK

    returned_ids = {
        item["id"] for item in response.json()
    }

    assert str(active.id) in returned_ids
    assert str(inactive.id) not in returned_ids


def test_public_centres_can_be_filtered_by_city(
    api_client,
    db_session,
):
    recycler = create_user(db_session)

    kolkata = create_centre(
        db_session,
        recycler,
        name="Kolkata Centre",
        city="Kolkata",
    )

    create_centre(
        db_session,
        recycler,
        name="Delhi Centre",
        city="Delhi",
        state="Delhi",
    )

    response = api_client.get(
        "/public/centres",
        params={"city": "Kolkata"},
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == str(kolkata.id)


def test_public_centres_can_be_filtered_by_state(
    api_client,
    db_session,
):
    recycler = create_user(db_session)

    west_bengal = create_centre(
        db_session,
        recycler,
        name="West Bengal Centre",
        state="West Bengal",
    )

    create_centre(
        db_session,
        recycler,
        name="Delhi Centre",
        city="Delhi",
        state="Delhi",
    )

    response = api_client.get(
        "/public/centres",
        params={"state": "West Bengal"},
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == str(west_bengal.id)


def test_public_response_does_not_expose_owner_id(
    api_client,
    db_session,
):
    recycler = create_user(db_session)
    create_centre(db_session, recycler)

    response = api_client.get("/public/centres")

    assert response.status_code == status.HTTP_200_OK

    for centre in response.json():
        assert "owner_id" not in centre


def test_public_centre_includes_accepted_materials(
    api_client,
    db_session,
):
    recycler = create_user(db_session)
    centre = create_centre(db_session, recycler)

    material = Material(
        name=f"Plastic-{uuid4()}",
        category="Plastic",
        description="Recyclable plastic",
        recyclable=True,
        biodegradable=False,
    )

    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(mapping)
    db_session.commit()

    response = api_client.get("/public/centres")

    assert response.status_code == status.HTTP_200_OK

    centre_data = next(
        item for item in response.json()
        if item["id"] == str(centre.id)
    )

    assert len(centre_data["accepted_materials"]) == 1
    assert (
        centre_data["accepted_materials"][0]["id"]
        == str(material.id)
    )