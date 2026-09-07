# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/compatibility.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
"""Real, safe "load" gate for a compiled .hef model: combines the
registry's existing checksum verification with a real Hailo-architecture
compatibility check, and never reports a model as ready to load unless
every real check passes.

`registry.py`'s `load_registry`/`verify_checksum` already do real,
independent checks - this module is deliberately not a rewrite of
either, it is the missing piece that COMBINES them into one safe
decision, in the order that makes the rejection reason meaningful: the
architecture check is pure metadata (no I/O, checked first, cheap), the
checksum check needs to read the real file (checked second, only once
the model is even the right chip target). Neither the Hailo runtime nor
real hardware is needed to prove this logic correct - both checks work
against plain data (a target architecture string, a file's real bytes).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path

from .registry import ModelEntry, verify_checksum


class LoadOutcome(enum.Enum):
    READY = "ready"
    REJECTED_ARCH_MISMATCH = "rejected_arch_mismatch"
    REJECTED_MISSING_FILE = "rejected_missing_file"
    REJECTED_CHECKSUM_MISMATCH = "rejected_checksum_mismatch"


@dataclass(frozen=True)
class LoadResult:
    outcome: LoadOutcome
    entry: ModelEntry
    detail: str

    @property
    def is_ready(self) -> bool:
        return self.outcome is LoadOutcome.READY


def check_arch_compatibility(entry: ModelEntry, target_arch: str) -> bool:
    """True only if `entry` was compiled for exactly `target_arch`.

    Deliberately exact-match, not a compatibility matrix (e.g. treating
    hailo15h as able to run a hailo8 .hef) - the Hailo Dataflow Compiler
    bakes the target chip into the .hef at compile time, and a real
    cross-architecture "compatibility" claim would need real hardware
    validation this environment cannot do. Exact match is the only
    claim honestly verifiable from registry metadata alone.
    """
    return entry.hailo_arch == target_arch


def safe_load(entry: ModelEntry, models_dir: Path, target_arch: str) -> LoadResult:
    """The real, combined safe-load decision for one registry entry.

    Checks architecture compatibility FIRST (pure metadata, no I/O) -
    a model compiled for the wrong chip is rejected before this function
    ever touches the filesystem, and the rejection reason names the
    most fundamental failing gate rather than a misleading "file missing"
    for a model that was never going to run on this hardware anyway.
    Only once the architecture matches does it verify the checksum
    against the real local file.
    """
    if not check_arch_compatibility(entry, target_arch):
        return LoadResult(
            outcome=LoadOutcome.REJECTED_ARCH_MISMATCH,
            entry=entry,
            detail=f"model compiled for {entry.hailo_arch!r}, this deployment targets {target_arch!r}",
        )

    checksum_ok = verify_checksum(entry, models_dir)
    if checksum_ok is None:
        return LoadResult(
            outcome=LoadOutcome.REJECTED_MISSING_FILE,
            entry=entry,
            detail=f"{entry.hef_path} not found under {models_dir}",
        )
    if not checksum_ok:
        return LoadResult(
            outcome=LoadOutcome.REJECTED_CHECKSUM_MISMATCH,
            entry=entry,
            detail=f"{entry.hef_path} does not match the registry's recorded sha256 - possibly corrupt or tampered",
        )

    return LoadResult(
        outcome=LoadOutcome.READY,
        entry=entry,
        detail=f"{entry.name} {entry.version} ({entry.hailo_arch}) verified and ready",
    )
