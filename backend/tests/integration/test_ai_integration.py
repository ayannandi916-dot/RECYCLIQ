import uuid
from io import BytesIO

import pytest

from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.database.dependencies import get_db
from app.api.dependencies import get_current_user
from app.utils.security import create_access_token

from app.models import (
    User,
    WasteScan,
    ScanObject,
    ScanObjectMaterial,
    Material,
    Recommendation,
)

from app.api import ai


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def ai_user(db_session):
    user = User(
        name="AI Integration User",
        email=f"ai_{uuid.uuid4().hex}@example.com",
        password_hash="test-hash",
        role="user",
    )

    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def ai_client(db_session, ai_user, monkeypatch):

    def override_db():
        yield db_session

    def override_user():
        return ai_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    # Generate a valid in-memory JPEG.
    image = Image.new("RGB", (100, 100), color="red")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    image_bytes = buffer.getvalue()

    # Mock Cloudinary upload.
    monkeypatch.setattr(
        ai,
        "upload_image",
        lambda file: {
            "image_url": "https://example.com/test-image.jpg",
            "public_id": "test-image",
        },
    )

    # Avoid threadpool execution during mocked tests.
    async def fake_threadpool(func, *args):
        return func(*args)

    monkeypatch.setattr(
        ai,
        "run_in_threadpool",
        fake_threadpool,
    )

    # Mock YOLO detection.
    monkeypatch.setattr(
        ai,
        "detect_waste",
        lambda image: {
            "image_width": 100,
            "image_height": 100,
            "detections": [
                {
                    "class_id": 5,
                    "label": "PLASTIC",
                    "confidence": 0.95,
                    "bounding_box": {
                        "x1": 10,
                        "y1": 20,
                        "x2": 80,
                        "y2": 90,
                    },
                }
            ],
        },
    )

    # Mock recommendation generation.
    monkeypatch.setattr(
        ai,
        "generate_recommendations",
        lambda material: [
            {
                "recommendation_type": "reuse",
                "title": "Reuse Plastic Container",
                "description": "Reuse the container at home.",
                "difficulty_level": "easy",
                "estimated_co2_saved": 1.5,
            },
            {
                "recommendation_type": "recycle",
                "title": "Recycle Plastic",
                "description": "Send plastic to a recycling centre.",
                "difficulty_level": "easy",
                "estimated_co2_saved": 2.0,
            },
        ],
    )

    with TestClient(app) as client:
        yield client, image_bytes

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def ai_materials(db_session):
    from app.models import Material

    material_names = [
        "Biodegradable",
        "Cardboard",
        "Glass",
        "Metal",
        "Paper",
        "Plastic",
    ]

    materials = []

    for name in material_names:
        material = (
            db_session.query(Material)
            .filter(Material.name == name)
            .first()
        )

        if material is None:
            material = Material(
                name=name,
                category=name,
                description=f"{name} material",
                recyclable=True,
                biodegradable=(name == "Biodegradable"),
            )
            db_session.add(material)

        materials.append(material)

    db_session.flush()

    return materials

# ============================================================
# TEST 1: COMPLETE AI PIPELINE
# ============================================================

def test_complete_ai_pipeline(
    ai_client,
    ai_materials,
    db_session,
    ai_user,
):

    client, image_bytes = ai_client

    response = client.post(
        "/ai/detect",
        files={
            "file": (
                "plastic.jpg",
                BytesIO(image_bytes),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["scan_status"] == "completed"
    assert data["total_detections"] == 1

    assert data["detections"][0]["label"] == "PLASTIC"
    assert data["detections"][0]["material_name"] == "Plastic"

    scan = db_session.get(
        WasteScan,
        uuid.UUID(data["scan_id"]),
    )

    assert scan is not None
    assert scan.user_id == ai_user.id
    assert scan.scan_status == "completed"

    detected_objects = db_session.query(ScanObject).filter(
        ScanObject.scan_id == scan.id
    ).all()

    assert len(detected_objects) == 1


# ============================================================
# TEST 2: MATERIAL CLASSIFICATION PERSISTENCE
# ============================================================

def test_material_classification_persisted(
    ai_client,
    ai_materials,
    db_session,
):

    client, image_bytes = ai_client

    response = client.post(
        "/ai/detect",
        files={
            "file": (
                "plastic.jpg",
                BytesIO(image_bytes),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200

    scan_id = uuid.UUID(response.json()["scan_id"])

    detected_object = db_session.query(ScanObject).filter(
        ScanObject.scan_id == scan_id
    ).first()

    classification = db_session.query(
        ScanObjectMaterial
    ).filter(
        ScanObjectMaterial.scan_object_id == detected_object.id
    ).first()

    assert classification is not None
    assert classification.confidence_score == 0.95
    assert classification.material.name == "Plastic"


# ============================================================
# TEST 3: RECOMMENDATIONS PERSISTENCE
# ============================================================

def test_recommendations_persisted(
    ai_client,
    ai_materials,
    db_session,
):

    client, image_bytes = ai_client

    response = client.post(
        "/ai/detect",
        files={
            "file": (
                "plastic.jpg",
                BytesIO(image_bytes),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200

    scan_id = uuid.UUID(response.json()["scan_id"])

    detected_object = db_session.query(ScanObject).filter(
        ScanObject.scan_id == scan_id
    ).first()

    recommendations = db_session.query(
        Recommendation
    ).filter(
        Recommendation.scan_object_id == detected_object.id
    ).all()

    assert len(recommendations) == 2

    titles = {item.title for item in recommendations}

    assert titles == {
        "Reuse Plastic Container",
        "Recycle Plastic",
    }


# ============================================================
# TEST 4: SCAN BELONGS TO AUTHENTICATED USER
# ============================================================

def test_ai_scan_ownership(
    ai_client,
    ai_materials,
    db_session,
    ai_user,
):

    client, image_bytes = ai_client

    response = client.post(
        "/ai/detect",
        files={
            "file": (
                "plastic.jpg",
                BytesIO(image_bytes),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200

    scan_id = uuid.UUID(response.json()["scan_id"])

    scan = db_session.get(WasteScan, scan_id)

    assert scan.user_id == ai_user.id


# ============================================================
# TEST 5: INVALID IMAGE REJECTED BEFORE PIPELINE
# ============================================================

def test_ai_invalid_image_rejected(
    ai_client,
    db_session,
):
    client, _ = ai_client

    scans_before = db_session.query(WasteScan).count()

    response = client.post(
        "/ai/detect",
        files={
            "file": (
                "invalid.jpg",
                BytesIO(b"not-an-image"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400
    assert db_session.query(WasteScan).count() == scans_before

# ============================================================
# TEST 6: NO DETECTIONS STILL COMPLETES SCAN
# ============================================================

def test_ai_no_detections(
    ai_client,
    ai_materials,
    db_session,
    monkeypatch,
):

    monkeypatch.setattr(
        ai,
        "detect_waste",
        lambda image: {
            "image_width": 100,
            "image_height": 100,
            "detections": [],
        },
    )

    client, image_bytes = ai_client

    response = client.post(
        "/ai/detect",
        files={
            "file": (
                "empty.jpg",
                BytesIO(image_bytes),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_detections"] == 0
    assert data["detections"] == []
    assert data["scan_status"] == "completed"


# ============================================================
# TEST 7: MISSING MATERIAL CAUSES FAILED SCAN
# ============================================================


def test_ai_missing_material_marks_scan_failed(
    ai_client,
    db_session,
    monkeypatch,
):
    from app.models import Material

    # Preserve the original database query method
    original_query = db_session.query

    # Mock only Material queries to simulate missing materials
    def mock_query(model):
        query = original_query(model)

        if model is Material:

            class MissingMaterialQuery:
                def filter(self, *args, **kwargs):
                    return self

                def all(self):
                    return []

            return MissingMaterialQuery()

        return query

    monkeypatch.setattr(
        db_session,
        "query",
        mock_query,
    )

    # Prepare API client and valid image
    client, image_bytes = ai_client

    # Send image to AI detection endpoint
    response = client.post(
        "/ai/detect",
        files={
            "file": (
                "plastic.jpg",
                BytesIO(image_bytes),
                "image/jpeg",
            )
        },
    )

    # Verify API returns an internal server error
    assert response.status_code == 500

    # Retrieve the scan created by this request
    scan = (
        original_query(WasteScan)
        .filter(
            WasteScan.image_url == "https://example.com/test-image.jpg"
        )
        .order_by(WasteScan.created_at.desc())
        .first()
    )

    # Verify failed scan is persisted
    assert scan is not None
    assert scan.scan_status == "failed"


# ============================================================
# TEST 8: DETECTION FAILURE MARKS SCAN FAILED
# ============================================================

def test_ai_detection_failure_marks_scan_failed(
    ai_client,
    ai_materials,
    db_session,
    monkeypatch,
):
    def fail_detection(image):
        raise RuntimeError("Simulated YOLO failure")

    monkeypatch.setattr(
        ai,
        "detect_waste",
        fail_detection,
    )

    existing_ids = {
        scan.id
        for scan in db_session.query(WasteScan.id).all()
    }

    client, image_bytes = ai_client

    response = client.post(
        "/ai/detect",
        files={
            "file": (
                "plastic.jpg",
                BytesIO(image_bytes),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 500

    new_scans = (
        db_session.query(WasteScan)
        .filter(~WasteScan.id.in_(existing_ids))
        .all()
    )

    assert len(new_scans) == 1
    assert new_scans[0].scan_status == "failed"