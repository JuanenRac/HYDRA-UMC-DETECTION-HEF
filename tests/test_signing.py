import json
import subprocess
import sys

import pytest

pytest.importorskip("cryptography")

from hydra_umc_detection_hef.registry import RegistryError, load_registry  # noqa: E402
from hydra_umc_detection_hef.signing import generate_keypair, resolve_public_key, sign_registry  # noqa: E402


def _registry(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps([{
        "name": "pcb", "version": "0.1.0", "task": "detection", "input_shape": [64, 64, 3],
        "classes": ["a"], "hef_path": "pcb.hef", "sha256": "a" * 64, "hailo_arch": "hailo8",
    }]), encoding="utf-8")
    return path


def _keys(tmp_path, stem="k"):
    private, public = tmp_path / (stem + ".key"), tmp_path / (stem + ".pub")
    generate_keypair(private, public)
    return private, public


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "hydra_umc_detection_hef.main", *args], capture_output=True, text=True)


def test_a_signed_registry_loads_with_the_public_key(tmp_path):
    registry = _registry(tmp_path)
    private, public = _keys(tmp_path)
    sign_registry(registry, private)
    assert len(load_registry(registry, public)) == 1


def test_without_a_public_key_nothing_changes(tmp_path):
    assert len(load_registry(_registry(tmp_path))) == 1


def test_an_unsigned_registry_is_refused_once_a_key_is_configured(tmp_path):
    registry = _registry(tmp_path)
    _, public = _keys(tmp_path)
    with pytest.raises(RegistryError, match="no readable signature"):
        load_registry(registry, public)


def test_a_registry_changed_after_signing_is_refused(tmp_path):
    registry = _registry(tmp_path)
    private, public = _keys(tmp_path)
    sign_registry(registry, private)
    registry.write_text(registry.read_text(encoding="utf-8").replace("a" * 64, "b" * 64), encoding="utf-8")
    with pytest.raises(RegistryError, match="does not match"):
        load_registry(registry, public)


def test_a_signature_made_with_another_key_is_refused(tmp_path):
    registry = _registry(tmp_path)
    other_private, _ = _keys(tmp_path, "other")
    _, public = _keys(tmp_path)
    sign_registry(registry, other_private)
    with pytest.raises(RegistryError, match="does not match"):
        load_registry(registry, public)


def test_a_key_is_never_overwritten(tmp_path):
    private, public = _keys(tmp_path)
    with pytest.raises(RegistryError, match="already exists"):
        generate_keypair(private, public)


def test_a_key_file_of_the_wrong_size_is_refused(tmp_path):
    registry = _registry(tmp_path)
    private, _ = _keys(tmp_path)
    sign_registry(registry, private)
    bad = tmp_path / "bad.pub"
    bad.write_text("abcd\n", encoding="ascii")
    with pytest.raises(RegistryError, match="must be 32 bytes"):
        load_registry(registry, bad)


def test_the_public_key_comes_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE", str(tmp_path / "p.pub"))
    assert resolve_public_key(None) == tmp_path / "p.pub"
    assert resolve_public_key(str(tmp_path / "x")) == tmp_path / "x"
    monkeypatch.delenv("HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE")
    assert resolve_public_key(None) is None


def test_the_command_line_signs_verifies_and_refuses_a_tampered_registry(tmp_path):
    registry = _registry(tmp_path)
    private, public = tmp_path / "c.key", tmp_path / "c.pub"
    assert run_cli("registry", "keygen", "--private-key-out", str(private), "--public-key-out", str(public)).returncode == 0
    assert run_cli("registry", "sign", "--registry", str(registry), "--private-key", str(private)).returncode == 0
    ok = run_cli("registry", "verify", "--registry", str(registry), "--public-key", str(public))
    assert ok.returncode == 0 and "signature OK" in ok.stdout
    assert run_cli("registry", "validate", "--registry", str(registry), "--public-key", str(public)).returncode == 0
    registry.write_text(registry.read_text(encoding="utf-8") + " ", encoding="utf-8")
    bad = run_cli("registry", "validate", "--registry", str(registry), "--public-key", str(public))
    assert bad.returncode == 1 and "does not match" in bad.stderr
