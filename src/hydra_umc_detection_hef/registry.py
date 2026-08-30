# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/registry.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
"""Compiled-model registry: versioning and integrity checking of .hef models.

Compiling and versioning models is a data/ML workflow, separate from the
Hailo Dataflow Compiler toolchain itself (which needs the real Hailo SDK
and hardware to run) - this is the part of that workflow that's pure file
and metadata bookkeeping, so it can be written and tested without either.
The registry file this reads is meant to travel with a build's compiled
.hef outputs; HYDRA-UMC-VISION-NODE (the integration parent) is the
consumer that picks the right entry off it at deploy time.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Real Hailo NPU family identifiers a compiled .hef targets - the Hailo
# Dataflow Compiler bakes the target architecture into the .hef itself,
# and loading one on the wrong chip is a real, well-documented failure
# mode (not a hypothetical one this registry invents a check for).
KNOWN_HAILO_ARCHS = frozenset(
    {"hailo8", "hailo8r", "hailo8l", "hailo15h", "hailo15m", "hailo15l", "hailo10h"}
)


class RegistryError(ValueError):
    """Raised for a malformed registry file or entry."""


@dataclass(frozen=True)
class ModelEntry:
    name: str
    version: str
    task: str
    input_shape: tuple[int, ...]
    classes: tuple[str, ...]
    hef_path: str
    sha256: str
    hailo_arch: str

    @property
    def version_tuple(self) -> tuple[int, int, int]:
        match = _VERSION_RE.match(self.version)
        if match is None:
            raise RegistryError(f"malformed version {self.version!r} for model {self.name!r}")
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _parse_entry(raw: object, index: int) -> ModelEntry:
    if not isinstance(raw, dict):
        raise RegistryError(f"entry {index}: entry must be a JSON object")
    required = ("name", "version", "task", "input_shape", "classes", "hef_path", "sha256", "hailo_arch")
    missing = [field for field in required if field not in raw]
    if missing:
        raise RegistryError(f"entry {index}: missing field(s) {missing}")

    if not isinstance(raw["name"], str) or not raw["name"].strip():
        raise RegistryError(f"entry {index}: name must not be empty")
    if not isinstance(raw["version"], str) or _VERSION_RE.match(raw["version"]) is None:
        raise RegistryError(f"entry {index}: version {raw['version']!r} must look like X.Y.Z")
    if not isinstance(raw["task"], str) or not raw["task"].strip():
        raise RegistryError(f"entry {index}: task must not be empty")

    if not isinstance(raw["input_shape"], list):
        raise RegistryError(f"entry {index}: input_shape must be an array")
    input_shape = tuple(raw["input_shape"])
    if not input_shape or any(not isinstance(d, int) or d <= 0 for d in input_shape):
        raise RegistryError(f"entry {index}: input_shape must be non-empty positive integers")

    if not isinstance(raw["classes"], list):
        raise RegistryError(f"entry {index}: classes must be an array")
    classes = tuple(raw["classes"])
    if not classes or any(not isinstance(label, str) or not label.strip() for label in classes):
        raise RegistryError(f"entry {index}: classes must not be empty")

    if not isinstance(raw["hef_path"], str) or not raw["hef_path"].strip():
        raise RegistryError(f"entry {index}: hef_path must not be empty")
    if Path(raw["hef_path"]).is_absolute():
        raise RegistryError(f"entry {index}: hef_path {raw['hef_path']!r} must be a relative path")
    if not isinstance(raw["sha256"], str) or not re.fullmatch(r"[0-9a-fA-F]{64}", raw["sha256"]):
        raise RegistryError(f"entry {index}: sha256 must be a 64-char hex digest")
    if not isinstance(raw["hailo_arch"], str) or raw["hailo_arch"] not in KNOWN_HAILO_ARCHS:
        raise RegistryError(
            f"entry {index}: hailo_arch {raw['hailo_arch']!r} is not a known Hailo architecture "
            f"({sorted(KNOWN_HAILO_ARCHS)}) - catches a typo'd or invented arch name at "
            "registry-validation time rather than at deploy time on the wrong chip"
        )

    return ModelEntry(
        name=raw["name"], version=raw["version"], task=raw["task"],
        input_shape=input_shape, classes=classes,
        hef_path=raw["hef_path"], sha256=raw["sha256"].lower(),
        hailo_arch=raw["hailo_arch"],
    )


def load_registry(path: Path) -> list[ModelEntry]:
    """Parse a registry JSON file: a top-level list of model entries."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"could not read registry {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise RegistryError(f"registry {path} must be a JSON array of entries")
    return [_parse_entry(item, i) for i, item in enumerate(raw)]


def duplicate_versions(entries: list[ModelEntry]) -> list[tuple[str, str]]:
    """(name, version) pairs that appear more than once - a registry bug."""
    seen: dict[tuple[str, str], int] = {}
    for entry in entries:
        key = (entry.name, entry.version)
        seen[key] = seen.get(key, 0) + 1
    return sorted(key for key, count in seen.items() if count > 1)


def find_latest(entries: list[ModelEntry], name: str, task: str | None = None) -> ModelEntry | None:
    """The highest-version entry matching name (and task, if given)."""
    candidates = [e for e in entries if e.name == name and (task is None or e.task == task)]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e.version_tuple)


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(entry: ModelEntry, models_dir: Path) -> bool | None:
    """True/False if the file was found and checked, None if it's absent.

    None (rather than a hard failure) matters here: a registry describes
    models that may live in a separate object store, not necessarily
    checked into this repo, so a missing local file isn't automatically a
    corrupt registry - only a mismatched checksum for a file that *is*
    present is.

    `entry.hef_path` comes from the registry JSON, which may be corrupt
    or untrusted - `_parse_entry` already rejects an absolute hef_path,
    but a relative one can still climb out of `models_dir` with enough
    `../` segments. Confining the *resolved* join target back under the
    *resolved* `models_dir` (rather than a naive string-prefix check,
    which a sibling directory like `models_dir_evil` would falsely pass)
    is what actually keeps this a safe-load gate rather than an arbitrary
    local file read.
    """
    file_path = models_dir / entry.hef_path
    models_dir_resolved = models_dir.resolve()
    resolved_path = file_path.resolve()
    if not resolved_path.is_relative_to(models_dir_resolved):
        raise RegistryError(
            f"model {entry.name!r} {entry.version!r}: hef_path {entry.hef_path!r} "
            f"resolves outside models_dir {models_dir}"
        )
    if not file_path.is_file():
        return None
    return compute_sha256(file_path) == entry.sha256
