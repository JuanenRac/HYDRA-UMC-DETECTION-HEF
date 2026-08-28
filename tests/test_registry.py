import hashlib
import json

import pytest

from hydra_umc_detection_hef.registry import (
    RegistryError,
    compute_sha256,
    duplicate_versions,
    find_latest,
    load_registry,
    verify_checksum,
)


def _write_registry(path, entries):
    path.write_text(json.dumps(entries), encoding="utf-8")


def _entry(name="pcb-defect", version="0.1.0", task="detection", sha256="a" * 64, hailo_arch="hailo8"):
    return {
        "name": name, "version": version, "task": task,
        "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component"],
        "hef_path": f"{name}-{version}.hef", "sha256": sha256, "hailo_arch": hailo_arch,
    }


def test_load_registry_valid(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    entries = load_registry(reg_path)
    assert len(entries) == 1
    assert entries[0].name == "pcb-defect"
    assert entries[0].version_tuple == (0, 1, 0)


def test_load_registry_missing_field(tmp_path):
    reg_path = tmp_path / "registry.json"
    bad = _entry()
    del bad["sha256"]
    _write_registry(reg_path, [bad])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_bad_version(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="v1")])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_bad_sha256(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(sha256="not-hex")])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_unknown_hailo_arch(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo9-doesnt-exist")])
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_accepts_every_known_hailo_arch(tmp_path):
    from hydra_umc_detection_hef.registry import KNOWN_HAILO_ARCHS

    for arch in sorted(KNOWN_HAILO_ARCHS):
        reg_path = tmp_path / f"registry-{arch}.json"
        _write_registry(reg_path, [_entry(hailo_arch=arch)])
        entries = load_registry(reg_path)
        assert entries[0].hailo_arch == arch


def test_load_registry_not_a_list(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_load_registry_malformed_json(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RegistryError):
        load_registry(reg_path)


def test_duplicate_versions(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="0.1.0"), _entry(version="0.1.0"), _entry(version="0.2.0")])
    entries = load_registry(reg_path)
    dupes = duplicate_versions(entries)
    assert dupes == [("pcb-defect", "0.1.0")]


def test_find_latest_picks_highest_version(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="0.1.0"), _entry(version="0.10.0"), _entry(version="0.2.0")])
    entries = load_registry(reg_path)
    latest = find_latest(entries, "pcb-defect")
    assert latest.version == "0.10.0"


def test_find_latest_filters_by_task(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(task="detection", version="0.2.0"), _entry(task="pose", version="0.9.0")])
    entries = load_registry(reg_path)
    latest = find_latest(entries, "pcb-defect", task="pose")
    assert latest.version == "0.9.0"


def test_find_latest_no_match_returns_none(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    entries = load_registry(reg_path)
    assert find_latest(entries, "nonexistent-model") is None


def test_compute_sha256(tmp_path):
    f = tmp_path / "model.hef"
    f.write_bytes(b"fake hef bytes")
    expected = hashlib.sha256(b"fake hef bytes").hexdigest()
    assert compute_sha256(f) == expected


def test_verify_checksum_match(tmp_path):
    content = b"fake hef bytes"
    digest = hashlib.sha256(content).hexdigest()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(content)

    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(sha256=digest)])
    entry = load_registry(reg_path)[0]

    assert verify_checksum(entry, models_dir) is True


def test_verify_checksum_mismatch(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"different bytes")

    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(sha256="a" * 64)])
    entry = load_registry(reg_path)[0]

    assert verify_checksum(entry, models_dir) is False


def test_verify_checksum_missing_file_returns_none(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    entry = load_registry(reg_path)[0]

    assert verify_checksum(entry, tmp_path / "nowhere") is None
