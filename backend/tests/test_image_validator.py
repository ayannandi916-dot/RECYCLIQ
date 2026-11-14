import asyncio
from io import BytesIO

import pytest
from PIL import Image
from fastapi import HTTPException
from fastapi import UploadFile

from app.utils.image_validator import (
    validate_image,
    MAX_FILE_SIZE,
    MAX_IMAGE_PIXELS,
)

def create_image(format="JPEG", size=(100, 100)):
    """Generate an in-memory test image."""
    image = Image.new("RGB", size, color="red")

    buffer = BytesIO()
    image.save(buffer, format=format)

    buffer.seek(0)
    return buffer.getvalue()

def create_upload_file(content, filename="test.jpg"):
    """Create a FastAPI UploadFile for testing."""
    return UploadFile(
        filename=filename,
        file=BytesIO(content)
    )


def run_validation(file):
    """Run the asynchronous validator."""
    return asyncio.run(validate_image(file))


# 1. Valid JPEG image
def test_valid_jpeg_image():
    file = create_upload_file(create_image("JPEG"))

    assert run_validation(file) is True


# 2. Valid PNG image
def test_valid_png_image():
    file = create_upload_file(
        create_image("PNG"),
        "test.png"
    )

    assert run_validation(file) is True


# 3. Valid WEBP image
def test_valid_webp_image():
    file = create_upload_file(
        create_image("WEBP"),
        "test.webp"
    )

    assert run_validation(file) is True


# 4. Missing filename
def test_missing_filename():
    file = create_upload_file(
        create_image(),
        filename=""
    )

    with pytest.raises(HTTPException) as exc:
        run_validation(file)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Filename is required."


# 5. Empty file
def test_empty_file():
    file = create_upload_file(b"")

    with pytest.raises(HTTPException) as exc:
        run_validation(file)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Uploaded file is empty."


# 6. File larger than 5 MB
def test_file_exceeds_maximum_size():
    content = b"x" * (MAX_FILE_SIZE + 1)
    file = create_upload_file(content)

    with pytest.raises(HTTPException) as exc:
        run_validation(file)

    assert exc.value.status_code == 413


# 7. Corrupted image
def test_corrupted_image():
    file = create_upload_file(
        b"This is not a valid image",
        "corrupted.jpg"
    )

    with pytest.raises(HTTPException) as exc:
        run_validation(file)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid or corrupted image."


# 8. Unsupported image format (GIF)
def test_unsupported_image_format():
    file = create_upload_file(
        create_image("GIF"),
        "test.gif"
    )

    with pytest.raises(HTTPException) as exc:
        run_validation(file)

    assert exc.value.status_code == 400
    assert exc.value.detail == (
        "Only JPEG, PNG and WEBP images are allowed."
    )


# 9. File pointer resets after validation
def test_file_pointer_resets():
    content = create_image("JPEG")
    file = create_upload_file(content)

    assert run_validation(file) is True

    remaining_content = asyncio.run(file.read())

    assert remaining_content == content

# 10. Image exceeding maximum pixel count
def test_image_exceeds_maximum_pixels():
    content = create_image(
        "JPEG",
        size=(5001, 5000),
    )

    file = create_upload_file(content)

    with pytest.raises(HTTPException) as exc:
        run_validation(file)

    assert exc.value.status_code == 413
    assert exc.value.detail == (
        "Image dimensions must not exceed 25 megapixels."
    )


# 11. Image exactly at maximum pixel count
def test_image_at_maximum_pixel_limit():
    content = create_image(
        "JPEG",
        size=(5000, 5000),
    )

    file = create_upload_file(content)

    assert run_validation(file) is True


# 12. Image below maximum pixel count
def test_image_below_maximum_pixel_limit():
    content = create_image(
        "JPEG",
        size=(4999, 5000),
    )

    file = create_upload_file(content)

    assert run_validation(file) is True


# 13. MIME type spoofing
def test_mime_type_does_not_override_actual_format():
    content = create_image("JPEG")

    file = UploadFile(
        filename="fake.png",
        file=BytesIO(content),
    )

    assert run_validation(file) is True


# 14. File pointer resets after oversized upload
def test_file_pointer_resets_after_oversized_upload():
    content = b"x" * (MAX_FILE_SIZE + 1)
    file = create_upload_file(content)

    with pytest.raises(HTTPException):
        run_validation(file)

    remaining_content = asyncio.run(file.read())

    assert remaining_content == content