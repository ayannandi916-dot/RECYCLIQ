import pytest
from unittest.mock import MagicMock

from app.services import cloudinary_service as cloudinary_service
from app.core.config import settings

# 1. Successful Cloudinary configuration
def test_successful_cloudinary_configuration(monkeypatch):
    monkeypatch.setattr(
        settings,
        "cloudinary_cloud_name",
        "test-cloud",
    )
    monkeypatch.setattr(
        settings,
        "cloudinary_api_key",
        "test-key",
    )
    monkeypatch.setattr(
        settings,
        "cloudinary_api_secret",
        "test-secret",
    )

    mock_config = MagicMock()

    monkeypatch.setattr(
        cloudinary_service.cloudinary,
        "config",
        mock_config,
    )

    cloudinary_service.configure_cloudinary()

    mock_config.assert_called_once_with(
        cloud_name="test-cloud",
        api_key="test-key",
        api_secret="test-secret",
        secure=True,
    )

def test_missing_cloudinary_credentials(monkeypatch):
    monkeypatch.setattr(
        settings,
        "cloudinary_cloud_name",
        None,
    )
    monkeypatch.setattr(
        settings,
        "cloudinary_api_key",
        None,
    )
    monkeypatch.setattr(
        settings,
        "cloudinary_api_secret",
        None,
    )

    with pytest.raises(
        RuntimeError,
        match="Cloudinary credentials are not configured",
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

    
    with pytest.raises(
        RuntimeError,
        match="Cloudinary returned an invalid upload response."
    ):
        cloudinary_service.upload_image(b"fake-image-data")

# 7. Successful image deletion
def test_successful_image_deletion(monkeypatch):
    monkeypatch.setattr(
        cloudinary_service,
        "configure_cloudinary",
        MagicMock()
    )

    mock_destroy = MagicMock(
        return_value={"result": "ok"}
    )

    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "destroy",
        mock_destroy
    )

    result = cloudinary_service.delete_image(
        "recycliq/scans/test-image"
    )

    assert result is True

    mock_destroy.assert_called_once_with(
        "recycliq/scans/test-image",
        resource_type="image"
    )


# 8. Image not found during deletion
def test_image_deletion_not_found(monkeypatch):
    monkeypatch.setattr(
        cloudinary_service,
        "configure_cloudinary",
        MagicMock()
    )

    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "destroy",
        MagicMock(return_value={"result": "not found"})
    )

    result = cloudinary_service.delete_image(
        "recycliq/scans/missing-image"
    )

    assert result is False


# 9. Cloudinary deletion failure
def test_cloudinary_deletion_failure(monkeypatch):
    monkeypatch.setattr(
        cloudinary_service,
        "configure_cloudinary",
        MagicMock()
    )

    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "destroy",
        MagicMock(side_effect=Exception("Deletion failed"))
    )

    with pytest.raises(Exception, match="Deletion failed"):
        cloudinary_service.delete_image(
            "recycliq/scans/test-image"
        )