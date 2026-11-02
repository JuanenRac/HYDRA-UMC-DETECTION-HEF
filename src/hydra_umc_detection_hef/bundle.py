# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/bundle.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Moving compiled models to a node as one signed bundle (the receiving end of an over-the-air update of models).

A bundle is a zip file: `bundle.json` (the format and the SHA-256 of every other member), `registry.json` with its detached signature `registry.json.sig`
(see signing.py) and the `.hef` files under `models/`, at the paths the registry gives them. `make_bundle` builds one from a registry and a models folder
after checking every file it packs against the checksum the registry records. `apply_bundle` is what a node runs, and it believes nothing it has not checked:

* it is off unless the operator turns it on (`--enable-ota` or HYDRA_UMC_DETECTION_HEF_OTA=1) and it refuses to run without the public key of the owner
  of the registry: an unsigned update is not an update;
* the member names are checked (no absolute path, no `..`, only the four kinds above), their number and their total size are limited, and every member
  must match the SHA-256 in `bundle.json`, and nothing may be in the zip that `bundle.json` does not list;
* the signature of `registry.json` must verify with the public key, and every `.hef` in the bundle must have the SHA-256 that its entry records;
* a model that goes to an older version than the node has is refused unless `allow_downgrade` says otherwise;
* only then are the `.hef` files put in place (each under a temporary name and renamed), the previous registry and signature kept as `.prev`, and the new
  registry and signature renamed over the old ones, all under the same lock `registry add` uses. `rollback_registry` puts the previous pair back.

Pushing a bundle to the nodes is the job of the updater of the ecosystem, which is not wired to this yet: today the bundle is carried to the node and applied
there by hand or by whatever runs a command on it.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .registry import ModelEntry, RegistryError, compute_sha256, load_registry, registry_lock
from .signing import SIGNATURE_SUFFIX, signature_path, verify_registry_bytes

OTA_ENV = "HYDRA_UMC_DETECTION_HEF_OTA"
BUNDLE_FORMAT = 1
MANIFEST = "bundle.json"
REGISTRY = "registry.json"
MAX_MEMBERS = 1000
DEFAULT_MAX_TOTAL_BYTES = 512 * 1024 * 1024
PREVIOUS_SUFFIX = ".prev"


class BundleError(RegistryError):
    """A bundle cannot be built or applied."""


def ota_enabled(flag: bool, environ: dict[str, str] | None = None) -> bool:
    """The switch of the over-the-air update: the flag of the command line or HYDRA_UMC_DETECTION_HEF_OTA set to 1, true or yes. Off otherwise."""
    env = os.environ if environ is None else environ
    return bool(flag) or env.get(OTA_ENV, "").strip().lower() in ("1", "true", "yes")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _member_ok(name: str) -> bool:
    if not name or name.startswith("/") or "\\" in name or "\x00" in name or len(name) > 300:
        return False
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    if name in (MANIFEST, REGISTRY, REGISTRY + SIGNATURE_SUFFIX):
        return True
    return parts[0] == "models" and len(parts) >= 2


def make_bundle(registry_path: Path, models_dir: Path, out_path: Path, names: list[str] | None = None) -> dict[str, Any]:
    """Pack the signed registry and the `.hef` files of the selected models (all of them when `names` is empty). Refuses a file that does not match its entry."""
    registry_path, models_dir, out_path = Path(registry_path), Path(models_dir), Path(out_path)
    sig = signature_path(registry_path)
    if not sig.is_file():
        raise BundleError(f"{sig.name} does not exist: sign the registry first (registry sign)")
    entries = load_registry(registry_path)
    chosen = [e for e in entries if not names or e.name in names]
    if names and {e.name for e in chosen} != set(names):
        raise BundleError(f"no entry named {sorted(set(names) - {e.name for e in chosen})[0]!r} in the registry")
    members: dict[str, bytes] = {REGISTRY: registry_path.read_bytes(), REGISTRY + SIGNATURE_SUFFIX: sig.read_bytes()}
    for entry in chosen:
        file = (models_dir / entry.hef_path).resolve()
        if not file.is_relative_to(models_dir.resolve()) or not file.is_file():
            raise BundleError(f"{entry.hef_path} is not a file inside {models_dir}")
        if compute_sha256(file) != entry.sha256:
            raise BundleError(f"{entry.hef_path} does not match the checksum of {entry.name} {entry.version}")
        members["models/" + entry.hef_path.replace("\\", "/")] = file.read_bytes()
    manifest = {"format": BUNDLE_FORMAT, "files": {name: _sha256(data) for name, data in sorted(members.items())}}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=out_path.parent, prefix=out_path.name + ".", suffix=".tmp")
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST, json.dumps(manifest, indent=2, sort_keys=True))
            for name, data in sorted(members.items()):
                archive.writestr(name, data)
        os.replace(temporary, out_path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return {"bundle": str(out_path), "models": [f"{e.name} {e.version}" for e in chosen], "files": len(members)}


def _read_bundle(path: Path, max_total_bytes: int) -> tuple[dict[str, bytes], dict[str, str]]:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise BundleError(f"{path} is not a readable bundle: {exc}") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise BundleError(f"a bundle holds at most {MAX_MEMBERS} members")
        if sum(i.file_size for i in infos) > max_total_bytes:
            raise BundleError(f"the bundle would unpack to more than {max_total_bytes} bytes")
        names = [i.filename for i in infos]
        if len(set(names)) != len(names):
            raise BundleError("the bundle repeats a member name")
        for name in names:
            if not _member_ok(name):
                raise BundleError(f"the bundle has a member that is not allowed: {name!r}")
        members = {}
        for info in infos:
            with archive.open(info) as handle:
                data = handle.read(info.file_size + 1)
            if len(data) != info.file_size:
                raise BundleError(f"{info.filename} is not the size the bundle announces")
            members[info.filename] = data
    if MANIFEST not in members:
        raise BundleError("the bundle has no bundle.json")
    try:
        manifest = json.loads(members.pop(MANIFEST).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BundleError(f"bundle.json is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != BUNDLE_FORMAT or not isinstance(manifest.get("files"), dict):
        raise BundleError(f"bundle.json must have format {BUNDLE_FORMAT} and a files object")
    listed = manifest["files"]
    if set(listed) != set(members):
        extra = sorted(set(members) ^ set(listed))[0]
        raise BundleError(f"the members of the bundle and the files of bundle.json differ at {extra!r}")
    for name, data in members.items():
        if listed[name] != _sha256(data):
            raise BundleError(f"{name} does not match the SHA-256 in bundle.json")
    for needed in (REGISTRY, REGISTRY + SIGNATURE_SUFFIX):
        if needed not in members:
            raise BundleError(f"the bundle has no {needed}")
    return members, listed


def _newest(entries: list[ModelEntry]) -> dict[tuple[str, str], tuple[int, int, int]]:
    best: dict[tuple[str, str], tuple[int, int, int]] = {}
    for entry in entries:
        key = (entry.name, entry.channel)
        if key not in best or entry.version_tuple > best[key]:
            best[key] = entry.version_tuple
    return best


def apply_bundle(bundle_path: Path, registry_path: Path, models_dir: Path, public_key_file: Path | None, *, enabled: bool,
                 allow_downgrade: bool = False, max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES) -> dict[str, Any]:
    """Check the bundle and put it in place. Raises BundleError before touching anything when a check fails."""
    if not enabled:
        raise BundleError(f"the over-the-air update is off: pass --enable-ota or set {OTA_ENV}=1")
    if public_key_file is None:
        raise BundleError("an update is only applied with the public key of the owner of the registry (--public-key): an unsigned bundle is refused")
    registry_path, models_dir = Path(registry_path), Path(models_dir)
    members, _ = _read_bundle(Path(bundle_path), max_total_bytes)
    with tempfile.TemporaryDirectory(prefix="hef-bundle-") as stage_name:
        stage = Path(stage_name)
        (stage / REGISTRY).write_bytes(members[REGISTRY])
        (stage / (REGISTRY + SIGNATURE_SUFFIX)).write_bytes(members[REGISTRY + SIGNATURE_SUFFIX])
        try:
            verify_registry_bytes(members[REGISTRY], stage / REGISTRY, public_key_file)
        except RegistryError as exc:
            raise BundleError("the signature of the registry in the bundle does not verify with this public key") from exc
        entries = load_registry(stage / REGISTRY)
    packed = {name[len("models/"):]: data for name, data in members.items() if name.startswith("models/")}
    by_path = {e.hef_path.replace("\\", "/"): e for e in entries}
    for rel, data in packed.items():
        entry = by_path.get(rel)
        if entry is None:
            raise BundleError(f"models/{rel} is in the bundle but no entry of the registry points at it")
        if _sha256(data) != entry.sha256:
            raise BundleError(f"models/{rel} does not have the SHA-256 that {entry.name} {entry.version} records")
    models_root = models_dir.resolve()
    targets = {}
    for rel in packed:
        target = (models_dir / rel).resolve()
        if not target.is_relative_to(models_root):
            raise BundleError(f"models/{rel} would be written outside {models_dir}")
        targets[rel] = target
    with registry_lock(registry_path):
        if registry_path.is_file() and not allow_downgrade:
            old = _newest(load_registry(registry_path))
            for key, version in _newest(entries).items():
                if key in old and version < old[key]:
                    raise BundleError(f"{key[0]} ({key[1]}) would go from {'.'.join(map(str, old[key]))} to {'.'.join(map(str, version))}: refused without --allow-downgrade")
            lost = sorted(k for k in old if k not in _newest(entries))
            if lost:
                raise BundleError(f"the new registry no longer lists {lost[0][0]} ({lost[0][1]}): refused without --allow-downgrade")
        installed = []
        for rel, target in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_name(target.name + ".part")
            part.write_bytes(packed[rel])
            os.replace(part, target)
            installed.append(rel)
        sig = signature_path(registry_path)
        if registry_path.is_file():
            shutil.copy2(registry_path, registry_path.with_name(registry_path.name + PREVIOUS_SUFFIX))
        if sig.is_file():
            shutil.copy2(sig, sig.with_name(sig.name + PREVIOUS_SUFFIX))
        for source, destination in ((REGISTRY, registry_path), (REGISTRY + SIGNATURE_SUFFIX, sig)):
            part = destination.with_name(destination.name + ".part")
            part.write_bytes(members[source])
            os.replace(part, destination)
    return {"models": sorted(f"{e.name} {e.version}" for e in entries), "files": sorted(installed), "entries": len(entries)}


def rollback_registry(registry_path: Path) -> list[str]:
    """Put the registry and signature that `apply_bundle` kept (`.prev`) back. The `.hef` files that were added stay where they are."""
    registry_path = Path(registry_path)
    sig = signature_path(registry_path)
    restored = []
    with registry_lock(registry_path):
        for destination in (registry_path, sig):
            previous = destination.with_name(destination.name + PREVIOUS_SUFFIX)
            if not previous.is_file():
                raise BundleError(f"{previous.name} does not exist: there is nothing to go back to")
        for destination in (registry_path, sig):
            previous = destination.with_name(destination.name + PREVIOUS_SUFFIX)
            part = destination.with_name(destination.name + ".part")
            shutil.copy2(previous, part)
            os.replace(part, destination)
            restored.append(destination.name)
    return restored


__all__ = ["BundleError", "apply_bundle", "make_bundle", "ota_enabled", "rollback_registry"]
