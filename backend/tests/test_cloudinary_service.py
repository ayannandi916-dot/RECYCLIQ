import pytest
from unittest.mock import MagicMock

from app.services import cloudinary_service as cloudinary_service


# 1. Successful Cloudinary configuration
def test_successful_cloudinary_configuration(monkeypatch):

    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "test-key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "test-secret")

    mock_config = MagicMock()

    monkeypatch.setattr(
        cloudinary_service.cloudinary,
        "config",
        mock_config
    )

    cloudinary_service.configure_cloudinary()

    mock_config.assert_called_once_with(
        cloud_name="test-cloud",
        api_key="test-key",
        api_secret="test-secret",
        secure=True
    )


# 2. Missing Cloudinary credentials
def test_missing_cloudinary_credentials(monkeypatch):

    monkeypatch.delenv(
        "CLOUDINARY_CLOUD_NAME",
        raising=False
    )

    monkeypatch.delenv(
        "CLOUDINARY_API_KEY",
        raising=False
    )

    monkeypatch.delenv(
        "CLOUDINARY_API_SECRET",
        raising=False
    )

    with pytest.raises(
        RuntimeError,
        match="Cloudinary credentials are not configured"
    ):
        cloudinary_service.configure_cloudinary()


# 3. Successful image upload
def test_successful_image_upload(monkeypatch):

    monkeypatch.setattr(
        cloudinary_service,
        "configure_cloudinary",
        MagicMock()
    )

    mock_upload = MagicMock(
        return_value={
            "secure_url": "https://res.cloudinary.com/test/image.jpg",
            "public_id": "recycliq/scans/test-image"
        }
    )

    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "upload",
        mock_upload
    )

    image = b"fake-image-data"

    result = cloudinary_service.upload_image(image)

    assert result["image_url"] == (
        "https://res.cloudinary.com/test/image.jpg"
    )

    assert result["public_id"] == "recycliq/scans/test-image"

    mock_upload.assert_called_once_with(
        image,
        folder="recycliq/scans",
        resource_type="image"
    )


# 4. Custom upload folder
def test_custom_upload_folder(monkeypatch):

    monkeypatch.setattr(
        cloudinary_service,
        "configure_cloudinary",
        MagicMock()
    )

    mock_upload = MagicMock(
        return_value={
            "secure_url": "https://example.com/image.jpg",
            "public_id": "custom/image"
        }
    )

    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "upload",
        mock_upload
    )

    cloudinary_service.upload_image(
        b"fake-image-data",
        folder="custom"
    )

    mock_upload.assert_called_once_with(
        b"fake-image-data",
        folder="custom",
        resource_type="image"
    )


# 5. Cloudinary upload failure
def test_cloudinary_upload_failure(monkeypatch):

    monkeypatch.setattr(
        cloudinary_service,
        "configure_cloudinary",
        MagicMock()
    )

    mock_upload = MagicMock(
        side_effect=Exception("Cloudinary upload failed")
    )

    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "upload",
        mock_upload
    )

    with pytest.raises(
        Exception,
        match="Cloudinary upload failed"
    ):
        cloudinary_service.upload_image(b"fake-image-data")


# 6. Invalid Cloudinary response
def test_invalid_cloudinary_response(monkeypatch):

    monkeypatch.setattr(
        cloudinary_service,
        "configure_cloudinary",
        MagicMock()
    )

    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "upload",
        MagicMock(return_value={})
    )

    with pytest.raises(KeyError):
        cloudinary_service.upload_image(b"fake-image-data")