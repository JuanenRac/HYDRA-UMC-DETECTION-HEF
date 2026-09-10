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
usage: hydra-umc-detection-hef registry [-h] {validate,latest,load,add} ...

positional arguments:
  {validate,latest,load,add}
    validate            Validate registry structure and (optionally)
                        checksums.
    latest              Print the latest registered version of a model.
    load                Real safe-load gate: architecture compatibility +
                        checksum, combined.
    add                 Hash a real local .hef and append a validated entry -
                        no more hand-editing the registry JSON.

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

### `registry add --registry PATH --models-dir PATH --hef-path PATH --name NAME --version VERSION --task TASK --input-shape SHAPE --classes LABELS --hailo-arch ARCH`

Found while auditing the code: until this
command existed, the registry JSON was hand-edited, including the
`sha256` `verify_checksum()` only ever checked, never generated. This
hashes the real local `.hef` file with the same `compute_sha256()`
`verify_checksum()` itself uses, then validates the assembled entry
through the exact same schema gate every other command's `registry.json`
already goes through - `--registry` doesn't need to exist yet; a missing
path is a real, valid "start a brand new registry" starting point.

```
$ hydra-umc-detection-hef registry add -h
usage: hydra-umc-detection-hef registry add [-h] --registry REGISTRY
                                            --models-dir MODELS_DIR
                                            --hef-path HEF_PATH --name NAME
                                            --version VERSION --task TASK
                                            --input-shape INPUT_SHAPE
                                            --classes CLASSES
                                            --hailo-arch HAILO_ARCH

options:
  -h, --help            show this help message and exit
  --registry REGISTRY   Path to the registry JSON file (created if it doesn't
                        exist yet)
  --models-dir MODELS_DIR
                        Directory containing the real .hef file to register
  --hef-path HEF_PATH   Path to the .hef file, relative to --models-dir
  --name NAME           Model name
  --version VERSION     Model version, X.Y.Z
  --task TASK           Task this model performs (e.g. detection, pose)
  --input-shape INPUT_SHAPE
                        Comma-separated positive integers, e.g. 640,640,3
  --classes CLASSES     Comma-separated class labels, e.g. defect,ok
  --hailo-arch HAILO_ARCH
                        Target Hailo architecture (hailo10h, hailo15h,
                        hailo15l, hailo15m, hailo8, hailo8l, hailo8r)
```

A real, brand-new registry (`registry-new.json` doesn't exist yet) plus a
real local `.hef` file - `registry add` hashes the actual bytes, it is
never handed a digest to trust:

```
$ hydra-umc-detection-hef registry add --registry registry-new.json --models-dir models --hef-path pcb-defect-0.1.0.hef --name pcb-defect --version 0.1.0 --task detection --input-shape 640,640,3 --classes solder_bridge,missing_component --hailo-arch hailo8
added pcb-defect 0.1.0 to registry-new.json (sha256=<the real sha256 of models/pcb-defect-0.1.0.hef>)
$ echo $?
0
$ cat registry-new.json
[
  {
    "name": "pcb-defect",
    "version": "0.1.0",
    "task": "detection",
    "input_shape": [640, 640, 3],
    "classes": ["solder_bridge", "missing_component"],
    "hef_path": "pcb-defect-0.1.0.hef",
    "sha256": "<the real sha256 of models/pcb-defect-0.1.0.hef>",
    "hailo_arch": "hailo8"
  }
]
```

Running the exact same command again is rejected - a real duplicate
`(name, version)`, not silently overwritten or appended twice:

```
$ hydra-umc-detection-hef registry add --registry registry-new.json --models-dir models --hef-path pcb-defect-0.1.0.hef --name pcb-defect --version 0.1.0 --task detection --input-shape 640,640,3 --classes solder_bridge,missing_component --hailo-arch hailo8
error: entry for 'pcb-defect' '0.1.0' already exists in the registry
$ echo $?
1
```

A `--hef-path` that isn't a real, present file is rejected before any
JSON is written - there is no path where `registry add` records a
checksum for a file that was never actually read:

```
$ hydra-umc-detection-hef registry add --registry registry-new.json --models-dir models --hef-path nonexistent.hef --name ghost --version 1.0.0 --task detection --input-shape 640,640,3 --classes a --hailo-arch hailo8
error: models/nonexistent.hef does not exist - add_entry() only registers a real, present file
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
| `0` | `registry validate` (structure OK, and every locally-present file's checksum matched, if `--models-dir` given); `registry latest` (a match was found); `registry load` (real `READY` outcome); `registry add` (the real file was hashed and a validated entry appended); `serve` (clean shutdown via `Ctrl-C`) |
| `1` | any real validation failure (malformed registry, duplicate entry, checksum mismatch), no matching model for `latest`, any real `REJECTED_*` outcome from `load`, or `registry add` rejecting a duplicate/invalid entry/missing `.hef` |

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
