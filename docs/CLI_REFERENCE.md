# HYDRA-UMC-DETECTION-HEF — CLI Reference

`hydra-umc-detection-hef` is a Python console script
(`src/hydra_umc_detection_hef/main.py`, installed as an entry point via
`pyproject.toml`). Real v0 is the model registry/versioning half of the
toolchain: parsing, validating, and checksumming a JSON registry of
compiled `.hef` models, plus a real, combined safe-load gate that checks
Hailo-architecture compatibility and checksum integrity together before
ever reporting a model ready to deploy — reachable both as one-shot
`registry` CLI subcommands and, via `serve`, as a long-running JSON/HTTP
API (`api.py`) exposing the same checks over `GET /registry`,
`GET /registry/latest`, `GET /registry/load`, and `GET /stats`. ONNX
export and Hailo Dataflow Compiler quantization need real Hailo
hardware/SDK and are not built yet. Every example below was captured
from a real run of the installed CLI, against a real registry JSON file
and real `.hef`-shaped fixture files (with real sha256 digests) — not
written from memory.

## Usage

```
$ hydra-umc-detection-hef -h
usage: hydra-umc-detection-hef [-h] {registry,serve} ...

positional arguments:
  {registry,serve}
    registry        Inspect the compiled-model registry.
    serve           Run the registry validate/latest/load queries as a
                    JSON/HTTP API (GET /registry, GET /registry/latest, GET
                    /registry/load) - registry and models directory are
                    configured once at startup, not per-request.

options:
  -h, --help        show this help message and exit
```

Bare invocation (no subcommand) prints identity/version/role and exits `0`:

```
$ hydra-umc-detection-hef
HYDRA-UMC-DETECTION-HEF v0.0.6
Library of hardware-accelerated YOLO detection models compiled to Hailo Executable Format (HEF) for industrial inspection.
```

```
$ hydra-umc-detection-hef registry -h
usage: hydra-umc-detection-hef registry [-h] {validate,latest,load} ...

positional arguments:
  {validate,latest,load}
    validate            Validate registry structure and (optionally)
                        checksums.
    latest              Print the latest registered version of a model.
    load                Real safe-load gate: architecture compatibility +
                        checksum, combined.

options:
  -h, --help            show this help message and exit
```

### The demo registry used below

A real registry JSON file with three real entries, and two real `.hef`
placeholder files with real sha256 digests computed from their actual
bytes:

```json
[
  {
    "name": "pcb-defect", "version": "0.1.0", "task": "detection",
    "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component"],
    "hef_path": "pcb-defect-0.1.0.hef",
    "sha256": "dce3f284863b41be924a512ae172fdaf91737c45158be164a05e1f7a299fbf9d",
    "hailo_arch": "hailo8"
  },
  {
    "name": "pcb-defect", "version": "0.2.0", "task": "pose",
    "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component", "tombstone"],
    "hef_path": "pcb-defect-0.2.0.hef",
    "sha256": "bbbb...bbbb",
    "hailo_arch": "hailo15h"
  },
  {
    "name": "tamper-demo", "version": "1.0.0", "task": "detection",
    "input_shape": [320, 320, 3], "classes": ["object"],
    "hef_path": "tamper-demo-1.0.0.hef",
    "sha256": "ec5fed2c7cfdbdb9f39689abbd271b0f7275af4c86b63082b8ac1408ae263838",
    "hailo_arch": "hailo8"
  }
]
```

`models/pcb-defect-0.1.0.hef` really exists on disk and its real sha256
matches the registry. `pcb-defect-0.2.0.hef` is intentionally absent
(the registry can describe models that live in a separate object store).
`tamper-demo-1.0.0.hef` exists but was overwritten with different bytes
*after* its checksum was recorded — a real tampered/corrupt-file case.

## Commands

### `registry validate --registry PATH [--models-dir PATH]`

```
$ hydra-umc-detection-hef registry validate -h
usage: hydra-umc-detection-hef registry validate [-h] --registry REGISTRY
                                                 [--models-dir MODELS_DIR]

options:
  -h, --help            show this help message and exit
  --registry REGISTRY   Path to the registry JSON file
  --models-dir MODELS_DIR
                        Directory to verify .hef checksums against, if present
```

Structure-only validation (no `--models-dir`) — checks required fields,
version format, known Hailo architecture, hex sha256 shape, and
duplicate `(name, version)` pairs:

```
$ hydra-umc-detection-hef registry validate --registry registry.json
3 entries in registry.json
registry OK
```

With `--models-dir`, each entry present locally is also checksummed for
real. `tamper-demo` really was overwritten after its checksum was
recorded, so this is a real, caught mismatch — and the whole command
exits `1`:

```
$ hydra-umc-detection-hef registry validate --registry registry.json --models-dir models
3 entries in registry.json
  pcb-defect 0.1.0: checksum OK
  pcb-defect 0.2.0: pcb-defect-0.2.0.hef not present locally, skipped
  tamper-demo 1.0.0: CHECKSUM MISMATCH
$ echo $?
1
```

A real duplicate `(name, version)` entry (two `pcb-defect 0.1.0` rows in
the same registry) is caught before any checksum work:

```
$ hydra-umc-detection-hef registry validate --registry registry-dup.json
2 entries in registry-dup.json
error: duplicate entry for pcb-defect 0.1.0
$ echo $?
1
```

A real missing registry file:

```
$ hydra-umc-detection-hef registry validate --registry does-not-exist.json
error: could not read registry does-not-exist.json: [Errno 2] No such file or directory: 'does-not-exist.json'
$ echo $?
1
```

### `registry latest --registry PATH --name NAME [--task TASK]`

```
$ hydra-umc-detection-hef registry latest -h
usage: hydra-umc-detection-hef registry latest [-h] --registry REGISTRY
                                               --name NAME [--task TASK]

options:
  -h, --help           show this help message and exit
  --registry REGISTRY  Path to the registry JSON file
  --name NAME          Model name to look up
  --task TASK          Restrict to this task (e.g. detection, pose)
```

Without `--task`, the highest version of `pcb-defect` overall wins
(`0.2.0`, a `pose` model):

```
$ hydra-umc-detection-hef registry latest --registry registry.json --name pcb-defect
pcb-defect 0.2.0  task=pose  input_shape=(640, 640, 3)
classes: solder_bridge, missing_component, tombstone
hef_path: pcb-defect-0.2.0.hef
sha256: bbbb...bbbb
```

With `--task detection`, only `0.1.0` (the `detection` entry) is a
candidate:

```
$ hydra-umc-detection-hef registry latest --registry registry.json --name pcb-defect --task detection
pcb-defect 0.1.0  task=detection  input_shape=(640, 640, 3)
classes: solder_bridge, missing_component
hef_path: pcb-defect-0.1.0.hef
sha256: dce3f284863b41be924a512ae172fdaf91737c45158be164a05e1f7a299fbf9d
```

A real name with no matching entry (exit `1`):

```
$ hydra-umc-detection-hef registry latest --registry registry.json --name nonexistent-model
no model named 'nonexistent-model'
$ echo $?
1
```

### `registry load --registry PATH --models-dir PATH --name NAME [--task TASK] --target-arch ARCH`

The real, combined safe-load gate: architecture compatibility is
checked first (pure metadata, no I/O), and only if it passes is the
checksum verified against the real local file. There are four real,
distinct outcomes — one `READY` and three `REJECTED_*` — all reproduced
below against the same fixture.

```
$ hydra-umc-detection-hef registry load -h
usage: hydra-umc-detection-hef registry load [-h] --registry REGISTRY
                                             --models-dir MODELS_DIR
                                             --name NAME [--task TASK]
                                             --target-arch TARGET_ARCH

options:
  -h, --help            show this help message and exit
  --registry REGISTRY   Path to the registry JSON file
  --models-dir MODELS_DIR
                        Directory containing the .hef files
  --name NAME           Model name to look up
  --task TASK           Restrict to this task (e.g. detection, pose)
  --target-arch TARGET_ARCH
                        Hailo architecture of this deployment (e.g. hailo8)
```

**READY** — `pcb-defect 0.1.0` really is `hailo8`, and its real file's
sha256 really matches the registry:

```
$ hydra-umc-detection-hef registry load --registry registry.json --models-dir models --name pcb-defect --task detection --target-arch hailo8
READY: pcb-defect 0.1.0 (hailo8) verified and ready
$ echo $?
0
```

**REJECTED_ARCH_MISMATCH** — same model, but the deployment targets a
different chip than it was compiled for. Rejected before the filesystem
is even touched:

```
$ hydra-umc-detection-hef registry load --registry registry.json --models-dir models --name pcb-defect --task detection --target-arch hailo15h
REJECTED_ARCH_MISMATCH: model compiled for 'hailo8', this deployment targets 'hailo15h'
$ echo $?
1
```

**REJECTED_MISSING_FILE** — `pcb-defect 0.2.0` is really `hailo15h` (the
architecture check passes), but its `.hef` genuinely isn't present under
`models/`:

```
$ hydra-umc-detection-hef registry load --registry registry.json --models-dir models --name pcb-defect --task pose --target-arch hailo15h
REJECTED_MISSING_FILE: pcb-defect-0.2.0.hef not found under models
$ echo $?
1
```

**REJECTED_CHECKSUM_MISMATCH** — `tamper-demo`'s real file on disk was
really modified after its sha256 was recorded in the registry:

```
$ hydra-umc-detection-hef registry load --registry registry.json --models-dir models --name tamper-demo --target-arch hailo8
REJECTED_CHECKSUM_MISMATCH: tamper-demo-1.0.0.hef does not match the registry's recorded sha256 - possibly corrupt or tampered
$ echo $?
1
```

### `serve --registry PATH [--models-dir PATH] [--addr ADDR] [--port PORT]`

Runs the same `registry.py`/`compatibility.py` logic the three `registry`
subcommands above use, but as a long-running JSON/HTTP API
(`src/hydra_umc_detection_hef/api.py`, stdlib `http.server`) instead of a
one-shot CLI call. Unlike the CLI, `--registry`/`--models-dir` are
configured once at startup, not per-request — a real deployed registry
server has one registry to serve. `--addr`/`--port` default to
`127.0.0.1:8093`. The registry file is re-read from disk on every request
(no cache to go stale).

Real startup output, then serves until `Ctrl-C`:

```
$ hydra-umc-detection-hef serve --registry registry.json --models-dir models --port 8093
[detection-hef] HTTP API listening on 127.0.0.1:8093 (registry=registry.json)
[detection-hef] GET /registry, GET /registry/latest, GET /registry/load, GET /stats
```

`GET /registry` — the full registry plus any duplicate `(name, version)`
pairs, real output against the demo registry above:

```
$ curl -s http://127.0.0.1:8093/registry
{"entries": [{"name": "pcb-defect", "version": "0.1.0", "task": "detection", "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component"], "hef_path": "pcb-defect-0.1.0.hef", "sha256": "dce3f284863b41be924a512ae172fdaf91737c45158be164a05e1f7a299fbf9d", "hailo_arch": "hailo8"}], "duplicateVersions": []}
```

`GET /registry/latest?name=NAME[&task=TASK]` — same lookup as
`registry latest`, JSON-shaped, real `404` for no match:

```
$ curl -s http://127.0.0.1:8093/registry/latest?name=pcb-defect
{"name": "pcb-defect", "version": "0.1.0", "task": "detection", "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component"], "hef_path": "pcb-defect-0.1.0.hef", "sha256": "dce3f284863b41be924a512ae172fdaf91737c45158be164a05e1f7a299fbf9d", "hailo_arch": "hailo8"}

$ curl -s -w '\nHTTP:%{http_code}\n' "http://127.0.0.1:8093/registry/latest?name=nonexistent"
{"error": "no model named 'nonexistent'"}
HTTP:404
```

`GET /registry/load?name=NAME&target_arch=ARCH[&task=TASK]` — the same
combined safe-load gate as `registry load`; real `503` if the server was
started without `--models-dir`:

```
$ curl -s http://127.0.0.1:8093/registry/load?name=pcb-defect&target_arch=hailo8
{"outcome": "ready", "isReady": true, "detail": "pcb-defect 0.1.0 (hailo8) verified and ready", "entry": {"name": "pcb-defect", "version": "0.1.0", "task": "detection", "input_shape": [640, 640, 3], "classes": ["solder_bridge", "missing_component"], "hef_path": "pcb-defect-0.1.0.hef", "sha256": "dce3f284863b41be924a512ae172fdaf91737c45158be164a05e1f7a299fbf9d", "hailo_arch": "hailo8"}}
```

`GET /stats` — which registry/models-dir this server instance is
configured with:

```
$ curl -s http://127.0.0.1:8093/stats
{"registry": "registry.json", "modelsDir": "models"}
```

A missing required query parameter is a real `400`, not a crash:

```
$ curl -s -w '\nHTTP:%{http_code}\n' http://127.0.0.1:8093/registry/latest
{"error": "missing required param: name"}
HTTP:400
```

Any other path is a real `404`:

```
$ curl -s -w '\nHTTP:%{http_code}\n' http://127.0.0.1:8093/nope
{"error": "not found"}
HTTP:404
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | `registry validate` (structure OK, and every locally-present file's checksum matched, if `--models-dir` given); `registry latest` (a match was found); `registry load` (real `READY` outcome); `serve` (clean shutdown via `Ctrl-C`) |
| `1` | any real validation failure (malformed registry, duplicate entry, checksum mismatch), no matching model for `latest`, or any real `REJECTED_*` outcome from `load` |

`serve` itself never exits with `1` for a bad request — a malformed query
or unknown route is a real HTTP error status (`400`/`404`/`502`/`503`),
not a process exit; the process itself only stops on `Ctrl-C`.

## Not yet implemented

ONNX export and Hailo Dataflow Compiler quantization (turning a trained
model into a real `.hef`) both need the real Hailo SDK and, for
quantization, real representative calibration data — neither is
available in this environment, and neither is built here yet. This CLI
covers the registry/versioning and safe-load bookkeeping around
already-compiled `.hef` files, independent of that toolchain.
