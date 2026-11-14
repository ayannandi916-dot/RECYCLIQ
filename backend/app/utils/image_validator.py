from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile, HTTPException

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_PIXELS = 25_000_000  # 25 Megapixels

ALLOWED_FORMATS = {
    "JPEG",
    "PNG",
    "WEBP",
}


async def validate_image(file: UploadFile):
    """
    Validate uploaded image size, format, dimensions and integrity.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    contents = await file.read(MAX_FILE_SIZE + 1)

    await file.seek(0)

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image size must not exceed 5 MB.",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(BytesIO(contents)) as image:

                if image.format not in ALLOWED_FORMATS:
                    raise HTTPException(
                        status_code=400,
                        detail="Only JPEG, PNG and WEBP images are allowed.",
                    )

                width, height = image.size

                if width <= 0 or height <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid image dimensions.",
                    )

                if width * height > MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=413,
                        detail="Image dimensions must not exceed 25 megapixels.",
                    )

                image.verify()

    except HTTPException:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or corrupted image.",
        )

    return True