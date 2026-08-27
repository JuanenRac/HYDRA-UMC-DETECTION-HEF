import hashlib
import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "hydra_umc_detection_hef.main", *args],
        capture_output=True, text=True,
    )


def _entry(sha256="a" * 64):
    return {
        "name": "pcb-defect", "version": "0.1.0", "task": "detection",
        "input_shape": [640, 640, 3], "classes": ["solder_bridge"],
        "hef_path": "pcb-defect-0.1.0.hef", "sha256": sha256,
    }


def test_bare_invocation_prints_identity():
    result = run_cli()
    assert result.returncode == 0
    assert "HYDRA-UMC-DETECTION-HEF" in result.stdout


def test_registry_validate_structure_only(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry()]), encoding="utf-8")

    result = run_cli("registry", "validate", "--registry", str(reg_path))
    assert result.returncode == 0
    assert "registry OK" in result.stdout


def test_registry_validate_detects_duplicate(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry(), _entry()]), encoding="utf-8")

    result = run_cli("registry", "validate", "--registry", str(reg_path))
    assert result.returncode == 1
    assert "duplicate entry" in result.stderr


def test_registry_validate_with_matching_checksum(tmp_path):
    content = b"fake hef bytes"
    digest = hashlib.sha256(content).hexdigest()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(content)

    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry(sha256=digest)]), encoding="utf-8")

    result = run_cli("registry", "validate", "--registry", str(reg_path), "--models-dir", str(models_dir))
    assert result.returncode == 0
    assert "checksum OK" in result.stdout


def test_registry_validate_with_mismatched_checksum(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"different bytes")

    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry(sha256="a" * 64)]), encoding="utf-8")

    result = run_cli("registry", "validate", "--registry", str(reg_path), "--models-dir", str(models_dir))
    assert result.returncode == 1
    assert "CHECKSUM MISMATCH" in result.stderr


def test_registry_latest(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry(), {**_entry(), "version": "0.2.0"}]), encoding="utf-8")

    result = run_cli("registry", "latest", "--registry", str(reg_path), "--name", "pcb-defect")
    assert result.returncode == 0
    assert "0.2.0" in result.stdout


def test_registry_latest_no_match(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry()]), encoding="utf-8")

    result = run_cli("registry", "latest", "--registry", str(reg_path), "--name", "nonexistent")
    assert result.returncode == 1
