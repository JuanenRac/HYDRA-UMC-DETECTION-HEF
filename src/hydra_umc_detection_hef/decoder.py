# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/decoder.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Reference decoder: the NMS output of a Hailo model -> detections in the pixels of the original frame.

Pure Python, no Hailo runtime. It is the single place that knows how to undo what the registry's
`io_contract` says was done to the frame before the model saw it:

* the box order (`ymin,xmin,ymax,xmax` or `xmin,ymin,xmax,ymax`) and whether the numbers are
  fractions of the model input (`bbox_normalized`) or pixels of it;
* the resize (`letterbox`: the frame was scaled to fit and padded equally on both sides;
  `stretch`: scaled independently in x and y).

The input is the output of an NMS-by-class model: for each class, a list of rows
`[a, b, c, d, score]` where `a..d` are the four box numbers in the contract's order.
Everything that cannot be a real detection is dropped, never repaired: a row that is not five
finite numbers, a score outside 0..1 or under the threshold, a box that has no area once clipped to
the frame. Kept boxes are clipped to the frame (a box a little over the edge is a real box).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_SCORE_THRESHOLD = 0.0


class DecodeError(ValueError):
    """The contract, the sizes or the output of the model cannot be used."""


@dataclass(frozen=True)
class Detection:
    class_id: int
    label: str
    score: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def as_dict(self) -> dict:
        return {
            "classId": self.class_id,
            "label": self.label,
            "score": self.score,
            "box": {"xMin": self.x_min, "yMin": self.y_min, "xMax": self.x_max, "yMax": self.y_max},
        }


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DecodeError(f"{label} must be a positive integer, got {value!r}")
    return value


def letterbox_geometry(frame_w: int, frame_h: int, in_w: int, in_h: int) -> tuple[float, float, float]:
    """(scale, pad_x, pad_y) of a letterbox: the frame scaled to fit the input and centred, padding floored."""
    scale = min(in_w / frame_w, in_h / frame_h)
    new_w = round(frame_w * scale)
    new_h = round(frame_h * scale)
    return scale, float((in_w - new_w) // 2), float((in_h - new_h) // 2)


def decode_nms_by_class(
    output: object,
    io_contract: dict,
    *,
    input_shape: tuple[int, int, int] | list[int],
    frame_size: tuple[int, int],
    classes: list[str] | tuple[str, ...],
    score_threshold: float | None = None,
) -> list[Detection]:
    """Detections, best score first, in the pixels of a `frame_size` = (width, height) frame.

    `input_shape` is the model input as the registry states it, (height, width, channels).
    `score_threshold` overrides the contract's own (which in turn defaults to 0)."""
    if not isinstance(io_contract, dict) or not isinstance(io_contract.get("output"), dict) or not isinstance(io_contract.get("input"), dict):
        raise DecodeError("io_contract must have an input and an output block")
    out, inp = io_contract["output"], io_contract["input"]
    if out.get("format") != "hailo_nms_by_class":
        raise DecodeError(f"only the hailo_nms_by_class output format is decoded, got {out.get('format')!r}")
    if len(input_shape) != 3:
        raise DecodeError("input_shape must be (height, width, channels)")
    in_h = _positive_int(input_shape[0], "input_shape height")
    in_w = _positive_int(input_shape[1], "input_shape width")
    frame_w = _positive_int(frame_size[0], "frame width")
    frame_h = _positive_int(frame_size[1], "frame height")
    if not isinstance(output, (list, tuple)):
        raise DecodeError("output must be a list with one entry per class")
    if len(output) != len(classes):
        raise DecodeError(f"output has {len(output)} classes, the model has {len(classes)}")
    threshold = score_threshold if score_threshold is not None else out.get("score_threshold", DEFAULT_SCORE_THRESHOLD)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise DecodeError(f"score threshold must be a number from 0 to 1, got {threshold!r}")
    per_class_cap = out.get("max_detections_per_class")
    ymin_first = out.get("bbox_order") == "ymin,xmin,ymax,xmax"
    normalized = bool(out.get("bbox_normalized"))
    resize = inp.get("resize")
    if resize == "letterbox":
        scale, pad_x, pad_y = letterbox_geometry(frame_w, frame_h, in_w, in_h)
        scale_x = scale_y = scale
    elif resize == "stretch":
        scale_x, scale_y = in_w / frame_w, in_h / frame_h
        pad_x = pad_y = 0.0
    else:
        raise DecodeError(f"unknown resize {resize!r}")

    found: list[Detection] = []
    for class_id, rows in enumerate(output):
        if not isinstance(rows, (list, tuple)):
            raise DecodeError(f"output[{class_id}] must be a list of rows")
        kept = 0
        for row in rows:
            if per_class_cap is not None and kept >= per_class_cap:
                break
            if not isinstance(row, (list, tuple)) or len(row) != 5:
                continue
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in row):
                continue
            a, b, c, d, score = (float(v) for v in row)
            if not 0.0 <= score <= 1.0 or score < threshold:
                continue
            y0, x0, y1, x1 = (a, b, c, d) if ymin_first else (b, a, d, c)
            if normalized:
                x0, x1, y0, y1 = x0 * in_w, x1 * in_w, y0 * in_h, y1 * in_h
            x0, x1 = (x0 - pad_x) / scale_x, (x1 - pad_x) / scale_x
            y0, y1 = (y0 - pad_y) / scale_y, (y1 - pad_y) / scale_y
            x0, x1 = max(0.0, min(x0, x1)), min(float(frame_w), max(x0, x1))
            y0, y1 = max(0.0, min(y0, y1)), min(float(frame_h), max(y0, y1))
            if x1 <= x0 or y1 <= y0:
                continue
            found.append(Detection(class_id, str(classes[class_id]), score, x0, y0, x1, y1))
            kept += 1
    found.sort(key=lambda det: (-det.score, det.class_id))
    return found
