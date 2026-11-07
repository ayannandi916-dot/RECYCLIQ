from io import BytesIO

from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile, HTTPException

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

ALLOWED_FORMATS = {
    "JPEG",
    "PNG",
    "WEBP"
}


async def validate_image(file: UploadFile):
    """
    Validate uploaded image size, format and integrity.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required."
        )

    # Read image contents
    contents = await file.read()

    # Reset file pointer for subsequent upload
    await file.seek(0)

    # Check file size
    if len(contents) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image size must not exceed 5 MB."
        )

    # Verify actual image format
    try:
        with Image.open(BytesIO(contents)) as image:
            image.verify()

            if image.format not in ALLOWED_FORMATS:
                raise HTTPException(
                    status_code=400,
                    detail="Only JPEG, PNG and WEBP images are allowed."
                )

    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=400,
            detail="Invalid or corrupted image."
        )

    return True