# =============================================================================
# HYDRA-UMC-DETECTION-HEF - src/hydra_umc_detection_hef/api.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
"""Plain JSON/HTTP surface (stdlib http.server) - same convention as this
family's other api.py files. Registry and models directory are configured
ONCE at server startup (`--registry`/`--models-dir`), unlike the CLI's own
`registry validate/latest/load` subcommands, which each take their own
`--registry` path per invocation - a real deployed registry server has one
registry to serve, not an arbitrary path chosen per request. The registry
file is re-read from disk on every request (same "always fresh, no cache
to go stale" reasoning as HYDRA-UMC-PRODUCTION-REPORTS' own api.py), since
this is real, occasionally-updated bookkeeping, not a hot path.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .compatibility import safe_load
from .registry import RegistryError, duplicate_versions, find_latest, load_registry


def _write_json(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    def default(o: object) -> object:
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        if hasattr(o, "value"):  # enum
            return o.value
        return str(o)
    body = json.dumps(payload, default=default).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _write_error(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    _write_json(handler, status, {"error": message})


def _query_params(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    parsed = urlparse(handler.path)
    values = parse_qs(parsed.query, keep_blank_values=True)
    repeated = sorted(key for key, value in values.items() if len(value) != 1)
    if repeated:
        raise ValueError(f"query parameters must occur exactly once: {repeated}")
    return {key: value[0] for key, value in values.items()}


class Handler(BaseHTTPRequestHandler):
    server: "RegistryServer"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # quiet by default, same reasoning as this family's other api.py files

    def _load_registry(self):
        try:
            return load_registry(self.server.registry_path), None
        except RegistryError as e:
            _write_error(self, 502, f"could not read registry: {e}")
            return None, "handled"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            params = _query_params(self)
        except ValueError as error:
            _write_error(self, 400, str(error))
            return

        if path == "/registry":
            self._handle_list()
        elif path == "/registry/latest":
            self._handle_latest(params)
        elif path == "/registry/load":
            self._handle_load(params)
        elif path == "/stats":
            _write_json(self, 200, {
                "registry": str(self.server.registry_path),
                "modelsDir": str(self.server.models_dir) if self.server.models_dir else None,
            })
        else:
            _write_error(self, 404, "not found")

    def _handle_list(self) -> None:
        entries, handled = self._load_registry()
        if handled:
            return
        dupes = duplicate_versions(entries)
        _write_json(self, 200, {
            "entries": [asdict(e) for e in entries],
            "duplicateVersions": [{"name": n, "version": v} for n, v in dupes],
        })

    def _handle_latest(self, params: dict[str, str]) -> None:
        if "name" not in params:
            _write_error(self, 400, "missing required param: name")
            return
        entries, handled = self._load_registry()
        if handled:
            return
        entry = find_latest(entries, params["name"], params.get("task"))
        if entry is None:
            _write_error(self, 404, f"no model named {params['name']!r}")
            return
        _write_json(self, 200, asdict(entry))

    def _handle_load(self, params: dict[str, str]) -> None:
        missing = {"name", "target_arch"} - params.keys()
        if missing:
            _write_error(self, 400, f"missing required params: {sorted(missing)}")
            return
        if self.server.models_dir is None:
            _write_error(self, 503, "this server was not started with --models-dir, cannot safe-load")
            return
        entries, handled = self._load_registry()
        if handled:
            return
        entry = find_latest(entries, params["name"], params.get("task"))
        if entry is None:
            _write_error(self, 404, f"no model named {params['name']!r}")
            return
        result = safe_load(entry, self.server.models_dir, params["target_arch"])
        _write_json(self, 200, {
            "outcome": result.outcome.value,
            "isReady": result.is_ready,
            "detail": result.detail,
            "entry": asdict(result.entry),
        })


class RegistryServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], registry_path: Path, models_dir: Path | None) -> None:
        super().__init__(address, Handler)
        self.registry_path = registry_path
        self.models_dir = models_dir
