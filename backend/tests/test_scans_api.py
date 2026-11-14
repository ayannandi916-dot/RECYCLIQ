from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user
from app.database.dependencies import get_db
from io import BytesIO
from app.models.waste_scan import WasteScan
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
# --------------------------------------------------
# 11. Successful upload and AI scanning
# --------------------------------------------------

def test_successful_scan_upload(
    client,
    mock_db,
    sample_user,
    monkeypatch,
):
    async def fake_validate(file):
        return True

    expected_response = {
        "message": "Waste detection completed successfully.",
        "scan_id": str(uuid.uuid4()),
        "user_id": str(sample_user.id),
        "image_url": "https://example.com/uploaded.jpg",
        "scan_status": "completed",
        "image_width": 640,
        "image_height": 480,
        "total_detections": 1,
        "detections": [],
    }

    mock_process = AsyncMock(return_value=expected_response)

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(scans, "process_scan", mock_process)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == expected_response

    mock_process.assert_awaited_once()

    kwargs = mock_process.await_args.kwargs

    assert kwargs["image_bytes"] == b"test-image-data"
    assert kwargs["current_user"] == sample_user
    assert kwargs["db"] == mock_db


# --------------------------------------------------
# 12. AI processing failure
# --------------------------------------------------

def test_scan_upload_processing_failure(
    client,
    monkeypatch,
):
    async def fake_validate(file):
        return True

    mock_process = AsyncMock(
        side_effect=RuntimeError("YOLO inference failed")
    )

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(scans, "process_scan", mock_process)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Scan processing failed."

    mock_process.assert_awaited_once()


# --------------------------------------------------
# 13. HTTP exception from scanning service
# --------------------------------------------------

def test_scan_upload_preserves_http_exception(
    client,
    monkeypatch,
):
    from fastapi import HTTPException

    async def fake_validate(file):
        return True

    mock_process = AsyncMock(
        side_effect=HTTPException(
            status_code=503,
            detail="AI model unavailable.",
        )
    )

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(scans, "process_scan", mock_process)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI model unavailable."


# --------------------------------------------------
# 14. Image validation failure
# --------------------------------------------------

def test_scan_upload_validation_failure(
    client,
    monkeypatch,
):
    from fastapi import HTTPException

    async def fail_validation(file):
        raise HTTPException(
            status_code=400,
            detail="Invalid image file.",
        )

    mock_process = AsyncMock()

    monkeypatch.setattr(
        scans,
        "validate_image",
        fail_validation,
    )

    monkeypatch.setattr(
        scans,
        "process_scan",
        mock_process,
    )

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"invalid-data"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid image file."

    mock_process.assert_not_awaited()


# --------------------------------------------------
# 15. Empty image upload
# --------------------------------------------------

def test_scan_upload_empty_image(
    client,
    monkeypatch,
):
    from fastapi import HTTPException

    async def fail_validation(file):
        raise HTTPException(
            status_code=400,
            detail="Image file is empty.",
        )

    mock_process = AsyncMock()

    monkeypatch.setattr(
        scans,
        "validate_image",
        fail_validation,
    )

    monkeypatch.setattr(
        scans,
        "process_scan",
        mock_process,
    )

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b""),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Image file is empty."

    mock_process.assert_not_awaited()


# --------------------------------------------------
# 16. Uploaded image is forwarded to AI exactly once
# --------------------------------------------------

def test_scan_upload_calls_processing_once(
    client,
    sample_user,
    mock_db,
    monkeypatch,
):
    async def fake_validate(file):
        return True

    mock_process = AsyncMock(
        return_value={
            "scan_id": str(uuid.uuid4()),
            "user_id": str(sample_user.id),
            "image_url": "https://example.com/test.jpg",
            "scan_status": "completed",
            "total_detections": 0,
            "detections": [],
        }
    )

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(scans, "process_scan", mock_process)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"unique-test-image"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200
    mock_process.assert_awaited_once()

    assert mock_process.await_args.kwargs["image_bytes"] == (
        b"unique-test-image"
    )


# --------------------------------------------------
# 17. Successful processing returns completed status
# --------------------------------------------------

def test_scan_upload_returns_completed_scan(
    client,
    sample_user,
    monkeypatch,
):
    async def fake_validate(file):
        return True

    mock_process = AsyncMock(
        return_value={
            "scan_id": str(uuid.uuid4()),
            "user_id": str(sample_user.id),
            "image_url": "https://example.com/test.jpg",
            "scan_status": "completed",
            "total_detections": 2,
            "detections": [
                {"label": "PLASTIC"},
                {"label": "GLASS"},
            ],
        }
    )

    monkeypatch.setattr(scans, "validate_image", fake_validate)
    monkeypatch.setattr(scans, "process_scan", mock_process)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["scan_status"] == "completed"
    assert data["total_detections"] == 2
    assert len(data["detections"]) == 2

# =========================================================
# 18. Pagination boundary and deterministic ordering tests
# =========================================================

@pytest.mark.parametrize(
    ("page", "limit", "expected_offset"),
    [
        (1, 2, 0),
        (2, 2, 2),
        (3, 2, 4),
    ],
)
def test_scan_history_pagination_offsets(
    client,
    mock_db,
    sample_user,
    page,
    limit,
    expected_offset,
):
    scans = [
        create_scan(sample_user.id)
        for _ in range(limit)
    ]

    query_all = MagicMock()
    query_all.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = scans

    query_count = MagicMock()
    query_count.filter.return_value.count.return_value = 5

    mock_db.query.side_effect = [
        query_all,
        query_count,
    ]

    response = client.get(
        f"/scans/history?page={page}&limit={limit}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["page"] == page
    assert data["limit"] == limit
    assert data["total_scans"] == 5

    ordered_query = query_all.filter.return_value.order_by

    # Verify ordering without relying on Python object identity.
    ordered_query.assert_called_once()

    ordering_args = ordered_query.call_args.args

    assert len(ordering_args) == 2

    assert ordering_args[0].compare(
        WasteScan.created_at.desc()
    )

    assert ordering_args[1].compare(
        WasteScan.id.asc()
    )

    ordered_query.return_value.offset.assert_called_once_with(
        expected_offset
    )

    ordered_query.return_value.offset.return_value.limit.assert_called_once_with(
        limit
    )


def test_scan_history_last_page_can_be_empty(
    client,
    mock_db,
):
    query_all = MagicMock()

    query_all.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    query_count = MagicMock()
    query_count.filter.return_value.count.return_value = 5

    mock_db.query.side_effect = [
        query_all,
        query_count,
    ]

    response = client.get(
        "/scans/history?page=4&limit=2"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["page"] == 4
    assert data["limit"] == 2
    assert data["total_scans"] == 5
    assert data["scans"] == []


# 19. Unauthenticated scan upload
def test_unauthenticated_scan_upload(client):
    app.dependency_overrides.pop(get_current_user, None)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.jpg",
                BytesIO(b"test-image-data"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


# 20. Unauthenticated scan history
def test_unauthenticated_scan_history(client):
    app.dependency_overrides.pop(get_current_user, None)

    response = client.get("/scans/history")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


# 21. Unauthenticated individual scan retrieval
def test_unauthenticated_scan_details(client):
    app.dependency_overrides.pop(get_current_user, None)

    scan_id = uuid.uuid4()

    response = client.get(f"/scans/{scan_id}")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


# 22. Invalid Bearer token cannot access scan history
def test_scan_history_with_invalid_token(client):
    app.dependency_overrides.pop(get_current_user, None)

    response = client.get(
        "/scans/history",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401


# 23. Invalid Bearer token cannot access scan details
def test_scan_details_with_invalid_token(client):
    app.dependency_overrides.pop(get_current_user, None)

    response = client.get(
        f"/scans/{uuid.uuid4()}",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401


# 24. Deactivated users cannot access scan history
def test_deactivated_user_cannot_access_scan_history(
    client,
    mock_db,
    sample_user,
    monkeypatch,
):
    from app.api import dependencies

    sample_user.is_active = False

    mock_db.query.return_value.filter.return_value.first.return_value = sample_user

    token = "valid-test-token"

    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda value: {"sub": str(sample_user.id)},
    )

    app.dependency_overrides.pop(get_current_user, None)

    response = client.get(
        "/scans/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Your account has been deactivated."
    )



# 25. Oversized upload is rejected before AI processing
def test_oversized_upload_never_reaches_scan_service(
    client,
    monkeypatch,
):
    async def fail_validation(file):
        raise HTTPException(
            status_code=413,
            detail="Image size must not exceed 5 MB.",
        )

    mock_process = AsyncMock()

    monkeypatch.setattr(scans, "validate_image", fail_validation)
    monkeypatch.setattr(scans, "process_scan", mock_process)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "large.jpg",
                BytesIO(b"large-image"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 413
    mock_process.assert_not_awaited()


# 26. Unsupported format is rejected before AI processing
def test_unsupported_format_never_reaches_scan_service(
    client,
    monkeypatch,
):
    async def fail_validation(file):
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG and WEBP images are allowed.",
        )

    mock_process = AsyncMock()

    monkeypatch.setattr(scans, "validate_image", fail_validation)
    monkeypatch.setattr(scans, "process_scan", mock_process)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "test.gif",
                BytesIO(b"invalid-gif"),
                "image/gif",
            )
        },
    )

    assert response.status_code == 400
    mock_process.assert_not_awaited()


# 27. Validator HTTP exceptions are preserved
def test_upload_preserves_validation_http_status(
    client,
    monkeypatch,
):
    async def fail_validation(file):
        raise HTTPException(
            status_code=413,
            detail="Image dimensions must not exceed 25 megapixels.",
        )

    mock_process = AsyncMock()

    monkeypatch.setattr(scans, "validate_image", fail_validation)
    monkeypatch.setattr(scans, "process_scan", mock_process)

    response = client.post(
        "/scans/upload",
        files={
            "file": (
                "large.jpg",
                BytesIO(b"test-image"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == (
        "Image dimensions must not exceed 25 megapixels."
    )

    mock_process.assert_not_awaited()
