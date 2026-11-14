import cloudinary
import cloudinary.uploader

from app.core.config import settings


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


def upload_image(image_file, folder="recycliq/scans"):
    """
    Upload an image to Cloudinary.
    """

    configure_cloudinary()

    result = cloudinary.uploader.upload(
        image_file,
        folder=folder,
        resource_type="image",
    )

    image_url = result.get("secure_url")
    public_id = result.get("public_id")

    if not image_url or not public_id:
        raise RuntimeError(
            "Cloudinary returned an invalid upload response."
        )

    return {
        "image_url": image_url,
        "public_id": public_id,
    }

def delete_image(public_id: str) -> bool:
    """
    Delete an image from Cloudinary using its public ID.
    """

    configure_cloudinary()

    result = cloudinary.uploader.destroy(
        public_id,
        resource_type="image",
    )

    return result.get("result") == "ok"