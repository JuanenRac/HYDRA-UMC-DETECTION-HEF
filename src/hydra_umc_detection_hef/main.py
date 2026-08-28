# =============================================================================
# HYDRA-UMC-DETECTION-HEF - entry point: src/hydra_umc_detection_hef/main.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
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
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .compatibility import safe_load
from .registry import RegistryError, duplicate_versions, find_latest, load_registry, verify_checksum

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


def _cmd_registry_validate(args: argparse.Namespace) -> int:
    try:
        entries = load_registry(Path(args.registry))
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
        entries = load_registry(Path(args.registry))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    entry = find_latest(entries, args.name, args.task)
    if entry is None:
        print(f"no model named {args.name!r}" + (f" with task {args.task!r}" if args.task else ""), file=sys.stderr)
        return 1

    print(f"{entry.name} {entry.version}  task={entry.task}  input_shape={entry.input_shape}")
    print(f"classes: {', '.join(entry.classes)}")
    print(f"hef_path: {entry.hef_path}")
    print(f"sha256: {entry.sha256}")
    return 0


def _cmd_registry_load(args: argparse.Namespace) -> int:
    try:
        entries = load_registry(Path(args.registry))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    entry = find_latest(entries, args.name, args.task)
    if entry is None:
        print(f"no model named {args.name!r}" + (f" with task {args.task!r}" if args.task else ""), file=sys.stderr)
        return 1

    result = safe_load(entry, Path(args.models_dir), args.target_arch)
    if result.is_ready:
        print(f"READY: {result.detail}")
        return 0

    print(f"{result.outcome.name}: {result.detail}", file=sys.stderr)
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hydra-umc-detection-hef")
    subparsers = parser.add_subparsers(dest="command")

    registry = subparsers.add_parser("registry", help="Inspect the compiled-model registry.")
    registry_sub = registry.add_subparsers(dest="registry_command", required=True)

    validate = registry_sub.add_parser("validate", help="Validate registry structure and (optionally) checksums.")
    validate.add_argument("--registry", required=True, help="Path to the registry JSON file")
    validate.add_argument("--models-dir", default=None, help="Directory to verify .hef checksums against, if present")
    validate.set_defaults(func=_cmd_registry_validate)

    latest = registry_sub.add_parser("latest", help="Print the latest registered version of a model.")
    latest.add_argument("--registry", required=True, help="Path to the registry JSON file")
    latest.add_argument("--name", required=True, help="Model name to look up")
    latest.add_argument("--task", default=None, help="Restrict to this task (e.g. detection, pose)")
    latest.set_defaults(func=_cmd_registry_latest)

    load = registry_sub.add_parser(
        "load", help="Real safe-load gate: architecture compatibility + checksum, combined."
    )
    load.add_argument("--registry", required=True, help="Path to the registry JSON file")
    load.add_argument("--models-dir", required=True, help="Directory containing the .hef files")
    load.add_argument("--name", required=True, help="Model name to look up")
    load.add_argument("--task", default=None, help="Restrict to this task (e.g. detection, pose)")
    load.add_argument(
        "--target-arch", required=True, help="Hailo architecture of this deployment (e.g. hailo8)"
    )
    load.set_defaults(func=_cmd_registry_load)

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
