# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/settings_file.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""A settings file the running process re-reads, so that an operator can turn the loaded-model reports on and off without restarting the service.

HYDRA-UMC-SERVER writes the file from its Server Admin panel; the service only reads it. The file is a small JSON object:

    {"acceptLoadedReports": true}

Rules, all of them on the side of keeping the service closed:

* Off by default. Without `--settings-file` (or HYDRA_UMC_DETECTION_HEF_SETTINGS_FILE) the only switch is the `--accept-loaded-reports` flag read at start.
* The file is re-read when its size or modification time changes, at most once per `MIN_RECHECK_SECONDS`; a request never waits on more than one small read.
* A missing file leaves the flag of the command line in force. A file that exists but cannot be trusted (not a regular file, larger than `MAX_BYTES`, not
  UTF-8 JSON, not an object, `acceptLoadedReports` not a real boolean) turns the reports OFF until it is fixed: a broken file never opens anything.
* Turning the reports on away from loopback needs a bearer token or the identity of the SERVER, exactly as the flag does at start: without one the file's
  "true" is refused and the reports stay off (`reason` says why).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

SETTINGS_FILE_ENV = "HYDRA_UMC_DETECTION_HEF_SETTINGS_FILE"
MAX_BYTES = 4096
MIN_RECHECK_SECONDS = 1.0
KEY = "acceptLoadedReports"


def settings_path_from(argument: str | None, environ: dict[str, str] | None = None) -> Path | None:
    """The settings file asked for by the command line, else by the environment (None when neither)."""
    env = os.environ if environ is None else environ
    chosen = (argument or env.get(SETTINGS_FILE_ENV, "")).strip()
    return Path(chosen) if chosen else None


class RuntimeSettings:
    """The switch of the loaded-model reports: the command-line flag, overridden by the settings file when there is one."""

    def __init__(self, path: Path | None, flag: bool = False, clock=time.monotonic) -> None:
        self.path = path
        self.flag = flag
        self._clock = clock
        self._lock = threading.Lock()
        self._stamp: tuple[int, int] | None = None
        self._checked_at = float("-inf")
        self._value: bool | None = None  # None: no file, the flag decides
        self.reason = ""

    def _read(self) -> None:
        assert self.path is not None
        try:
            info = self.path.stat()
        except FileNotFoundError:
            self._stamp, self._value, self.reason = None, None, ""
            return
        except OSError as error:
            self._stamp, self._value, self.reason = None, False, f"cannot look at the settings file: {error.strerror}"
            return
        stamp = (info.st_size, info.st_mtime_ns)
        if stamp == self._stamp:
            return
        self._stamp = stamp
        if not self.path.is_file() or info.st_size > MAX_BYTES:
            self._value, self.reason = False, "the settings file is not a regular file of at most 4096 bytes"
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"), parse_constant=lambda name: (_ for _ in ()).throw(ValueError(name)))
        except (OSError, ValueError):
            self._value, self.reason = False, "the settings file is not valid JSON"
            return
        if not isinstance(data, dict) or not isinstance(data.get(KEY, False), bool):
            self._value, self.reason = False, f"the settings file must be an object whose {KEY} is true or false"
            return
        # a key that is absent leaves the flag of the command line in force
        self._value = data[KEY] if KEY in data else None
        self.reason = ""

    def accept_loaded_reports(self) -> bool:
        """True when the reports are on right now."""
        if self.path is None:
            return self.flag
        with self._lock:
            now = self._clock()
            if now - self._checked_at >= MIN_RECHECK_SECONDS:
                self._checked_at = now
                self._read()
            return self.flag if self._value is None else self._value
