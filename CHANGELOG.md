# Changelog

All notable changes to HYDRA-UMC-DETECTION-HEF are documented in this file.

Versioning follows the ecosystem-wide `MAJOR.MINOR.PATCH` "odometer" scheme,
applied automatically on every real build by `bump_version.py` (invoked
from build.sh/build.bat right before the compile-check): `PATCH` goes up by
1 per build; once `PATCH` would exceed 9 it resets to 0 and `MINOR` goes up
by 1 instead (e.g. `0.0.9` -> `0.1.0`), the same carry cascading into
`MAJOR` if `MINOR` also exceeds 9. `MAJOR` is otherwise only ever bumped by
hand.

## [0.0.3]

- Build version synchronized with `hydra-umc.project.json` and the repository-native version source.

## [0.0.3] - Real v0: compiled-model registry (versioning + integrity)

- **`src/hydra_umc_detection_hef/registry.py`** - the versioning/data
  half of the intended model compilation flow, independent of the
  Hailo SDK and hardware the compiler half needs: `ModelEntry` (name,
  version, task, input shape, class list, `.hef` path, sha256),
  `load_registry()` (schema-validates a JSON array of entries),
  `duplicate_versions()` (flags a registry bug: the same name+version
  twice), `find_latest()` (highest semver-style version for a name,
  optionally filtered by task), and `verify_checksum()` (sha256 of a
  local file against the registry - returns `None`, not a failure, for
  a model the registry describes but that isn't present locally, since
  the `.hef` binaries themselves are expected to live in a separate
  object store, not this repo).
- **`main.py`** - new `registry validate --registry PATH
  [--models-dir DIR]` (structure + duplicate check always; checksum
  check only for files actually found under `--models-dir`) and
  `registry latest --registry PATH --name NAME [--task TASK]`
  subcommands.
- 21 tests (`test_registry.py`, `test_cli.py`).
- `pyproject.toml` - added a `dev` extra (`pytest`).
- `build.sh`/`build.bat` - fixed the version-bump step ordering (the
  manifest sync must run after, not before, the odometer bump), added
  the real test-suite step, and the no-autoclose-on-double-click
  behavior common to the rest of the ecosystem's scripts.
- `run.sh`/`run.bat` - now forward CLI arguments through to the entry
  point instead of ignoring them.
- Still out of scope: the ONNX export / Hailo Dataflow Compiler /
  HAR-HEF packaging toolchain that would actually produce the models
  this registry describes - all of that needs real Hailo hardware.

## [0.0.2]

Polish pass: copyright headers normalized across `main.py`, `__init__.py`,
`bump_version.py` and `build.sh`/`build.bat`/`run.sh`/`run.bat`; "why"
comments added; this `CHANGELOG.md` added; README (5 languages) expanded
with an Advanced Technical Information section, a detailed Build & Run
walkthrough with troubleshooting, a dateless "Current Status & Next
Steps" section replacing the previous dated roadmap, and a full Related
Projects section. No behavior change - the bump is this verification
build.

## [0.0.1]

Real build verification. `build.sh`/`build.bat` run end-to-end for real:
odometer bump, `.venv` creation, editable install, `python -m compileall`
clean across `src/`. `run.sh`/`run.bat` executed the entry point for real,
printing name + version + role. No business-logic change - the bump is the
recorded event.

## [0.0.0]

Initial skeleton: `pyproject.toml` (package metadata, no runtime
dependencies yet), `src/hydra_umc_detection_hef/` (`__init__.py` +
`main.py` entry point reading its version from installed package
metadata), `bump_version.py` (odometer-style version bump),
`build.sh`/`build.bat` (venv + editable install + compile-check) and
`run.sh`/`run.bat`.
