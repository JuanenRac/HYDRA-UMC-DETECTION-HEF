# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/accuracy.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The accuracy of a quantized model, measured after compilation, as a number the registry can keep and a node can insist on.

Compiling a model to a `.hef` quantizes it, and quantization can cost accuracy. The measure here is the mean average precision at an IoU of 0.5 (mAP@0.5,
all-point interpolation per class, the mean taken over the classes that have at least one true box). It is computed from two files that do not need the
Hailo runtime to be read: the detections the model produced for a validation set (decoded to pixel boxes, for example with `decoder.py`) and the true boxes of
that set (for example the labels of the synthetic dataset generator). Running the compiled model on the validation images to produce the first file needs
the accelerator, and is not done here; the arithmetic that turns the two files into a number is.

    detections file:  {"images": {"img-1": [{"class_id": 0, "score": 0.9, "box": {"x_min": 1, "y_min": 2, "x_max": 30, "y_max": 40}}, ...]}}
    truth file:       {"images": {"img-1": [{"class_id": 0, "box": {"x_min": 2, "y_min": 2, "x_max": 31, "y_max": 41}}, ...]}}

`record_accuracy` puts the result in the `accuracy` block of the entry: the quantized score, the score of the reference (the model before quantization, measured
on the same truth, or a number given), the SHA-256 of the truth file and the number of images. The registry can then refuse to load a model whose ratio is below a
minimum (`safe_load(..., min_accuracy_ratio=...)`), and a gate that is on refuses an entry with no measurement.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from typing import Any

from .registry import ModelEntry, RegistryError

MAX_IMAGES = 100_000
MAX_BOXES_PER_IMAGE = 1000
IOU_THRESHOLD = 0.5
BOX_KEYS = ("x_min", "y_min", "x_max", "y_max")


class AccuracyError(RegistryError):
    """A detections file, a truth file or a measurement cannot be used."""


def _box(raw: Any, where: str) -> tuple[float, float, float, float]:
    if not isinstance(raw, dict) or set(raw) != set(BOX_KEYS):
        raise AccuracyError(f"{where}: box must have exactly {', '.join(BOX_KEYS)}")
    values = []
    for key in BOX_KEYS:
        v = raw[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise AccuracyError(f"{where}: box.{key} must be a finite number")
        values.append(float(v))
    x0, y0, x1, y1 = values
    if x1 < x0 or y1 < y0:
        raise AccuracyError(f"{where}: box must have x_min <= x_max and y_min <= y_max")
    return x0, y0, x1, y1


def _images(doc: Any, what: str, scored: bool) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(doc, dict) or set(doc) != {"images"} or not isinstance(doc["images"], dict):
        raise AccuracyError(f'the {what} file is an object {{"images": {{name: [boxes]}}}}')
    images = doc["images"]
    if len(images) > MAX_IMAGES:
        raise AccuracyError(f"the {what} file holds more than {MAX_IMAGES} images")
    out: dict[str, list[dict[str, Any]]] = {}
    for name, items in images.items():
        if not isinstance(items, list) or len(items) > MAX_BOXES_PER_IMAGE:
            raise AccuracyError(f"{what} {name!r}: a list of at most {MAX_BOXES_PER_IMAGE} boxes is expected")
        parsed = []
        for index, item in enumerate(items):
            where = f"{what} {name!r}[{index}]"
            allowed = {"class_id", "box", "score"} if scored else {"class_id", "box"}
            if not isinstance(item, dict) or set(item) != allowed:
                raise AccuracyError(f"{where}: expected exactly {sorted(allowed)}")
            class_id = item["class_id"]
            if isinstance(class_id, bool) or not isinstance(class_id, int) or class_id < 0:
                raise AccuracyError(f"{where}: class_id must be a non-negative integer")
            entry: dict[str, Any] = {"class_id": class_id, "box": _box(item["box"], where)}
            if scored:
                score = item["score"]
                if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0.0 <= score <= 1.0:
                    raise AccuracyError(f"{where}: score must be a number in 0..1")
                entry["score"] = float(score)
            parsed.append(entry)
        out[str(name)] = parsed
    return out


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _average_precision(ranked: list[tuple[float, bool]], positives: int) -> float:
    """All-point interpolated AP of detections already marked true or false positive and sorted by score."""
    if positives == 0:
        return 0.0
    tp = fp = 0
    points: list[tuple[float, float]] = []  # (recall, precision)
    for _score, hit in ranked:
        tp, fp = (tp + 1, fp) if hit else (tp, fp + 1)
        points.append((tp / positives, tp / (tp + fp)))
    recalls = [0.0] + [r for r, _ in points] + [1.0]
    precisions = [0.0] + [p for _, p in points] + [0.0]
    for i in range(len(precisions) - 2, -1, -1):
        precisions[i] = max(precisions[i], precisions[i + 1])
    return sum((recalls[i + 1] - recalls[i]) * precisions[i + 1] for i in range(len(recalls) - 1) if recalls[i + 1] != recalls[i])


def map50(detections_doc: Any, truth_doc: Any) -> dict[str, Any]:
    """{"map50", "per_class", "images", "dataset_sha256"}: the mAP@0.5 of the detections against the truth. A detection counts once and only against the
    best still-free true box of its class in its image; detections of an image the truth does not list are false positives."""
    truth = _images(truth_doc, "truth", scored=False)
    found = _images(detections_doc, "detections", scored=True)
    classes = sorted({t["class_id"] for items in truth.values() for t in items})
    if not classes:
        raise AccuracyError("the truth file holds no box: there is nothing to measure against")
    per_class: dict[int, float] = {}
    for class_id in classes:
        positives = sum(1 for items in truth.values() for t in items if t["class_id"] == class_id)
        ranked: list[tuple[float, bool]] = []
        candidates = [(d["score"], name, d["box"]) for name, items in found.items() for d in items if d["class_id"] == class_id]
        candidates.sort(key=lambda c: (-c[0], c[1]))
        taken: dict[str, set[int]] = {}
        for score, name, box in candidates:
            best, best_iou = -1, IOU_THRESHOLD
            for index, t in enumerate(truth.get(name, [])):
                if t["class_id"] != class_id or index in taken.get(name, set()):
                    continue
                overlap = iou(box, t["box"])
                if overlap >= best_iou:
                    best, best_iou = index, overlap
            if best >= 0:
                taken.setdefault(name, set()).add(best)
            ranked.append((score, best >= 0))
        per_class[class_id] = _average_precision(ranked, positives)
    canonical = json.dumps(truth_doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"map50": sum(per_class.values()) / len(per_class), "per_class": {str(k): v for k, v in per_class.items()}, "images": len(truth),
            "dataset_sha256": hashlib.sha256(canonical).hexdigest()}


def record_accuracy(entry: ModelEntry, quantized: dict[str, Any], reference: float | dict[str, Any]) -> ModelEntry:
    """A copy of `entry` with its `accuracy` block: `quantized` is the result of `map50` for the compiled model; `reference` is a number (the score of
    the model before quantization, measured elsewhere on the same set) or the result of `map50` for it on the same truth."""
    if isinstance(reference, dict):
        if reference["dataset_sha256"] != quantized["dataset_sha256"]:
            raise AccuracyError("the reference was measured on another truth file than the quantized model")
        ref_value = reference["map50"]
    else:
        ref_value = reference
    if isinstance(ref_value, bool) or not isinstance(ref_value, (int, float)) or not math.isfinite(ref_value) or not 0.0 < ref_value <= 1.0:
        raise AccuracyError("the reference score must be a number above 0 and at most 1")
    block = {"metric": "map50", "quantized": round(float(quantized["map50"]), 6), "reference": round(float(ref_value), 6),
             "dataset_sha256": quantized["dataset_sha256"], "samples": int(quantized["images"])}
    return replace(entry, accuracy=block)
