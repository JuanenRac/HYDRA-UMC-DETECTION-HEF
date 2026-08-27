# =============================================================================
# HYDRA-UMC-DETECTION-HEF - entry point: src/hydra_umc_detection_hef/main.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
"""Entry point for HYDRA-UMC-DETECTION-HEF.

Skeleton stage: prints identity and exits 0. Real toolchain logic (ONNX
export, Hailo Dataflow Compiler quantization, HAR/HEF packaging, model
registry/versioning) lands when this project's turn comes up in
SONNET/5.PLAN_EJECUCION_32_PROYECTOS_NUEVOS.txt.
"""
from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version

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


def main() -> int:
    # Skeleton stage on purpose: this is the whole entry point today. It
    # confirms the package installs, imports and runs cleanly end to end
    # before the real ONNX/Dataflow-Compiler/HEF toolchain is built on
    # top of it.
    print(f"{PROJECT_NAME} v{get_version()}")
    print(ROLE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
