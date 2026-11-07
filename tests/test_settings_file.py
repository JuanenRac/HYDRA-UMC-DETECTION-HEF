# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_settings_file.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The settings file that switches the loaded-model reports while the service runs: re-read, closed by default, closed again by a broken file."""
from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from hydra_umc_detection_hef.api import RegistryServer
from hydra_umc_detection_hef.settings_file import MAX_BYTES, RuntimeSettings, settings_path_from
from test_bundle_and_loaded import _call, _entries, _report

TOKEN = "t" * 16


class Clock:
    """A clock the test moves by hand, so that the re-read interval never makes a test wait."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def tick(self) -> None:
        self.now += 10.0


def _write(path: Path, value: object) -> None:
    path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")


def test_without_a_file_the_flag_decides(tmp_path: Path) -> None:
    assert RuntimeSettings(None, flag=False).accept_loaded_reports() is False
    assert RuntimeSettings(None, flag=True).accept_loaded_reports() is True
    missing = RuntimeSettings(tmp_path / "absent.json", flag=True, clock=Clock())
    assert missing.accept_loaded_reports() is True  # a file that does not exist yet changes nothing


def test_the_file_is_read_again_when_it_changes(tmp_path: Path) -> None:
    path, clock = tmp_path / "settings.json", Clock()
    settings = RuntimeSettings(path, clock=clock)
    assert settings.accept_loaded_reports() is False
    _write(path, {"acceptLoadedReports": True})
    clock.tick()
    assert settings.accept_loaded_reports() is True
    _write(path, {"acceptLoadedReports": False, "padding": "x" * 20})  # a different size, so a different stamp
    clock.tick()
    assert settings.accept_loaded_reports() is False


def test_the_file_is_not_read_more_than_once_per_interval(tmp_path: Path) -> None:
    path, clock = tmp_path / "settings.json", Clock()
    _write(path, {"acceptLoadedReports": True})
    settings = RuntimeSettings(path, clock=clock)
    assert settings.accept_loaded_reports() is True
    _write(path, {"acceptLoadedReports": False, "padding": "x" * 20})
    assert settings.accept_loaded_reports() is True  # still inside the interval
    clock.tick()
    assert settings.accept_loaded_reports() is False


@pytest.mark.parametrize("content", [
    "not json", "[]", '{"acceptLoadedReports": "yes"}', '{"acceptLoadedReports": 1}', '{"acceptLoadedReports": NaN}', "ÿþ", "x" * (MAX_BYTES + 1),
])
def test_a_file_that_cannot_be_trusted_turns_the_reports_off_even_when_the_flag_is_on(tmp_path: Path, content: str) -> None:
    path = tmp_path / "settings.json"
    _write(path, content)
    settings = RuntimeSettings(path, flag=True, clock=Clock())
    assert settings.accept_loaded_reports() is False and settings.reason


def test_a_directory_is_not_a_settings_file(tmp_path: Path) -> None:
    settings = RuntimeSettings(tmp_path, flag=True, clock=Clock())
    assert settings.accept_loaded_reports() is False


def test_a_file_without_the_key_leaves_the_flag_in_force(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    _write(path, {})
    assert RuntimeSettings(path, flag=True, clock=Clock()).accept_loaded_reports() is True
    assert RuntimeSettings(path, flag=False, clock=Clock()).accept_loaded_reports() is False


def test_the_path_comes_from_the_argument_or_the_environment() -> None:
    assert settings_path_from(None, {}) is None
    assert settings_path_from("  ", {}) is None
    assert settings_path_from("a.json", {"HYDRA_UMC_DETECTION_HEF_SETTINGS_FILE": "b.json"}) == Path("a.json")
    assert settings_path_from(None, {"HYDRA_UMC_DETECTION_HEF_SETTINGS_FILE": "b.json"}) == Path("b.json")


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[str, Path, Clock]]:
    registry, _entries_ = _entries(tmp_path)
    path, clock = tmp_path / "settings.json", Clock()
    server = RegistryServer(("127.0.0.1", 0), registry, None, token=TOKEN)
    server.settings = RuntimeSettings(path, clock=clock)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", path, clock
    server.shutdown()
    server.server_close()


def test_the_routes_follow_the_file_while_the_server_runs(served: tuple[str, Path, Clock]) -> None:
    base, path, clock = served
    assert _call(base + "/models/loaded", _report("0.1.0"), TOKEN)[0] == 404  # closed until the file opens it
    _write(path, {"acceptLoadedReports": True})
    clock.tick()
    status, answer = _call(base + "/models/loaded", _report("0.1.0"), TOKEN)
    assert status == 200 and answer["verdict"] == "outdated"
    assert _call(base + "/models/loaded")[0] == 401  # the token still protects the routes
    assert [n["node"] for n in _call(base + "/models/loaded", token=TOKEN)[1]["nodes"]] == ["cm5-1"]
    _write(path, {"acceptLoadedReports": False})
    clock.tick()
    assert _call(base + "/models/loaded", token=TOKEN)[0] == 404
    _write(path, {"acceptLoadedReports": True, "padding": "x" * 20})
    clock.tick()
    assert _call(base + "/models/loaded", token=TOKEN)[1]["nodes"] == []  # what was reported before it was turned off is forgotten


def test_a_broken_file_closes_the_routes(served: tuple[str, Path, Clock]) -> None:
    base, path, clock = served
    _write(path, {"acceptLoadedReports": True})
    clock.tick()
    assert _call(base + "/models/loaded", token=TOKEN)[0] == 200
    _write(path, "{broken")
    clock.tick()
    assert _call(base + "/models/loaded", token=TOKEN)[0] == 404


def test_the_file_cannot_open_the_routes_away_from_loopback_without_a_token(tmp_path: Path) -> None:
    registry, _entries_ = _entries(tmp_path)
    path = tmp_path / "settings.json"
    _write(path, {"acceptLoadedReports": True})
    server = RegistryServer(("0.0.0.0", 0), registry, None)  # noqa: S104 - the point of the test: a wildcard address with no token
    try:
        server.settings = RuntimeSettings(path, clock=Clock())
        assert server.reports() is None
        server.token = TOKEN
        assert server.reports() is not None
    finally:
        server.server_close()
