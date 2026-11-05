"""Offline contract, transport failures, minimized payload and hostile text."""

import copy
import http.client
import json
from pathlib import Path

import pytest
from test_business_report import Document, run

from propane_demo import business, narrative, report
from propane_demo.generator import generate

ENV = {"ANTHROPIC_API_KEY": "synthetic-test-key", "ANTHROPIC_MODEL": "test-model"}


@pytest.fixture(scope="module")
def computed():
    return run(generate("P04"))


def response(result, text="Review the computed exception"):
    refs = [f["finding_id"] for f in result["checks"]["findings"]]
    return {
        "text": text + " " + " ".join(f"[{ref}]" for ref in refs),
        "finding_ids": refs,
    }


def test_payload_allowlist_and_no_backfeed(computed):
    result, raw = computed
    before = copy.deepcopy(result)
    payload = narrative.minimal(result)
    assert set(payload) == {
        "status",
        "kpis",
        "findings",
        "coverage",
        "quality_warnings",
    }
    for f in payload["findings"]:
        assert set(f) == {"finding_id", "severity", "delta", "threshold"}
    for k in payload["kpis"].values():
        assert set(k) == {"value", "unit", "quality"}
    serialized = json.dumps(payload)
    for forbidden in (
        "source_refs",
        "CustomerRef",
        "DisplayName",
        "source_digest",
        "run_id",
        "explanation",
        "raw",
        "missing_lookup_key",
    ):
        assert forbidden not in serialized
    calls = []
    hostile = '<script src="https://evil.test">&"</script>'

    def fake(key, model, value):
        calls.append((key, model, value))
        return response(result, hostile)

    text = narrative.build(result, enabled=True, client=fake, environ=ENV)
    assert text["status"] == "AI_generated"
    assert calls == [(ENV["ANTHROPIC_API_KEY"], ENV["ANTHROPIC_MODEL"], payload)]
    html = report.render(result, raw, narrative_status=text)
    assert hostile not in html and "&lt;script" in html
    doc = Document(html)
    assert "script" not in doc.tags and not doc.assets
    assert "sentence accuracy, numbers, causes or remedies" in html
    assert result == before


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"ANTHROPIC_API_KEY": "x"},
        {"ANTHROPIC_MODEL": "x"},
        {**ENV, "ANTHROPIC_API_KEY": " "},
        {**ENV, "ANTHROPIC_MODEL": " "},
    ],
)
def test_missing_environment_no_call(computed, env):
    def forbidden(*args):
        pytest.fail("network attempted")

    result, _ = computed
    item = narrative.build(result, enabled=True, client=forbidden, environ=env)
    assert item["reason"] == "missing_environment"
    assert item["text"] == report.summary(result)


def test_default_does_not_even_read_environment(computed):
    class Forbidden(dict):
        def get(self, *args):
            pytest.fail("environment accessed")

    assert (
        narrative.build(computed[0], environ=Forbidden())["reason"]
        == "disabled_offline"
    )


@pytest.mark.parametrize(
    "error,reason",
    [
        (TimeoutError("PRIVATE"), "timeout"),
        (OSError("PRIVATE"), "network"),
        (http.client.HTTPException("PRIVATE"), "network"),
        (ValueError("PRIVATE"), "malformed"),
        (TypeError(), "malformed"),
        (KeyError(), "malformed"),
        (IndexError(), "malformed"),
        (UnicodeError(), "malformed"),
    ],
)
def test_client_errors_are_safe(computed, error, reason):
    def fake(*args):
        raise error

    item = narrative.build(computed[0], enabled=True, client=fake, environ=ENV)
    assert item["reason"] == reason and "PRIVATE" not in json.dumps(item)


@pytest.mark.parametrize(
    "value,reason",
    [
        (None, "malformed"),
        ({}, "malformed"),
        ({"text": " ", "finding_ids": []}, "empty"),
        ({"text": None, "finding_ids": []}, "empty"),
        ({"text": "x" * 12001, "finding_ids": []}, "malformed"),
        ({"text": "x", "finding_ids": "bad"}, "malformed"),
        ({"text": "x", "finding_ids": [1]}, "malformed"),
        ({"text": "[invented]", "finding_ids": ["invented"]}, "unsupported_references"),
        ({"text": "no citation", "finding_ids": []}, "unsupported_references"),
        ({"failure": "authentication"}, "authentication"),
        ({"failure": "rate_limit"}, "rate_limit"),
        ({"failure": "provider_error"}, "provider_error"),
        ({"failure": "malformed"}, "malformed"),
        ({"failure": "PRIVATE"}, "malformed"),
        ({"failure": []}, "malformed"),
    ],
)
def test_rejected_responses_use_computed_summary(computed, value, reason):
    item = narrative.build(
        computed[0], enabled=True, environ=ENV, client=lambda *args: value
    )
    assert item["reason"] == reason
    assert item["status"] == "computed_fallback"
    assert item["text"] == report.summary(computed[0])


def test_citation_consistency_and_duplicates(computed):
    result, _ = computed
    valid = response(result)
    assert narrative.validate(valid, result) is None
    wrong = copy.deepcopy(valid)
    wrong["finding_ids"] *= 2
    assert narrative.validate(wrong, result) == "unsupported_references"
    wrong = copy.deepcopy(valid)
    wrong["text"] += " [C99|invented]"
    assert narrative.validate(wrong, result) == "unsupported_references"
    wrong = copy.deepcopy(valid)
    wrong["text"] = "No citations"
    assert narrative.validate(wrong, result) == "unsupported_references"
    clean, _ = run()
    assert narrative.validate({"text": "No findings", "finding_ids": []}, clean) is None


def test_illustrative_digest_and_matching_report(computed):
    result, raw = computed
    sample = {"digest": narrative.digest(result), "response": response(result)}
    item = narrative.build(result, illustrative=sample)
    assert item["status"] == "illustrative_not_live"
    assert "illustrative_not_live" in report.render(result, raw, narrative_status=item)
    changed = copy.deepcopy(result)
    changed["kpis"]["revenue"]["value"] = "999.00"
    assert narrative.build(changed, illustrative=sample)["reason"] == "digest_mismatch"
    sample["response"] = None
    assert narrative.build(result, illustrative=sample)["reason"] == "malformed"


class Transport:
    def __init__(self, status=200, value=None, error=None):
        self.status, self.value, self.error = status, value, error
        self.calls, self.closed = [], False

    def request(self, *args):
        self.calls.append(args)
        if self.error:
            raise self.error

    def getresponse(self):
        return self

    def read(self, limit):
        assert limit == 100001
        return self.value

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "status,reason",
    [
        (401, "authentication"),
        (403, "authentication"),
        (429, "rate_limit"),
        (500, "provider_error"),
        (302, "provider_error"),
    ],
)
def test_http_status_no_retry(monkeypatch, computed, status, reason):
    transport = Transport(status)
    connections = []

    def connection(host, timeout):
        connections.append((host, timeout))
        return transport

    monkeypatch.setattr(http.client, "HTTPSConnection", connection)
    item = narrative.build(computed[0], enabled=True, environ=ENV)
    assert item["reason"] == reason
    assert connections == [("api.anthropic.com", 15)]
    assert transport.closed and len(transport.calls) == 1
    method, path, body, headers = transport.calls[0]
    assert (method, path) == ("POST", "/v1/messages")
    body = json.loads(body)
    assert body["model"] == ENV["ANTHROPIC_MODEL"]
    assert body["system"] == narrative.SYSTEM
    assert json.loads(body["messages"][0]["content"]) == narrative.minimal(computed[0])
    assert ENV["ANTHROPIC_API_KEY"] not in json.dumps(body)
    assert headers["x-api-key"] == ENV["ANTHROPIC_API_KEY"]


@pytest.mark.parametrize(
    "envelope,reason",
    [
        ({"stop_reason": "max_tokens", "content": []}, "malformed"),
        ({"stop_reason": "end_turn", "content": []}, "malformed"),
        ({"stop_reason": "end_turn", "content": [{"type": "tool_use"}]}, "malformed"),
        (
            {"stop_reason": "end_turn", "content": [{"type": "text", "text": ""}]},
            "malformed",
        ),
        ({}, "malformed"),
    ],
)
def test_malformed_transport_envelope(monkeypatch, computed, envelope, reason):
    transport = Transport(value=json.dumps(envelope).encode())
    monkeypatch.setattr(http.client, "HTTPSConnection", lambda *a, **k: transport)
    assert narrative.build(computed[0], enabled=True, environ=ENV)["reason"] == reason
    assert transport.closed


def test_transport_success_and_close_on_timeout(monkeypatch, computed):
    value = response(computed[0])
    transport = Transport(
        value=json.dumps(
            {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": json.dumps(value)}],
            }
        ).encode()
    )
    monkeypatch.setattr(http.client, "HTTPSConnection", lambda *a, **k: transport)
    assert (
        narrative.build(computed[0], enabled=True, environ=ENV)["status"]
        == "AI_generated"
    )
    assert transport.closed
    transport.error = TimeoutError("PRIVATE")
    assert (
        narrative.build(computed[0], enabled=True, environ=ENV)["reason"] == "timeout"
    )
    assert transport.closed


def test_execute_with_injected_fake_keeps_computed_artifacts(tmp_path, monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    files = generate("P04")
    result, _ = run(files)
    before = copy.deepcopy(result)
    assert (
        business.execute(
            files, tmp_path, narrative=True, client=lambda *a: response(result)
        )
        == 0
    )
    assert json.loads((tmp_path / "results.json").read_text()) == before
    assert (
        json.loads((tmp_path / "narrative.json").read_text())["status"]
        == "AI_generated"
    )
    assert (tmp_path / "summary.txt").read_text() == report.summary(result) + "\n"


def test_cli_opt_in_missing_env_offline(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    assert (
        business.main(["--narrative", "--scenario", "clean", "--output", str(tmp_path)])
        == 0
    )
    assert (
        json.loads((tmp_path / "narrative.json").read_text())["reason"]
        == "missing_environment"
    )


def test_committed_issues_and_illustration_reproduce():
    result, raw = run(generate("issues"))
    root = Path(__file__).resolve().parents[1] / "samples"
    sample = json.loads((root / "issues-illustrative-narrative.json").read_text())
    item = narrative.build(result, illustrative=sample)
    assert item["status"] == "illustrative_not_live"
    assert json.loads((root / "issues-results.json").read_text()) == result
    assert (root / "issues-summary.txt").read_text() == report.summary(result) + "\n"
    assert (root / "issues-report.html").read_text() == report.render(
        result, raw, narrative_status=item
    )


def test_renderer_rejects_stale_text_and_source_digest_change(computed):
    result, raw = computed
    item = narrative.build(
        result,
        illustrative={
            "digest": narrative.digest(result),
            "response": response(result, "STALE-TEXT"),
        },
    )
    changed = copy.deepcopy(result)
    changed["source_digest"] = "different"
    text = report.render(changed, raw, narrative_status=item)
    assert "STALE-TEXT" not in text
    assert "digest_mismatch" in text
    assert report.summary(changed) in text


@pytest.mark.parametrize("suffix", [" [broken", " ]", " []"])
def test_unbalanced_citation_rejected(computed, suffix):
    value = response(computed[0])
    value["text"] += suffix
    assert narrative.validate(value, computed[0]) == "unsupported_references"


def test_unavailable_values_are_preformatted_not_null():
    result, _ = run(generate("issues"))
    payload = narrative.minimal(result)
    assert all(isinstance(k["value"], str) for k in payload["kpis"].values())
    assert all(
        isinstance(f[k], str)
        for f in payload["findings"]
        for k in ("finding_id", "severity", "delta", "threshold")
    )
    assert {k["value"] for k in payload["kpis"].values()} == {"Not available"}
    assert "Not available" in {f["delta"] for f in payload["findings"]}


def test_recursive_provider_json_falls_back_without_details(monkeypatch, computed):
    transport = Transport(value=b"[" * 1500 + b"0" + b"]" * 1500)
    monkeypatch.setattr(http.client, "HTTPSConnection", lambda *a, **k: transport)
    item = narrative.build(computed[0], enabled=True, environ=ENV)
    assert item["reason"] == "malformed"
    assert item["text"] == report.summary(computed[0])
    assert transport.closed


def test_injected_client_cannot_mutate_calculation(computed):
    result, _ = computed
    original = copy.deepcopy(result)

    def fake(key, model, payload):
        payload["kpis"]["revenue"]["value"] = "999.00"
        payload["coverage"]["evaluated"] = -1
        payload["findings"].clear()
        return response(result)

    assert (
        narrative.build(result, enabled=True, environ=ENV, client=fake)["status"]
        == "AI_generated"
    )
    assert result == original
