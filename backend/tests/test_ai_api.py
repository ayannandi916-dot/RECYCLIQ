import uuid
from types import SimpleNamespace
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user
from app.database.dependencies import get_db
from app.models import Material, WasteScan

from app.api import ai
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def sample_user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Test User",
        email="test@recycliq.com",
        role="user"
    )


@pytest.fixture
def sample_materials():
    names = [
        "Biodegradable",
        "Cardboard",
        "Glass",
        "Metal",
        "Paper",
        "Plastic"
    ]

    return [
        SimpleNamespace(
            id=uuid.uuid4(),
            name=name
        )
        for name in names
    ]

@pytest.fixture
def client(mock_db, sample_user):

    app.dependency_overrides[get_db] = lambda: mock_db

    app.dependency_overrides[get_current_user] = (
        lambda: sample_user
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

@pytest.fixture
def setup_ai_mocks(monkeypatch, mock_db, sample_materials):

    scan = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        image_url="https://example.com/test.jpg",
        scan_status="pending"
    )

    async def fake_validate(file):
        return True

    async def fake_threadpool(func, *args):
        return func(*args)

    def fake_refresh(obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    monkeypatch.setattr(
        ai,
        "validate_image",
        fake_validate
    )

    monkeypatch.setattr(
        ai,
        "upload_image",
        lambda file: {
            "image_url": "https://example.com/test.jpg"
        }
    )

    monkeypatch.setattr(
        ai,
        "run_in_threadpool",
        fake_threadpool
    )

    monkeypatch.setattr(
        ai,
        "generate_recommendations",
        lambda material: [
            {
                "recommendation_type": "reuse",
                "title": "Reuse Container",
                "description": "Reuse suitable containers.",
                "difficulty_level": "easy",
                "estimated_co2_saved": None
            },
            {
                "recommendation_type": "recycle",
                "title": "Recycle Plastic",
                "description": "Send waste for recycling.",
                "difficulty_level": "easy",
                "estimated_co2_saved": None
            }
        ]
    )

    mock_db.refresh.side_effect = fake_refresh

    def query_side_effect(model):

        query = MagicMock()

        if model == Material:
            query.filter.return_value.all.return_value = sample_materials

        elif model == WasteScan:
            query.filter.return_value.first.return_value = scan

        return query

    mock_db.query.side_effect = query_side_effect

    return scan

def upload_test_image(client):

    return client.post(
        "/ai/detect",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg"
            )
        }
    )


# 1. Successful detection and persistence
def test_successful_detection(
    client,
    mock_db,
    setup_ai_mocks,
    monkeypatch
):

    monkeypatch.setattr(
        ai,
        "detect_waste",
        lambda image: {
            "image_width": 640,
            "image_height": 480,
            "detections": [
                {
                    "class_id": 5,
                    "label": "PLASTIC",
                    "confidence": 0.95,
                    "bounding_box": {
                        "x1": 10,
                        "y1": 20,
                        "x2": 100,
                        "y2": 120
                    }
                }
            ]
        }
    )

    response = upload_test_image(client)

    assert response.status_code == 200

    data = response.json()

    assert data["scan_status"] == "completed"
    assert data["total_detections"] == 1
    assert data["detections"][0]["material_name"] == "Plastic"
    assert len(data["detections"][0]["recommendations"]) == 2

    mock_db.commit.assert_called()


# 2. Successful detection with no objects
def test_detection_with_no_objects(
    client,
    mock_db,
    setup_ai_mocks,
    monkeypatch
):

    monkeypatch.setattr(
        ai,
        "detect_waste",
        lambda image: {
            "image_width": 640,
            "image_height": 480,
            "detections": []
        }
    )

    response = upload_test_image(client)

    assert response.status_code == 200

    data = response.json()

    assert data["total_detections"] == 0
    assert data["detections"] == []
    assert data["scan_status"] == "completed"


# 3. Missing YOLO checkpoint
def test_missing_yolo_checkpoint(
    client,
    mock_db,
    setup_ai_mocks,
    monkeypatch
):

    def fail_detection(image):
        raise FileNotFoundError("Model not found")

    monkeypatch.setattr(
        ai,
        "detect_waste",
        fail_detection
    )

    response = upload_test_image(client)

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "YOLO model checkpoint is unavailable."
    )

    mock_db.rollback.assert_called()


# 4. Invalid inference data
def test_invalid_inference_data(
    client,
    mock_db,
    setup_ai_mocks,
    monkeypatch
):

    def fail_detection(image):
        raise ValueError("Invalid image data")

    monkeypatch.setattr(
        ai,
        "detect_waste",
        fail_detection
    )

    response = upload_test_image(client)

    assert response.status_code == 422

    assert response.json()["detail"] == "Invalid image data"

    mock_db.rollback.assert_called()


# 5. Unknown YOLO class
def test_unknown_yolo_class(
    client,
    mock_db,
    setup_ai_mocks,
    monkeypatch
):

    monkeypatch.setattr(
        ai,
        "detect_waste",
        lambda image: {
            "image_width": 640,
            "image_height": 480,
            "detections": [
                {
                    "class_id": 6,
                    "label": "WOOD",
                    "confidence": 0.90,
                    "bounding_box": {
                        "x1": 10,
                        "y1": 20,
                        "x2": 100,
                        "y2": 120
                    }
                }
            ]
        }
    )

    response = upload_test_image(client)

    assert response.status_code == 500

    assert response.json()["detail"] == (
        "Waste detection or database persistence failed."
    )

    mock_db.rollback.assert_called()


# 6. Missing material in database
def test_missing_material_in_database(
    client,
    mock_db,
    monkeypatch
):

    scan = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        image_url="https://example.com/test.jpg",
        scan_status="pending"
    )
    def fake_refresh(obj):
        if getattr(obj, "id", None) is None:
         obj.id = uuid.uuid4()

    mock_db.refresh.side_effect = fake_refresh

    async def fake_validate(file):
        return True

    async def fake_threadpool(func, *args):
        return func(*args)

    monkeypatch.setattr(ai, "validate_image", fake_validate)

    monkeypatch.setattr(
        ai,
        "upload_image",
        lambda file: {
            "image_url": "https://example.com/test.jpg"
        }
    )

    monkeypatch.setattr(
        ai,
        "run_in_threadpool",
        fake_threadpool
    )

    monkeypatch.setattr(
        ai,
        "detect_waste",
        lambda image: {
            "image_width": 640,
            "image_height": 480,
            "detections": []
        }
    )

    def query_side_effect(model):

        query = MagicMock()

        if model == Material:
            query.filter.return_value.all.return_value = []

        elif model == WasteScan:
            query.filter.return_value.first.return_value = scan

        return query

    mock_db.query.side_effect = query_side_effect

    response = upload_test_image(client)

    assert response.status_code == 500

    mock_db.rollback.assert_called()


    # 7. Database IntegrityError and scan recovery
def test_database_integrity_failure(
    client,
    mock_db,
    setup_ai_mocks,
    monkeypatch
):

    scan = setup_ai_mocks

    # Ensure the newly created scan receives
    # the same ID returned by our mocked database query.
    def fake_refresh(obj):
        if isinstance(obj, WasteScan):
            obj.id = scan.id

    mock_db.refresh.side_effect = fake_refresh

    # First commit: initial scan creation succeeds.
    # Second commit: final persistence fails.
    # Third commit: marking the scan as failed succeeds.
    mock_db.commit.side_effect = [
        None,
        IntegrityError(
            "INSERT INTO recommendations",
            {},
            Exception("Simulated database constraint violation")
        ),
        None
    ]

    monkeypatch.setattr(
        ai,
        "detect_waste",
        lambda image: {
            "image_width": 640,
            "image_height": 480,
            "detections": [
                {
                    "class_id": 5,
                    "label": "PLASTIC",
                    "confidence": 0.95,
                    "bounding_box": {
                        "x1": 10,
                        "y1": 20,
                        "x2": 100,
                        "y2": 120
                    }
                }
            ]
        }
    )

    response = upload_test_image(client)

    assert response.status_code == 500

    assert mock_db.rollback.called

    assert scan.scan_status == "failed"

    assert mock_db.commit.call_count == 3

# 8. No scan ID: recovery should return immediately
def test_mark_scan_failed_with_none_id(mock_db):

    ai.mark_scan_failed(mock_db, None)

    mock_db.rollback.assert_not_called()
    mock_db.query.assert_not_called()


# 9. Scan does not exist during recovery
def test_mark_scan_failed_scan_not_found(mock_db):

    query = MagicMock()
    query.filter.return_value.first.return_value = None

    mock_db.query.return_value = query

    ai.mark_scan_failed(mock_db, uuid.uuid4())

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()


# 10. Recovery itself fails
def test_mark_scan_failed_recovery_exception(mock_db):

    mock_db.query.side_effect = RuntimeError(
        "Database recovery failed"
    )

    ai.mark_scan_failed(mock_db, uuid.uuid4())

    assert mock_db.rollback.call_count == 2
    mock_db.query.assert_called_once()
    mock_db.commit.assert_not_called()
# 11. Scan is successfully marked as failed
def test_mark_scan_failed_success(mock_db):

    scan = SimpleNamespace(scan_status="pending")

    query = MagicMock()
    query.filter.return_value.first.return_value = scan

    mock_db.query.return_value = query

    ai.mark_scan_failed(mock_db, uuid.uuid4())

    assert scan.scan_status == "failed"
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_called_once()