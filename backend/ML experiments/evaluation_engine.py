"""Class-aware, one-to-one detection matching and fixed-threshold metrics."""
import math


def box_iou(a, b):
    if len(a) != 4 or len(b) != 4:
        raise ValueError("Boxes must contain four coordinates")
    if not all(math.isfinite(float(v)) for v in (*a, *b)):
        raise ValueError("Box coordinates must be finite")
    ax1, ay1, ax2, ay2 = map(float, a)
    bx1, by1, bx2, by2 = map(float, b)
    if ax2 <= ax1 or ay2 <= ay1 or bx2 <= bx1 or by2 <= by1:
        return 0.0
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def match_image(predictions, ground_truth, class_count=6, match_iou=0.5):
    if class_count < 1 or not 0 <= match_iou <= 1:
        raise ValueError("class_count must be positive and match_iou must be in [0, 1]")
    stats = {c: {"tp": 0, "fp": 0, "fn": 0} for c in range(class_count)}
    for item in [*predictions, *ground_truth]:
        if not isinstance(item.get("class"), int) or not 0 <= item["class"] < class_count:
            raise ValueError("Detection class is outside configured class range")
        box_iou(item["box"], item["box"])
    for cls in range(class_count):
        preds = sorted((p for p in predictions if p["class"] == cls), key=lambda p: float(p["confidence"]), reverse=True)
        targets = [g for g in ground_truth if g["class"] == cls]
        matched = set()
        for pred in preds:
            confidence = float(pred["confidence"])
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("Prediction confidence must be finite and in [0, 1]")
            candidates = [(box_iou(pred["box"], gt["box"]), idx) for idx, gt in enumerate(targets) if idx not in matched]
            best_iou, best_idx = max(candidates, default=(0.0, None))
            if best_idx is not None and best_iou >= match_iou:
                stats[cls]["tp"] += 1
                matched.add(best_idx)
            else:
                stats[cls]["fp"] += 1
        stats[cls]["fn"] = len(targets) - len(matched)
    return stats


def metrics(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def aggregate(class_stats):
    totals = {key: sum(value[key] for value in class_stats.values()) for key in ("tp", "fp", "fn")}
    return {**totals, **metrics(**totals)}
