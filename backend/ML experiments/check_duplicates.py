from pathlib import Path
import hashlib

ROOT = Path(
    "datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET/train/images"
)

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

checked = 0
identical = 0
different = 0

for image in ROOT.glob("*(1).*"):

    original_name = image.stem.removesuffix("(1)") + image.suffix
    original = image.with_name(original_name)

    if not original.exists():
        continue

    checked += 1

    if sha256(image) == sha256(original):
        identical += 1
        print("IDENTICAL:", image.name)
    else:
        different += 1
        print("DIFFERENT:", image.name)

print("\n========== SUMMARY ==========")
print("Duplicate pairs checked:", checked)
print("Identical:", identical)
print("Different:", different)