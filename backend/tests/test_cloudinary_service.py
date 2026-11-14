import pytest
from io import BytesIO
from unittest.mock import MagicMock

from app.services import cloudinary_service as cloudinary_service
from app.core.config import settings


def _mock_configuration(monkeypatch):
    monkeypatch.setattr(
        cloudinary_service,
        "configure_cloudinary",
        MagicMock(),
    )


# Configuration
def test_successful_cloudinary_configuration(monkeypatch):
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test-cloud")
    monkeypatch.setattr(settings, "cloudinary_api_key", "test-key")
    monkeypatch.setattr(settings, "cloudinary_api_secret", "test-secret")

    mock_config = MagicMock()
    monkeypatch.setattr(cloudinary_service.cloudinary, "config", mock_config)

    cloudinary_service.configure_cloudinary()

    mock_config.assert_called_once_with(
        cloud_name="test-cloud",
        api_key="test-key",
        api_secret="test-secret",
        secure=True,
    )


def test_missing_cloudinary_credentials(monkeypatch):
    monkeypatch.setattr(settings, "cloudinary_cloud_name", None)
    monkeypatch.setattr(settings, "cloudinary_api_key", None)
    monkeypatch.setattr(settings, "cloudinary_api_secret", None)

    with pytest.raises(
        RuntimeError,
        match="Cloudinary credentials are not configured",
    ):
        cloudinary_service.configure_cloudinary()


# Uploads
def test_successful_image_upload(monkeypatch):
    _mock_configuration(monkeypatch)
    mock_upload = MagicMock(
        return_value={
            "secure_url": "https://res.cloudinary.com/test/image.jpg",
            "public_id": "recycliq/scans/test-image",
        }
    )
    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "upload", mock_upload)

    image = b"fake-image-data"
    result = cloudinary_service.upload_image(image)

    assert result == {
        "image_url": "https://res.cloudinary.com/test/image.jpg",
        "public_id": "recycliq/scans/test-image",
    }
    mock_upload.assert_called_once_with(
        image,
        folder="recycliq/scans",
        resource_type="image",
        timeout=cloudinary_service.CLOUDINARY_UPLOAD_TIMEOUT_SECONDS,
    )


def test_custom_upload_folder(monkeypatch):
    _mock_configuration(monkeypatch)
    mock_upload = MagicMock(
        return_value={
            "secure_url": "https://example.com/image.jpg",
            "public_id": "custom/image",
        }
    )
    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "upload", mock_upload)

    cloudinary_service.upload_image(b"fake-image-data", folder="custom")

    mock_upload.assert_called_once_with(
        b"fake-image-data",
        folder="custom",
        resource_type="image",
        timeout=cloudinary_service.CLOUDINARY_UPLOAD_TIMEOUT_SECONDS,
    )


def test_bytesio_upload_gets_filename(monkeypatch):
    _mock_configuration(monkeypatch)
    mock_upload = MagicMock(
        return_value={
            "secure_url": "https://example.com/image.jpg",
            "public_id": "recycliq/scans/stream-image",
        }
    )
    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "upload", mock_upload)

    image_stream = BytesIO(b"image-bytes")
    cloudinary_service.upload_image(image_stream)

    assert image_stream.name == "recycliq-upload"
    assert mock_upload.call_args.args[0] is image_stream


def test_existing_bytesio_filename_is_preserved(monkeypatch):
    _mock_configuration(monkeypatch)
    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "upload",
        MagicMock(
            return_value={
                "secure_url": "https://example.com/image.jpg",
                "public_id": "recycliq/scans/stream-image",
            }
        ),
    )

    image_stream = BytesIO(b"image-bytes")
    image_stream.name = "scan-123.png"

    cloudinary_service.upload_image(image_stream)

    assert image_stream.name == "scan-123.png"


def test_none_upload_input_is_rejected_before_network_call(monkeypatch):
    mock_upload = MagicMock()
    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "upload", mock_upload)

    with pytest.raises(ValueError, match="Image file cannot be None"):
        cloudinary_service.upload_image(None)

    mock_upload.assert_not_called()


def test_cloudinary_upload_failure_propagates(monkeypatch):
    _mock_configuration(monkeypatch)
    mock_upload = MagicMock(side_effect=Exception("Cloudinary upload failed"))
    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "upload", mock_upload)

    with pytest.raises(Exception, match="Cloudinary upload failed"):
        cloudinary_service.upload_image(b"fake-image-data")


@pytest.mark.parametrize(
    "invalid_response",
    [
        None,
        [],
        "invalid",
        123,
        {},
        {"secure_url": "", "public_id": "test/image"},
        {"secure_url": "https://example.com/image.jpg", "public_id": ""},
        {"secure_url": [], "public_id": "test/image"},
        {"secure_url": "https://example.com/image.jpg", "public_id": {}},
        {"secure_url": "   ", "public_id": "test/image"},
        {"secure_url": "https://example.com/image.jpg", "public_id": "   "},
    ],
)
def test_invalid_cloudinary_upload_responses(monkeypatch, invalid_response):
    _mock_configuration(monkeypatch)
    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "upload",
        MagicMock(return_value=invalid_response),
    )

    with pytest.raises(
        RuntimeError,
        match="Cloudinary returned an invalid upload response.",
    ):
        cloudinary_service.upload_image(b"fake-image-data")


# Deletions
def test_successful_image_deletion(monkeypatch):
    _mock_configuration(monkeypatch)
    mock_destroy = MagicMock(return_value={"result": "ok"})
    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "destroy", mock_destroy)

    result = cloudinary_service.delete_image("recycliq/scans/test-image")

    assert result is True
    mock_destroy.assert_called_once_with(
        "recycliq/scans/test-image",
        resource_type="image",
        timeout=cloudinary_service.CLOUDINARY_DELETE_TIMEOUT_SECONDS,
    )


def test_image_deletion_not_found(monkeypatch):
    _mock_configuration(monkeypatch)
    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "destroy",
        MagicMock(return_value={"result": "not found"}),
    )

    assert cloudinary_service.delete_image("recycliq/scans/missing-image") is False


def test_cloudinary_deletion_failure_propagates(monkeypatch):
    _mock_configuration(monkeypatch)
    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "destroy",
        MagicMock(side_effect=Exception("Deletion failed")),
    )

    with pytest.raises(Exception, match="Deletion failed"):
        cloudinary_service.delete_image("recycliq/scans/test-image")


@pytest.mark.parametrize("invalid_public_id", [None, "", "   ", 123, [], {}])
def test_invalid_public_id_rejected_before_network_call(monkeypatch, invalid_public_id):
    mock_destroy = MagicMock()
    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "destroy", mock_destroy)

    with pytest.raises(
        ValueError,
        match="Cloudinary public_id must be a non-empty string",
    ):
        cloudinary_service.delete_image(invalid_public_id)

    mock_destroy.assert_not_called()


@pytest.mark.parametrize("invalid_response", [None, [], "invalid", 123])
def test_invalid_cloudinary_deletion_response(monkeypatch, invalid_response):
    _mock_configuration(monkeypatch)
    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "destroy",
        MagicMock(return_value=invalid_response),
    )

    with pytest.raises(
        RuntimeError,
        match="Cloudinary returned an invalid deletion response",
    ):
        cloudinary_service.delete_image("recycliq/scans/test-image")


@pytest.mark.parametrize("unexpected_response", [{}, {"result": "error"}, {"result": None}])
def test_unexpected_cloudinary_deletion_response(monkeypatch, unexpected_response):
    _mock_configuration(monkeypatch)
    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "destroy",
        MagicMock(return_value=unexpected_response),
    )

    with pytest.raises(
        RuntimeError,
        match="Cloudinary returned an unexpected deletion response",
    ):
        cloudinary_service.delete_image("recycliq/scans/test-image")
