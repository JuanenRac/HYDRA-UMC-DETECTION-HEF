# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_bundle_and_loaded.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Signed bundles of models (the receiving end of an update over the air) and the reports of the models nodes loaded."""
from __future__ import annotations

import hashlib
import json
import threading
import urllib.error
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from hydra_umc_detection_hef.api import RegistryServer  # noqa: E402
from hydra_umc_detection_hef.bundle import (  # noqa: E402
    BundleError,
    apply_bundle,
    make_bundle,
    ota_enabled,
    rollback_registry,
)
from hydra_umc_detection_hef.loaded import LoadedModels, ReportError, judge, parse_report  # noqa: E402
from hydra_umc_detection_hef.main import main  # noqa: E402
from hydra_umc_detection_hef.registry import load_registry  # noqa: E402
from hydra_umc_detection_hef.signing import generate_keypair, sign_registry  # noqa: E402


def _entry(version: str, data: bytes, **extra):
    entry = {
        "name": "pcb", "version": version, "task": "detection", "input_shape": [64, 64, 3], "classes": ["a"],
        "hef_path": f"pcb-{version}.hef", "sha256": hashlib.sha256(data).hexdigest(), "hailo_arch": "hailo8",
    }
    entry.update(extra)
    return entry


def _publisher(tmp_path: Path, versions=("0.1.0",), name="pub") -> tuple[Path, Path, Path, Path]:
    """The side of the owner: a registry, its models, a key pair and the signature."""
    base = tmp_path / name
    models = base / "models"
    models.mkdir(parents=True)
    entries = []
    for version in versions:
        data = f"model {version}".encode()
        (models / f"pcb-{version}.hef").write_bytes(data)
        entries.append(_entry(version, data))
    registry = base / "registry.json"
    registry.write_text(json.dumps(entries), encoding="utf-8")
    private, public = base / "k.key", base / "k.pub"
    generate_keypair(private, public)
    sign_registry(registry, private)
    return registry, models, private, public


def _node(tmp_path: Path) -> tuple[Path, Path]:
    node = tmp_path / "node"
    (node / "models").mkdir(parents=True)
    return node / "registry.json", node / "models"


def _bundle(tmp_path: Path, registry: Path, models: Path, *names: str, out: str = "update.zip") -> Path:
    path = tmp_path / out
    make_bundle(registry, models, path, list(names))
    return path


def test_a_signed_bundle_installs_models_and_registry_on_a_node(tmp_path: Path) -> None:
    registry, models, _private, public = _publisher(tmp_path, ("0.1.0", "0.2.0"))
    bundle = _bundle(tmp_path, registry, models)
    node_registry, node_models = _node(tmp_path)
    summary = apply_bundle(bundle, node_registry, node_models, public, enabled=True)
    assert summary["models"] == ["pcb 0.1.0", "pcb 0.2.0"] and summary["files"] == ["pcb-0.1.0.hef", "pcb-0.2.0.hef"]
    assert (node_models / "pcb-0.2.0.hef").read_bytes() == b"model 0.2.0"
    assert len(load_registry(node_registry, public)) == 2  # the signature that came with it verifies
    assert not list(node_models.glob("*.part")) and not list(node_registry.parent.glob("*.part"))


def test_the_update_is_off_until_it_is_turned_on_and_needs_the_public_key(tmp_path: Path) -> None:
    registry, models, _private, public = _publisher(tmp_path)
    bundle = _bundle(tmp_path, registry, models)
    node_registry, node_models = _node(tmp_path)
    with pytest.raises(BundleError, match="is off"):
        apply_bundle(bundle, node_registry, node_models, public, enabled=False)
    with pytest.raises(BundleError, match="public key"):
        apply_bundle(bundle, node_registry, node_models, None, enabled=True)
    assert not node_registry.exists() and not list(node_models.iterdir())
    assert ota_enabled(False, {}) is False and ota_enabled(True, {}) is True
    assert ota_enabled(False, {"HYDRA_UMC_DETECTION_HEF_OTA": "1"}) is True and ota_enabled(False, {"HYDRA_UMC_DETECTION_HEF_OTA": "no"}) is False


def test_a_bundle_signed_by_someone_else_changes_nothing(tmp_path: Path) -> None:
    registry, models, _private, _public = _publisher(tmp_path)
    _, _, _, stranger_public = _publisher(tmp_path, name="other")
    bundle = _bundle(tmp_path, registry, models)
    node_registry, node_models = _node(tmp_path)
    with pytest.raises(BundleError, match="signature"):
        apply_bundle(bundle, node_registry, node_models, stranger_public, enabled=True)
    assert not node_registry.exists() and not list(node_models.iterdir())


def _rewrite(bundle: Path, change) -> Path:
    members = {}
    with zipfile.ZipFile(bundle) as archive:
        for info in archive.infolist():
            members[info.filename] = archive.read(info)
    members = change(members)
    out = bundle.with_name("tampered.zip")
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return out


def test_a_tampered_bundle_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    registry, models, _private, public = _publisher(tmp_path)
    good = _bundle(tmp_path, registry, models)
    node_registry, node_models = _node(tmp_path)

    def swap_model(members):
        members["models/pcb-0.1.0.hef"] = b"evil"
        return members

    def swap_model_and_manifest(members):
        manifest = json.loads(members["bundle.json"])
        members["models/pcb-0.1.0.hef"] = b"evil"
        manifest["files"]["models/pcb-0.1.0.hef"] = hashlib.sha256(b"evil").hexdigest()
        members["bundle.json"] = json.dumps(manifest).encode()
        return members

    def extra_member(members):
        members["models/extra.hef"] = b"x"
        return members

    def no_signature(members):
        members.pop("registry.json.sig")
        manifest = json.loads(members["bundle.json"])
        manifest["files"].pop("registry.json.sig")
        members["bundle.json"] = json.dumps(manifest).encode()
        return members

    def bad_names(name):
        def change(members):
            members[name] = b"x"
            manifest = json.loads(members["bundle.json"])
            manifest["files"][name] = hashlib.sha256(b"x").hexdigest()
            members["bundle.json"] = json.dumps(manifest).encode()
            return members
        return change

    cases = [(swap_model, "SHA-256 in bundle.json"), (swap_model_and_manifest, "records"), (extra_member, "differ"), (no_signature, "no registry.json.sig")]
    cases += [(bad_names(name), "not allowed") for name in ("../escape.hef", "/abs.hef", "models/../../x", "other/file")]
    for change, text in cases:
        with pytest.raises(BundleError, match=text):
            apply_bundle(_rewrite(good, change), node_registry, node_models, public, enabled=True)
    assert not node_registry.exists() and not list(node_models.iterdir())
    not_a_zip = tmp_path / "x.zip"
    not_a_zip.write_bytes(b"not a zip")
    with pytest.raises(BundleError, match="not a readable bundle"):
        apply_bundle(not_a_zip, node_registry, node_models, public, enabled=True)
    with pytest.raises(BundleError, match="more than 100 bytes"):
        apply_bundle(good, node_registry, node_models, public, enabled=True, max_total_bytes=100)


def test_a_model_that_goes_back_to_an_older_version_is_refused_unless_allowed(tmp_path: Path) -> None:
    registry, models, private, public = _publisher(tmp_path, ("0.1.0", "0.2.0"))
    node_registry, node_models = _node(tmp_path)
    apply_bundle(_bundle(tmp_path, registry, models), node_registry, node_models, public, enabled=True)
    old_registry, old_models, _old_private, _old_public = _publisher(tmp_path, ("0.1.0",), name="old")
    sign_registry(old_registry, private)  # an older registry, signed by the same owner
    old_bundle = _bundle(tmp_path, old_registry, old_models, out="old.zip")
    before = node_registry.read_bytes()
    with pytest.raises(BundleError, match=r"would go from 0\.2\.0 to 0\.1\.0"):
        apply_bundle(old_bundle, node_registry, node_models, public, enabled=True)
    assert node_registry.read_bytes() == before
    apply_bundle(old_bundle, node_registry, node_models, public, enabled=True, allow_downgrade=True)
    assert [e.version for e in load_registry(node_registry, public)] == ["0.1.0"]


def test_a_model_the_new_registry_drops_is_refused_without_allow_downgrade(tmp_path: Path) -> None:
    registry, models, private, public = _publisher(tmp_path)
    node_registry, node_models = _node(tmp_path)
    apply_bundle(_bundle(tmp_path, registry, models), node_registry, node_models, public, enabled=True)
    registry.write_text("[]", encoding="utf-8")
    sign_registry(registry, private)
    with pytest.raises(BundleError, match="no longer lists pcb"):
        apply_bundle(_bundle(tmp_path, registry, models, out="empty.zip"), node_registry, node_models, public, enabled=True)


def test_rollback_puts_the_previous_registry_and_signature_back(tmp_path: Path) -> None:
    registry, models, private, public = _publisher(tmp_path)
    node_registry, node_models = _node(tmp_path)
    apply_bundle(_bundle(tmp_path, registry, models), node_registry, node_models, public, enabled=True)
    with pytest.raises(BundleError, match="nothing to go back to"):
        rollback_registry(node_registry)
    before = node_registry.read_bytes()
    data = b"model 0.2.0"
    (models / "pcb-0.2.0.hef").write_bytes(data)
    registry.write_text(json.dumps([_entry("0.1.0", b"model 0.1.0"), _entry("0.2.0", data)]), encoding="utf-8")
    sign_registry(registry, private)
    apply_bundle(_bundle(tmp_path, registry, models, out="two.zip"), node_registry, node_models, public, enabled=True)
    assert len(load_registry(node_registry, public)) == 2
    assert rollback_registry(node_registry) == ["registry.json", "registry.json.sig"]
    assert node_registry.read_bytes() == before and len(load_registry(node_registry, public)) == 1


def test_a_bundle_is_built_only_from_a_signed_registry_and_checked_files(tmp_path: Path) -> None:
    registry, models, _private, _public = _publisher(tmp_path)
    (models / "pcb-0.1.0.hef").write_bytes(b"changed after registering")
    with pytest.raises(BundleError, match="does not match the checksum"):
        make_bundle(registry, models, tmp_path / "x.zip")
    (models / "pcb-0.1.0.hef").unlink()
    with pytest.raises(BundleError, match="not a file"):
        make_bundle(registry, models, tmp_path / "x.zip")
    registry2, models2, _, _ = _publisher(tmp_path, name="second")
    with pytest.raises(BundleError, match="no entry named 'nope'"):
        make_bundle(registry2, models2, tmp_path / "y.zip", ["nope"])
    registry2.with_name("registry.json.sig").unlink()
    with pytest.raises(BundleError, match="sign the registry first"):
        make_bundle(registry2, models2, tmp_path / "y.zip")


def test_the_commands_make_apply_and_roll_back(tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    registry, models, _private, public = _publisher(tmp_path)
    node_registry, node_models = _node(tmp_path)

    def run(*argv: str) -> int:
        monkeypatch.setattr("sys.argv", ["x", *argv])
        return main()

    out = tmp_path / "cli.zip"
    assert run("registry", "make-bundle", "--registry", str(registry), "--models-dir", str(models), "--out", str(out), "--name", "pcb") == 0
    apply = ["registry", "apply-bundle", "--bundle", str(out), "--registry", str(node_registry), "--models-dir", str(node_models), "--public-key", str(public)]
    assert run(*apply) == 1 and "is off" in capsys.readouterr().err
    assert run(*apply, "--enable-ota") == 0 and "applied the bundle" in capsys.readouterr().out
    monkeypatch.setenv("HYDRA_UMC_DETECTION_HEF_OTA", "1")
    assert run(*apply) == 0
    assert run("registry", "rollback", "--registry", str(node_registry)) == 0
    assert run("registry", "make-bundle", "--registry", str(registry), "--models-dir", str(models), "--out", str(out), "--name", "nope") == 1


# ---------------------------------------------------------------------------------------------------- loaded models


def _entries(tmp_path: Path):
    registry, _models, _private, _public = _publisher(tmp_path, ("0.1.0", "0.2.0"))
    data = json.loads(registry.read_text(encoding="utf-8"))
    data.append(_entry("0.3.0", b"canary", channel="canary"))
    registry.write_text(json.dumps(data), encoding="utf-8")
    return registry, load_registry(registry)


def _report(version="0.2.0", data=None, **change):
    payload = data if data is not None else f"model {version}".encode()
    body = {"node": "cm5-1", "model_name": "pcb", "model_version": version, "model_sha256": hashlib.sha256(payload).hexdigest(), "hailo_arch": "hailo8"}
    body.update(change)
    return body


def test_the_verdicts_of_a_report(tmp_path: Path) -> None:
    _registry, entries = _entries(tmp_path)
    assert judge(entries, _report("0.2.0"))["verdict"] == "current"
    outdated = judge(entries, _report("0.1.0"))
    assert outdated["verdict"] == "outdated" and outdated["latest"] == "0.2.0"
    assert judge(entries, _report("0.9.0"))["verdict"] == "unknown_model"
    assert judge(entries, _report("0.2.0", model_sha256="f" * 64))["verdict"] == "sha256_mismatch"
    assert judge(entries, _report("0.2.0", hailo_arch="hailo8l"))["verdict"] == "arch_mismatch"
    canary = judge(entries, _report("0.3.0", data=b"canary"))
    assert canary["verdict"] == "current" and canary["channel"] == "canary"  # the newest of its own channel


@pytest.mark.parametrize("change", [
    {"node": ""}, {"node": "a b"}, {"model_name": "x y"}, {"model_version": "1.2"}, {"model_sha256": "A" * 64}, {"hailo_arch": "hailo9"},
    {"pipeline_version": "x"}, {"io_contract_sha256": "short"}, {"extra": "x"}, {"node": 5},
])
def test_a_bad_report_is_refused(change: dict) -> None:
    with pytest.raises(ReportError):
        parse_report({**_report(), **change})
    with pytest.raises(ReportError):
        parse_report([])
    with pytest.raises(ReportError, match="missing"):
        parse_report({"node": "a"})


def test_the_newest_report_of_a_node_wins_and_the_list_is_bounded(tmp_path: Path) -> None:
    _registry, entries = _entries(tmp_path)
    ticks = iter(range(1, 100))
    store = LoadedModels(limit=2, clock=lambda: next(ticks))
    store.record(entries, _report("0.1.0", node="a"))
    store.record(entries, _report("0.2.0", node="a"))
    store.record(entries, _report("0.2.0", node="b"))
    store.record(entries, _report("0.2.0", node="c"))
    nodes = store.snapshot()
    assert [n["node"] for n in nodes] == ["b", "c"] and nodes[0]["reportedAtMs"] == 3000


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    registry, _entries_ = _entries(tmp_path)
    server = RegistryServer(("127.0.0.1", 0), registry, None, loaded=LoadedModels(), token="t" * 16)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", registry
    server.shutdown()
    server.server_close()


def _call(url: str, body: object = None, token: str = "") -> tuple[int, dict]:
    data = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET", headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_the_routes_take_reports_with_the_token_and_list_them(served: tuple[str, Path]) -> None:
    base, _registry = served
    assert _call(base + "/models/loaded", _report("0.1.0"))[0] == 401
    assert _call(base + "/models/loaded")[0] == 401
    status, answer = _call(base + "/models/loaded", _report("0.1.0"), "t" * 16)
    assert status == 200 and answer["verdict"] == "outdated" and answer["latest"] == "0.2.0"
    status, listed = _call(base + "/models/loaded", token="t" * 16)
    assert status == 200 and [n["node"] for n in listed["nodes"]] == ["cm5-1"]
    for body in (b"", b"not json", b'{"node": NaN}', json.dumps({"node": "x"}).encode(), b"x" * 3000):
        assert _call(base + "/models/loaded", body, "t" * 16)[0] == 400
    assert _call(base + "/registry/latest?name=pcb&channel=beta")[0] == 400
    assert _call(base + "/registry/latest?name=pcb&channel=canary")[1]["version"] == "0.3.0"
    assert _call(base + "/registry/latest?name=pcb")[1]["version"] == "0.2.0"


def test_without_the_switch_the_routes_do_not_exist(tmp_path: Path) -> None:
    registry, _entries_ = _entries(tmp_path)
    server = RegistryServer(("127.0.0.1", 0), registry, None)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        assert _call(base + "/models/loaded")[0] == 404
        assert _call(base + "/models/loaded", _report())[0] == 404
    finally:
        server.shutdown()
        server.server_close()


def test_the_load_route_carries_the_identity_and_applies_the_gates(tmp_path: Path) -> None:
    registry, models, _private, _public = _publisher(tmp_path)
    server = RegistryServer(("127.0.0.1", 0), registry, models, min_accuracy_ratio=0.9)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        status, answer = _call(base + "/registry/load?name=pcb&target_arch=HAILO8")
        assert status == 200 and answer["isReady"] is False and answer["outcome"] == "rejected_accuracy"
    finally:
        server.shutdown()
        server.server_close()
    plain = RegistryServer(("127.0.0.1", 0), registry, models)
    threading.Thread(target=plain.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{plain.server_address[1]}"
        status, answer = _call(base + "/registry/load?name=pcb&target_arch=hailo8")
        assert answer["isReady"] is True and answer["identity"]["model_name"] == "pcb" and answer["identity"]["model_version"] == "0.1.0"
    finally:
        plain.shutdown()
        plain.server_close()
