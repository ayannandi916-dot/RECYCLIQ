from pathlib import Path
from collections import Counter

ROOT = Path(
    "datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET"
)

extensions = {".jpg", ".jpeg", ".png", ".webp"}

for split in ["train", "valid", "test"]:

    image_dir = ROOT / split / "images"
    label_dir = ROOT / split / "labels"

    images = {
        p.stem: p
        for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    }

    labels = {
        p.stem: p
        for p in label_dir.glob("*.txt")
    }

    missing = sorted(set(images) - set(labels))
    orphan = sorted(set(labels) - set(images))

    print(f"\n========== {split.upper()} ==========")

    print("\nMISSING LABELS:")
    for stem in missing[:10]:
        print("IMAGE:", images[stem].name)

        possible = [
            name for name in labels
            if name.replace("(1)", "") == stem.replace("(1)", "")
        ]

        print("POSSIBLE MATCHES:", possible[:3])

    print("\nORPHAN LABELS:")
    for stem in orphan[:10]:
        print("LABEL:", labels[stem].name)

        possible = [
            name for name in images
            if name.replace("(1)", "") == stem.replace("(1)", "")
        ]

        print("POSSIBLE MATCHES:", possible[:3])