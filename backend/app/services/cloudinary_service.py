from io import BytesIO
import logging

import cloudinary
import cloudinary.uploader

from app.core.config import settings


logger = logging.getLogger(__name__)

# Request-level timeouts prevent Cloudinary calls from waiting indefinitely.
CLOUDINARY_UPLOAD_TIMEOUT_SECONDS = 30
CLOUDINARY_DELETE_TIMEOUT_SECONDS = 15


def configure_cloudinary():
    """
    Configure Cloudinary using centralized application settings.
    """

    cloud_name = settings.cloudinary_cloud_name
    api_key = settings.cloudinary_api_key
    api_secret = settings.cloudinary_api_secret

    if not all([cloud_name, api_key, api_secret]):
        raise RuntimeError(
            "Cloudinary credentials are not configured!"
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def _prepare_upload_file(image_file):
    """
    Give in-memory streams a filename, as expected by the Python SDK.
    Bytes and existing file-like objects are otherwise left unchanged.
    """
    if isinstance(image_file, BytesIO) and not getattr(image_file, "name", None):
        image_file.name = "recycliq-upload"

    return image_file


def upload_image(image_file, folder="recycliq/scans"):
    """
    Upload an image to Cloudinary with a bounded request timeout.

    SDK/network exceptions are intentionally allowed to propagate so the
    scan workflow can mark the scan as failed and apply its cleanup policy.
    """

    if image_file is None:
        raise ValueError("Image file cannot be None.")

    configure_cloudinary()

    upload_file = _prepare_upload_file(image_file)

    result = cloudinary.uploader.upload(
        upload_file,
        folder=folder,
        resource_type="image",
        timeout=CLOUDINARY_UPLOAD_TIMEOUT_SECONDS,
    )

    if not isinstance(result, dict):
        raise RuntimeError(
            "Cloudinary returned an invalid upload response."
        )

    image_url = result.get("secure_url")
    public_id = result.get("public_id")

    if (
        not isinstance(image_url, str)
        or not image_url.strip()
        or not isinstance(public_id, str)
        or not public_id.strip()
    ):
        raise RuntimeError(
            "Cloudinary returned an invalid upload response."
        )

    return {
        "image_url": image_url.strip(),
        "public_id": public_id.strip(),
    }


def delete_image(public_id: str) -> bool:
    """
    Delete an image from Cloudinary with a bounded request timeout.

    Returns True only when Cloudinary confirms deletion. A missing asset
    returns False. SDK/network errors and malformed responses are surfaced.
    """

    if not isinstance(public_id, str) or not public_id.strip():
        raise ValueError("Cloudinary public_id must be a non-empty string.")

    configure_cloudinary()

    result = cloudinary.uploader.destroy(
        public_id.strip(),
        resource_type="image",
        timeout=CLOUDINARY_DELETE_TIMEOUT_SECONDS,
    )

    if not isinstance(result, dict):
        raise RuntimeError(
            "Cloudinary returned an invalid deletion response."
        )

    deletion_status = result.get("result")

    if deletion_status == "ok":
        return True

    if deletion_status == "not found":
        return False

    raise RuntimeError(
        "Cloudinary returned an unexpected deletion response."
    )
