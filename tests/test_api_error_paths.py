# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_api_error_paths.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The refusals of the HTTP API, one by one, against a real server: a query parameter given twice, a missing parameter, a model that does not exist, a name that
is two models, a version that is not a version, a server started without a folder of models, a registry that cannot be read, an entry that points outside the
folder of models and the routes that do not exist. Each one has its own status and none of them is an answer that looks like a model."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from hydra_umc_detection_hef.api import RegistryServer


def entry(name="pcb-defect", version="0.1.0", task="detection", hef="pcb-defect-0.1.0.hef", sha="a" * 64) -> dict:
    return {
        "name": name, "version": version, "task": task, "input_shape": [640, 640, 3], "classes": ["solder_bridge"],
        "hef_path": hef, "sha256": sha, "hailo_arch": "hailo8",
    }


def get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        with error:
            return error.code, json.loads(error.read())


@contextmanager
def serving(registry_text: str | None, models_dir: bool = True, tmp: Path | None = None) -> Iterator[str]:
    assert tmp is not None
    registry = tmp / "registry.json"
    if registry_text is not None:
        registry.write_text(registry_text, encoding="utf-8")
    models = tmp / "models"
    models.mkdir(exist_ok=True)
    server = RegistryServer(("127.0.0.1", 0), registry, models if models_dir else None)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def registry(*entries: dict) -> str:
    return json.dumps(list(entries))


class TestQuery:
    def test_a_parameter_given_twice_is_refused_by_name(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            for path in ("/registry/latest?name=a&name=b", "/registry/load?name=a&target_arch=hailo8&target_arch=hailo10", "/registry?x=1&x=2"):
                status, body = get(base + path)
                assert status == 400, path
                assert "exactly once" in body["error"] and "x" in body["error"] or "name" in body["error"] or "target_arch" in body["error"]

    def test_a_parameter_with_no_value_is_a_value_that_is_empty_not_a_missing_one(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            status, body = get(base + "/registry/latest?name=")
            assert status in (400, 404)
            assert "error" in body


class TestLatest:
    def test_a_name_is_required(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            status, body = get(base + "/registry/latest")
            assert (status, body["error"]) == (400, "missing required param: name")

    def test_an_unknown_model_is_a_404_that_names_it(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            status, body = get(base + "/registry/latest?name=ghost")
            assert status == 404 and "'ghost'" in body["error"]

    def test_a_name_that_is_two_models_is_a_409_not_a_guess(self, tmp_path) -> None:
        with serving(registry(entry(task="detection"), entry(task="segmentation", hef="seg.hef")), tmp=tmp_path) as base:
            status, body = get(base + "/registry/latest?name=pcb-defect")
            assert status == 409 and body["error"]
            status, body = get(base + "/registry/latest?name=pcb-defect&task=segmentation")
            assert status == 200 and body["task"] == "segmentation"

    def test_a_version_that_is_not_a_version_is_a_400(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            status, body = get(base + "/registry/latest?name=pcb-defect&version=not-a-version")
            assert status in (400, 404)
            assert "error" in body

    def test_the_newest_version_wins_and_a_wanted_version_is_found_exactly(self, tmp_path) -> None:
        with serving(registry(entry(version="0.1.0"), entry(version="0.10.0", hef="b.hef"), entry(version="0.2.0", hef="c.hef")), tmp=tmp_path) as base:
            assert get(base + "/registry/latest?name=pcb-defect")[1]["version"] == "0.10.0", "versions are compared as numbers, not as text"
            status, body = get(base + "/registry/latest?name=pcb-defect&version=0.2.0")
            assert status == 200 and body["version"] == "0.2.0"


class TestLoad:
    def test_the_name_and_the_architecture_are_both_required_and_the_missing_ones_are_listed(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            status, body = get(base + "/registry/load")
            assert status == 400 and "['name', 'target_arch']" in body["error"]
            status, body = get(base + "/registry/load?name=pcb-defect")
            assert status == 400 and "['target_arch']" in body["error"]

    def test_a_server_without_a_folder_of_models_cannot_load_anything(self, tmp_path) -> None:
        with serving(registry(entry()), models_dir=False, tmp=tmp_path) as base:
            status, body = get(base + "/registry/load?name=pcb-defect&target_arch=hailo8")
            assert status == 503 and "--models-dir" in body["error"]

    def test_an_unknown_model_is_a_404_and_an_ambiguous_one_a_409(self, tmp_path) -> None:
        with serving(registry(entry(task="detection"), entry(task="segmentation", hef="seg.hef")), tmp=tmp_path) as base:
            assert get(base + "/registry/load?name=ghost&target_arch=hailo8")[0] == 404
            assert get(base + "/registry/load?name=pcb-defect&target_arch=hailo8")[0] == 409

    def test_an_entry_that_points_outside_the_folder_of_models_is_a_502_never_a_load(self, tmp_path) -> None:
        with serving(registry(entry(hef="../outside.hef")), tmp=tmp_path) as base:
            status, body = get(base + "/registry/load?name=pcb-defect&target_arch=hailo8")
            assert status == 502 and "must not contain '..' segments" in body["error"]
            assert get(base + "/registry/latest?name=pcb-defect")[0] == 502, "the registry is refused as a whole, not entry by entry"

    def test_a_file_that_is_not_there_is_an_answer_that_says_not_ready_and_not_a_server_error(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            status, body = get(base + "/registry/load?name=pcb-defect&target_arch=hailo8")
            assert status == 200
            assert body["isReady"] is False
            assert body["entry"]["name"] == "pcb-defect"
            assert body["outcome"]


class TestRegistryFile:
    @pytest.mark.parametrize("path", ["/registry", "/registry/latest?name=a", "/registry/load?name=a&target_arch=hailo8"])
    def test_a_registry_that_cannot_be_read_is_a_502_on_every_route_that_reads_it(self, tmp_path, path: str) -> None:
        with serving(None, tmp=tmp_path) as base:
            status, body = get(base + path)
            assert status == 502 and "could not read registry" in body["error"]

    @pytest.mark.parametrize("text", ["{not json", "[1, 2]", '{"entries": 5}', '[{"name": "x"}]', ""])
    def test_a_registry_that_is_not_a_list_of_entries_is_a_502_not_a_crash(self, tmp_path, text: str) -> None:
        with serving(text, tmp=tmp_path) as base:
            status, body = get(base + "/registry")
            assert status == 502 and "could not read registry" in body["error"]
            assert get(base + "/stats")[0] in (200, 404), "the server is still up after reading a bad file"


class TestRoutes:
    def test_a_route_that_does_not_exist_is_a_404_with_a_message(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            for path in ("/", "/nothing", "/registry/", "/registry/latest/extra", "/models/loaded"):
                status, body = get(base + path)
                assert status == 404, path
                assert "error" in body

    def test_a_post_to_a_route_that_takes_no_posts_is_a_404(self, tmp_path) -> None:
        with serving(registry(entry()), tmp=tmp_path) as base:
            request = urllib.request.Request(base + "/registry", data=b"{}", method="POST", headers={"Content-Type": "application/json"})
            with pytest.raises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=5)
            assert caught.value.code == 404
            caught.value.close()
