import os
from pathlib import Path

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv


# Load environment variables
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def configure_cloudinary():
    """
    Configure Cloudinary using environment variables.
    """

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    if not all([cloud_name, api_key, api_secret]):
        raise RuntimeError(
            "Cloudinary credentials are not configured!"
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )


def upload_image(image_file, folder="recycliq/scans"):
    """
    Upload an image to Cloudinary.
    """

    configure_cloudinary()

    result = cloudinary.uploader.upload(
        image_file,
        folder=folder,
        resource_type="image"
    )

    return {
        "image_url": result["secure_url"],
        "public_id": result["public_id"]
    }