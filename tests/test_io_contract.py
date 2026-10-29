import copy
import json

import pytest

from hydra_umc_detection_hef.compatibility import model_identity
from hydra_umc_detection_hef.registry import (
    RegistryError,
    io_contract_sha256,
    load_registry,
    write_registry,
    validate_io_contract,
)

CONTRACT = {
    "input": {
        "layout": "NHWC", "color_order": "RGB", "dtype": "uint8", "normalization": "on-chip",
        "resize": "letterbox", "pad_value": 114,
    },
    "output": {
        "format": "hailo_nms_by_class", "bbox_order": "ymin,xmin,ymax,xmax", "bbox_normalized": True,
        "nms_on_chip": True, "max_detections_per_class": 100, "score_threshold": 0.25, "iou_threshold": 0.45,
    },
}


def _entry(contract=None):
    entry = {
        "name": "pcb-defect", "version": "0.1.0", "task": "detection", "input_shape": [640, 640, 3],
        "classes": ["a", "b"], "hef_path": "pcb.hef", "sha256": "a" * 64, "hailo_arch": "hailo8",
    }
    if contract is not None:
        entry["io_contract"] = contract
    return entry


def _load(tmp_path, entry):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps([entry]), encoding="utf-8")
    return load_registry(path)


def test_a_valid_contract_is_accepted_and_an_entry_without_one_still_loads(tmp_path):
    assert validate_io_contract(CONTRACT) == []
    assert _load(tmp_path, _entry(CONTRACT))[0].io_contract == CONTRACT
    assert _load(tmp_path, _entry())[0].io_contract is None


def test_mean_std_normalization_is_accepted():
    contract = copy.deepcopy(CONTRACT)
    contract["input"]["normalization"] = {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}
    assert validate_io_contract(contract) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["input"].__setitem__("color_order", "RBG"),
        lambda c: c["input"].__setitem__("normalization", {"mean": [0], "std": [0]}),
        lambda c: c["input"].__setitem__("normalization", {"mean": [0, 0], "std": [1]}),
        lambda c: c["input"].__setitem__("normalization", "auto"),
        lambda c: c["input"].__setitem__("pad_value", 300),
        lambda c: c["input"].__setitem__("extra", 1),
        lambda c: c["input"].pop("resize"),
        lambda c: c["output"].__setitem__("bbox_normalized", "yes"),
        lambda c: c["output"].__setitem__("score_threshold", 1.5),
        lambda c: c["output"].__setitem__("iou_threshold", float("nan")),
        lambda c: c["output"].__setitem__("max_detections_per_class", 0),
        lambda c: c["output"].__setitem__("max_detections_per_class", True),
        lambda c: c["output"].__setitem__("bbox_order", "xywh"),
        lambda c: c.pop("output"),
        lambda c: c.__setitem__("other", {}),
    ],
)
def test_bad_contracts_are_rejected(mutate, tmp_path):
    contract = copy.deepcopy(CONTRACT)
    mutate(contract)
    assert validate_io_contract(contract)
    with pytest.raises(RegistryError):
        _load(tmp_path, _entry(contract))


def test_a_contract_that_is_not_an_object_is_rejected():
    assert validate_io_contract([]) and validate_io_contract("x") and validate_io_contract(None)


def test_identity_carries_the_contract_hash_only_when_there_is_a_contract(tmp_path):
    with_contract = _load(tmp_path, _entry(CONTRACT))[0]
    without = _load(tmp_path, _entry())[0]
    assert model_identity(with_contract)["io_contract_sha256"] == io_contract_sha256(CONTRACT)
    assert "io_contract_sha256" not in model_identity(without)
    reordered = {"output": CONTRACT["output"], "input": dict(reversed(list(CONTRACT["input"].items())))}
    assert io_contract_sha256(reordered) == io_contract_sha256(CONTRACT)
    changed = copy.deepcopy(CONTRACT)
    changed["input"]["color_order"] = "BGR"
    assert io_contract_sha256(changed) != io_contract_sha256(CONTRACT)


def test_saving_the_registry_keeps_the_contract(tmp_path):
    entries = _load(tmp_path, _entry(CONTRACT))
    out = tmp_path / "out.json"
    write_registry(out, entries)
    assert json.loads(out.read_text(encoding="utf-8"))[0]["io_contract"] == CONTRACT
