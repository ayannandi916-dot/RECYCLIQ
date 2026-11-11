from pathlib import Path

ROOT = Path(
    "datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET/train/labels"
)

identical = 0
different = 0

for label in ROOT.glob("*(1).txt"):

    original = label.with_name(
        label.stem.removesuffix("(1)") + ".txt"
    )

    if not original.exists():
        print("NO ORIGINAL:", label.name)
        continue

    if label.read_bytes() == original.read_bytes():
        identical += 1
        print("IDENTICAL:", label.name)
    else:
        different += 1
        print("DIFFERENT:", label.name)

print("\nIdentical:", identical)
print("Different:", different)