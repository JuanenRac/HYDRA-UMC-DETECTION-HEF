# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_simulation_bench.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Simulation bench: the real decoder, accuracy measure and model registry against a simulated accelerator and a simulated fleet.

The accelerator is a function that takes the true boxes of a scene drawn from a fixed seed and writes them the way the chip does (the `hailo_nms_by_class` tensor of
a letterboxed or stretched input, with the order and the unit of the contract), with a chosen amount of jitter, missed objects, invented ones and garbage rows.
The real decoder brings them back to the pixels of the frame and the real mAP measure scores them. The fleet is a set of nodes that report the model they loaded
to a real registry on disk. Nothing here says how a real Hailo chip, a real network or a real camera behave: that needs the hardware."""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import pytest

from hydra_umc_detection_hef.accuracy import map50
from hydra_umc_detection_hef.decoder import DecodeError, decode_nms_by_class, letterbox_geometry
from hydra_umc_detection_hef.loaded import LoadedModels
from hydra_umc_detection_hef.registry import add_entry, io_contract_sha256, load_registry, write_registry

SEED = 20260101
CLASSES = ["solder_bridge", "missing_component", "tombstone"]
SHAPE = (640, 640, 3)


def _contract(resize: str = "letterbox", order: str = "ymin,xmin,ymax,xmax", normalized: bool = True, threshold: float = 0.25) -> dict:
    return {
        "input": {"layout": "NHWC", "color_order": "RGB", "dtype": "uint8", "normalization": "on-chip", "resize": resize, "pad_value": 114},
        "output": {"format": "hailo_nms_by_class", "bbox_order": order, "bbox_normalized": normalized, "nms_on_chip": True,
                   "max_detections_per_class": 100, "score_threshold": threshold, "iou_threshold": 0.45},
    }


def _scene(rng: random.Random, frame: tuple[int, int], count: int) -> list[tuple[int, tuple[float, float, float, float]]]:
    boxes = []
    for _ in range(count):
        w, h = rng.uniform(40, frame[0] / 4), rng.uniform(40, frame[1] / 4)
        x, y = rng.uniform(0, frame[0] - w), rng.uniform(0, frame[1] - h)
        boxes.append((rng.randrange(len(CLASSES)), (x, y, x + w, y + h)))
    return boxes


def _chip(rng: random.Random, truth, frame, contract, *, jitter: float = 0.0, miss: float = 0.0, invent: int = 0, garbage: int = 0) -> list[list[list[float]]]:
    """What the accelerator would write for this frame, per class, one row per detection."""
    inp, out = contract["input"], contract["output"]
    in_h, in_w = SHAPE[0], SHAPE[1]
    if inp["resize"] == "letterbox":
        scale, pad_x, pad_y = letterbox_geometry(frame[0], frame[1], in_w, in_h)
        sx = sy = scale
    else:
        sx, sy, pad_x, pad_y = in_w / frame[0], in_h / frame[1], 0.0, 0.0
    tensor: list[list[list[float]]] = [[] for _ in CLASSES]

    def put(class_id: int, box, score: float) -> None:
        x0, y0, x1, y1 = box
        px0, px1, py0, py1 = x0 * sx + pad_x, x1 * sx + pad_x, y0 * sy + pad_y, y1 * sy + pad_y
        if out["bbox_normalized"]:
            px0, px1, py0, py1 = px0 / in_w, px1 / in_w, py0 / in_h, py1 / in_h
        row = [py0, px0, py1, px1, score] if out["bbox_order"] == "ymin,xmin,ymax,xmax" else [px0, py0, px1, py1, score]
        tensor[class_id].append(row)

    for class_id, (x0, y0, x1, y1) in truth:
        if rng.random() < miss:
            continue
        j = jitter * min(x1 - x0, y1 - y0)
        box = (x0 + rng.uniform(-j, j), y0 + rng.uniform(-j, j), x1 + rng.uniform(-j, j), y1 + rng.uniform(-j, j))
        put(class_id, box, round(rng.uniform(0.6, 0.99), 3))
    for _ in range(invent):
        class_id, box = _scene(rng, frame, 1)[0]
        put(class_id, box, round(rng.uniform(0.3, 0.9), 3))
    for _ in range(garbage):
        tensor[rng.randrange(len(CLASSES))].append([float("nan"), 0.1, 0.2, 0.3, 0.9])
        tensor[rng.randrange(len(CLASSES))].append([0.1, 0.1, 0.2])
        tensor[rng.randrange(len(CLASSES))].append([0.1, 0.1, 0.2, 0.2, 1.7])
    return tensor


def _documents(rng: random.Random, frames: int, frame: tuple[int, int], contract: dict, **chip) -> tuple[dict, dict]:
    truth_doc, found_doc = {"images": {}}, {"images": {}}
    for index in range(frames):
        name = f"frame-{index:03d}"
        truth = _scene(rng, frame, rng.randint(1, 6))
        decoded = decode_nms_by_class(_chip(rng, truth, frame, contract, **chip), contract, input_shape=SHAPE, frame_size=frame, classes=CLASSES, score_threshold=0.0)
        truth_doc["images"][name] = [{"class_id": c, "box": dict(zip(("x_min", "y_min", "x_max", "y_max"), box, strict=True))} for c, box in truth]
        found_doc["images"][name] = [{"class_id": d.class_id, "score": d.score, "box": {"x_min": d.x_min, "y_min": d.y_min, "x_max": d.x_max, "y_max": d.y_max}} for d in decoded]
    return truth_doc, found_doc


@pytest.mark.parametrize("frame", [(1280, 720), (640, 640), (720, 1280), (1920, 1080), (333, 777)])
@pytest.mark.parametrize("resize", ["letterbox", "stretch"])
def test_a_perfect_chip_is_decoded_back_to_the_true_boxes_in_every_geometry(frame, resize):
    rng = random.Random(SEED)
    contract = _contract(resize)
    truth = _scene(rng, frame, 8)
    decoded = decode_nms_by_class(_chip(rng, truth, frame, contract), contract, input_shape=SHAPE, frame_size=frame, classes=CLASSES, score_threshold=0.0)
    assert len(decoded) == len(truth)
    for class_id, (x0, y0, x1, y1) in truth:
        near = [d for d in decoded if d.class_id == class_id and abs(d.x_min - x0) < 2 and abs(d.y_min - y0) < 2 and abs(d.x_max - x1) < 2 and abs(d.y_max - y1) < 2]
        assert near, (class_id, (x0, y0, x1, y1))


@pytest.mark.parametrize(("order", "normalized"), [("ymin,xmin,ymax,xmax", True), ("ymin,xmin,ymax,xmax", False), ("xmin,ymin,xmax,ymax", True), ("xmin,ymin,xmax,ymax", False)])
def test_the_order_and_the_unit_of_the_contract_give_the_same_boxes(order, normalized):
    frame = (1280, 720)
    reference = _contract()
    other = _contract(order=order, normalized=normalized)
    truth = _scene(random.Random(SEED), frame, 6)
    a = decode_nms_by_class(_chip(random.Random(1), truth, frame, reference), reference, input_shape=SHAPE, frame_size=frame, classes=CLASSES, score_threshold=0.0)
    b = decode_nms_by_class(_chip(random.Random(1), truth, frame, other), other, input_shape=SHAPE, frame_size=frame, classes=CLASSES, score_threshold=0.0)
    assert [(d.class_id, round(d.x_min, 6), round(d.y_max, 6)) for d in a] == [(d.class_id, round(d.x_min, 6), round(d.y_max, 6)) for d in b]


def test_a_chip_without_errors_scores_a_map_of_one():
    contract = _contract()
    truth_doc, found_doc = _documents(random.Random(SEED), 30, (1280, 720), contract)
    assert map50(found_doc, truth_doc)["map50"] == pytest.approx(1.0, abs=1e-9)


def test_the_map_falls_as_the_chip_gets_worse_and_never_goes_below_zero_or_above_one():
    contract = _contract()
    scores = []
    for jitter, miss, invent in [(0.0, 0.0, 0), (0.1, 0.0, 0), (0.1, 0.2, 1), (0.3, 0.4, 3), (0.6, 0.8, 6)]:
        truth_doc, found_doc = _documents(random.Random(SEED + 1), 40, (1280, 720), contract, jitter=jitter, miss=miss, invent=invent)
        scores.append(map50(found_doc, truth_doc)["map50"])
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True) and scores[0] > 0.99 and scores[-1] < 0.5


def test_rows_the_chip_garbles_are_dropped_and_do_not_change_the_result():
    contract = _contract()
    frame = (1280, 720)
    truth = _scene(random.Random(SEED + 2), frame, 9)
    clean = _chip(random.Random(5), truth, frame, contract, jitter=0.1)
    dirty = [list(rows) for rows in clean]
    for rows in dirty:
        rows += [[float("nan"), 0.1, 0.2, 0.3, 0.9], [0.1, 0.1, 0.2], [0.1, 0.1, 0.2, 0.2, 1.7], [0.1, 0.1, 0.2, 0.2, -0.1], [float("inf"), 0, 0, 0, 0.5], "row", None, [True, 0, 0, 0, 0.5]]
    args = {"input_shape": SHAPE, "frame_size": frame, "classes": CLASSES, "score_threshold": 0.0}
    assert decode_nms_by_class(dirty, contract, **args) == decode_nms_by_class(clean, contract, **args)


def test_a_threshold_over_the_scores_of_the_chip_leaves_nothing_and_one_under_them_leaves_everything():
    contract = _contract()
    frame = (1280, 720)
    tensor = _chip(random.Random(SEED + 3), _scene(random.Random(SEED + 3), frame, 7), frame, contract)
    total = sum(len(rows) for rows in tensor)
    args = {"input_shape": SHAPE, "frame_size": frame, "classes": CLASSES}
    assert len(decode_nms_by_class(tensor, contract, score_threshold=0.0, **args)) == total
    assert decode_nms_by_class(tensor, contract, score_threshold=1.0, **args) == []
    assert all(d.score >= 0.8 for d in decode_nms_by_class(tensor, contract, score_threshold=0.8, **args))


def test_a_chip_that_answers_with_the_wrong_shape_is_refused_not_guessed():
    contract = _contract()
    args = {"input_shape": SHAPE, "frame_size": (1280, 720), "classes": CLASSES}
    for output in ("nothing", {"0": []}, [[], []], [[], [], [], []], [[], [], "rows"]):
        with pytest.raises(DecodeError):
            decode_nms_by_class(output, contract, **args)
    with pytest.raises(DecodeError):
        decode_nms_by_class([[], [], []], {"input": {"resize": "letterbox"}, "output": {"format": "yolo_raw"}}, **args)


def test_the_same_seed_gives_the_same_score_and_another_seed_does_not():
    contract = _contract()

    def run(seed: int) -> float:
        truth_doc, found_doc = _documents(random.Random(seed), 25, (1280, 720), contract, jitter=0.3, miss=0.3, invent=2)
        return map50(found_doc, truth_doc)["map50"]

    assert run(SEED) == run(SEED) and run(SEED) != run(SEED + 1)


# ----------------------------------------------------------------------------------------------------------------------------- the fleet
def _registry(tmp_path: Path, versions: list[str]) -> list:
    models = tmp_path / "models"
    models.mkdir()
    entries: list = []
    for version in versions:
        (models / f"pcb-{version}.hef").write_bytes(hashlib.sha256(version.encode()).digest() * 8)
        entries.append(add_entry(entries, models_dir=models, name="pcb", version=version, task="detection", input_shape=SHAPE, classes=tuple(CLASSES),
                                 hef_path=f"pcb-{version}.hef", hailo_arch="hailo8", io_contract=_contract()))
    write_registry(tmp_path / "registry.json", entries)
    return load_registry(tmp_path / "registry.json")


def _report(entry, node: str, **over) -> dict:
    body = {"node": node, "model_name": entry.name, "model_version": entry.version, "model_sha256": entry.sha256, "hailo_arch": entry.hailo_arch,
            "io_contract_sha256": io_contract_sha256(entry.io_contract)}
    body.update(over)
    return body


def test_a_fleet_that_reports_old_tampered_and_unknown_models_is_told_apart(tmp_path: Path):
    entries = _registry(tmp_path, ["0.1.0", "0.2.0", "0.3.0"])
    old, new = entries[0], entries[2]
    loaded = LoadedModels(clock=lambda: 1_800_000_000.0)
    verdicts = {
        "cell-1": loaded.record(entries, _report(new, "cell-1"))["verdict"],
        "cell-2": loaded.record(entries, _report(old, "cell-2"))["verdict"],
        "cell-3": loaded.record(entries, _report(new, "cell-3", model_sha256="0" * 64))["verdict"],
        "cell-4": loaded.record(entries, _report(new, "cell-4", hailo_arch="hailo10h"))["verdict"],
        "cell-5": loaded.record(entries, _report(new, "cell-5", model_version="9.9.9"))["verdict"],
        "cell-6": loaded.record(entries, _report(new, "cell-6", io_contract_sha256="f" * 64))["verdict"],
    }
    assert verdicts == {"cell-1": "current", "cell-2": "outdated", "cell-3": "sha256_mismatch", "cell-4": "arch_mismatch", "cell-5": "unknown_model", "cell-6": "io_contract_changed"}
    assert [row["node"] for row in loaded.snapshot()] == sorted(verdicts)


def test_a_node_that_updates_is_current_afterwards_and_the_newest_report_wins(tmp_path: Path):
    entries = _registry(tmp_path, ["0.1.0", "0.2.0"])
    loaded = LoadedModels()
    assert loaded.record(entries, _report(entries[0], "cell-1"))["verdict"] == "outdated"
    assert loaded.record(entries, _report(entries[1], "cell-1"))["verdict"] == "current"
    assert [row["verdict"] for row in loaded.snapshot()] == ["current"]


def test_a_flood_of_nodes_is_bounded_and_the_oldest_report_is_forgotten_first(tmp_path: Path):
    entries = _registry(tmp_path, ["0.1.0"])
    loaded = LoadedModels(limit=5)
    for n in range(12):
        loaded.record(entries, _report(entries[0], f"cell-{n:02d}"))
    assert [row["node"] for row in loaded.snapshot()] == [f"cell-{n:02d}" for n in range(7, 12)]


def test_a_registry_that_is_edited_by_hand_after_it_was_written_is_found(tmp_path: Path):
    entries = _registry(tmp_path, ["0.1.0"])
    path = tmp_path / "registry.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw[0]["sha256"] = "g" * 64
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(path)
    assert entries[0].sha256 != "g" * 64


# ----------------------------------------------------------------------------------------------------------------- the update over the air
def _owner(tmp_path: Path, versions: list[str]):
    pytest.importorskip("cryptography")
    from hydra_umc_detection_hef.signing import generate_keypair, sign_registry

    base = tmp_path / "owner"
    models = base / "models"
    models.mkdir(parents=True)
    entries: list = []
    for version in versions:
        (models / f"pcb-{version}.hef").write_bytes(f"model {version}".encode() * 50)
        entries.append(add_entry(entries, models_dir=models, name="pcb", version=version, task="detection", input_shape=SHAPE, classes=tuple(CLASSES),
                                 hef_path=f"pcb-{version}.hef", hailo_arch="hailo8", io_contract=_contract()))
    registry = base / "registry.json"
    write_registry(registry, entries)
    generate_keypair(base / "k.key", base / "k.pub")
    sign_registry(registry, base / "k.key")
    return registry, models, base / "k.pub"


def test_a_bundle_cut_short_anywhere_on_the_way_is_refused_and_the_node_keeps_what_it_had(tmp_path: Path):
    from hydra_umc_detection_hef.bundle import BundleError, apply_bundle, make_bundle

    registry, models, public = _owner(tmp_path, ["0.1.0", "0.2.0"])
    bundle = tmp_path / "update.zip"
    make_bundle(registry, models, bundle, [])
    data = bundle.read_bytes()
    node = tmp_path / "node"
    (node / "models").mkdir(parents=True)
    rng = random.Random(SEED)
    for cut in sorted({rng.randrange(1, len(data) - 1) for _ in range(12)}):
        broken = tmp_path / "broken.zip"
        broken.write_bytes(data[:cut])
        with pytest.raises(BundleError):
            apply_bundle(broken, node / "registry.json", node / "models", public, enabled=True)
        assert not (node / "registry.json").exists() and list((node / "models").iterdir()) == []


def test_a_node_that_updates_refuses_an_older_bundle_and_can_roll_back_on_purpose(tmp_path: Path):
    from hydra_umc_detection_hef.bundle import BundleError, apply_bundle, make_bundle, rollback_registry
    from hydra_umc_detection_hef.signing import sign_registry

    registry, models, public = _owner(tmp_path, ["0.1.0"])
    first = tmp_path / "first.zip"
    make_bundle(registry, models, first, [])
    # the owner publishes a later release with the same key
    entries = load_registry(registry)
    (models / "pcb-0.2.0.hef").write_bytes(b"model 0.2.0" * 50)
    entries.append(add_entry(entries, models_dir=models, name="pcb", version="0.2.0", task="detection", input_shape=SHAPE, classes=tuple(CLASSES),
                             hef_path="pcb-0.2.0.hef", hailo_arch="hailo8", io_contract=_contract()))
    write_registry(registry, entries)
    sign_registry(registry, registry.parent / "k.key")
    second = tmp_path / "second.zip"
    make_bundle(registry, models, second, [])

    node = tmp_path / "node"
    (node / "models").mkdir(parents=True)
    node_registry = node / "registry.json"
    apply_bundle(first, node_registry, node / "models", public, enabled=True)
    with pytest.raises(BundleError, match="nothing to go back to"):
        rollback_registry(node_registry)
    apply_bundle(second, node_registry, node / "models", public, enabled=True)
    assert [e.version for e in load_registry(node_registry, public)] == ["0.1.0", "0.2.0"]
    with pytest.raises(BundleError):
        apply_bundle(first, node_registry, node / "models", public, enabled=True)  # an older registry is not a quiet downgrade
    assert [e.version for e in load_registry(node_registry, public)] == ["0.1.0", "0.2.0"]
    rollback_registry(node_registry)
    assert [e.version for e in load_registry(node_registry, public)] == ["0.1.0"]
