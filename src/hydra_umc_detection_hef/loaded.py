# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/loaded.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Which model each node says it loaded, and whether the registry agrees (traceability of the model that is running).

A node that loaded a model tells the registry service what it loaded (`POST /models/loaded`): its own name, and the identity of the model as the registry
writes it (`model_name`, `model_version`, `model_sha256`, `hailo_arch`, and optionally `pipeline_version` and `io_contract_sha256`). The service compares the
report with the registry and keeps the newest report of each node with a verdict:

* `current`: the model is in the registry, the SHA-256 and the architecture are the registered ones, and no newer version exists in its channel;
* `outdated`: the same, but a newer version exists in the channel (`latest` says which);
* `unknown_model`: no entry has that name and version;
* `sha256_mismatch` / `arch_mismatch` / `io_contract_changed`: the entry exists but the node runs something that is not what the registry describes.

The reports live in memory only, at most `limit` nodes (the oldest report is forgotten first), and the whole thing is off unless the server is started with
`--accept-loaded-reports`. A report is a claim of the node, not a proof: nothing here checks the file the node really holds.
"""
from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from .registry import KNOWN_HAILO_ARCHS, ModelEntry

MAX_NODES = 256
_NODE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
_SHA = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
_VERSION = re.compile(r"\d+\.\d+\.\d+")
_REQUIRED = ("node", "model_name", "model_version", "model_sha256", "hailo_arch")
_OPTIONAL = ("pipeline_version", "io_contract_sha256")


class ReportError(ValueError):
    """A report of a loaded model is malformed."""


def parse_report(body: object) -> dict[str, str]:
    if not isinstance(body, dict):
        raise ReportError("the report is a JSON object")
    missing = [k for k in _REQUIRED if k not in body]
    if missing:
        raise ReportError(f"missing field(s) {missing}")
    unknown = sorted(set(body) - set(_REQUIRED) - set(_OPTIONAL))
    if unknown:
        raise ReportError(f"unknown field(s) {unknown}")
    if not all(isinstance(v, str) for v in body.values()):
        raise ReportError("every field is a text")
    if not _NODE.fullmatch(body["node"]):
        raise ReportError("node is 1 to 64 characters of letters, digits and _ . : -")
    if not _NAME.fullmatch(body["model_name"]):
        raise ReportError("model_name is 1 to 64 characters of letters, digits and _ . : -")
    if not _VERSION.fullmatch(body["model_version"]):
        raise ReportError("model_version must look like X.Y.Z")
    for key in ("model_sha256", "io_contract_sha256"):
        if key in body and not _SHA.fullmatch(body[key]):
            raise ReportError(f"{key} must be 64 lowercase hexadecimal digits")
    if body["hailo_arch"] not in KNOWN_HAILO_ARCHS:
        raise ReportError(f"hailo_arch must be one of {sorted(KNOWN_HAILO_ARCHS)}")
    if "pipeline_version" in body and not _VERSION.fullmatch(body["pipeline_version"]):
        raise ReportError("pipeline_version must look like X.Y.Z")
    return dict(body)


def judge(entries: list[ModelEntry], report: dict[str, str]) -> dict[str, Any]:
    """The verdict of one report against the registry."""
    entry = next((e for e in entries if e.name == report["model_name"] and e.version == report["model_version"]), None)
    if entry is None:
        return {"verdict": "unknown_model", "latest": None}
    from .registry import io_contract_sha256

    in_channel = [e for e in entries if e.name == entry.name and e.channel == entry.channel]
    latest = max(in_channel, key=lambda e: e.version_tuple)
    if entry.sha256 != report["model_sha256"]:
        verdict = "sha256_mismatch"
    elif entry.hailo_arch != report["hailo_arch"]:
        verdict = "arch_mismatch"
    elif "io_contract_sha256" in report and entry.io_contract is not None and io_contract_sha256(entry.io_contract) != report["io_contract_sha256"]:
        verdict = "io_contract_changed"
    elif latest.version_tuple > entry.version_tuple:
        verdict = "outdated"
    else:
        verdict = "current"
    return {"verdict": verdict, "latest": latest.version, "channel": entry.channel}


class LoadedModels:
    def __init__(self, limit: int = MAX_NODES, clock: Callable[[], float] = time.time) -> None:
        self.limit = limit
        self._clock = clock
        self._lock = threading.Lock()
        self._reports: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def record(self, entries: list[ModelEntry], body: object) -> dict[str, Any]:
        report = parse_report(body)
        verdict = judge(entries, report)
        item = {**report, **verdict, "reportedAtMs": int(self._clock() * 1000)}
        with self._lock:
            self._reports.pop(report["node"], None)
            self._reports[report["node"]] = item
            while len(self._reports) > self.limit:
                self._reports.popitem(last=False)
        return item

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return sorted(self._reports.values(), key=lambda r: r["node"])
