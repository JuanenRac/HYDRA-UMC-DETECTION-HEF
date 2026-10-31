# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_cli_inprocess.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Characterization tests that run the CLI in-process, so the command
handlers of main.py are measured and their current output is pinned."""
import hashlib
import json

import pytest

from hydra_umc_detection_hef import main as main_module
from hydra_umc_detection_hef.main import main

HEF = b"fake hef bytes"
DIGEST = hashlib.sha256(HEF).hexdigest()


def _entry(**over):
    entry = {
        "name": "pcb-defect", "version": "0.1.0", "task": "detection",
        "input_shape": [640, 640, 3], "classes": ["solder_bridge"],
        "hef_path": "pcb-defect-0.1.0.hef", "sha256": DIGEST, "hailo_arch": "hailo8",
    }
    entry.update(over)
    return entry


def _run(monkeypatch, capsys, *argv):
    monkeypatch.setattr("sys.argv", ["prog", *argv])
    code = main()
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.fixture(autouse=True)
def _no_key_env(monkeypatch):
    monkeypatch.delenv("HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE", raising=False)


@pytest.fixture
def workspace(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    (models / "pcb-defect-0.1.0.hef").write_bytes(HEF)
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps([_entry()]), encoding="utf-8")
    return reg, models


def test_get_version_returns_a_string():
    assert isinstance(main_module.get_version(), str)


def test_bare_invocation_prints_identity(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys)
    assert code == 0
    assert out.startswith("HYDRA-UMC-DETECTION-HEF v")
    assert "Hailo Executable Format" in out


def test_validate_reports_missing_registry(monkeypatch, capsys, tmp_path):
    code, _, err = _run(monkeypatch, capsys, "registry", "validate", "--registry", str(tmp_path / "none.json"))
    assert code == 1
    assert err.startswith("error:")


def test_validate_counts_entries_and_skips_missing_hef(monkeypatch, capsys, tmp_path):
    reg = tmp_path / "r.json"
    reg.write_text(json.dumps([_entry(), _entry(version="0.2.0")]), encoding="utf-8")
    (tmp_path / "m").mkdir()
    code, out, _ = _run(monkeypatch, capsys, "registry", "validate", "--registry", str(reg), "--models-dir", str(tmp_path / "m"))
    assert code == 0
    assert "2 entries in" in out
    assert "not present locally, skipped" in out
    assert out.rstrip().endswith("registry OK")


def test_validate_singular_entry_wording(monkeypatch, capsys, workspace):
    reg, models = workspace
    code, out, _ = _run(monkeypatch, capsys, "registry", "validate", "--registry", str(reg), "--models-dir", str(models))
    assert code == 0
    assert "1 entry in" in out
    assert "checksum OK" in out


def test_latest_prints_details_and_task_filter(monkeypatch, capsys, workspace):
    reg, _ = workspace
    code, out, _ = _run(monkeypatch, capsys, "registry", "latest", "--registry", str(reg), "--name", "pcb-defect")
    assert code == 0
    assert "task=detection" in out and "classes: solder_bridge" in out and f"sha256: {DIGEST}" in out
    code, _, err = _run(monkeypatch, capsys, "registry", "latest", "--registry", str(reg), "--name", "pcb-defect", "--task", "pose")
    assert code == 1
    assert "with task 'pose'" in err


def test_latest_reports_unreadable_registry(monkeypatch, capsys, tmp_path):
    code, _, err = _run(monkeypatch, capsys, "registry", "latest", "--registry", str(tmp_path / "x.json"), "--name", "a")
    assert code == 1 and err.startswith("error:")


def test_load_ready_for_matching_arch(monkeypatch, capsys, workspace):
    reg, models = workspace
    code, out, _ = _run(
        monkeypatch, capsys, "registry", "load", "--registry", str(reg), "--models-dir", str(models),
        "--name", "pcb-defect", "--target-arch", "hailo8",
    )
    assert code == 0
    assert out.startswith("READY:")


def test_load_not_ready_for_other_arch(monkeypatch, capsys, workspace):
    reg, models = workspace
    code, _, err = _run(
        monkeypatch, capsys, "registry", "load", "--registry", str(reg), "--models-dir", str(models),
        "--name", "pcb-defect", "--target-arch", "hailo15h",
    )
    assert code == 1
    assert err.strip() != ""


def test_load_unknown_model_and_unknown_version(monkeypatch, capsys, workspace):
    reg, models = workspace
    base = ("registry", "load", "--registry", str(reg), "--models-dir", str(models), "--target-arch", "hailo8")
    code, _, err = _run(monkeypatch, capsys, *base, "--name", "ghost")
    assert code == 1 and "no model named 'ghost'" in err
    code, _, err = _run(monkeypatch, capsys, *base, "--name", "pcb-defect", "--task", "pose")
    assert code == 1 and "with task 'pose'" in err


def test_load_rejects_tampered_file(monkeypatch, capsys, workspace):
    reg, models = workspace
    (models / "pcb-defect-0.1.0.hef").write_bytes(b"tampered")
    code, out, err = _run(
        monkeypatch, capsys, "registry", "load", "--registry", str(reg), "--models-dir", str(models),
        "--name", "pcb-defect", "--target-arch", "hailo8",
    )
    assert code == 1
    assert "READY" not in out
    assert err.strip() != ""


def test_load_with_unreadable_registry(monkeypatch, capsys, tmp_path):
    code, _, err = _run(
        monkeypatch, capsys, "registry", "load", "--registry", str(tmp_path / "x.json"), "--models-dir", str(tmp_path),
        "--name", "a", "--target-arch", "hailo8",
    )
    assert code == 1 and err.startswith("error:")


def _add_args(reg, models, **over):
    args = {
        "--registry": str(reg), "--models-dir": str(models), "--hef-path": "pcb-defect-0.1.0.hef",
        "--name": "pcb-defect", "--version": "0.3.0", "--task": "detection",
        "--input-shape": "640,640,3", "--classes": "a,b", "--hailo-arch": "hailo8",
    }
    args.update(over)
    out = ["registry", "add"]
    for key, value in args.items():
        out += [key, value]
    return out


def test_add_creates_registry_and_entry(monkeypatch, capsys, workspace, tmp_path):
    _, models = workspace
    fresh = tmp_path / "fresh.json"
    code, out, _ = _run(monkeypatch, capsys, *_add_args(fresh, models))
    assert code == 0
    assert f"sha256={DIGEST}" in out
    data = json.loads(fresh.read_text(encoding="utf-8"))
    assert [e["version"] for e in data] == ["0.3.0"]
    assert data[0]["classes"] == ["a", "b"]


def test_add_rejects_non_numeric_shape(monkeypatch, capsys, workspace):
    reg, models = workspace
    code, _, err = _run(monkeypatch, capsys, *_add_args(reg, models, **{"--input-shape": "a,b,c"}))
    assert code == 1
    assert "--input-shape must be comma-separated integers" in err


def test_add_checks_classes_hash(monkeypatch, capsys, workspace):
    reg, models = workspace
    code, _, err = _run(monkeypatch, capsys, *_add_args(reg, models, **{"--classes-sha256": "0" * 64}))
    assert code == 1
    assert "does not match --classes-sha256" in err
    good = main_module.classes_sha256(("a", "b"))
    code, _, _ = _run(monkeypatch, capsys, *_add_args(reg, models, **{"--classes-sha256": good.upper()}))
    assert code == 0


def test_add_duplicate_version_is_rejected(monkeypatch, capsys, workspace):
    reg, models = workspace
    code, _, err = _run(monkeypatch, capsys, *_add_args(reg, models, **{"--version": "0.1.0"}))
    assert code == 1
    assert err.startswith("error:")


def test_add_with_missing_hef_is_rejected(monkeypatch, capsys, workspace):
    reg, models = workspace
    code, _, err = _run(monkeypatch, capsys, *_add_args(reg, models, **{"--hef-path": "nothing.hef"}))
    assert code == 1
    assert err.startswith("error:")


def test_verify_requires_a_public_key(monkeypatch, capsys, workspace):
    reg, _ = workspace
    code, _, err = _run(monkeypatch, capsys, "registry", "verify", "--registry", str(reg))
    assert code == 1
    assert "give --public-key" in err


def test_sign_with_missing_key_reports_error(monkeypatch, capsys, workspace, tmp_path):
    reg, _ = workspace
    code, _, err = _run(monkeypatch, capsys, "registry", "sign", "--registry", str(reg), "--private-key", str(tmp_path / "none.key"))
    assert code == 1
    assert err.startswith("error:")


def test_keygen_sign_verify_roundtrip(monkeypatch, capsys, workspace, tmp_path):
    pytest.importorskip("cryptography")
    reg, _ = workspace
    priv, pub = tmp_path / "k.priv", tmp_path / "k.pub"
    code, out, _ = _run(monkeypatch, capsys, "registry", "keygen", "--private-key-out", str(priv), "--public-key-out", str(pub))
    assert code == 0 and "keep it off the nodes" in out
    code, _, err = _run(monkeypatch, capsys, "registry", "keygen", "--private-key-out", str(priv), "--public-key-out", str(pub))
    assert code == 1 and err.startswith("error:")
    code, out, _ = _run(monkeypatch, capsys, "registry", "sign", "--registry", str(reg), "--private-key", str(priv))
    assert code == 0 and out.startswith("signed ")
    code, out, _ = _run(monkeypatch, capsys, "registry", "verify", "--registry", str(reg), "--public-key", str(pub))
    assert code == 0 and "signature OK (1 entry)" in out
    reg.write_text(json.dumps([_entry(version="9.9.9")]), encoding="utf-8")
    code, _, err = _run(monkeypatch, capsys, "registry", "verify", "--registry", str(reg), "--public-key", str(pub))
    assert code == 1 and err.startswith("error:")


class _FakeServer:
    created: list = []

    def __init__(self, addr, registry, models_dir, show_paths=False, public_key_file=None):
        self.args = (addr, registry, models_dir, show_paths, public_key_file)
        self.closed = False
        _FakeServer.created.append(self)

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


def test_serve_warns_and_shuts_down_on_ctrl_c(monkeypatch, capsys, tmp_path):
    _FakeServer.created.clear()
    monkeypatch.setattr(main_module, "RegistryServer", _FakeServer)
    code, out, err = _run(monkeypatch, capsys, "serve", "--registry", str(tmp_path / "missing.json"), "--port", "18093")
    assert code == 0
    assert "does not exist - every query will answer 502" in err
    assert "listening on 127.0.0.1:18093" in out and "shutting down" in out
    assert _FakeServer.created[0].closed is True
    assert _FakeServer.created[0].args[3] is False


def test_serve_warns_when_registry_is_a_directory(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(main_module, "RegistryServer", _FakeServer)
    code, _, err = _run(monkeypatch, capsys, "serve", "--registry", str(tmp_path), "--models-dir", str(tmp_path), "--stats-full-paths")
    assert code == 0
    assert "is a directory, not a registry file" in err
    assert _FakeServer.created[-1].args[3] is True
