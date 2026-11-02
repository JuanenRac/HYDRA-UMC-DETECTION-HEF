# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_accuracy_and_channels.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The io_contract that can be required, the channels, the accuracy measured after compilation and the gates that use them."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hydra_umc_detection_hef.accuracy import AccuracyError, iou, map50, record_accuracy
from hydra_umc_detection_hef.compatibility import LoadOutcome, safe_load
from hydra_umc_detection_hef.main import main
from hydra_umc_detection_hef.registry import (
    RegistryError,
    accuracy_ratio,
    find_latest,
    load_registry,
    validate_accuracy,
    write_registry,
)

CONTRACT = {
    "input": {"layout": "NHWC", "color_order": "RGB", "dtype": "uint8", "normalization": "on-chip", "resize": "letterbox"},
    "output": {"format": "hailo_nms_by_class", "bbox_order": "ymin,xmin,ymax,xmax", "bbox_normalized": True, "nms_on_chip": True},
}
ACCURACY = {"metric": "map50", "quantized": 0.8, "reference": 0.85, "dataset_sha256": "c" * 64, "samples": 40}


def _entry(version="0.1.0", **extra):
    entry = {
        "name": "pcb", "version": version, "task": "detection", "input_shape": [64, 64, 3], "classes": ["a", "b"],
        "hef_path": f"pcb-{version}.hef", "sha256": hashlib.sha256(version.encode()).hexdigest(), "hailo_arch": "hailo8",
    }
    entry.update(extra)
    return entry


def _registry(tmp_path: Path, *entries: dict) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(list(entries)), encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------------------- io_contract required


def test_an_entry_without_io_contract_loads_as_before_and_fails_when_it_is_required(tmp_path: Path) -> None:
    path = _registry(tmp_path, _entry(), _entry("0.2.0", io_contract=CONTRACT))
    assert len(load_registry(path)) == 2
    with pytest.raises(RegistryError, match="entry 0: 'pcb' '0.1.0' has no io_contract"):
        load_registry(path, None, True)
    assert len(load_registry(_registry(tmp_path, _entry(io_contract=CONTRACT)), None, True)) == 1


def test_safe_load_refuses_an_entry_without_io_contract_only_when_asked(tmp_path: Path) -> None:
    entry = load_registry(_registry(tmp_path, _entry()))[0]
    (tmp_path / entry.hef_path).write_bytes(b"0.1.0")
    assert safe_load(entry, tmp_path, "hailo8").is_ready
    result = safe_load(entry, tmp_path, "hailo8", require_io_contract=True)
    assert result.outcome is LoadOutcome.REJECTED_NO_IO_CONTRACT and "io_contract" in result.detail
    with_contract = load_registry(_registry(tmp_path, _entry(io_contract=CONTRACT)))[0]
    assert safe_load(with_contract, tmp_path, "hailo8", require_io_contract=True).is_ready


def _add(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch, *extra: str) -> tuple[int, str]:
    models = tmp_path / "models"
    models.mkdir(exist_ok=True)
    (models / "m.hef").write_bytes(b"x")
    argv = ["registry", "add", "--registry", str(tmp_path / "reg.json"), "--models-dir", str(models), "--hef-path", "m.hef", "--name", "m", "--version", "0.1.0",
            "--task", "detection", "--input-shape", "64,64,3", "--classes", "a,b", "--hailo-arch", "hailo8", *extra]
    monkeypatch.setattr("sys.argv", ["hydra-umc-detection-hef", *argv])
    code = main()
    return code, capsys.readouterr().err


def test_registry_add_needs_an_io_contract_unless_told_otherwise(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    code, err = _add(tmp_path, capsys, monkeypatch)
    assert code == 1 and "--io-contract" in err and not (tmp_path / "reg.json").exists()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"input": {}}), encoding="utf-8")
    code, err = _add(tmp_path, capsys, monkeypatch, "--io-contract", str(bad))
    assert code == 1 and "not valid" in err
    good = tmp_path / "good.json"
    good.write_text(json.dumps(CONTRACT), encoding="utf-8")
    code, _ = _add(tmp_path, capsys, monkeypatch, "--io-contract", str(good), "--channel", "canary")
    assert code == 0
    stored = json.loads((tmp_path / "reg.json").read_text(encoding="utf-8"))
    assert stored[0]["io_contract"] == CONTRACT and stored[0]["channel"] == "canary"


def test_registry_add_can_add_without_a_contract_when_asked_to(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    code, _ = _add(tmp_path, capsys, monkeypatch, "--no-io-contract")
    assert code == 0
    stored = json.loads((tmp_path / "reg.json").read_text(encoding="utf-8"))
    assert "io_contract" not in stored[0] and "channel" not in stored[0]  # a stable entry does not write the default


def test_the_environment_switch_requires_the_contract(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _registry(tmp_path, _entry())
    monkeypatch.setattr("sys.argv", ["x", "registry", "validate", "--registry", str(path)])
    assert main() == 0
    monkeypatch.setenv("HYDRA_UMC_DETECTION_HEF_REQUIRE_IO_CONTRACT", "1")
    assert main() == 1 and "no io_contract" in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------------------ channels


def test_the_latest_model_is_the_latest_stable_one_unless_the_channel_is_asked_for(tmp_path: Path) -> None:
    entries = load_registry(_registry(tmp_path, _entry("0.1.0"), _entry("0.2.0"), _entry("0.3.0", channel="canary"), _entry("0.0.9", channel="canary")))
    assert find_latest(entries, "pcb").version == "0.2.0"  # type: ignore[union-attr]
    assert find_latest(entries, "pcb", channel="canary").version == "0.3.0"  # type: ignore[union-attr]
    assert find_latest(entries, "pcb", version="0.3.0").channel == "canary"  # type: ignore[union-attr]  # a pinned version is taken as asked
    assert find_latest(entries, "pcb", version="0.3.0", channel="stable") is None
    assert find_latest(load_registry(_registry(tmp_path, _entry("0.3.0", channel="canary"))), "pcb") is None
    with pytest.raises(RegistryError):
        find_latest(entries, "pcb", channel="beta")


def test_a_bad_channel_is_refused_and_the_default_is_not_written(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="channel"):
        load_registry(_registry(tmp_path, _entry(channel="beta")))
    entries = load_registry(_registry(tmp_path, _entry(), _entry("0.2.0", channel="canary")))
    write_registry(tmp_path / "out.json", entries)
    stored = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert "channel" not in stored[0] and stored[1]["channel"] == "canary"


def test_the_cli_looks_in_the_channel_it_is_told_to(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _registry(tmp_path, _entry("0.1.0"), _entry("0.2.0", channel="canary"))
    monkeypatch.setattr("sys.argv", ["x", "registry", "latest", "--registry", str(path), "--name", "pcb"])
    assert main() == 0 and "pcb 0.1.0" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["x", "registry", "latest", "--registry", str(path), "--name", "pcb", "--channel", "canary"])
    assert main() == 0 and "pcb 0.2.0  task=detection  channel=canary" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------------------ accuracy


def _det(class_id, score, x0, y0, x1, y1):
    return {"class_id": class_id, "score": score, "box": {"x_min": x0, "y_min": y0, "x_max": x1, "y_max": y1}}


def _truth(class_id, x0, y0, x1, y1):
    return {"class_id": class_id, "box": {"x_min": x0, "y_min": y0, "x_max": x1, "y_max": y1}}


def test_iou() -> None:
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1 / 3)
    assert iou((0, 0, 0, 0), (0, 0, 0, 0)) == 0.0


def test_a_perfect_detector_scores_one_and_a_blind_one_zero() -> None:
    truth = {"images": {"a": [_truth(0, 0, 0, 10, 10), _truth(1, 20, 20, 40, 40)], "b": [_truth(0, 5, 5, 25, 25)]}}
    perfect = {"images": {"a": [_det(0, 0.9, 0, 0, 10, 10), _det(1, 0.8, 20, 20, 40, 40)], "b": [_det(0, 0.7, 5, 5, 25, 25)]}}
    result = map50(perfect, truth)
    assert result["map50"] == pytest.approx(1.0) and result["images"] == 2 and set(result["per_class"]) == {"0", "1"}
    assert map50({"images": {}}, truth)["map50"] == 0.0
    assert len(result["dataset_sha256"]) == 64 and result["dataset_sha256"] == map50(perfect, truth)["dataset_sha256"]


def test_false_positives_a_missed_box_and_duplicates_lower_the_score() -> None:
    truth = {"images": {"a": [_truth(0, 0, 0, 10, 10), _truth(0, 50, 50, 60, 60)]}}
    # one right, one wrong box with a higher score, the second truth box never found: precision 1/2 at recall 1/2
    found = {"images": {"a": [_det(0, 0.95, 100, 100, 110, 110), _det(0, 0.9, 0, 0, 10, 10)]}}
    assert map50(found, truth)["map50"] == pytest.approx(0.25)
    twice = {"images": {"a": [_det(0, 0.9, 0, 0, 10, 10), _det(0, 0.8, 0, 0, 10, 10)]}}  # the same box twice: the second is a false positive
    assert map50(twice, truth)["map50"] == pytest.approx(0.5)
    assert map50({"images": {"zzz": [_det(0, 0.9, 0, 0, 10, 10)]}}, truth)["map50"] == 0.0  # an image the truth does not list


def test_the_files_are_checked() -> None:
    truth = {"images": {"a": [_truth(0, 0, 0, 10, 10)]}}
    bad_inputs = [
        [], {"images": []}, {"x": 1}, {"images": {"a": "text"}}, {"images": {"a": [{"class_id": 0}]}},
        {"images": {"a": [_det(0, 1.5, 0, 0, 1, 1)]}}, {"images": {"a": [_det(0, 0.5, 5, 0, 1, 1)]}}, {"images": {"a": [_det(-1, 0.5, 0, 0, 1, 1)]}},
        {"images": {"a": [_det(True, 0.5, 0, 0, 1, 1)]}}, {"images": {"a": [{"class_id": 0, "score": 0.5, "box": {"x_min": 0}}]}},
        {"images": {"a": [_det(0, 0.5, 0, 0, 1, float("nan"))]}},
    ]
    for bad in bad_inputs:
        with pytest.raises(AccuracyError):
            map50(bad, truth)
    with pytest.raises(AccuracyError, match="nothing to measure"):
        map50({"images": {}}, {"images": {"a": []}})
    with pytest.raises(AccuracyError):
        map50({"images": {}}, {"images": {"a": [_det(0, 0.9, 0, 0, 1, 1)]}})  # a truth box has no score


def test_the_accuracy_block_is_recorded_and_validated(tmp_path: Path) -> None:
    entry = load_registry(_registry(tmp_path, _entry()))[0]
    truth = {"images": {"a": [_truth(0, 0, 0, 10, 10)]}}
    quantized = map50({"images": {"a": [_det(0, 0.9, 0, 0, 10, 10)]}}, truth)
    updated = record_accuracy(entry, quantized, 0.9)
    assert updated.accuracy == {"metric": "map50", "quantized": 1.0, "reference": 0.9, "dataset_sha256": quantized["dataset_sha256"], "samples": 1}
    assert accuracy_ratio(updated) == pytest.approx(1 / 0.9) and accuracy_ratio(entry) is None
    other = map50({"images": {}}, {"images": {"b": [_truth(0, 0, 0, 1, 1)]}})
    with pytest.raises(AccuracyError, match="another truth"):
        record_accuracy(entry, quantized, other)
    for bad in (0, -0.1, 1.5, True, float("nan")):
        with pytest.raises(AccuracyError):
            record_accuracy(entry, quantized, bad)  # type: ignore[arg-type]
    assert validate_accuracy(ACCURACY) == []
    for change in ({"quantized": 2}, {"reference": 0}, {"dataset_sha256": "x"}, {"samples": 0}, {"metric": "map"}, {"extra": 1}):
        assert validate_accuracy({**ACCURACY, **change}), change
    assert validate_accuracy("text") and validate_accuracy({k: v for k, v in ACCURACY.items() if k != "samples"})
    write_registry(tmp_path / "out.json", [updated])
    assert load_registry(tmp_path / "out.json")[0].accuracy == updated.accuracy


def test_a_registry_with_a_bad_accuracy_block_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="accuracy"):
        load_registry(_registry(tmp_path, _entry(accuracy={**ACCURACY, "quantized": 5})))


def test_the_accuracy_gate_refuses_a_low_ratio_and_a_missing_measurement(tmp_path: Path) -> None:
    good = load_registry(_registry(tmp_path, _entry(accuracy=ACCURACY)))[0]  # ratio 0.941
    (tmp_path / good.hef_path).write_bytes(b"0.1.0")
    assert safe_load(good, tmp_path, "hailo8").is_ready
    assert safe_load(good, tmp_path, "hailo8", min_accuracy_ratio=0.9).is_ready
    low = safe_load(good, tmp_path, "hailo8", min_accuracy_ratio=0.95)
    assert low.outcome is LoadOutcome.REJECTED_ACCURACY and "0.941" in low.detail
    none = load_registry(_registry(tmp_path, _entry()))[0]
    refused = safe_load(none, tmp_path, "hailo8", min_accuracy_ratio=0.5)
    assert refused.outcome is LoadOutcome.REJECTED_ACCURACY and "no accuracy measurement" in refused.detail


def test_record_accuracy_command_and_the_load_gate(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _registry(tmp_path, _entry(io_contract=CONTRACT))
    (tmp_path / "pcb-0.1.0.hef").write_bytes(b"0.1.0")
    truth = tmp_path / "truth.json"
    truth.write_text(json.dumps({"images": {"a": [_truth(0, 0, 0, 10, 10), _truth(0, 50, 50, 60, 60)]}}), encoding="utf-8")
    quantized = tmp_path / "quantized.json"
    quantized.write_text(json.dumps({"images": {"a": [_det(0, 0.9, 0, 0, 10, 10)]}}), encoding="utf-8")
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"images": {"a": [_det(0, 0.9, 0, 0, 10, 10), _det(0, 0.8, 50, 50, 60, 60)]}}), encoding="utf-8")

    def run(*argv: str) -> int:
        monkeypatch.setattr("sys.argv", ["x", *argv])
        return main()

    base = ["registry", "record-accuracy", "--registry", str(registry), "--name", "pcb", "--version", "0.1.0", "--detections", str(quantized), "--truth", str(truth)]
    assert run(*base) == 1 and "exactly one of" in capsys.readouterr().err
    assert run(*base, "--reference-detections", str(reference)) == 0
    assert "ratio 0.500" in capsys.readouterr().out
    block = json.loads(registry.read_text(encoding="utf-8"))[0]["accuracy"]
    assert block["quantized"] == 0.5 and block["reference"] == 1.0 and block["samples"] == 1
    load = ["registry", "load", "--registry", str(registry), "--models-dir", str(tmp_path), "--name", "pcb", "--target-arch", "hailo8"]
    assert run(*load) == 0
    assert run(*load, "--min-accuracy-ratio", "0.9") == 1 and "REJECTED_ACCURACY" in capsys.readouterr().err
    assert run(*load, "--min-accuracy-ratio", "0.4") == 0
    assert run(*load, "--min-accuracy-ratio", "2") == 1 and "must be above 0" in capsys.readouterr().err
    assert run(*base[:-2], "--truth", str(tmp_path / "missing.json"), "--reference-map", "0.9") == 1
    assert run(*base, "--reference-map", "0.9") == 0
