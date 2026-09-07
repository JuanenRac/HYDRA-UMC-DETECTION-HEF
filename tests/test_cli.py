import hashlib
import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "hydra_umc_detection_hef.main", *args],
        capture_output=True, text=True,
    )


def _entry(sha256="a" * 64, hailo_arch="hailo8"):
    return {
        "name": "pcb-defect", "version": "0.1.0", "task": "detection",
        "input_shape": [640, 640, 3], "classes": ["solder_bridge"],
        "hef_path": "pcb-defect-0.1.0.hef", "sha256": sha256, "hailo_arch": hailo_arch,
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


def test_registry_load_ready(tmp_path):
    content = b"a real fake hef payload"
    digest = hashlib.sha256(content).hexdigest()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(content)

    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry(sha256=digest, hailo_arch="hailo8")]), encoding="utf-8")

    result = run_cli(
        "registry", "load", "--registry", str(reg_path), "--models-dir", str(models_dir),
        "--name", "pcb-defect", "--target-arch", "hailo8",
    )
    assert result.returncode == 0
    assert "READY" in result.stdout


def test_registry_load_rejects_arch_mismatch(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry(hailo_arch="hailo8")]), encoding="utf-8")

    result = run_cli(
        "registry", "load", "--registry", str(reg_path), "--models-dir", str(tmp_path / "models"),
        "--name", "pcb-defect", "--target-arch", "hailo15h",
    )
    assert result.returncode == 1
    assert "REJECTED_ARCH_MISMATCH" in result.stderr


def test_registry_load_rejects_a_real_tampered_file(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    real_content = b"original bytes"
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(real_content)
    digest = hashlib.sha256(real_content).hexdigest()

    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps([_entry(sha256=digest, hailo_arch="hailo8")]), encoding="utf-8")

    # Real file tampering after the registry recorded the real checksum.
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(b"tampered bytes")

    result = run_cli(
        "registry", "load", "--registry", str(reg_path), "--models-dir", str(models_dir),
        "--name", "pcb-defect", "--target-arch", "hailo8",
    )
    assert result.returncode == 1
    assert "REJECTED_CHECKSUM_MISMATCH" in result.stderr
