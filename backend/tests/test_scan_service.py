import asyncio
import uuid

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sqlalchemy.exc import IntegrityError

from app.models import (
    Material,
    WasteScan,
    ScanObject,
    ScanObjectMaterial,
    Recommendation,
)

from app.services import scan_service
from fastapi import HTTPException


# --------------------------------------------------
# TEST DATA
# --------------------------------------------------

def sample_detection():
    return {
        "class_id": 5,
        "label": "PLASTIC",
        "confidence": 0.95,
        "bounding_box": {
            "x1": 10,
            "y1": 20,
            "x2": 100,
            "y2": 120,
        },
    }


def sample_result(detections=None):
    return {
        "image_width": 640,
        "image_height": 480,
        "total_detections": len(detections or []),
        "detections": detections or [],
    }


def sample_recommendations():
    return [
        {
            "recommendation_type": "reuse",
            "title": "Reuse Container",
            "description": "Reuse suitable containers.",
            "difficulty_level": "easy",
            "estimated_co2_saved": None,
        },
        {
            "recommendation_type": "recycle",
            "title": "Recycle Plastic",
            "description": "Send waste for recycling.",
            "difficulty_level": "easy",
            "estimated_co2_saved": None,
        },
    ]


# --------------------------------------------------
# FIXTURES
# --------------------------------------------------

@pytest.fixture
def current_user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Test User",
        email="test@recycliq.com",
        role="user",
    )


@pytest.fixture
def sample_materials():
    names = [
        "Biodegradable",
        "Cardboard",
        "Glass",
        "Metal",
        "Paper",
        "Plastic",
    ]

    return [
        SimpleNamespace(
            id=uuid.uuid4(),
            name=name,
        )
        for name in names
    ]


@pytest.fixture
def mock_db(current_user, sample_materials):
    db = MagicMock()

    scan = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=current_user.id,
        image_url="https://example.com/test.jpg",
        scan_status="pending",
    )

    def fake_add(obj):
        if isinstance(obj, (WasteScan, ScanObject)):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    db.add.side_effect = fake_add

    def query_side_effect(model):
        query = MagicMock()

        if model == Material:
            query.filter.return_value.all.return_value = (
                sample_materials
            )

        elif model == WasteScan:
            query.filter.return_value.first.return_value = scan

        return query

    db.query.side_effect = query_side_effect

    db.refresh.side_effect = lambda obj: None

    return db


@pytest.fixture
def scan_mocks(monkeypatch):
    async def fake_threadpool(func, *args):
        return func(*args)

    monkeypatch.setattr(
        scan_service,
        "run_in_threadpool",
        fake_threadpool,
    )

    monkeypatch.setattr(
        scan_service,
        "upload_image",
        lambda file: {
            "image_url": "https://example.com/test.jpg",
            "public_id": "recycliq/test-image",
        },
    )

    monkeypatch.setattr(
        scan_service,
        "detect_waste",
        lambda image: sample_result([sample_detection()]),
    )

    monkeypatch.setattr(
        scan_service,
        "generate_recommendations",
        lambda material: sample_recommendations(),
    )


# --------------------------------------------------
# 1. SUCCESSFUL SCAN
# --------------------------------------------------

def test_successful_scan(
    mock_db,
    current_user,
    scan_mocks,
):
    response = asyncio.run(
        scan_service.process_scan(
            image_bytes=b"test-image-data",
            current_user=current_user,
            db=mock_db,
        )
    )

    assert response["scan_status"] == "completed"
    assert response["total_detections"] == 1

    detection = response["detections"][0]

    assert detection["material_name"] == "Plastic"
    assert detection["confidence"] == 0.95
    assert len(detection["recommendations"]) == 2

    mock_db.commit.assert_called()
    mock_db.refresh.assert_called()


# --------------------------------------------------
# 2. SUCCESSFUL SCAN WITH NO DETECTIONS
# --------------------------------------------------

def test_scan_with_no_detections(
    mock_db,
    current_user,
    scan_mocks,
    monkeypatch,
):
    monkeypatch.setattr(
        scan_service,
        "detect_waste",
        lambda image: sample_result([]),
    )

    response = asyncio.run(
        scan_service.process_scan(
            image_bytes=b"test-image-data",
            current_user=current_user,
            db=mock_db,
        )
    )

    assert response["scan_status"] == "completed"
    assert response["total_detections"] == 0
    assert response["detections"] == []


# --------------------------------------------------
# 3. MATERIAL CLASSIFICATION
# --------------------------------------------------

def test_material_classification(
    mock_db,
    current_user,
    scan_mocks,
):
    response = asyncio.run(
        scan_service.process_scan(
            image_bytes=b"test-image-data",
            current_user=current_user,
            db=mock_db,
        )
    )

    assert response["detections"][0]["material_name"] == "Plastic"
    assert mock_db.flush.called

    added_objects = [
        call.args[0]
        for call in mock_db.add.call_args_list
    ]

    assert any(
        isinstance(obj, ScanObject)
        for obj in added_objects
    )

    assert any(
        isinstance(obj, ScanObjectMaterial)
        for obj in added_objects
    )


# --------------------------------------------------
# 4. RECOMMENDATION PERSISTENCE
# --------------------------------------------------

def test_recommendations_are_persisted(
    mock_db,
    current_user,
    scan_mocks,
):
    asyncio.run(
        scan_service.process_scan(
            image_bytes=b"test-image-data",
            current_user=current_user,
            db=mock_db,
        )
    )

    added_objects = [
        call.args[0]
        for call in mock_db.add.call_args_list
    ]

    recommendations = [
        obj
        for obj in added_objects
        if isinstance(obj, Recommendation)
    ]

    assert len(recommendations) == 2

    assert recommendations[0].title == "Reuse Container"
    assert recommendations[1].title == "Recycle Plastic"


# --------------------------------------------------
# 5. CLOUDINARY UPLOAD FAILURE
# --------------------------------------------------

def test_cloudinary_upload_failure(
    mock_db,
    current_user,
    scan_mocks,
    monkeypatch,
):
    delete_mock = MagicMock()

    monkeypatch.setattr(
        scan_service,
        "upload_image",
        MagicMock(
            side_effect=RuntimeError("Cloudinary upload failed")
        ),
    )

    monkeypatch.setattr(
        scan_service,
        "delete_image",
        delete_mock,
    )

    with pytest.raises(RuntimeError):
        asyncio.run(
            scan_service.process_scan(
                image_bytes=b"test-image-data",
                current_user=current_user,
                db=mock_db,
            )
        )

    mock_db.add.assert_not_called()
    mock_db.rollback.assert_called_once()
    delete_mock.assert_not_called()


# --------------------------------------------------
# 6. INITIAL DATABASE COMMIT FAILURE
# --------------------------------------------------

def test_database_commit_failure_cleans_cloudinary(
    mock_db,
    current_user,
    scan_mocks,
    monkeypatch,
):
    delete_mock = MagicMock(return_value=True)

    monkeypatch.setattr(
        scan_service,
        "delete_image",
        delete_mock,
    )

    mock_db.commit.side_effect = RuntimeError(
        "Database commit failed"
    )

    with pytest.raises(RuntimeError):
        asyncio.run(
            scan_service.process_scan(
                image_bytes=b"test-image-data",
                current_user=current_user,
                db=mock_db,
            )
        )

    mock_db.rollback.assert_called_once()

    delete_mock.assert_called_once_with(
        "recycliq/test-image"
    )


# --------------------------------------------------
# 7. YOLO DETECTION FAILURE
# --------------------------------------------------

def test_detection_failure_marks_scan_failed(
    mock_db,
    current_user,
    scan_mocks,
    monkeypatch,
):
    monkeypatch.setattr(
        scan_service,
        "detect_waste",
        MagicMock(
            side_effect=FileNotFoundError("Model not found")
        ),
    )

    delete_mock = MagicMock()

    monkeypatch.setattr(
        scan_service,
        "delete_image",
        delete_mock,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            scan_service.process_scan(
                image_bytes=b"test-image-data",
                current_user=current_user,
                db=mock_db,
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == (
        "YOLO model checkpoint is unavailable."
)


# --------------------------------------------------
# 8. FINAL DATABASE PERSISTENCE FAILURE
# --------------------------------------------------

def test_final_persistence_failure_marks_scan_failed(
    mock_db,
    current_user,
    scan_mocks,
):
    mock_db.commit.side_effect = [
        None,
        IntegrityError(
            "INSERT INTO recommendations",
            {},
            Exception("Database constraint violation"),
        ),
        None,
    ]

    with pytest.raises(IntegrityError):
        asyncio.run(
            scan_service.process_scan(
                image_bytes=b"test-image-data",
                current_user=current_user,
                db=mock_db,
            )
        )

    mock_db.rollback.assert_called()

    # Initial scan creation, failed final commit,
    # and failed-scan recovery.
    assert mock_db.commit.call_count == 3


# --------------------------------------------------
# 9. UNKNOWN YOLO CLASS
# --------------------------------------------------

def test_unknown_yolo_class_fails_scan(
    mock_db,
    current_user,
    scan_mocks,
    monkeypatch,
):
    unknown_detection = sample_detection()
    unknown_detection["label"] = "WOOD"

    monkeypatch.setattr(
        scan_service,
        "detect_waste",
        lambda image: sample_result([unknown_detection]),
    )

    with pytest.raises(RuntimeError, match="Unknown YOLO class"):
        asyncio.run(
            scan_service.process_scan(
                image_bytes=b"test-image-data",
                current_user=current_user,
                db=mock_db,
            )
        )

    mock_db.rollback.assert_called()
    mock_db.commit.assert_called()

def test_invalid_image_data_returns_422(
    mock_db,
    current_user,
    scan_mocks,
    monkeypatch,
):
    monkeypatch.setattr(
        scan_service,
        "detect_waste",
        MagicMock(
            side_effect=ValueError("Unable to decode image.")
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            scan_service.process_scan(
                image_bytes=b"invalid-image",
                current_user=current_user,
                db=mock_db,
            )
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Unable to decode image."

    mock_db.rollback.assert_called()
    mock_db.commit.assert_called()

def test_missing_material_in_database(
    mock_db,
    current_user,
    scan_mocks,
    monkeypatch,
):
    query = MagicMock()
    query.filter.return_value.all.return_value = []

    def query_side_effect(model):
        if model == Material:
            return query

        return mock_db.query.return_value

    mock_db.query.side_effect = query_side_effect

    with pytest.raises(RuntimeError, match="Missing materials in database"):
        asyncio.run(
            scan_service.process_scan(
                image_bytes=b"test-image-data",
                current_user=current_user,
                db=mock_db,
            )
        )

    mock_db.rollback.assert_called()
    mock_db.commit.assert_called()

def test_mark_scan_failed_with_none_id(mock_db):
        scan_service.mark_scan_failed(mock_db, None)

        mock_db.rollback.assert_not_called()
        mock_db.query.assert_not_called()


def test_mark_scan_failed_scan_not_found(mock_db):
    query = MagicMock()
    query.filter.return_value.first.return_value = None

    mock_db.query.side_effect = None
    mock_db.query.return_value = query

    scan_service.mark_scan_failed(mock_db, uuid.uuid4())

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()

def test_mark_scan_failed_success(mock_db):
    scan = SimpleNamespace(scan_status="pending")

    query = MagicMock()
    query.filter.return_value.first.return_value = scan

    mock_db.query.side_effect = None
    mock_db.query.return_value = query

    scan_service.mark_scan_failed(mock_db, uuid.uuid4())

    assert scan.scan_status == "failed"
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_called_once()

def test_mark_scan_failed_recovery_exception(mock_db):
    mock_db.query.side_effect = RuntimeError(
        "Database recovery failed"
    )

    scan_service.mark_scan_failed(mock_db, uuid.uuid4())

    assert mock_db.rollback.call_count == 2
    mock_db.query.assert_called_once()
    mock_db.commit.assert_not_called()

def test_cloudinary_cleanup_failure_preserves_original_error(
    mock_db,
    current_user,
    scan_mocks,
    monkeypatch,
    caplog,
):
    from sqlalchemy.exc import IntegrityError

    monkeypatch.setattr(
        scan_service,
        "delete_image",
        MagicMock(
            side_effect=RuntimeError("Cloudinary deletion failed")
        ),
    )

    mock_db.commit.side_effect = IntegrityError(
        "INSERT INTO waste_scans",
        {},
        Exception("Original database error"),
    )

    with pytest.raises(IntegrityError):
        asyncio.run(
            scan_service.process_scan(
                image_bytes=b"test-image-data",
                current_user=current_user,
                db=mock_db,
            )
        )

    assert "Failed to delete uncommitted Cloudinary image" in caplog.text
    assert "Original database error" in caplog.text