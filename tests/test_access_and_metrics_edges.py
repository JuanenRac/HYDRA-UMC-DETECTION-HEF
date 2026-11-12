# =============================================================================
# HYDRA-UMC-DETECTION-HEF - tests/test_access_and_metrics_edges.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The edges of the bearer token and of the metrics of the service: what counts as loopback, where the token comes from and how short it may be, what a request must
present, the 401 that is given, the labels that can never carry free text, the counters by class of status and the answer of `GET /metrics`."""
from __future__ import annotations

import io
import json
import random
from email.message import Message
from pathlib import Path

import pytest

from hydra_umc_detection_hef import access
from hydra_umc_detection_hef import service_metrics as sm


class FakeHandler:
    """The parts of a request handler that the checks read and write."""

    def __init__(self, authorization: str | None = None, path: str = "/", command: str = "GET") -> None:
        self.command = command
        self.headers = Message()
        if authorization is not None:
            self.headers["Authorization"] = authorization
        self.path = path
        self.wfile = io.BytesIO()
        self.sent: list[tuple[str, str]] = []
        self.status: int | None = None

    def send_response(self, code: int, message: str | None = None) -> None:
        self.status = code

    def send_header(self, name: str, value: str) -> None:
        self.sent.append((name, value))

    def end_headers(self) -> None:
        pass


class TestLoopback:
    @pytest.mark.parametrize("address", ["localhost", "LOCALHOST", " localhost ", "127.0.0.1", "127.255.255.254", "::1", "[::1]", " 127.0.0.1 "])
    def test_these_are_loopback(self, address: str) -> None:
        assert access.is_loopback(address) is True

    @pytest.mark.parametrize("address", ["0.0.0.0", "::", "[::]", "192.168.0.180", "10.0.0.1", "8.8.8.8", "", "example.com", "127.0.0", "127.0.0.1.5", "localhost.localdomain", "300.1.1.1"])
    def test_these_are_not(self, address: str) -> None:
        assert access.is_loopback(address) is False

    def test_a_token_is_only_needed_away_from_loopback(self) -> None:
        assert access.bind_problem("127.0.0.1", "") is None
        assert access.bind_problem("localhost", "") is None
        assert access.bind_problem("0.0.0.0", "a-token-of-sixteen+") is None
        problem = access.bind_problem("0.0.0.0", "")
        assert problem is not None and "--addr 0.0.0.0 is not loopback" in problem and access.TOKEN_ENV in problem
        assert access.bind_problem("192.168.0.5", "") is not None


class TestLoadToken:
    def test_no_file_and_no_environment_is_no_token(self) -> None:
        assert access.load_token(None, {}) == ""
        assert access.load_token("", {}) == ""

    def test_the_environment_gives_the_token_trimmed(self) -> None:
        assert access.load_token(None, {access.TOKEN_ENV: "  a-token-of-sixteen+\n"}) == "a-token-of-sixteen+"

    def test_the_file_wins_over_the_environment(self, tmp_path: Path) -> None:
        path = tmp_path / "token"
        path.write_text("the-token-of-the-file-0123\n", encoding="utf-8")
        assert access.load_token(path, {access.TOKEN_ENV: "the-token-of-the-environment"}) == "the-token-of-the-file-0123"
        assert access.load_token(str(path), {}) == "the-token-of-the-file-0123"

    def test_a_missing_or_unreadable_file_is_an_error_that_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="cannot read the token file"):
            access.load_token(tmp_path / "absent", {})
        binary = tmp_path / "binary"
        binary.write_bytes(b"\xff\xfe\x00\x80")
        with pytest.raises(ValueError, match="cannot read the token file"):
            access.load_token(binary, {})
        with pytest.raises(ValueError, match="cannot read the token file"):
            access.load_token(tmp_path, {})  # a folder

    def test_a_token_below_the_minimum_is_refused_from_either_source_and_the_minimum_itself_is_fine(self, tmp_path: Path) -> None:
        short = "x" * (access.MIN_TOKEN_LENGTH - 1)
        exact = "x" * access.MIN_TOKEN_LENGTH
        with pytest.raises(ValueError, match=f"at least {access.MIN_TOKEN_LENGTH} characters"):
            access.load_token(None, {access.TOKEN_ENV: short})
        path = tmp_path / "token"
        path.write_text(short + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="at least"):
            access.load_token(path, {})
        assert access.load_token(None, {access.TOKEN_ENV: exact}) == exact

    def test_an_empty_file_is_no_token_and_replaces_the_one_of_the_environment(self, tmp_path: Path) -> None:
        path = tmp_path / "token"
        path.write_text("\n", encoding="utf-8")
        assert access.load_token(path, {access.TOKEN_ENV: "an-environment-token-0123"}) == ""


class TestAuthorized:
    TOKEN = "the-expected-token-0123"

    def test_without_a_configured_token_everything_passes(self) -> None:
        assert access.authorized(FakeHandler(), "") is True
        assert access.authorized(FakeHandler("Bearer anything"), "") is True

    @pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer ", "bearer " + TOKEN, "Basic " + TOKEN, TOKEN, "Bearer " + TOKEN + "x", "Bearer x" + TOKEN, "Bearer " + TOKEN[:-1], "Token " + TOKEN])
    def test_anything_but_the_exact_bearer_token_is_refused(self, header: str | None) -> None:
        assert access.authorized(FakeHandler(header), self.TOKEN) is False

    def test_the_exact_token_passes_with_surrounding_spaces_ignored_after_the_scheme(self) -> None:
        assert access.authorized(FakeHandler("Bearer " + self.TOKEN), self.TOKEN) is True
        assert access.authorized(FakeHandler("Bearer  " + self.TOKEN + "  "), self.TOKEN) is True

    def test_a_token_with_non_ascii_characters_is_compared_as_bytes_not_crashed_on(self) -> None:
        assert access.authorized(FakeHandler("Bearer tokén-of-the-sixteen"), "tokén-of-the-sixteen") is True
        assert access.authorized(FakeHandler("Bearer token-of-the-sixteen-"), "tokén-of-the-sixteen") is False

    def test_with_the_key_of_the_server_the_identity_decides_and_nothing_is_open(self) -> None:
        key = b"a-signing-key-of-the-server-0123456789"
        from hydra_umc_detection_hef import server_identity as si

        assert access.authorized(FakeHandler(), "", key) is False, "no token at all: refused although none is configured"
        good = "Bearer " + si.sign_token(key, "ana", "admin")
        assert access.authorized(FakeHandler(good), "", key) is True
        assert access.authorized(FakeHandler("Bearer " + self.TOKEN), self.TOKEN, key) is True, "the own token still works next to the identity"

    def test_the_401_names_the_scheme_and_carries_a_json_body_of_the_right_length(self) -> None:
        handler = FakeHandler()
        access.reject(handler)  # type: ignore[arg-type]
        assert handler.status == 401
        headers = dict(handler.sent)
        assert headers["WWW-Authenticate"] == "Bearer"
        assert headers["Content-Type"] == "application/json"
        body = handler.wfile.getvalue()
        assert int(headers["Content-Length"]) == len(body)
        assert json.loads(body) == {"error": "a valid bearer token is required"}


class TestNamesAndLabels:
    def test_a_check_name_is_lower_case_letters_digits_and_underscores_only(self) -> None:
        assert sm.check_name("Registry-File Readable!") == "registry_file_readable"
        assert sm.check_name("  --  ") == "check"
        assert sm.check_name("") == "check"
        assert sm.check_name("ok_1") == "ok_1"
        assert sm.check_name('quote"; DROP\n') == "quote_drop"

    def test_a_fixed_seed_walk_of_names_never_yields_anything_outside_the_alphabet(self) -> None:
        rng = random.Random(4242)
        alphabet = [chr(c) for c in range(0, 300)]
        for _ in range(300):
            name = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 20)))
            result = sm.check_name(name)
            assert result and all(ch.islower() and ch.isascii() or ch.isdigit() and ch.isascii() or ch == "_" for ch in result), repr(name)
            assert not result.startswith("_") and not result.endswith("_") or result == "check"

    def test_labels_escape_backslashes_quotes_and_newlines(self) -> None:
        assert sm._label('a"b') == 'a\\"b'
        assert sm._label("a\\b") == "a\\\\b"
        assert sm._label("a\nb") == "a b"
        assert sm._label('\\"') == '\\\\\\"'

    def test_the_installed_version_or_unknown(self) -> None:
        assert sm.installed_version("a-distribution-that-is-not-installed-9f2c") == "unknown"
        assert sm.installed_version("pytest")  # any installed distribution has a version


class TestCounters:
    def test_responses_are_counted_by_class_and_odd_statuses_count_as_5xx(self) -> None:
        metrics = sm.ServiceMetrics("svc", "1.2.3")
        for status in (200, 204, 301, 404, 404, 418, 500, 503, 100, 700, 0):
            metrics.count(status)
        text = metrics.render()
        counts = {klass: int(line.rsplit(" ", 1)[1]) for klass in sm.STATUS_CLASSES for line in text.splitlines() if f'class="{klass}"' in line}
        assert counts == {"2xx": 2, "3xx": 1, "4xx": 3, "5xx": 5}, "100, 700 and 0 are not a class of ours: they are failures"

    def test_the_text_has_the_four_families_and_ends_with_a_newline(self) -> None:
        text = sm.ServiceMetrics("my service", "9.9.9").render()
        assert text.endswith("\n") and not text.endswith("\n\n")
        for name in ("hydra_umc_service_info", "hydra_umc_service_uptime_seconds", "hydra_umc_service_http_responses_total", "hydra_umc_service_health"):
            assert f"# TYPE {name} " in text
        assert 'hydra_umc_service_info{service="my service",version="9.9.9"} 1' in text
        assert "hydra_umc_service_health_check" not in text, "no checks, no per-check line"
        assert 'hydra_umc_service_health{service="my service"} 1' in text

    def test_a_failing_check_makes_the_service_unhealthy_and_is_named_in_a_safe_label(self) -> None:
        text = sm.ServiceMetrics("svc", "1").render({"Registry OK": True, "Disk-Space": False})
        assert 'hydra_umc_service_health{service="svc"} 0' in text
        assert 'hydra_umc_service_health_check{service="svc",check="registry_ok"} 1' in text
        assert 'hydra_umc_service_health_check{service="svc",check="disk_space"} 0' in text
        assert text.index('check="disk_space"') < text.index('check="registry_ok"'), "sorted by name"

    def test_a_service_name_cannot_break_out_of_its_label(self) -> None:
        text = sm.ServiceMetrics('evil"}\nfake_metric 1', "1").render()
        assert "\nfake_metric 1" not in text
        assert 'service="evil\\"} fake_metric 1"' in text

    def test_the_counters_are_safe_from_many_threads(self) -> None:
        import threading

        metrics = sm.ServiceMetrics("svc", "1")
        workers = [threading.Thread(target=lambda: [metrics.count(200) for _ in range(500)]) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        assert 'class="2xx"} 4000' in metrics.render()


class MetricsHandler(sm.MetricsHandlerMixin):
    """The mixin with the parts of a real handler faked, so that its decisions can be seen."""

    metrics_service = "unit-test-service"
    metrics_version = "0.0.1"

    def __init__(self, path: str, failing: bool = False, checks: dict[str, bool] | None = None) -> None:
        self.path = path
        self.server = type("S", (), {})()
        self.wfile = io.BytesIO()
        self.sent: list[tuple[str, str]] = []
        self.status: int | None = None
        self._failing = failing
        self._checks = checks or {}

    def metrics_checks(self) -> dict[str, bool]:
        if self._failing:
            raise RuntimeError("cannot check")
        return self._checks

    def send_response(self, code: int, message: str | None = None) -> None:  # type: ignore[override]
        self._service_metrics().count(code)
        self.status = code

    def send_header(self, name: str, value: str) -> None:  # type: ignore[override]
        self.sent.append((name, value))

    def end_headers(self) -> None:  # type: ignore[override]
        pass


class TestMetricsRoute:
    def test_any_other_path_is_not_taken(self) -> None:
        handler = MetricsHandler("/stats")
        assert handler.serve_metrics() is False
        assert handler.status is None and handler.wfile.getvalue() == b""

    def test_the_path_is_matched_without_its_query_and_not_as_a_prefix(self) -> None:
        assert MetricsHandler("/metrics?x=1").serve_metrics() is True
        assert MetricsHandler("/metrics/extra").serve_metrics() is False
        assert MetricsHandler("/metricsx").serve_metrics() is False

    def test_an_authorized_request_gets_the_text_in_the_prometheus_type(self) -> None:
        handler = MetricsHandler("/metrics", checks={"registry": True})
        assert handler.serve_metrics(True) is True
        assert handler.status == 200
        headers = dict(handler.sent)
        assert headers["Content-Type"] == "text/plain; version=0.0.4; charset=utf-8"
        body = handler.wfile.getvalue()
        assert int(headers["Content-Length"]) == len(body)
        assert b'hydra_umc_service_info{service="unit-test-service",version="0.0.1"} 1' in body
        assert b'check="registry"} 1' in body

    def test_an_unauthorized_request_gets_a_401_and_no_numbers(self) -> None:
        handler = MetricsHandler("/metrics")
        assert handler.serve_metrics(False) is True
        assert handler.status == 401
        assert dict(handler.sent)["WWW-Authenticate"] == "Bearer"
        assert json.loads(handler.wfile.getvalue()) == {"error": "unauthorized"}
        assert b"hydra_umc" not in handler.wfile.getvalue()

    def test_a_check_that_raises_is_a_failed_check_not_a_failed_answer(self) -> None:
        handler = MetricsHandler("/metrics", failing=True)
        assert handler.serve_metrics() is True
        assert handler.status == 200
        body = handler.wfile.getvalue().decode()
        assert 'hydra_umc_service_health{service="unit-test-service"} 0' in body
        assert 'check="checks"} 0' in body

    def test_the_responses_given_are_counted_in_the_next_scrape(self) -> None:
        handler = MetricsHandler("/metrics")
        handler.serve_metrics(False)
        handler.serve_metrics(False)
        handler.wfile = io.BytesIO()
        handler.serve_metrics(True)
        assert 'class="4xx"} 2' in handler.wfile.getvalue().decode()

    def test_the_counters_belong_to_the_server_and_are_made_once(self) -> None:
        handler = MetricsHandler("/metrics")
        first = handler._service_metrics()
        assert handler._service_metrics() is first
        other = MetricsHandler("/metrics")
        other.server = handler.server
        assert other._service_metrics() is first

    def test_the_version_defaults_to_the_installed_one_of_the_service_name(self) -> None:
        handler = MetricsHandler("/metrics")
        handler.metrics_version = ""
        handler.metrics_service = "a-service-nobody-installed-9f2c"
        assert handler._service_metrics().version == "unknown"
