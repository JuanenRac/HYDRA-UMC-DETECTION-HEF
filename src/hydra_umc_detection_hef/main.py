# =============================================================================
# HYDRA-UMC-DETECTION-HEF - entry point: src/hydra_umc_detection_hef/main.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Entry point for HYDRA-UMC-DETECTION-HEF.

Real v0: the model registry/versioning half of the toolchain
(registry.py) - parsing, validating, and checksumming a JSON registry of
compiled .hef models, independent of the Hailo SDK and hardware needed
to actually produce one - plus a real, combined safe-load gate
(compatibility.py) that checks Hailo-architecture compatibility and
checksum integrity together before ever reporting a model ready to
deploy. ONNX export and Hailo Dataflow Compiler quantization still need
real hardware and land later.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .access import bind_problem, load_token
from .accuracy import AccuracyError, map50, record_accuracy
from .api import RegistryServer
from .health_route import health_open_requested
from .server_identity import identity_key_from
from .bundle import apply_bundle, make_bundle, ota_enabled, rollback_registry
from .compatibility import safe_load
from .loaded import LoadedModels
from .registry import (
    CHANNELS,
    DEFAULT_CHANNEL,
    KNOWN_HAILO_ARCHS,
    RegistryError,
    add_entry,
    classes_sha256,
    duplicate_versions,
    find_latest,
    load_registry,
    load_registry_or_empty,
    registry_lock,
    validate_io_contract,
    verify_checksum,
    write_registry,
)
from .signing import SIGNING_KEY_ENV, generate_keypair, resolve_public_key, sign_registry

PROJECT_NAME = "HYDRA-UMC-DETECTION-HEF"
DIST_NAME = "hydra-umc-detection-hef"
ROLE = (
    "Library of hardware-accelerated YOLO detection models compiled to "
    "Hailo Executable Format (HEF) for industrial inspection."
)


def get_version() -> str:
    """Read the running version from installed package metadata, which is
    sourced from pyproject.toml - the single place bump_version.py edits.

    Why not a hardcoded __version__ string here instead? That would give
    this project two places to keep in sync on every build. Reading it
    back from installed metadata means this function can never drift out
    of sync with the number bump_version.py actually wrote."""
    try:
        return version(DIST_NAME)
    except PackageNotFoundError:
        return "0.0.0-dev (package not installed - run build.sh/build.bat first)"


REQUIRE_IO_ENV = "HYDRA_UMC_DETECTION_HEF_REQUIRE_IO_CONTRACT"
MAX_JSON_FILE_BYTES = 64 * 1024 * 1024


def _require_io(args: argparse.Namespace) -> bool:
    """The io_contract is required when the flag says so or HYDRA_UMC_DETECTION_HEF_REQUIRE_IO_CONTRACT is 1, true or yes; off otherwise."""
    return bool(getattr(args, "require_io_contract", False)) or os.environ.get(REQUIRE_IO_ENV, "").strip().lower() in ("1", "true", "yes")


def _ratio(args: argparse.Namespace) -> float | None:
    """The minimum accuracy ratio asked for (0 to 1), None when not asked. Raises RegistryError for a value that is not a ratio."""
    value = getattr(args, "min_accuracy_ratio", None)
    if value is None:
        return None
    if not 0.0 < value <= 1.0:
        raise RegistryError("--min-accuracy-ratio must be above 0 and at most 1")
    return float(value)


def _read_json(path: str, what: str) -> object:
    file = Path(path)
    try:
        if file.stat().st_size > MAX_JSON_FILE_BYTES:
            raise RegistryError(f"{what} {path} is larger than {MAX_JSON_FILE_BYTES} bytes")
        return json.loads(file.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except OSError as exc:
        raise RegistryError(f"could not read {what} {path}: {exc.strerror}") from exc
    except ValueError as exc:
        if isinstance(exc, RegistryError):
            raise
        raise RegistryError(f"{what} {path} is not valid JSON: {exc}") from exc


def _reject_constant(name: str) -> float:
    raise ValueError(f"{name} is not a valid JSON number")


def _cmd_registry_validate(args: argparse.Namespace) -> int:
    try:
        entries = load_registry(Path(args.registry), resolve_public_key(getattr(args, "public_key", None)), _require_io(args))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'} in {args.registry}")

    dupes = duplicate_versions(entries)
    if dupes:
        for name, ver in dupes:
            print(f"error: duplicate entry for {name} {ver}", file=sys.stderr)
        return 1

    if args.models_dir is not None:
        models_dir = Path(args.models_dir)
        mismatches = 0
        for entry in entries:
            result = verify_checksum(entry, models_dir)
            if result is None:
                print(f"  {entry.name} {entry.version}: {entry.hef_path} not present locally, skipped")
            elif result:
                print(f"  {entry.name} {entry.version}: checksum OK")
            else:
                print(f"  {entry.name} {entry.version}: CHECKSUM MISMATCH", file=sys.stderr)
                mismatches += 1
        if mismatches:
            return 1

    print("registry OK")
    return 0


def _cmd_registry_latest(args: argparse.Namespace) -> int:
    try:
        entries = load_registry(Path(args.registry), resolve_public_key(getattr(args, "public_key", None)), _require_io(args))
        entry = find_latest(entries, args.name, args.task, None, getattr(args, "channel", None))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if entry is None:
        print(f"no model named {args.name!r}" + (f" with task {args.task!r}" if args.task else ""), file=sys.stderr)
        return 1

    print(f"{entry.name} {entry.version}  task={entry.task}  channel={entry.channel}  input_shape={entry.input_shape}")
    print(f"classes: {', '.join(entry.classes)}")
    print(f"hef_path: {entry.hef_path}")
    print(f"sha256: {entry.sha256}")
    return 0


def _cmd_registry_load(args: argparse.Namespace) -> int:
    try:
        entries = load_registry(Path(args.registry), resolve_public_key(getattr(args, "public_key", None)), _require_io(args))
        ratio = _ratio(args)
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        entry = find_latest(entries, args.name, args.task, getattr(args, "version", None), getattr(args, "channel", None))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if entry is None:
        print(f"no model named {args.name!r}" + (f" with task {args.task!r}" if args.task else ""), file=sys.stderr)
        return 1

    try:
        result = safe_load(entry, Path(args.models_dir), args.target_arch, require_io_contract=_require_io(args), min_accuracy_ratio=ratio)
    except RegistryError as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    if result.is_ready:
        print(f"READY: {result.detail}")
        return 0

    print(f"{result.outcome.name}: {result.detail}", file=sys.stderr)
    return 1


def _sign_after_write(args: argparse.Namespace, registry_path: Path) -> None:
    """Sign the registry again right after a command rewrote it, when the private key was given (--sign-with or the environment)."""
    key = getattr(args, "sign_with", None) or os.environ.get(SIGNING_KEY_ENV) or None
    if key:
        target = sign_registry(registry_path, Path(key))
        print(f"signed {registry_path} -> {target}")


def _cmd_registry_add(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry)
    try:
        with registry_lock(registry_path):
            return _registry_add_locked(args, registry_path)
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _registry_add_locked(args: argparse.Namespace, registry_path: Path) -> int:
    try:
        entries = load_registry_or_empty(registry_path)
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        input_shape = tuple(int(d) for d in args.input_shape.split(","))
    except ValueError:
        print(f"error: --input-shape must be comma-separated integers, got {args.input_shape!r}", file=sys.stderr)
        return 1
    classes = tuple(c for c in args.classes.split(",") if c)
    expected_hash = getattr(args, "classes_sha256", None)
    if expected_hash and classes_sha256(classes).lower() != expected_hash.strip().lower():
        print(
            "error: --classes does not match --classes-sha256 (the dataset's class list); "
            "the class ids are positions in that list, so the labels or their order differ",
            file=sys.stderr,
        )
        return 1

    contract = None
    if getattr(args, "io_contract", None):
        try:
            contract = _read_json(args.io_contract, "the io_contract file")
            problems = validate_io_contract(contract)
        except RegistryError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if problems:
            print("error: the io_contract file is not valid:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
    elif not getattr(args, "no_io_contract", False):
        print("error: give --io-contract FILE (how the input is prepared and how the output is read); --no-io-contract adds the model without one, "
              "and a node that requires the io_contract will refuse it", file=sys.stderr)
        return 1

    try:
        new_entry = add_entry(
            entries,
            models_dir=Path(args.models_dir),
            name=args.name,
            version=args.version,
            task=args.task,
            input_shape=input_shape,
            classes=classes,
            hef_path=args.hef_path,
            hailo_arch=args.hailo_arch,
            io_contract=contract,  # type: ignore[arg-type]
            channel=getattr(args, "channel", None) or DEFAULT_CHANNEL,
        )
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    entries.append(new_entry)
    write_registry(registry_path, entries)
    _sign_after_write(args, registry_path)
    print(f"added {new_entry.name} {new_entry.version} to {registry_path} (sha256={new_entry.sha256})")
    return 0


def _cmd_registry_keygen(args: argparse.Namespace) -> int:
    try:
        generate_keypair(Path(args.private_key_out), Path(args.public_key_out))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote the private key to {args.private_key_out} (keep it off the nodes) and the public key to {args.public_key_out}")
    return 0


def _cmd_registry_sign(args: argparse.Namespace) -> int:
    try:
        target = sign_registry(Path(args.registry), Path(args.private_key))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"signed {args.registry} -> {target}")
    return 0


def _cmd_registry_verify(args: argparse.Namespace) -> int:
    key = resolve_public_key(args.public_key)
    if key is None:
        print("error: give --public-key (or set HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE)", file=sys.stderr)
        return 1
    try:
        entries = load_registry(Path(args.registry), key)
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"signature OK ({len(entries)} entr{'y' if len(entries) == 1 else 'ies'})")
    return 0


def _cmd_registry_record_accuracy(args: argparse.Namespace) -> int:
    """Measure the mAP@0.5 of the detections of the quantized model against the truth and write it in the accuracy block of the entry."""
    registry_path = Path(args.registry)
    try:
        with registry_lock(registry_path):
            entries = load_registry(registry_path)
            entry = find_latest(entries, args.name, None, args.version, getattr(args, "channel", None))
            if entry is None:
                print(f"error: no model named {args.name!r} {args.version}", file=sys.stderr)
                return 1
            truth = _read_json(args.truth, "the truth file")
            quantized = map50(_read_json(args.detections, "the detections file"), truth)
            if (args.reference_map is None) == (args.reference_detections is None):
                print("error: give exactly one of --reference-map and --reference-detections", file=sys.stderr)
                return 1
            reference = args.reference_map if args.reference_map is not None else map50(_read_json(args.reference_detections, "the reference detections file"), truth)
            updated = record_accuracy(entry, quantized, reference)
            write_registry(registry_path, [updated if e is entry else e for e in entries])
            _sign_after_write(args, registry_path)
    except (RegistryError, AccuracyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    block = updated.accuracy or {}
    print(f"{entry.name} {entry.version}: quantized mAP@0.5 {block['quantized']:.4f}, reference {block['reference']:.4f}, "
          f"ratio {block['quantized'] / block['reference']:.3f} on {block['samples']} image(s); sign the registry again")
    return 0


def _cmd_registry_make_bundle(args: argparse.Namespace) -> int:
    try:
        summary = make_bundle(Path(args.registry), Path(args.models_dir), Path(args.out), list(args.name))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {summary['bundle']} ({summary['files']} files; models: {', '.join(summary['models'])})")
    return 0


def _cmd_registry_apply_bundle(args: argparse.Namespace) -> int:
    try:
        summary = apply_bundle(
            Path(args.bundle), Path(args.registry), Path(args.models_dir), resolve_public_key(args.public_key),
            enabled=ota_enabled(args.enable_ota), allow_downgrade=args.allow_downgrade,
        )
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"applied the bundle: {summary['entries']} entries, {len(summary['files'])} model file(s) installed; the previous registry is kept as .prev")
    return 0


def _cmd_registry_rollback(args: argparse.Namespace) -> int:
    try:
        restored = rollback_registry(Path(args.registry))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"restored {', '.join(restored)} from the previous copies")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    models_dir = Path(args.models_dir) if args.models_dir else None
    registry_path = Path(args.registry)
    if registry_path.is_dir():
        print(f"[detection-hef] warning: {registry_path} is a directory, not a registry file (a bind mount of a missing file does this)", file=sys.stderr)
    elif not registry_path.is_file():
        print(f"[detection-hef] warning: registry {registry_path} does not exist - every query will answer 502", file=sys.stderr)
    try:
        token = load_token(args.token_file)
        identity_key = identity_key_from(args.identity_key_file)
        ratio = _ratio(args)
    except (ValueError, RegistryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    reports = bool(getattr(args, "accept_loaded_reports", False))
    problem = bind_problem(args.addr, token) if reports and identity_key is None else None
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    server = RegistryServer((args.addr, args.port), Path(args.registry), models_dir, show_paths=args.stats_full_paths,
                            public_key_file=resolve_public_key(args.public_key), require_io_contract=_require_io(args), min_accuracy_ratio=ratio,
                            loaded=LoadedModels() if reports else None, token=token)
    server.identity_key = identity_key
    print(f"[detection-hef] HTTP API listening on {args.addr}:{args.port} (registry={args.registry})")
    print("[detection-hef] GET /registry, GET /registry/latest, GET /registry/load, GET /stats" + ("; tokens of HYDRA-UMC-SERVER accepted, nothing is open" if identity_key is not None else ""))
    if reports:
        print("[detection-hef] LOADED-MODEL REPORTS ON: POST /models/loaded, GET /models/loaded" + (" (bearer token required)" if token else ""))
    try:
        server.health_open = health_open_requested(args.health_open)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("[detection-hef] shutting down")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hydra-umc-detection-hef")
    subparsers = parser.add_subparsers(dest="command")

    registry = subparsers.add_parser("registry", help="Inspect the compiled-model registry.")
    registry_sub = registry.add_subparsers(dest="registry_command", required=True)

    validate = registry_sub.add_parser("validate", help="Validate registry structure and (optionally) checksums.")
    validate.add_argument("--registry", required=True, help="Path to the registry JSON file")
    validate.add_argument("--models-dir", default=None, help="Directory to verify .hef checksums against, if present")
    validate.add_argument("--public-key", default=None, help="Ed25519 public key file; when set (or in HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE) the registry must carry a valid <registry>.sig")
    validate.add_argument("--require-io-contract", action="store_true", dest="require_io_contract", help="Treat an entry without an io_contract as an error (off by default; also HYDRA_UMC_DETECTION_HEF_REQUIRE_IO_CONTRACT=1)")
    validate.set_defaults(func=_cmd_registry_validate)

    latest = registry_sub.add_parser("latest", help="Print the latest registered version of a model.")
    latest.add_argument("--registry", required=True, help="Path to the registry JSON file")
    latest.add_argument("--name", required=True, help="Model name to look up")
    latest.add_argument("--task", default=None, help="Restrict to this task (e.g. detection, pose)")
    latest.add_argument("--public-key", default=None, help="Ed25519 public key file; when set (or in HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE) the registry must carry a valid <registry>.sig")
    latest.add_argument("--require-io-contract", action="store_true", dest="require_io_contract", help="Treat an entry without an io_contract as an error (off by default; also HYDRA_UMC_DETECTION_HEF_REQUIRE_IO_CONTRACT=1)")
    latest.add_argument("--channel", choices=CHANNELS, default=None, help="Channel to look in (default: stable)")
    latest.set_defaults(func=_cmd_registry_latest)

    load = registry_sub.add_parser(
        "load", help="Real safe-load gate: architecture compatibility + checksum, combined."
    )
    load.add_argument("--registry", required=True, help="Path to the registry JSON file")
    load.add_argument("--models-dir", required=True, help="Directory containing the .hef files")
    load.add_argument("--name", required=True, help="Model name to look up")
    load.add_argument("--task", default=None, help="Restrict to this task (e.g. detection, pose)")
    load.add_argument("--version", default=None, help="Load exactly this version instead of the latest (pin or roll back)")
    load.add_argument(
        "--target-arch", required=True, help="Hailo architecture of this deployment (e.g. hailo8)"
    )
    load.add_argument("--public-key", default=None, help="Ed25519 public key file; when set (or in HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE) the registry must carry a valid <registry>.sig")
    load.add_argument("--require-io-contract", action="store_true", dest="require_io_contract", help="Treat an entry without an io_contract as an error (off by default; also HYDRA_UMC_DETECTION_HEF_REQUIRE_IO_CONTRACT=1)")
    load.add_argument("--channel", choices=CHANNELS, default=None, help="Channel to look in (default: stable; a pinned --version ignores it unless given)")
    load.add_argument("--min-accuracy-ratio", type=float, default=None, dest="min_accuracy_ratio", help="Refuse a model whose quantized mAP@0.5 is below this share (above 0, at most 1) of its reference, or that has no measurement (off by default)")
    load.set_defaults(func=_cmd_registry_load)

    add = registry_sub.add_parser(
        "add",
        help="Hash a real local .hef and append a validated entry - no more hand-editing the registry JSON.",
    )
    add.add_argument("--registry", required=True, help="Path to the registry JSON file (created if it doesn't exist yet)")
    add.add_argument("--models-dir", required=True, help="Directory containing the real .hef file to register")
    add.add_argument("--hef-path", required=True, help="Path to the .hef file, relative to --models-dir")
    add.add_argument("--name", required=True, help="Model name")
    add.add_argument("--version", required=True, help="Model version, X.Y.Z")
    add.add_argument("--task", required=True, help="Task this model performs (e.g. detection, pose)")
    add.add_argument("--input-shape", required=True, help="Height,width,channels (HWC) with 1, 3 or 4 channels, e.g. 640,640,3")
    add.add_argument("--classes", required=True, help="Comma-separated class labels, e.g. defect,ok")
    add.add_argument(
        "--classes-sha256", default=None,
        help="Optional sha256 of the dataset's class list (classes_sha256 of its manifest); when given, --classes must hash to it",
    )
    add.add_argument(
        "--hailo-arch", required=True, help=f"Target Hailo architecture ({', '.join(sorted(KNOWN_HAILO_ARCHS))})"
    )
    add.add_argument("--io-contract", default=None, metavar="FILE", help="JSON file with the io_contract of the model (how the input is prepared and how the output is read); required unless --no-io-contract")
    add.add_argument("--no-io-contract", action="store_true", dest="no_io_contract", help="Add the model without an io_contract (a node that requires one will refuse it)")
    add.add_argument("--channel", choices=CHANNELS, default=DEFAULT_CHANNEL, help="Channel the model is published on (default: stable)")
    add.add_argument("--sign-with", default=None, metavar="PRIVATE_KEY", dest="sign_with", help="Ed25519 private key file: sign the registry again as soon as it is written (or HYDRA_UMC_DETECTION_HEF_SIGNING_KEY_FILE); keep that key on the build machine, never on a node")
    add.set_defaults(func=_cmd_registry_add)

    accuracy = registry_sub.add_parser("record-accuracy", help="Measure the mAP@0.5 of the quantized model from its detections and the true boxes, and record it in the entry.")
    accuracy.add_argument("--registry", required=True, help="Path to the registry JSON file")
    accuracy.add_argument("--name", required=True, help="Model name")
    accuracy.add_argument("--version", required=True, help="Model version, X.Y.Z (any channel)")
    accuracy.add_argument("--channel", choices=CHANNELS, default=None, help="Channel of the entry (default: the one the version is on)")
    accuracy.add_argument("--detections", required=True, help="JSON file with the detections of the compiled model on the validation images")
    accuracy.add_argument("--truth", required=True, help="JSON file with the true boxes of the same images")
    accuracy.add_argument("--reference-map", type=float, default=None, dest="reference_map", help="mAP@0.5 of the model before quantization on the same images")
    accuracy.add_argument("--reference-detections", default=None, dest="reference_detections", help="Detections of the model before quantization on the same images (instead of --reference-map)")
    accuracy.add_argument("--sign-with", default=None, metavar="PRIVATE_KEY", dest="sign_with", help="Ed25519 private key file: sign the registry again as soon as it is written (or HYDRA_UMC_DETECTION_HEF_SIGNING_KEY_FILE); keep that key on the build machine, never on a node")
    accuracy.set_defaults(func=_cmd_registry_record_accuracy)

    pack = registry_sub.add_parser("make-bundle", help="Pack the signed registry and the .hef files into one bundle for the nodes.")
    pack.add_argument("--registry", required=True, help="Path to the registry JSON file (its .sig must exist)")
    pack.add_argument("--models-dir", required=True, help="Directory containing the .hef files")
    pack.add_argument("--out", required=True, help="Bundle file to write")
    pack.add_argument("--name", action="append", default=[], help="Pack only the files of this model (repeat for several); default: all")
    pack.set_defaults(func=_cmd_registry_make_bundle)

    apply = registry_sub.add_parser("apply-bundle", help="Check a signed bundle and put it in place (off unless --enable-ota or HYDRA_UMC_DETECTION_HEF_OTA=1).")
    apply.add_argument("--bundle", required=True, help="Bundle file")
    apply.add_argument("--registry", required=True, help="Path to the registry JSON file of this node")
    apply.add_argument("--models-dir", required=True, help="Directory of the .hef files of this node")
    apply.add_argument("--public-key", default=None, help="Ed25519 public key file of the owner of the registry (required)")
    apply.add_argument("--enable-ota", action="store_true", dest="enable_ota", help="Turn the update on for this command")
    apply.add_argument("--allow-downgrade", action="store_true", dest="allow_downgrade", help="Accept a bundle that goes to older versions or drops a model")
    apply.set_defaults(func=_cmd_registry_apply_bundle)

    rollback = registry_sub.add_parser("rollback", help="Put the registry and signature that apply-bundle kept back.")
    rollback.add_argument("--registry", required=True, help="Path to the registry JSON file")
    rollback.set_defaults(func=_cmd_registry_rollback)

    keygen = registry_sub.add_parser("keygen", help="Create an Ed25519 key pair to sign registries (needs 'cryptography').")
    keygen.add_argument("--private-key-out", required=True, help="Where to write the private key (refuses to overwrite)")
    keygen.add_argument("--public-key-out", required=True, help="Where to write the public key (refuses to overwrite)")
    keygen.set_defaults(func=_cmd_registry_keygen)

    sign = registry_sub.add_parser("sign", help="Write <registry>.sig, the Ed25519 signature of the registry file.")
    sign.add_argument("--registry", required=True, help="Path to the registry JSON file")
    sign.add_argument("--private-key", required=True, help="Private key file (32 bytes, raw or 64 hex digits)")
    sign.set_defaults(func=_cmd_registry_sign)

    verify = registry_sub.add_parser("verify", help="Check <registry>.sig against the public key.")
    verify.add_argument("--registry", required=True, help="Path to the registry JSON file")
    verify.add_argument("--public-key", default=None, help="Ed25519 public key file; when set (or in HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE) the registry must carry a valid <registry>.sig")
    verify.set_defaults(func=_cmd_registry_verify)

    serve = subparsers.add_parser(
        "serve",
        help="Run the registry validate/latest/load queries as a JSON/HTTP API "
             "(GET /registry, GET /registry/latest, GET /registry/load) - registry "
             "and models directory are configured once at startup, not per-request.",
    )
    serve.add_argument("--registry", required=True, help="Path to the registry JSON file")
    serve.add_argument("--models-dir", default=None, help="Directory containing the .hef files, needed for GET /registry/load")
    serve.add_argument("--addr", default="127.0.0.1", help="address to bind the HTTP API to")
    serve.add_argument("--health-open", action="store_true", help="answer GET /health (open to loopback, to other callers only with the bearer token); closed by default, or set HYDRA_UMC_DETECTION_HEF_HEALTH_OPEN=1")
    serve.add_argument("--port", type=int, default=8093, help="port for the HTTP API")
    serve.add_argument("--stats-full-paths", action="store_true", help="let GET /stats show absolute paths instead of file names")
    serve.add_argument("--public-key", default=None, help="Ed25519 public key file; when set (or in HYDRA_UMC_DETECTION_HEF_PUBLIC_KEY_FILE) the registry must carry a valid <registry>.sig")
    serve.add_argument("--require-io-contract", action="store_true", dest="require_io_contract", help="Treat an entry without an io_contract as an error and refuse to load one (off by default)")
    serve.add_argument("--min-accuracy-ratio", type=float, default=None, dest="min_accuracy_ratio", help="Refuse to load a model whose quantized mAP@0.5 is below this share (above 0, at most 1) of its reference, or that has no measurement (off by default)")
    serve.add_argument("--accept-loaded-reports", action="store_true", dest="accept_loaded_reports", help="Turn on POST and GET /models/loaded (off by default): the nodes say which model they loaded and get a verdict against the registry")
    serve.add_argument("--identity-key-file", default=None, help="file with the signing key of HYDRA-UMC-SERVER (its JWT_SECRET): a valid token of the SERVER is then accepted, every route (GET /health and GET /stats too) demands an identity and a viewer may read but not change (off by default; or set HYDRA_UMC_DETECTION_HEF_IDENTITY_KEY_FILE)")
    serve.add_argument("--token-file", default=None, help="File with the bearer token the /models/loaded routes need (or HYDRA_UMC_DETECTION_HEF_TOKEN); required to bind an address that is not loopback with the reports on")
    serve.set_defaults(func=_cmd_serve)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        # Skeleton stage identity print, still the default bare invocation:
        # confirms the package installs, imports and runs cleanly end to
        # end before/alongside the real ONNX/Dataflow-Compiler toolchain.
        print(f"{PROJECT_NAME} v{get_version()}")
        print(ROLE)
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
