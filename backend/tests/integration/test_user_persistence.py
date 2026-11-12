import os
import uuid

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import (
    User,
    WasteScan,
    ScanObject,
    Material,
    ScanObjectMaterial,
    Recommendation,
)
from sqlalchemy.exc import IntegrityError
from app.models import (
    RecyclingCentre,
    RecyclingCentreMaterial,
)

from fastapi.testclient import TestClient

from app.main import app
from app.database.dependencies import get_db
from app.utils.security import create_access_token, hash_password




    


def test_create_and_retrieve_user(db_session):
    """Verify that a user can be inserted and retrieved from PostgreSQL."""

    unique_email = f"integration_{uuid.uuid4().hex}@recycliq.test"

    user = User(
        name="Integration Test User",
        email=unique_email,
        password_hash="integration-test-hash",
        role="user",
    )

    db_session.add(user)
    db_session.commit()

    assert user.id is not None

    retrieved_user = db_session.execute(
        select(User).where(User.email == unique_email)
    ).scalar_one_or_none()

    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.name == "Integration Test User"
    assert retrieved_user.email == unique_email
    assert retrieved_user.password_hash == "integration-test-hash"
    assert retrieved_user.role == "user"


def test_delete_user(db_session):
    """Verify that a persisted user can be deleted."""

    unique_email = f"delete_{uuid.uuid4().hex}@recycliq.test"

    user = User(
        name="User To Delete",
        email=unique_email,
        password_hash="integration-test-hash",
        role="user",
    )

    db_session.add(user)
    db_session.commit()

    user_id = user.id

    db_session.delete(user)
    db_session.commit()

    deleted_user = db_session.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    assert deleted_user is None


def test_user_default_role(db_session):
    """Verify that the database applies the default user role."""

    unique_email = f"default_{uuid.uuid4().hex}@recycliq.test"

    user = User(
        name="Default Role User",
        email=unique_email,
        password_hash="integration-test-hash",
    )

    db_session.add(user)
    db_session.commit()

    retrieved_user = db_session.execute(
        select(User).where(User.email == unique_email)
    ).scalar_one()

    assert retrieved_user.role == "user"

def test_duplicate_email_rejected(db_session):
    """PostgreSQL must reject duplicate email addresses."""

    email = f"duplicate_{uuid.uuid4().hex}@recycliq.test"

    user1 = User(
        name="First User",
        email=email,
        password_hash="test-hash",
        role="user",
    )

    db_session.add(user1)
    db_session.commit()

    user2 = User(
        name="Second User",
        email=email,
        password_hash="another-hash",
        role="user",
    )

    db_session.add(user2)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    users = db_session.execute(
        select(User).where(User.email == email)
    ).scalars().all()

    assert len(users) == 1
    assert users[0].name == "First User"


def test_null_name_rejected(db_session):
    """PostgreSQL must reject a user without a name."""

    user = User(
        name=None,
        email=f"null_name_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
        role="user",
    )

    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_null_email_rejected(db_session):
    """PostgreSQL must reject a user without an email."""

    user = User(
        name="Missing Email User",
        email=None,
        password_hash="test-hash",
        role="user",
    )

    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_failed_insert_does_not_persist(db_session):
    """A failed insert must not leave a partial database record."""

    email = f"rollback_{uuid.uuid4().hex}@recycliq.test"

    user = User(
        name=None,
        email=email,
        password_hash="test-hash",
        role="user",
    )

    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    retrieved_user = db_session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()

    assert retrieved_user is None

def test_create_and_retrieve_waste_scan(db_session):
    """Verify that a waste scan can be persisted and retrieved."""

    user = User(
        name="Scan Test User",
        email=f"scan_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
        role="user",
    )

    db_session.add(user)
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/test-waste.jpg",
        scan_status="pending",
    )

    db_session.add(scan)
    db_session.commit()

    retrieved_scan = db_session.execute(
        select(WasteScan).where(WasteScan.id == scan.id)
    ).scalar_one()

    assert retrieved_scan.user_id == user.id
    assert retrieved_scan.image_url == (
        "https://example.com/test-waste.jpg"
    )
    assert retrieved_scan.scan_status == "pending"


def test_user_scan_relationship(db_session):
    """Verify that a user can access their scans through the ORM relationship."""

    user = User(
        name="Relationship Test User",
        email=f"relationship_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
        role="user",
    )

    db_session.add(user)
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/relationship-test.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    db_session.refresh(user)

    assert len(user.waste_scans) == 1
    assert user.waste_scans[0].image_url == (
        "https://example.com/relationship-test.jpg"
    )


def test_scan_with_invalid_user_rejected(db_session):
    """Verify that PostgreSQL rejects scans referencing nonexistent users."""

    scan = WasteScan(
        user_id=uuid.uuid4(),
        image_url="https://example.com/invalid-user.jpg",
        scan_status="pending",
    )

    db_session.add(scan)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_deleting_user_cascades_to_scans(db_session):
    """Verify that deleting a user also deletes their associated scans."""

    user = User(
        name="Cascade Test User",
        email=f"cascade_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
        role="user",
    )

    db_session.add(user)
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/cascade-test.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    scan_id = scan.id

    db_session.delete(user)
    db_session.commit()

    remaining_scan = db_session.execute(
        select(WasteScan).where(WasteScan.id == scan_id)
    ).scalar_one_or_none()

    assert remaining_scan is None

def test_create_detected_object(db_session):
    """Verify that a detected object is linked to its waste scan."""

    user = User(
        name="Detection Test User",
        email=f"detection_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )

    db_session.add(user)
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/detection.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    detected_object = ScanObject(
        scan_id=scan.id,
        object_label="PLASTIC",
        detection_confidence=0.95,
        bounding_box={
            "x1": 10,
            "y1": 20,
            "x2": 100,
            "y2": 120,
        },
    )

    db_session.add(detected_object)
    db_session.commit()

    retrieved = db_session.get(ScanObject, detected_object.id)

    assert retrieved is not None
    assert retrieved.scan_id == scan.id
    assert retrieved.object_label == "PLASTIC"
    assert retrieved.detection_confidence == 0.95
    assert retrieved.bounding_box["x1"] == 10


def test_link_detected_object_to_material(db_session):
    """Verify material classification persistence."""

    user = User(
        name="Material Test User",
        email=f"material_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )

    material = Material(
        name=f"Plastic_{uuid.uuid4().hex}",
        category="Plastic",
        description="Recyclable plastic",
    )

    db_session.add_all([user, material])
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/material.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    detected_object = ScanObject(
        scan_id=scan.id,
        object_label="PLASTIC",
        detection_confidence=0.96,
        bounding_box={"x1": 10, "y1": 20, "x2": 100, "y2": 120},
    )

    db_session.add(detected_object)
    db_session.commit()

    classification = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=material.id,
        confidence_score=0.96,
        quantity_estimate=2.5,
        quantity_unit="kg",
    )

    db_session.add(classification)
    db_session.commit()

    retrieved = db_session.get(
        ScanObjectMaterial,
        classification.id,
    )

    assert retrieved is not None
    assert retrieved.scan_object_id == detected_object.id
    assert retrieved.material_id == material.id
    assert retrieved.confidence_score == 0.96
    assert retrieved.quantity_estimate == 2.5


def test_invalid_detection_confidence_rejected(db_session):
    """Verify confidence scores above 1 are rejected."""

    user = User(
        name="Invalid Confidence User",
        email=f"confidence_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )

    db_session.add(user)
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/confidence.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    detected_object = ScanObject(
        scan_id=scan.id,
        object_label="PLASTIC",
        detection_confidence=1.5,
        bounding_box={"x1": 10, "y1": 20, "x2": 100, "y2": 120},
    )

    db_session.add(detected_object)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_duplicate_material_classification_rejected(db_session):
    """Verify duplicate material classifications are rejected."""

    user = User(
        name="Duplicate Classification User",
        email=f"duplicate_class_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )

    material = Material(
        name=f"Glass_{uuid.uuid4().hex}",
        category="Glass",
    )

    db_session.add_all([user, material])
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/duplicate.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    detected_object = ScanObject(
        scan_id=scan.id,
        object_label="GLASS",
        detection_confidence=0.9,
        bounding_box={"x1": 10, "y1": 20, "x2": 100, "y2": 120},
    )

    db_session.add(detected_object)
    db_session.commit()

    classification1 = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=material.id,
        confidence_score=0.9,
    )

    db_session.add(classification1)
    db_session.commit()

    classification2 = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=material.id,
        confidence_score=0.85,
    )

    db_session.add(classification2)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    classifications = db_session.execute(
        select(ScanObjectMaterial).where(
            ScanObjectMaterial.scan_object_id == detected_object.id
        )
    ).scalars().all()

    assert len(classifications) == 1


def test_deleting_scan_cascades_to_detected_objects(db_session):
    """Verify deleting a scan removes its detected objects."""

    user = User(
        name="Cascade Detection User",
        email=f"cascade_detection_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )

    db_session.add(user)
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/cascade.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    detected_object = ScanObject(
        scan_id=scan.id,
        object_label="PAPER",
        detection_confidence=0.88,
        bounding_box={"x1": 10, "y1": 20, "x2": 100, "y2": 120},
    )

    db_session.add(detected_object)
    db_session.commit()

    object_id = detected_object.id

    db_session.delete(scan)
    db_session.commit()

    remaining_object = db_session.get(ScanObject, object_id)

    assert remaining_object is None

def create_detected_object(db_session):
    """Create a user, scan and detected object for recommendation tests."""

    user = User(
        name="Recommendation Test User",
        email=f"recommendation_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )

    db_session.add(user)
    db_session.commit()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/recommendation.jpg",
        scan_status="completed",
    )

    db_session.add(scan)
    db_session.commit()

    detected_object = ScanObject(
        scan_id=scan.id,
        object_label="PLASTIC",
        detection_confidence=0.95,
        bounding_box={"x1": 10, "y1": 20, "x2": 100, "y2": 120},
    )

    db_session.add(detected_object)
    db_session.commit()

    return detected_object
    
def test_create_and_retrieve_recommendation(db_session):
    """Verify recommendation persistence."""

    detected_object = create_detected_object(db_session)

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="reuse",
        title="Reuse Plastic Container",
        description="Use the container for household storage.",
        difficulty_level="easy",
        estimated_co2_saved=1.5,
    )

    db_session.add(recommendation)
    db_session.commit()

    retrieved = db_session.get(Recommendation, recommendation.id)

    assert retrieved is not None
    assert retrieved.recommendation_type == "reuse"
    assert retrieved.title == "Reuse Plastic Container"
    assert retrieved.difficulty_level == "easy"
    assert retrieved.estimated_co2_saved == 1.5


def test_recommendation_relationship(db_session):
    """Verify detected objects expose their recommendations."""

    detected_object = create_detected_object(db_session)

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="recycle",
        title="Recycle Plastic",
        description="Send plastic to a recycling facility.",
        difficulty_level="easy",
        estimated_co2_saved=2.0,
    )

    db_session.add(recommendation)
    db_session.commit()
    db_session.refresh(detected_object)

    assert len(detected_object.recommendations) == 1
    assert detected_object.recommendations[0].title == "Recycle Plastic"


def test_invalid_recommendation_type_rejected(db_session):
    """Verify invalid recommendation types are rejected."""

    detected_object = create_detected_object(db_session)

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="throw_away",
        title="Invalid Recommendation",
        description="This type should not be accepted.",
        difficulty_level="easy",
        estimated_co2_saved=1.0,
    )

    db_session.add(recommendation)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_invalid_difficulty_level_rejected(db_session):
    """Verify invalid difficulty levels are rejected."""

    detected_object = create_detected_object(db_session)

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="reuse",
        title="Invalid Difficulty",
        description="Testing difficulty constraints.",
        difficulty_level="extreme",
        estimated_co2_saved=1.0,
    )

    db_session.add(recommendation)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_negative_co2_savings_rejected(db_session):
    """Verify negative CO2 savings are rejected."""

    detected_object = create_detected_object(db_session)

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="recycle",
        title="Negative CO2",
        description="Testing CO2 constraints.",
        difficulty_level="medium",
        estimated_co2_saved=-5.0,
    )

    db_session.add(recommendation)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_deleting_detected_object_cascades_to_recommendations(
    db_session
):
    """Verify deleting a detected object deletes its recommendations."""

    detected_object = create_detected_object(db_session)

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="upcycle",
        title="Create Something New",
        description="Turn the waste into a useful product.",
        difficulty_level="medium",
        estimated_co2_saved=3.0,
    )

    db_session.add(recommendation)
    db_session.commit()

    recommendation_id = recommendation.id

    db_session.delete(detected_object)
    db_session.commit()

    remaining = db_session.get(Recommendation, recommendation_id)

    assert remaining is None

def create_recycling_centre(db_session):
    centre = RecyclingCentre(
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

    return centre

def create_recycler(db_session):
    recycler = User(
        name="Integration Recycler",
        email=f"recycler_{uuid.uuid4().hex}@recycliq.test",
        password_hash="integration-test-hash",
        role="recycler"
    )

    db_session.add(recycler)
    db_session.commit()

    return recycler



def create_material(db_session):
    material = Material(
        name=f"Plastic_{uuid.uuid4().hex[:8]}",
        category="Plastic",
        description="Recyclable plastic material",
        recyclable=True,
        biodegradable=False,
    )

    db_session.add(material)
    db_session.commit()

    return material

def test_create_and_retrieve_recycling_centre(db_session):
    centre = create_recycling_centre(db_session)

    retrieved = db_session.get(RecyclingCentre, centre.id)

    assert retrieved is not None
    assert retrieved.name == "Green Earth Recycling"
    assert retrieved.city == "Kolkata"
    assert retrieved.state == "West Bengal"
    assert retrieved.is_active is True


def test_recycling_centre_coordinates_persist(db_session):
    centre = create_recycling_centre(db_session)

    retrieved = db_session.get(RecyclingCentre, centre.id)

    assert retrieved.latitude == pytest.approx(22.5726)
    assert retrieved.longitude == pytest.approx(88.3639)


def test_link_material_to_recycling_centre(db_session):
    centre = create_recycling_centre(db_session)
    material = create_material(db_session)

    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(mapping)
    db_session.commit()

    retrieved = db_session.get(RecyclingCentreMaterial, mapping.id)

    assert retrieved is not None
    assert retrieved.recycling_centre_id == centre.id
    assert retrieved.material_id == material.id


def test_invalid_latitude_rejected(db_session):
    centre = RecyclingCentre(
        name="Invalid Latitude Centre",
        address="Test Address",
        city="Kolkata",
        state="West Bengal",
        latitude=95.0,
        longitude=88.3639,
    )

    db_session.add(centre)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_invalid_longitude_rejected(db_session):
    centre = RecyclingCentre(
        name="Invalid Longitude Centre",
        address="Test Address",
        city="Kolkata",
        state="West Bengal",
        latitude=22.5726,
        longitude=190.0,
    )

    db_session.add(centre)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_duplicate_centre_material_mapping_rejected(db_session):
    centre = create_recycling_centre(db_session)
    material = create_material(db_session)

    first_mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(first_mapping)
    db_session.commit()

    duplicate_mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(duplicate_mapping)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_deleting_centre_cascades_to_material_mappings(db_session):
    centre = create_recycling_centre(db_session)
    material = create_material(db_session)

    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(mapping)
    db_session.commit()

    mapping_id = mapping.id

    db_session.delete(centre)
    db_session.commit()

    assert db_session.get(
        RecyclingCentreMaterial,
        mapping_id
    ) is None

    # The material itself must remain.
    assert db_session.get(Material, material.id) is not None

def test_complete_user_scan_object_relationship_chain(db_session):
    """Verify User -> WasteScan -> ScanObject relationships."""

    detected_object = create_detected_object(db_session)

    scan = db_session.get(WasteScan, detected_object.scan_id)
    user = db_session.get(User, scan.user_id)

    assert scan is not None
    assert user is not None

    assert scan.user.id == user.id
    assert detected_object.scan.id == scan.id

    assert detected_object in scan.detected_objects
    assert scan in user.waste_scans


def test_detected_object_material_relationship(db_session):
    """Verify detected objects are linked to their classified materials."""

    detected_object = create_detected_object(db_session)
    material = create_material(db_session)

    classification = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=material.id,
        confidence_score=0.96,
        quantity_estimate=2.5,
        quantity_unit="kg",
    )

    db_session.add(classification)
    db_session.commit()

    db_session.refresh(detected_object)

    assert len(detected_object.material_classifications) == 1

    linked_classification = detected_object.material_classifications[0]

    assert linked_classification.material_id == material.id
    assert linked_classification.material.name == material.name
    assert linked_classification.confidence_score == 0.96


def test_detected_object_recommendation_relationship(db_session):
    """Verify recommendations are associated with detected objects."""

    detected_object = create_detected_object(db_session)

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="upcycle",
        title="Create a Plant Holder",
        description="Reuse the plastic container as a plant holder.",
        difficulty_level="easy",
        estimated_co2_saved=2.5,
    )

    db_session.add(recommendation)
    db_session.commit()

    db_session.refresh(detected_object)

    assert len(detected_object.recommendations) == 1

    linked_recommendation = detected_object.recommendations[0]

    assert linked_recommendation.title == "Create a Plant Holder"
    assert linked_recommendation.scan_object_id == detected_object.id


def test_recycling_centre_accepted_material_relationship(db_session):
    """Verify recycling centres expose their accepted materials."""

    centre = create_recycling_centre(db_session)
    material = create_material(db_session)

    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(mapping)
    db_session.commit()

    db_session.refresh(centre)

    assert len(centre.accepted_materials) == 1

    accepted_mapping = centre.accepted_materials[0]

    assert accepted_mapping.material_id == material.id
    assert accepted_mapping.material.name == material.name


def test_invalid_material_foreign_key_rejected(db_session):
    """Verify classifications cannot reference nonexistent materials."""

    detected_object = create_detected_object(db_session)

    classification = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=uuid.uuid4(),
        confidence_score=0.90,
        quantity_estimate=1.0,
    )

    db_session.add(classification)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_full_user_deletion_cascades_through_scan_hierarchy(db_session):
    """
    Verify deleting a user removes scans, detected objects,
    classifications and recommendations.
    """

    detected_object = create_detected_object(db_session)

    scan = db_session.get(WasteScan, detected_object.scan_id)
    user = db_session.get(User, scan.user_id)

    material = create_material(db_session)

    classification = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=material.id,
        confidence_score=0.95,
        quantity_estimate=1.5,
    )

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="recycle",
        title="Recycle This Material",
        description="Send the detected material for recycling.",
        difficulty_level="easy",
        estimated_co2_saved=1.5,
    )

    db_session.add_all([classification, recommendation])
    db_session.commit()

    scan_id = scan.id
    object_id = detected_object.id
    classification_id = classification.id
    recommendation_id = recommendation.id
    user_id = user.id
    material_id = material.id

    db_session.delete(user)
    db_session.commit()

    assert db_session.get(User, user_id) is None
    assert db_session.get(WasteScan, scan_id) is None
    assert db_session.get(ScanObject, object_id) is None

    assert db_session.get(
        ScanObjectMaterial,
        classification_id
    ) is None

    assert db_session.get(
        Recommendation,
        recommendation_id
    ) is None

    # Deleting the user must NOT delete the shared material.
    assert db_session.get(Material, material_id) is not None

def test_rollback_removes_complete_related_transaction(db_session):
    user = User(
        name="Rollback User",
        email=f"rollback_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )
    db_session.add(user)
    db_session.flush()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/rollback.jpg",
        scan_status="completed",
    )
    db_session.add(scan)
    db_session.flush()

    detected_object = ScanObject(
        scan_id=scan.id,
        object_label="PLASTIC",
        detection_confidence=0.95,
        bounding_box={"x1": 1, "y1": 2, "x2": 10, "y2": 20},
    )
    db_session.add(detected_object)
    db_session.flush()

    user_id = user.id
    scan_id = scan.id
    object_id = detected_object.id

    db_session.rollback()

    assert db_session.get(User, user_id) is None
    assert db_session.get(WasteScan, scan_id) is None
    assert db_session.get(ScanObject, object_id) is None

def test_failed_transaction_leaves_no_partial_records(db_session):
    user = User(
        name="Failed Transaction User",
        email=f"failed_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )
    db_session.add(user)
    db_session.flush()

    scan = WasteScan(
        user_id=user.id,
        image_url="https://example.com/failed.jpg",
        scan_status="completed",
    )
    db_session.add(scan)
    db_session.flush()

    invalid_object = ScanObject(
        scan_id=scan.id,
        object_label="PLASTIC",
        detection_confidence=1.5,
        bounding_box={"x1": 1, "y1": 2, "x2": 10, "y2": 20},
    )
    db_session.add(invalid_object)

    user_id = user.id
    scan_id = scan.id

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    assert db_session.get(User, user_id) is None
    assert db_session.get(WasteScan, scan_id) is None

def test_material_deletion_restricted_by_classification(db_session):
    detected_object = create_detected_object(db_session)
    material = create_material(db_session)

    classification = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=material.id,
        confidence_score=0.95,
        quantity_estimate=2.0,
    )

    db_session.add(classification)
    db_session.commit()

    material_id = material.id

    db_session.delete(material)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    assert db_session.get(Material, material_id) is not None

def test_material_deletion_restricted_by_recycling_centre(db_session):
    centre = create_recycling_centre(db_session)
    material = create_material(db_session)

    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add(mapping)
    db_session.commit()

    material_id = material.id

    db_session.delete(material)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    assert db_session.get(Material, material_id) is not None

def test_user_can_have_multiple_scans(db_session):
    user = User(
        name="Multiple Scan User",
        email=f"multiscan_{uuid.uuid4().hex}@recycliq.test",
        password_hash="test-hash",
    )

    db_session.add(user)
    db_session.commit()

    scans = [
        WasteScan(
            user_id=user.id,
            image_url=f"https://example.com/scan_{i}.jpg",
            scan_status="completed",
        )
        for i in range(3)
    ]

    db_session.add_all(scans)
    db_session.commit()
    db_session.refresh(user)

    assert len(user.waste_scans) == 3
    assert all(scan.user_id == user.id for scan in user.waste_scans)

def test_scan_can_have_multiple_detected_objects(db_session):
    first_object = create_detected_object(db_session)
    scan = db_session.get(WasteScan, first_object.scan_id)

    second_object = ScanObject(
        scan_id=scan.id,
        object_label="PAPER",
        detection_confidence=0.88,
        bounding_box={"x1": 20, "y1": 30, "x2": 80, "y2": 90},
    )

    third_object = ScanObject(
        scan_id=scan.id,
        object_label="METAL",
        detection_confidence=0.92,
        bounding_box={"x1": 40, "y1": 50, "x2": 100, "y2": 120},
    )

    db_session.add_all([second_object, third_object])
    db_session.commit()
    db_session.refresh(scan)

    assert len(scan.detected_objects) == 3

    labels = {obj.object_label for obj in scan.detected_objects}

    assert labels == {"PLASTIC", "PAPER", "METAL"}

def test_material_deletion_after_removing_references(db_session):
    detected_object = create_detected_object(db_session)
    centre = create_recycling_centre(db_session)
    material = create_material(db_session)

    classification = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=material.id,
        confidence_score=0.95,
        quantity_estimate=1.0,
    )

    mapping = RecyclingCentreMaterial(
        recycling_centre_id=centre.id,
        material_id=material.id,
    )

    db_session.add_all([classification, mapping])
    db_session.commit()

    material_id = material.id

    db_session.delete(classification)
    db_session.delete(mapping)
    db_session.commit()

    db_session.delete(material)
    db_session.commit()

    assert db_session.get(Material, material_id) is None
# ============================================================
# FASTAPI + REAL POSTGRESQL INTEGRATION TESTS
# ============================================================

from fastapi.testclient import TestClient

from app.main import app
from app.database.dependencies import get_db
from app.utils.security import create_access_token, hash_password


@pytest.fixture
def api_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(get_db, None)


# 1. Registration persists user in PostgreSQL
def test_api_registration_persists_user(api_client, db_session):
    email = f"api_{uuid.uuid4().hex}@example.com"

    response = api_client.post(
        "/auth/register",
        json={
            "name": "API Integration User",
            "email": email,
            "password": "TestPassword@123",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == email
    assert data["name"] == "API Integration User"
    assert data["role"] == "user"

    stored_user = db_session.query(User).filter(
        User.email == email
    ).first()

    assert stored_user is not None
    assert stored_user.password_hash != "TestPassword@123"


# 2. Duplicate registration is rejected
def test_api_duplicate_registration_rejected(api_client):
    email = f"duplicate_{uuid.uuid4().hex}@example.com"

    payload = {
        "name": "Duplicate Test",
        "email": email,
        "password": "TestPassword@123",
    }

    first = api_client.post("/auth/register", json=payload)
    second = api_client.post("/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409

    assert second.json()["detail"] == (
        "Email is already registered!"
    )


# 3. Login and authenticated user profile
def test_api_login_and_authenticated_profile(
    api_client,
    db_session,
):
    email = f"login_{uuid.uuid4().hex}@example.com"
    password = "TestPassword@123"

    user = User(
        name="Login Integration User",
        email=email,
        password_hash=hash_password(password),
    )

    db_session.add(user)
    db_session.commit()

    login_response = api_client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    assert token

    profile_response = api_client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == email
    assert profile_response.json()["name"] == "Login Integration User"


# 4. Invalid login is rejected
def test_api_invalid_login_rejected(api_client, db_session):
    email = f"wrong_password_{uuid.uuid4().hex}@example.com"

    user = User(
        name="Invalid Login User",
        email=email,
        password_hash=hash_password("CorrectPassword@123"),
    )

    db_session.add(user)
    db_session.commit()

    response = api_client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "WrongPassword@123",
        },
    )

    assert response.status_code == 401


# 5. Scan history requires authentication
def test_api_scan_history_requires_authentication(api_client):
    response = api_client.get("/scans/history")

    assert response.status_code in (401, 403)


# 6. Scan history retrieves real database records
def test_api_scan_history_from_database(
    api_client,
    db_session,
):
    user = User(
        name="Scan History User",
        email=f"history_{uuid.uuid4().hex}@example.com",
        password_hash="test-hash",
    )

    db_session.add(user)
    db_session.flush()

    scans = [
        WasteScan(
            user_id=user.id,
            image_url=f"https://example.com/history_{i}.jpg",
            scan_status="completed",
        )
        for i in range(3)
    ]

    db_session.add_all(scans)
    db_session.commit()

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
    })

    response = api_client.get(
        "/scans/history",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_scans"] == 3
    assert len(data["scans"]) == 3

    returned_ids = {
        scan["scan_id"] for scan in data["scans"]
    }

    expected_ids = {
        str(scan.id) for scan in scans
    }

    assert returned_ids == expected_ids


# 7. Scan details retrieve complete related database records
def test_api_scan_details_with_real_relationships(
    api_client,
    db_session,
):
    detected_object = create_detected_object(db_session)

    scan = db_session.get(
        WasteScan,
        detected_object.scan_id,
    )

    user = db_session.get(User, scan.user_id)

    material = create_material(db_session)

    classification = ScanObjectMaterial(
        scan_object_id=detected_object.id,
        material_id=material.id,
        confidence_score=0.96,
        quantity_estimate=2.5,
        quantity_unit="kg",
    )

    recommendation = Recommendation(
        scan_object_id=detected_object.id,
        recommendation_type="recycle",
        title="Recycle Plastic",
        description="Send this material to a recycling facility.",
        difficulty_level="easy",
        estimated_co2_saved=2.0,
    )

    db_session.add_all([
        classification,
        recommendation,
    ])

    db_session.commit()

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
    })

    response = api_client.get(
        f"/scans/{scan.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()["scan"]

    assert data["scan_id"] == str(scan.id)
    assert data["total_detected_objects"] == 1
    assert data["total_recommendations"] == 1

    detected = data["detected_objects"][0]

    assert detected["object_label"] == "PLASTIC"

    assert detected["materials"][0]["material_name"] == (
        material.name
    )

    assert detected["recommendations"][0]["title"] == (
        "Recycle Plastic"
    )

def test_recycler_can_own_multiple_centres(db_session):
    recycler = create_recycler(db_session)

    centre1 = RecyclingCentre(
        name="Green Earth Recycling",
        address="12 Eco Park Road",
        city="Kolkata",
        state="West Bengal",
        latitude=22.5726,
        longitude=88.3639,
        owner=recycler
    )

    centre2 = RecyclingCentre(
        name="Eco Waste Solutions",
        address="24 Salt Lake",
        city="Kolkata",
        state="West Bengal",
        latitude=22.5800,
        longitude=88.4200,
        owner=recycler
    )

    db_session.add_all([centre1, centre2])
    db_session.commit()
    db_session.refresh(recycler)

    assert len(recycler.recycling_centres) == 2

    assert centre1.owner_id == recycler.id
    assert centre2.owner_id == recycler.id

    assert centre1.owner.id == recycler.id
    assert centre2.owner.id == recycler.id

def test_different_recyclers_have_separate_centres(db_session):
    recycler1 = create_recycler(db_session)
    recycler2 = create_recycler(db_session)

    centre1 = create_recycling_centre(db_session)
    centre2 = create_recycling_centre(db_session)

    centre1.owner = recycler1
    centre2.owner = recycler2

    db_session.commit()

    db_session.refresh(recycler1)
    db_session.refresh(recycler2)

    assert len(recycler1.recycling_centres) == 1
    assert len(recycler2.recycling_centres) == 1

    assert recycler1.recycling_centres[0].id == centre1.id
    assert recycler2.recycling_centres[0].id == centre2.id

def test_deleting_recycler_with_owned_centres_is_restricted(
    db_session
):
    recycler = create_recycler(db_session)

    centre = create_recycling_centre(db_session)
    centre.owner = recycler

    db_session.commit()

    recycler_id = recycler.id
    centre_id = centre.id

    db_session.delete(recycler)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    assert db_session.get(User, recycler_id) is not None
    assert db_session.get(RecyclingCentre, centre_id) is not None