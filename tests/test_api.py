# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_api.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
"""Real end-to-end HTTP tests: a real RegistryServer (ThreadingHTTPServer)
against a real registry.json/models_dir on tmp_path, hit with real urllib
requests - same convention and fixture shapes as this repo's own
tests/test_compatibility.py, just reached over HTTP instead of called
directly."""
from __future__ import annotations

import hashlib
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager

from hydra_umc_detection_hef.api import RegistryServer


def _write_registry(path, entries):
    path.write_text(json.dumps(entries), encoding="utf-8")


def _entry(name="pcb-defect", version="0.1.0", task="detection", sha256="a" * 64, hailo_arch="hailo8"):
    return {
        "name": name, "version": version, "task": task,
        "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component"],
        "hef_path": f"{name}-{version}.hef", "sha256": sha256, "hailo_arch": hailo_arch,
    }


def _get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@contextmanager
def running_server(registry_path, models_dir=None) -> Iterator[str]:
    server = RegistryServer(("127.0.0.1", 0), registry_path, models_dir)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_list_registry(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="0.1.0"), _entry(version="0.2.0")])
    with running_server(reg_path) as base:
        status, body = _get(f"{base}/registry")
        assert status == 200
        assert len(body["entries"]) == 2
        assert body["duplicateVersions"] == []


def test_list_registry_reports_duplicate_versions(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="0.1.0"), _entry(version="0.1.0")])
    with running_server(reg_path) as base:
        status, body = _get(f"{base}/registry")
        assert status == 200
        assert body["duplicateVersions"] == [{"name": "pcb-defect", "version": "0.1.0"}]


def test_registry_latest(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(version="0.1.0"), _entry(version="0.2.0")])
    with running_server(reg_path) as base:
        status, body = _get(f"{base}/registry/latest?name=pcb-defect")
        assert status == 200
        assert body["version"] == "0.2.0"


def test_registry_latest_not_found(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(name="pcb-defect")])
    with running_server(reg_path) as base:
        status, body = _get(f"{base}/registry/latest?name=nope")
        assert status == 404


def test_registry_latest_missing_name_param(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    with running_server(reg_path) as base:
        status, body = _get(f"{base}/registry/latest")
        assert status == 400


def test_registry_load_ready_when_arch_and_checksum_both_check_out(tmp_path) -> None:
    content = b"a real fake hef payload"
    digest = hashlib.sha256(content).hexdigest()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "pcb-defect-0.1.0.hef").write_bytes(content)

    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo8", sha256=digest)])

    with running_server(reg_path, models_dir) as base:
        status, body = _get(f"{base}/registry/load?name=pcb-defect&target_arch=hailo8")
        assert status == 200
        assert body["outcome"] == "ready"
        assert body["isReady"] is True


def test_registry_load_rejects_arch_mismatch(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry(hailo_arch="hailo8")])
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    with running_server(reg_path, models_dir) as base:
        status, body = _get(f"{base}/registry/load?name=pcb-defect&target_arch=hailo15h")
        assert status == 200
        assert body["outcome"] == "rejected_arch_mismatch"
        assert body["isReady"] is False


def test_registry_load_without_models_dir_returns_503(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    with running_server(reg_path, models_dir=None) as base:
        status, body = _get(f"{base}/registry/load?name=pcb-defect&target_arch=hailo8")
        assert status == 503


def test_stats(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    with running_server(reg_path) as base:
        status, body = _get(f"{base}/stats")
        assert status == 200
        assert body["registry"] == str(reg_path)


def test_not_found(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    _write_registry(reg_path, [_entry()])
    with running_server(reg_path) as base:
        status, body = _get(f"{base}/nope")
        assert status == 404


def test_malformed_registry_returns_502(tmp_path) -> None:
    reg_path = tmp_path / "registry.json"
    reg_path.write_text("not json", encoding="utf-8")
    with running_server(reg_path) as base:
        status, body = _get(f"{base}/registry")
        assert status == 502
