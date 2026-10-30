# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/registry.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
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

import contextlib
import hashlib
import json
import math
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
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
    # How a consumer must prepare the input and read the output of the model (colour order, normalisation, resize,
    # box order, NMS). Optional in the registry file; when present it is validated by `validate_io_contract`.
    io_contract: dict | None = field(default=None, compare=False, hash=False)

    @property
    def version_tuple(self) -> tuple[int, int, int]:
        match = _VERSION_RE.match(self.version)
        if match is None:
            raise RegistryError(f"malformed version {self.version!r} for model {self.name!r}")
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


_IO_INPUT_REQUIRED = ("layout", "color_order", "dtype", "normalization", "resize")
_IO_INPUT_OPTIONAL = ("pad_value",)
_IO_OUTPUT_REQUIRED = ("format", "bbox_order", "bbox_normalized", "nms_on_chip")
_IO_OUTPUT_OPTIONAL = ("max_detections_per_class", "score_threshold", "iou_threshold")
_IO_CHOICES = {
    "layout": ("NHWC", "NCHW"),
    "color_order": ("RGB", "BGR", "GRAY"),
    "dtype": ("uint8", "float32"),
    "resize": ("letterbox", "stretch"),
    "format": ("hailo_nms_by_class", "raw_yolo"),
    "bbox_order": ("ymin,xmin,ymax,xmax", "xmin,ymin,xmax,ymax"),
}


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_io_contract(contract: object) -> list[str]:
    """Every problem found in an `io_contract` block (empty list: valid). Nothing here needs the Hailo runtime."""
    if not isinstance(contract, dict):
        return ["io_contract must be a JSON object with an input and an output block"]
    problems: list[str] = []
    for extra in sorted(set(contract) - {"input", "output"}):
        problems.append(f"io_contract: unknown key {extra!r}")
    for part, required, optional in (
        ("input", _IO_INPUT_REQUIRED, _IO_INPUT_OPTIONAL),
        ("output", _IO_OUTPUT_REQUIRED, _IO_OUTPUT_OPTIONAL),
    ):
        block = contract.get(part)
        if not isinstance(block, dict):
            problems.append(f"io_contract.{part} is required and must be an object")
            continue
        for key in sorted(set(block) - set(required) - set(optional)):
            problems.append(f"io_contract.{part}: unknown key {key!r}")
        for key in required:
            if key not in block:
                problems.append(f"io_contract.{part}.{key} is required")
        for key, allowed in _IO_CHOICES.items():
            if key in block and block[key] not in allowed:
                problems.append(f"io_contract.{part}.{key} must be one of {list(allowed)}")
        for key in ("bbox_normalized", "nms_on_chip"):
            if key in block and not isinstance(block[key], bool):
                problems.append(f"io_contract.{part}.{key} must be true or false")
    inp = contract.get("input") if isinstance(contract.get("input"), dict) else {}
    norm = inp.get("normalization")
    if "normalization" in inp and norm != "on-chip":
        if not (isinstance(norm, dict) and set(norm) == {"mean", "std"}):
            problems.append('io_contract.input.normalization must be "on-chip" or {"mean": [...], "std": [...]}')
        else:
            mean, std = norm["mean"], norm["std"]
            if not (isinstance(mean, list) and mean and all(_is_number(v) for v in mean)):
                problems.append("io_contract.input.normalization.mean must be a non-empty list of numbers")
            if not (isinstance(std, list) and std and all(_is_number(v) and v > 0 for v in std)):
                problems.append("io_contract.input.normalization.std must be a non-empty list of numbers above 0")
            if isinstance(mean, list) and isinstance(std, list) and len(mean) != len(std):
                problems.append("io_contract.input.normalization: mean and std must have the same length")
    pad = inp.get("pad_value")
    if "pad_value" in inp and not (isinstance(pad, int) and not isinstance(pad, bool) and 0 <= pad <= 255):
        problems.append("io_contract.input.pad_value must be an integer in 0..255")
    out = contract.get("output") if isinstance(contract.get("output"), dict) else {}
    for key in ("score_threshold", "iou_threshold"):
        if key in out and not (_is_number(out[key]) and 0.0 <= out[key] <= 1.0):
            problems.append(f"io_contract.output.{key} must be a number in 0..1")
    maxdet = out.get("max_detections_per_class")
    if "max_detections_per_class" in out and not (isinstance(maxdet, int) and not isinstance(maxdet, bool) and maxdet > 0):
        problems.append("io_contract.output.max_detections_per_class must be an integer above 0")
    return problems


def classes_sha256(classes: tuple[str, ...] | list[str]) -> str:
    """sha256 of the class list written as a classes.txt file: one label a line and a final newline. A dataset
    generator that publishes this hash lets `registry add` prove that the labels it is given are the dataset's."""
    return hashlib.sha256(("\n".join(classes) + "\n").encode("utf-8")).hexdigest()


def io_contract_sha256(contract: dict) -> str:
    """sha256 of the contract as canonical JSON (sorted keys, no spaces), so two registries that spell it differently
    but mean the same thing give the same hash."""
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


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
    # bool is a subclass of int in Python, so `isinstance(True, int)`
    # is True and `True <= 0` is False (True == 1) - a dimension of
    # `True` used to sail through this check as a "valid positive
    # integer" instead of being rejected as the non-numeric value it
    # actually is.
    if not input_shape or any(isinstance(d, bool) or not isinstance(d, int) or d <= 0 for d in input_shape):
        raise RegistryError(f"entry {index}: input_shape must be non-empty positive integers")
    # The input is an image in HWC order: height, width, channels,
    # with 1 (grey), 3 (colour) or 4 (colour with alpha) channels.
    if len(input_shape) != 3 or input_shape[2] not in (1, 3, 4):
        raise RegistryError(
            f"entry {index}: input_shape must be height, width, channels (HWC) with 1, 3 or 4 channels, got {list(input_shape)}"
        )

    if not isinstance(raw["classes"], list):
        raise RegistryError(f"entry {index}: classes must be an array")
    classes = tuple(raw["classes"])
    if not classes or any(not isinstance(label, str) or not label.strip() for label in classes):
        raise RegistryError(f"entry {index}: classes must not be empty")
    if len(set(classes)) != len(classes):
        raise RegistryError(f"entry {index}: classes must not repeat a label - class ids are positions in this list")

    if not isinstance(raw["hef_path"], str) or not raw["hef_path"].strip():
        raise RegistryError(f"entry {index}: hef_path must not be empty")
    if Path(raw["hef_path"]).is_absolute():
        raise RegistryError(f"entry {index}: hef_path {raw['hef_path']!r} must be a relative path")
    if ".." in Path(raw["hef_path"]).parts or ".." in raw["hef_path"].replace("\\", "/").split("/"):
        raise RegistryError(f"entry {index}: hef_path {raw['hef_path']!r} must not contain '..' segments")
    if not isinstance(raw["sha256"], str) or not re.fullmatch(r"[0-9a-fA-F]{64}", raw["sha256"]):
        raise RegistryError(f"entry {index}: sha256 must be a 64-char hex digest")
    if not isinstance(raw["hailo_arch"], str) or raw["hailo_arch"] not in KNOWN_HAILO_ARCHS:
        raise RegistryError(
            f"entry {index}: hailo_arch {raw['hailo_arch']!r} is not a known Hailo architecture "
            f"({sorted(KNOWN_HAILO_ARCHS)}) - catches a typo'd or invented arch name at "
            "registry-validation time rather than at deploy time on the wrong chip"
        )

    io_contract = None
    if "io_contract" in raw:
        problems = validate_io_contract(raw["io_contract"])
        if problems:
            raise RegistryError(f"entry {index}: " + "; ".join(problems))
        io_contract = raw["io_contract"]

    return ModelEntry(
        name=raw["name"], version=raw["version"], task=raw["task"],
        input_shape=input_shape, classes=classes,
        hef_path=raw["hef_path"], sha256=raw["sha256"].lower(),
        hailo_arch=raw["hailo_arch"], io_contract=io_contract,
    )


def load_registry(path: Path, public_key_file: Path | None = None) -> list[ModelEntry]:
    """Parse a registry JSON file: a top-level list of model entries.

    With `public_key_file` the signature next to the registry (`<registry>.sig`, see signing.py) must be a valid
    Ed25519 signature of exactly the bytes that are parsed here; without it the registry is read as before."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RegistryError(f"could not read registry {path}: {exc}") from exc
    if public_key_file is not None:
        from .signing import verify_registry_bytes

        verify_registry_bytes(data, path, public_key_file)
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"could not read registry {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise RegistryError(f"registry {path} must be a JSON array of entries")
    return [_parse_entry(item, i) for i, item in enumerate(raw)]


def load_registry_or_empty(path: Path) -> list[ModelEntry]:
    """Same as `load_registry()`, except a missing file is a real, valid
    "no entries yet" starting point rather than an error - the natural
    first call `add_entry()`'s own CLI makes when creating a brand new
    registry, not just appending to an existing one."""
    if not path.is_file():
        return []
    return load_registry(path)


def _entry_to_json(entry: ModelEntry) -> dict[str, object]:
    data: dict[str, object] = {
        "name": entry.name,
        "version": entry.version,
        "task": entry.task,
        "input_shape": list(entry.input_shape),
        "classes": list(entry.classes),
        "hef_path": entry.hef_path,
        "sha256": entry.sha256,
        "hailo_arch": entry.hailo_arch,
    }
    if entry.io_contract is not None:
        data["io_contract"] = entry.io_contract
    return data


def _fsync_directory(directory: Path) -> None:
    """Best effort: makes the rename itself survive a power cut (not possible on every OS)."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


@contextlib.contextmanager
def registry_lock(path: Path, timeout: float = 10.0):
    """Serialises read-modify-write cycles on one registry file: two
    `registry add` running together used to overwrite each other's entry."""
    lock_path = Path(path).with_name(Path(path).name + ".lock")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise RegistryError(f"{lock_path} is held by another process (remove it if that process is gone)") from None
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except OSError:
            pass


def write_registry(path: Path, entries: list[ModelEntry]) -> None:
    """Write `entries` back as the same JSON-array-of-objects shape
    `load_registry()` reads, one real key order, human-diffable."""
    payload = [_entry_to_json(entry) for entry in entries]
    text = json.dumps(payload, indent=2) + "\n"
    # This file is the trust source for every model `safe_load` accepts (names,
    # architectures, sha256). Rewriting it in place meant a power cut or a full
    # disk halfway through left a truncated file and the whole registry
    # unreadable; the new content is now written beside it, flushed and fsynced,
    # then renamed over it, so the previous registry stays intact until the
    # new one is complete.
    path = Path(path)
    # a unique temporary name: two writers must never share one
    handle_fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    temporary = Path(temporary_name)
    try:
        with open(handle_fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def add_entry(
    entries: list[ModelEntry],
    *,
    models_dir: Path,
    name: str,
    version: str,
    task: str,
    input_shape: tuple[int, ...],
    classes: tuple[str, ...],
    hef_path: str,
    hailo_arch: str,
) -> ModelEntry:
    """Build and validate a new real entry from a real local `.hef` file -
    found while auditing the code: today the
    registry JSON is hand-edited, including the sha256 that
    `verify_checksum()` only ever checks, never generates - a real risk
    of a corrupted-by-hand registry (a typo'd hex digit never fails until
    someone runs `registry validate` against the real file). This hashes
    the real file at `models_dir / hef_path` with the same
    `compute_sha256()` `verify_checksum()` itself uses, then validates
    the assembled entry through the exact same `_parse_entry()` gate
    `load_registry()` runs every entry through - no separate, potentially
    divergent set of rules for an entry created this way. Never mutates
    `entries` - the real CLI command decides whether to append and write.
    """
    file_path = models_dir / hef_path
    models_dir_resolved = models_dir.resolve()
    resolved_path = file_path.resolve()
    if not resolved_path.is_relative_to(models_dir_resolved):
        raise RegistryError(f"hef_path {hef_path!r} resolves outside models_dir {models_dir}")
    if not file_path.is_file():
        raise RegistryError(f"{file_path} does not exist - add_entry() only registers a real, present file")

    sha256 = compute_sha256(file_path)
    raw = {
        "name": name,
        "version": version,
        "task": task,
        "input_shape": list(input_shape),
        "classes": list(classes),
        "hef_path": hef_path,
        "sha256": sha256,
        "hailo_arch": hailo_arch,
    }
    new_entry = _parse_entry(raw, len(entries))

    if any(e.name == new_entry.name and e.version == new_entry.version for e in entries):
        raise RegistryError(f"entry for {new_entry.name!r} {new_entry.version!r} already exists in the registry")

    return new_entry


def duplicate_versions(entries: list[ModelEntry]) -> list[tuple[str, str]]:
    """(name, version) pairs that appear more than once - a registry bug."""
    seen: dict[tuple[str, str], int] = {}
    for entry in entries:
        key = (entry.name, entry.version)
        seen[key] = seen.get(key, 0) + 1
    return sorted(key for key, count in seen.items() if count > 1)


class AmbiguousModelError(RegistryError):
    """Two registry entries claim the same name and version but point at different files."""


def find_latest(
    entries: list[ModelEntry], name: str, task: str | None = None, version: str | None = None
) -> ModelEntry | None:
    """The highest-version entry matching name (and task, if given), or the
    entry of exactly `version` when one is asked for (to pin or roll back).

    Raises AmbiguousModelError when the winning name+version appears more than
    once with a different file or checksum: picking "the first one in the
    file" would let a bad merge of the registry deploy a different binary
    while the answer still says it is verified."""
    candidates = [e for e in entries if e.name == name and (task is None or e.task == task)]
    if version is not None:
        candidates = [e for e in candidates if e.version == version]
    if not candidates:
        return None
    best = max(candidates, key=lambda e: e.version_tuple)
    rivals = [e for e in candidates if e.version == best.version and (e.hef_path, e.sha256) != (best.hef_path, best.sha256)]
    if rivals:
        raise AmbiguousModelError(
            f"{name!r} {best.version!r} appears more than once with different files "
            f"({best.hef_path}, {rivals[0].hef_path}) - fix the registry"
        )
    return best


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_verified(entry: ModelEntry, models_dir: Path) -> tuple[bool | None, bytes | None]:
    """Like `verify_checksum`, but reads the file ONCE and returns the bytes that were hashed: `(None, None)` when the
    file is absent, `(False, None)` when the hash differs, `(True, data)` when it matches. A consumer that loads `data`
    (instead of opening the path again later) cannot get a file that changed, or a symlink that was repointed, between
    the check and the use. The path is confined under `models_dir` exactly as in `verify_checksum`."""
    file_path = models_dir / entry.hef_path
    if not file_path.resolve().is_relative_to(models_dir.resolve()):
        raise RegistryError(
            f"model {entry.name!r} {entry.version!r}: hef_path {entry.hef_path!r} "
            f"resolves outside models_dir {models_dir}"
        )
    if not file_path.is_file():
        return None, None
    data = file_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry.sha256:
        return False, None
    return True, data


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
