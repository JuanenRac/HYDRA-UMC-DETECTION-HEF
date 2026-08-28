import hashlib
import json

from hydra_umc_detection_hef.compatibility import LoadOutcome, check_arch_compatibility, safe_load
from hydra_umc_detection_hef.registry import load_registry


def _write_registry(path, entries):
    path.write_text(json.dumps(entries), encoding="utf-8")


def _entry(name="pcb-defect", version="0.1.0", task="detection", sha256="a" * 64, hailo_arch="hailo8"):
    return {
        "name": name, "version": version, "task": task,
        "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component"],
        "hef_path": f"{name}-{version}.hef", "sha256": sha256, "hailo_arch": hailo_arch,
    }


def test_check_arch_compatibility_matches_exactly(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo8")])
    entry = load_registry(reg_path)[0]

    assert check_arch_compatibility(entry, "hailo8") is True
    assert check_arch_compatibility(entry, "hailo8l") is False


def test_safe_load_rejects_arch_mismatch_before_touching_the_filesystem(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo8")])
    entry = load_registry(reg_path)[0]

    # No models_dir even exists - the arch check must fail first, never
    # attempting (and never needing) a real filesystem read.
    result = safe_load(entry, tmp_path / "does-not-exist", target_arch="hailo15h")

    assert result.outcome is LoadOutcome.REJECTED_ARCH_MISMATCH
    assert not result.is_ready
    assert "hailo8" in result.detail
    assert "hailo15h" in result.detail


def test_safe_load_rejects_missing_file_when_arch_matches(tmp_path):
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo8")])
    entry = load_registry(reg_path)[0]

    result = safe_load(entry, tmp_path / "models", target_arch="hailo8")

    assert result.outcome is LoadOutcome.REJECTED_MISSING_FILE
    assert not result.is_ready


def test_safe_load_rejects_checksum_mismatch_when_arch_and_file_are_present(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"corrupted or tampered bytes")

    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo8", sha256="a" * 64)])
    entry = load_registry(reg_path)[0]

    result = safe_load(entry, models_dir, target_arch="hailo8")

    assert result.outcome is LoadOutcome.REJECTED_CHECKSUM_MISMATCH
    assert not result.is_ready


def test_safe_load_is_ready_only_when_arch_and_checksum_both_check_out(tmp_path):
    content = b"a real fake hef payload"
    digest = hashlib.sha256(content).hexdigest()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(content)

    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo8", sha256=digest)])
    entry = load_registry(reg_path)[0]

    result = safe_load(entry, models_dir, target_arch="hailo8")

    assert result.outcome is LoadOutcome.READY
    assert result.is_ready


def test_safe_load_never_reports_ready_for_a_tampered_file_even_on_the_right_arch(tmp_path):
    # The exact "unsafe load" scenario this gate exists to prevent: right
    # chip, file present, but its bytes were corrupted/tampered after the
    # registry recorded its real checksum.
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"original bytes")
    real_digest = hashlib.sha256(b"original bytes").hexdigest()

    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo8", sha256=real_digest)])
    entry = load_registry(reg_path)[0]

    # Now the file on disk is silently swapped out - simulating corruption
    # or tampering after the registry was written.
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"swapped-in malicious bytes")

    result = safe_load(entry, models_dir, target_arch="hailo8")

    assert result.outcome is LoadOutcome.REJECTED_CHECKSUM_MISMATCH
    assert not result.is_ready
