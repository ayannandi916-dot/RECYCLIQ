from pathlib import Path
import cv2

ROOT = Path(
    "datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET"
)

OUTPUT = Path("segmentation_inspection")
OUTPUT.mkdir(exist_ok=True)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

checked = 0

for split in ["train", "valid", "test"]:

    image_dir = ROOT / split / "images"
    label_dir = ROOT / split / "labels"

    for label_file in label_dir.glob("*.txt"):

        lines = label_file.read_text().splitlines()

        polygons = [
            line.split()
            for line in lines
            if len(line.split()) > 5
        ]

        if not polygons:
            continue

        image_path = next(
            (
                image_dir / f"{label_file.stem}{ext}"
                for ext in IMAGE_EXTENSIONS
                if (image_dir / f"{label_file.stem}{ext}").exists()
            ),
            None
        )

        if image_path is None:
            continue

        image = cv2.imread(str(image_path))

        if image is None:
            continue

        height, width = image.shape[:2]

        for parts in polygons:

            try:
                class_id = int(parts[0])
                coordinates = list(map(float, parts[1:]))

                if len(coordinates) < 6 or len(coordinates) % 2:
                    continue

                points = [
                    (
                        round(coordinates[i] * width),
                        round(coordinates[i + 1] * height)
                    )
                    for i in range(0, len(coordinates), 2)
                ]

                for point in points:
                    if not (0 <= point[0] <= width and
                            0 <= point[1] <= height):
                        print("Suspicious coordinate:", label_file.name)

                cv2.polylines(
                    image,
                    [__import__("numpy").array(points, dtype="int32")],
                    True,
                    (0, 255, 0),
                    2
                )

            except (ValueError, IndexError):
                print("Could not parse:", label_file.name)

        output_path = OUTPUT / f"{checked}_{image_path.name}"
        cv2.imwrite(str(output_path), image)

        checked += 1

        if checked >= 12:
            break

    if checked >= 12:
        break

print(f"\nGenerated {checked} annotated inspection images.")
print(f"Check the folder: {OUTPUT}")