import asyncio
from io import BytesIO

from PIL import Image
from fastapi import UploadFile
from fastapi.exceptions import HTTPException

from app.utils.image_validator import validate_image


async def main():

    # Test 1: Valid JPEG image
    image_buffer = BytesIO()
    Image.new("RGB", (100, 100), "red").save(
        image_buffer,
        format="JPEG"
    )

    image_buffer.seek(0)

    valid_file = UploadFile(
        filename="test.jpg",
        file=BytesIO(image_buffer.getvalue())
    )

    try:
        result = await validate_image(valid_file)
        print("Valid image:", result)
    except HTTPException as error:
        print("Valid image failed:", error.detail)

    # Test 2: Invalid file
    invalid_file = UploadFile(
        filename="test.txt",
        file=BytesIO(b"This is not an image")
    )

    try:
        await validate_image(invalid_file)
        print("Invalid file: Unexpectedly accepted")
    except HTTPException as error:
        print("Invalid file rejected:", error.detail)

    # Test 3: Oversized file
    oversized_file = UploadFile(
        filename="large.jpg",
        file=BytesIO(b"x" * (6 * 1024 * 1024))
    )

    try:
        await validate_image(oversized_file)
        print("Oversized file: Unexpectedly accepted")
    except HTTPException as error:
        print("Oversized file rejected:", error.detail)


asyncio.run(main())