from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user
from app.database.dependencies import get_db
from io import BytesIO

from app.api import scans


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
def client(mock_db, sample_user):

    app.dependency_overrides[get_db] = lambda: mock_db

    app.dependency_overrides[get_current_user] = (
        lambda: sample_user
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def create_scan(user_id, scan_id=None):

    return SimpleNamespace(
        id=scan_id or uuid.uuid4(),
        user_id=user_id,
        image_url="https://example.com/test.jpg",
        scan_status="completed",
        created_at=datetime.now(timezone.utc)
    )


# 1. Successful scan history retrieval
def test_scan_history(client, mock_db, sample_user):

    scan = create_scan(sample_user.id)

    query_all = MagicMock()
    query_all.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        scan
    ]

    query_count = MagicMock()
    query_count.filter.return_value.count.return_value = 1

    mock_db.query.side_effect = [
        query_all,
        query_count
    ]

    response = client.get("/scans/history")

    assert response.status_code == 200

    data = response.json()

    assert data["total_scans"] == 1
    assert data["page"] == 1
    assert data["limit"] == 10
    assert len(data["scans"]) == 1

    assert data["scans"][0]["scan_id"] == str(scan.id)


# 2. Empty scan history
def test_empty_scan_history(client, mock_db):

    query_all = MagicMock()
    query_all.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    query_count = MagicMock()
    query_count.filter.return_value.count.return_value = 0

    mock_db.query.side_effect = [
        query_all,
        query_count
    ]

    response = client.get("/scans/history")

    assert response.status_code == 200

    data = response.json()

    assert data["total_scans"] == 0
    assert data["scans"] == []


# 3. Pagination
def test_scan_history_pagination(client, mock_db, sample_user):

    scan = create_scan(sample_user.id)

    query_all = MagicMock()
    query_all.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        scan
    ]

    query_count = MagicMock()
    query_count.filter.return_value.count.return_value = 5

    mock_db.query.side_effect = [
        query_all,
        query_count
    ]

    response = client.get(
        "/scans/history?page=2&limit=2"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["page"] == 2
    assert data["limit"] == 2
    assert data["total_scans"] == 5

    query_all.filter.return_value.order_by.return_value.offset.assert_called_once_with(2)

    query_all.filter.return_value.order_by.return_value.offset.return_value.limit.assert_called_once_with(2)


# 4. Invalid page number
def test_invalid_page_number(client):

    response = client.get(
        "/scans/history?page=0"
    )

    assert response.status_code == 422


# 5. Invalid limit
def test_invalid_limit(client):

    response = client.get(
        "/scans/history?limit=0"
    )

    assert response.status_code == 422


# 6. Limit exceeding maximum
def test_limit_exceeding_maximum(client):

    response = client.get(
        "/scans/history?limit=51"
    )

    assert response.status_code == 422


# 7. Successful individual scan retrieval
def test_get_scan_details(client, mock_db, sample_user):

    scan_id = uuid.uuid4()
    object_id = uuid.uuid4()
    material_id = uuid.uuid4()
    recommendation_id = uuid.uuid4()

    material = SimpleNamespace(
        id=material_id,
        name="Plastic",
        category="Plastic",
        recyclable=True,
        biodegradable=False
    )

    classification = SimpleNamespace(
        material=material,
        confidence_score=0.95,
        quantity_estimate=None,
        quantity_unit=None
    )

    recommendation = SimpleNamespace(
        id=recommendation_id,
        recommendation_type="reuse",
        title="Reuse Plastic Container",
        description="Reuse suitable containers.",
        difficulty_level="easy",
        estimated_co2_saved=None,
        created_at=datetime.now(timezone.utc)
    )

    detected_object = SimpleNamespace(
        id=object_id,
        object_label="PLASTIC",
        detection_confidence=0.95,
        bounding_box={
            "x1": 10,
            "y1": 20,
            "x2": 100,
            "y2": 120
        },
        created_at=datetime.now(timezone.utc),
        material_classifications=[classification],
        recommendations=[recommendation]
    )

    scan = SimpleNamespace(
        id=scan_id,
        user_id=sample_user.id,
        image_url="https://example.com/test.jpg",
        scan_status="completed",
        created_at=datetime.now(timezone.utc),
        detected_objects=[detected_object]
    )

    query = MagicMock()

    query.options.return_value.filter.return_value.first.return_value = scan

    mock_db.query.return_value = query

    response = client.get(
        f"/scans/{scan_id}"
    )

    assert response.status_code == 200

    data = response.json()["scan"]

    assert data["scan_id"] == str(scan_id)
    assert data["total_detected_objects"] == 1
    assert data["total_recommendations"] == 1

    assert data["detected_objects"][0]["object_label"] == "PLASTIC"

    assert data["detected_objects"][0]["materials"][0]["material_name"] == "Plastic"

    assert data["detected_objects"][0]["recommendations"][0]["title"] == "Reuse Plastic Container"


# 8. Scan not found
def test_scan_not_found(client, mock_db):

    query = MagicMock()

    query.options.return_value.filter.return_value.first.return_value = None

    mock_db.query.return_value = query

    scan_id = uuid.uuid4()

    response = client.get(
        f"/scans/{scan_id}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Scan not found."


# 9. Cross-user scan access
def test_other_users_scan_access(client, mock_db):

    query = MagicMock()

    query.options.return_value.filter.return_value.first.return_value = None

    mock_db.query.return_value = query

    another_user_scan_id = uuid.uuid4()

    response = client.get(
        f"/scans/{another_user_scan_id}"
    )

    assert response.status_code == 404


# 10. Invalid scan UUID
def test_invalid_scan_uuid(client):

    response = client.get(
        "/scans/not-a-valid-uuid"
    )

    assert response.status_code == 422
# 11. Successful image upload and scan creation
def test_successful_scan_upload(
    client,
    mock_db,
    sample_user,
    monkeypatch
):
    scan = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        image_url="https://example.com/uploaded.jpg",
        scan_status="pending"
    )

    async def fake_validate(file):
        return True

    def fake_upload(file):
        return {
            "image_url": "https://example.com/uploaded.jpg",
            "public_id": "recycliq/scans/test-image"
        }

    def fake_refresh(obj):
        obj.id = scan.id

    monkeypatch.setattr(
        scans,
        "validate_image",
        fake_validate
    )

    monkeypatch.setattr(
        scans,
        "upload_image",
        fake_upload
    )

    mock_db.refresh.side_effect = fake_refresh

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg"
            )
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["scan_id"] == str(scan.id)
    assert data["user_id"] == str(sample_user.id)
    assert data["scan_status"] == "pending"
    assert data["image_url"] == "https://example.com/uploaded.jpg"

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()


# 12. Cloudinary upload failure
def test_scan_upload_cloudinary_failure(
    client,
    mock_db,
    monkeypatch
):
    async def fake_validate(file):
        return True

    def fail_upload(file):
        raise RuntimeError("Cloudinary upload failed")

    monkeypatch.setattr(
        scans,
        "validate_image",
        fake_validate
    )

    monkeypatch.setattr(
        scans,
        "upload_image",
        fail_upload
    )

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg"
            )
        }
    )

    assert response.status_code == 500

    assert response.json()["detail"] == (
        "Failed to upload image or create scan."
    )

    mock_db.rollback.assert_called_once()


# 13. Database commit failure (without a Cloudinary public ID)
def test_scan_upload_database_failure(
    client,
    mock_db,
    monkeypatch
):
    async def fake_validate(file):
        return True

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(
        scans,
        "upload_image",
        lambda file: {"image_url": "https://example.com/test.jpg"}
    )

    mock_db.commit.side_effect = RuntimeError("Database commit failed")

    response = client.post(
        "/scans/upload",
        files={
            "file": ("test.jpg", BytesIO(b"test-image-data"), "image/jpeg")
        }
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Failed to upload image or create scan."
    )
    mock_db.add.assert_called_once()
    mock_db.rollback.assert_called_once()


# 14. Database failure triggers Cloudinary cleanup
def test_scan_upload_database_failure_cleans_cloudinary(
    client, mock_db, monkeypatch
):
    async def fake_validate(file):
        return True

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(
        scans,
        "upload_image",
        lambda file: {
            "image_url": "https://example.com/test.jpg",
            "public_id": "recycliq/scans/test-image"
        }
    )

    mock_delete = MagicMock(return_value=True)
    monkeypatch.setattr(scans, "delete_image", mock_delete)
    mock_db.commit.side_effect = RuntimeError("Database commit failed")

    response = client.post(
        "/scans/upload",
        files={
            "file": ("test.jpg", BytesIO(b"test-image-data"), "image/jpeg")
        }
    )

    assert response.status_code == 500
    mock_db.rollback.assert_called_once()
    mock_delete.assert_called_once_with("recycliq/scans/test-image")


# 15. Cloudinary cleanup failure does not hide the original API error
def test_scan_upload_cleanup_failure(
    client, mock_db, monkeypatch
):
    async def fake_validate(file):
        return True

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(
        scans,
        "upload_image",
        lambda file: {
            "image_url": "https://example.com/test.jpg",
            "public_id": "recycliq/scans/test-image"
        }
    )
    monkeypatch.setattr(
        scans,
        "delete_image",
        MagicMock(side_effect=RuntimeError("Cloudinary deletion failed"))
    )
    mock_db.commit.side_effect = RuntimeError("Database commit failed")

    response = client.post(
        "/scans/upload",
        files={
            "file": ("test.jpg", BytesIO(b"test-image-data"), "image/jpeg")
        }
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Failed to upload image or create scan."
    )
    mock_db.rollback.assert_called_once()


# 16. Successful upload does not delete the Cloudinary image
def test_successful_scan_upload_does_not_delete_image(
    client, mock_db, monkeypatch
):
    scan_id = uuid.uuid4()

    async def fake_validate(file):
        return True

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(
        scans,
        "upload_image",
        lambda file: {
            "image_url": "https://example.com/uploaded.jpg",
            "public_id": "recycliq/scans/test-image"
        }
    )
    mock_delete = MagicMock()
    monkeypatch.setattr(scans, "delete_image", mock_delete)
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", scan_id)

    response = client.post(
        "/scans/upload",
        files={
            "file": ("test.jpg", BytesIO(b"test-image-data"), "image/jpeg")
        }
    )

    assert response.status_code == 201
    assert response.json()["scan_id"] == str(scan_id)
    mock_db.commit.assert_called_once()
    mock_delete.assert_not_called()

# 17. Refresh failure after successful database commit
def test_scan_upload_refresh_failure_preserves_cloudinary_image(
    client, mock_db, monkeypatch
):
    async def fake_validate(file):
        return True

    monkeypatch.setattr(
        scans,
        "validate_image",
        fake_validate
    )

    monkeypatch.setattr(
        scans,
        "upload_image",
        lambda file: {
            "image_url": "https://example.com/test.jpg",
            "public_id": "recycliq/scans/test-image"
        }
    )

    mock_delete = MagicMock(return_value=True)

    monkeypatch.setattr(
        scans,
        "delete_image",
        mock_delete
    )

    # Database commit succeeds
    mock_db.commit.return_value = None

    # Refresh fails after commit
    mock_db.refresh.side_effect = RuntimeError(
        "Database refresh failed"
    )

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg"
            )
        }
    )

    assert response.status_code == 500

    # Database commit succeeded
    mock_db.commit.assert_called_once()

    # Refresh was attempted
    mock_db.refresh.assert_called_once()

    # Cloudinary image must be preserved
    mock_delete.assert_not_called()