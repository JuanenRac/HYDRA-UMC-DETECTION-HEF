# =============================================================================
# HYDRA-UMC-DETECTION-HEF - package init: src/hydra_umc_detection_hef/__init__.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
"""HYDRA-UMC-DETECTION-HEF - library and toolchain of hardware-accelerated
YOLO detection models compiled to Hailo Executable Format (HEF), consumed by
HYDRA-UMC-VISION-NODE (the integration parent of this project).

No `hardware/`/`firmware/` folder here: this project ships models, not a
physical device. No `os/`/`models/` folder either, even though this is
where `.hef` files are *compiled* - the *served, running* copy loaded onto
the Hailo-8 NPU lives only in the integration parent,
HYDRA-UMC-VISION-NODE, which owns the device handle; this project's own
`build/` is where compiled output lands before being published there.

The installed package version is the single source of truth in
pyproject.toml (read at runtime via importlib.metadata), never duplicated
here, so bump_version.py only ever has one place to edit.
"""
