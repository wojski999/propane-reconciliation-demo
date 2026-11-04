"""Business command acceptance, raw evidence, safe failures and offline HTML."""

import copy
import json
import os
import runpy
from decimal import Decimal, localcontext
from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_ingestion import change
from test_rules import ORACLE

from propane_demo import business, report
from propane_demo.contracts import SCENARIOS
from propane_demo.generator import generate
from propane_demo.ingestion import ingest


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links, self.tags, self.assets = [], [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        self.tags.append(tag)
        attrs = dict(attributes)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if "href" in attrs:
            self.links.append(attrs["href"])
        if "src" in attrs:
            self.assets.append(attrs["src"])


def run(files=None):
    db = ingest((generate() if files is None else files).__getitem__)
    try:
        result = business.compute(db)
        raw = report.evidence(db, report.collect_refs(result))
        return result, raw
    finally:
        db.close()


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_all_scenarios_exact_end_to_end_oracle_and_html(tmp_path, scenario):
    output = tmp_path / scenario
    status = business.main(["--scenario", scenario, "--output", str(output)])
    result = json.loads((output / "results.json").read_text())
    expected = ORACLE["scenarios"][scenario]
    assert [
        {k: v for k, v in f.items() if k != "explanation"}
        for f in result["checks"]["findings"]
    ] == [
        {k: v for k, v in f.items() if k != "explanation"} for f in expected["findings"]
    ]
    assert [a["alert_id"] for a in result["alerts"]] == expected["alerts"]
    assert set(result["checks"]["not_evaluated"]) == set(expected["not_evaluated"])
    assert status == (2 if result["status"] == "incomplete" else 0)
    document = Document((output / "report.html").read_text())
    assert len(document.ids) == len(set(document.ids))
    assert all(
        link.startswith("#") and link[1:] in document.ids for link in document.links
    )
    assert not document.assets and "script" not in document.tags
    raw = json.loads((output / "evidence.json").read_text())
    assert set(raw) == report.collect_refs(result)
    assert all("missing_lookup_key" not in record for record in raw.values())
    for ref, record in raw.items():
        # Every reference has immutable raw support OR an explicit missing key.
        assert (
            "raw" in record
            or "derived_from" in record
            or record == {"missing_lookup_key": ref}
        )
    assert json.loads((output / "alerts.json").read_text()) == result["alerts"]
    assert "Offline computed summary" in (output / "summary.txt").read_text()
    if scenario == "clean":
        assert (
            status == 0
            and result["checks"]["findings"] == []
            and result["alerts"] == []
        )
        assert result["coverage"]["not_evaluated"] == 0
        assert result["coverage"]["evaluated"] > 12
        assert all(s["status"] == "complete" for s in result["kpis"].values())
        if os.environ.get("BUSINESS_ARTIFACT"):
            artifact = Path(os.environ["BUSINESS_ARTIFACT"])
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes((output / "report.html").read_bytes())
    if scenario == "issues":
        assert status == 2
        assert result["prioritized_alerts"][0]["severity"] == "critical"
        text = (output / "report.html").read_text()
        assert text.index("CRITICAL: CSV_SCHEMA") < text.index("HIGH: STALE_COVERAGE")
        assert result["kpis"]["AR"]["value"] is None
        assert "critical" == result["prioritized_findings"][0]["severity"]
    if scenario == "P04":
        assert status == 0  # Business exceptions do not imply execution failure.
        assert result["kpis"]["revenue"]["value"] == "1260.02"
        assert result["kpis"]["AR"]["value"] == "870.01"


def test_reproducible_bytes_explicit_as_of_and_seed(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    args = [
        "--scenario",
        "clean",
        "--seed",
        "7",
        "--as-of",
        "2026-11-04T07:00:00+00:00",
    ]
    assert business.main([*args, "--output", str(left)]) == 0
    assert business.main([*args, "--output", str(right)]) == 0
    assert {
        p.relative_to(left): p.read_bytes() for p in left.rglob("*") if p.is_file()
    } == {p.relative_to(right): p.read_bytes() for p in right.rglob("*") if p.is_file()}
    assert "synthetic-7" in (left / "report.html").read_text()


@pytest.mark.parametrize(
    "args",
    [
        ["--scenario", "unknown"],
        ["--seed", "-1"],
        ["--seed", "abc"],
        ["--business-date", "x"],
        ["--business-date", "2035-01-01"],
        ["--as-of", "2026-11-04T07:00:00"],
        ["--as-of", "2026-11-01T07:00:00+00:00"],
        ["--unknown"],
        ["--as-of", "not-a-date"],
    ],
)
def test_invalid_configuration_fatal_safe_no_output(tmp_path, capsys, args):
    output = tmp_path / "report"
    assert business.main([*args, "--output", str(output)]) == 1
    assert not output.exists()
    text = capsys.readouterr().err
    assert "Report failed" in text and "Traceback" not in text


@pytest.mark.parametrize(
    "failure", ["mkdir", "inputs", "write", "render", "report_write", "compute"]
)
def test_safe_boundary_failures_and_preserved_computed_artifacts(
    tmp_path, monkeypatch, capsys, failure
):
    output = tmp_path / "report"
    if failure == "mkdir":
        output.write_text("blocked")
    elif failure == "inputs":
        output.mkdir()
        (output / "inputs").write_text("blocked")
    elif failure == "write":
        monkeypatch.setattr(
            business, "write_json", lambda *a: (_ for _ in ()).throw(OSError("PRIVATE"))
        )
    elif failure == "render":
        output.mkdir()
        (output / "report.html").write_text("old successful report")
        monkeypatch.setattr(
            business, "render", lambda *a: (_ for _ in ()).throw(ValueError("PRIVATE"))
        )
    elif failure == "report_write":
        original = Path.write_text

        def fail_html(path, *args, **kwargs):
            if path.name == "report.html":
                raise OSError("PRIVATE")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_html)
    else:
        monkeypatch.setattr(
            business, "compute", lambda *a: (_ for _ in ()).throw(ValueError("PRIVATE"))
        )
    assert business.main(["--scenario", "clean", "--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert "PRIVATE" not in captured.err and "Traceback" not in captured.err
    assert "Report written" not in captured.out
    if failure in {"render", "report_write"}:
        assert json.loads((output / "results.json").read_text())["status"] == "complete"
        assert (output / "alerts.json").exists()
        assert not (output / "report.html").exists()


def test_business_module_entry_point_and_help(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["propane_demo", "--scenario", "clean", "--output", str(tmp_path)]
    )
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("propane_demo", run_name="__main__")
    assert caught.value.code == 0
    with pytest.raises(SystemExit) as caught:
        business.main(["--help"])
    assert caught.value.code == 0


def test_hostile_source_keys_raw_narrative_and_every_anchor(tmp_path):
    hostile = '<script src="https://evil.test/x">&"</script>'
    files = generate("P04")
    change(files, "qbo.json", lambda q: q["Customer"][0].update(DisplayName=hostile))
    # Arbitrary hostile text is rendered as text, never attribute markup.
    result, raw = run(files)
    result = copy.deepcopy(result)
    result["run"]["run_id"] = hostile
    result["checks"]["findings"][0]["explanation"] = hostile
    result["prioritized_findings"][0]["explanation"] = hostile
    raw[hostile] = {"raw": hostile}
    text = report.render(result, raw, narrative=hostile)
    parsed = Document(text)
    assert "script" not in parsed.tags and not parsed.assets
    assert "&lt;script src=&quot;https://evil.test/x&quot;&gt;" in text
    assert hostile not in text
    assert report.anchor(hostile) in parsed.ids
    assert all(h[1:] in parsed.ids for h in parsed.links)


def test_raw_file_occurrence_derived_and_missing_resolvers():
    db = ingest(generate("raw-repeat").__getitem__)
    try:
        refs = {
            "file:qbo.json#/Invoice/0/Line/0",
            "file:absent.json",
            "run:x",
            "policy:x",
            "qbo:version:I-PRICE:0",
            "pos:external_reference:EXT-EQUAL-A",
            "qbo:external_reference:I-PRICE",
            "pos:fee:B-SETTLED:fees",
            "cargas:meter_ticket:MT-D-OUT",
            "qbo:account:CLEARING",
            "not:a:record",
        }
        records = report.evidence(db, refs)
        assert records["file:absent.json"] == {"missing_lookup_key": "file:absent.json"}
        assert records["not:a:record"] == {"missing_lookup_key": "not:a:record"}
        assert (
            records["file:qbo.json#/Invoice/0/Line/0"]["pointer"]
            == "#/Invoice/0/Line/0"
        )
        assert "I-PRICE" in records["file:qbo.json#/Invoice/0/Line/0"]["raw"]
        for key in refs - {
            "not:a:record",
            "file:absent.json",
            "cargas:meter_ticket:MT-D-OUT",
            "pos:external_reference:EXT-EQUAL-A",
            "qbo:account:CLEARING",
        }:
            assert "missing_lookup_key" not in records[key]
    finally:
        db.close()


def test_missing_source_manifests_freshness_and_basis_e2e(tmp_path):
    files = generate()
    files.pop("qbo.json")
    result, raw = run(files)
    assert result["status"] == "incomplete"
    assert any(a["check_id"] == "C10" for a in result["alerts"])
    assert "missing_lookup_key" in raw["file:qbo.json"]
    files = generate()
    change(
        files,
        "deliveries.csv",
        lambda rows: next(r for r in rows if r["ticket_id"] == "D-FRACTION").update(
            gallon_basis=""
        ),
    )
    assert business.execute(files, tmp_path) == 2
    result = json.loads((tmp_path / "results.json").read_text())
    assert result["kpis"]["delivered"]["status"] == "partial"
    assert result["kpis"]["delivered"]["value"] is None


def test_subsecond_staleness_is_exact_readable_duration():
    with localcontext() as ctx:
        ctx.prec = 80
        hours = format(Decimal("86400.000001") / 3600, "f")
    assert report.duration(hours) == "1 day, 0:00:00.000001"
    result, raw = run(generate("P10"))
    result["prioritized_findings"][0]["actual"] = hours
    text = report.render(result, raw)
    assert "1 day, 0:00:00.000001" in text
    assert hours not in text


def test_raw_credit_refund_event_crosswalk_full_pipeline():
    files = generate()

    def crosswalk(qbo):
        qbo["CreditMemo"][0]["RevenueEvent"] = "CREDIT-SETTLEMENT"
        refund = qbo["RefundReceipt"][0]
        refund["RevenueEvent"] = "CREDIT-SETTLEMENT"
        refund["LinkedTxn"] = [
            {"TxnType": "Invoice", "TxnId": "I-CREDIT"},
            {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"},
        ]

    change(files, "qbo.json", crosswalk)
    result, _ = run(files)
    assert result["status"] == "complete"
    assert result["checks"]["findings"] == []
    # Yesterday's credit recognized once, today's cash refund settles it only.
    assert result["kpis"]["revenue"]["value"] == "1350.02"
    assert result["kpis"]["AR"]["value"] == "860.01"


def test_partial_html_write_removed_and_results_preserved(tmp_path, monkeypatch):
    original = Path.write_text

    def partial(path, text, *args, **kwargs):
        if path.name == "report.html":
            original(path, "<html>partial", *args, **kwargs)
            raise OSError("PRIVATE")
        return original(path, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", partial)
    assert business.main(["--scenario", "clean", "--output", str(tmp_path)]) == 1
    assert (tmp_path / "results.json").exists()
    assert not (tmp_path / "report.html").exists()


def test_installed_business_command_no_key_or_network(tmp_path, monkeypatch):
    import subprocess
    import sys

    monkeypatch.setenv("ANTHROPIC_API_KEY", "DO-NOT-READ-THIS")
    monkeypatch.setenv("ANTHROPIC_MODEL", "DO-NOT-READ-THIS")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "propane_demo",
            "--scenario",
            "clean",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0
    assert "Report written: complete" in completed.stdout
    assert "DO-NOT-READ-THIS" not in (tmp_path / "report.html").read_text()


def test_committed_sample_matches_current_computation_and_render():
    result, raw = run()
    root = Path(__file__).resolve().parents[1] / "samples"
    assert (root / "clean-report.html").read_text() == report.render(result, raw)
    assert json.loads((root / "clean-results.json").read_text()) == result
    assert (root / "clean-summary.txt").read_text() == report.summary(result) + "\n"


@pytest.mark.parametrize("state", ["missing", "void", "pending"])
def test_dangling_current_pos_crosswalk_is_partial_never_zero(state):
    files = generate()

    def omit(rows):
        row = next(r for r in rows if r["transaction_id"] == "T-CYLINDER")
        if state == "missing":
            rows.remove(row)
        else:
            row["status"] = state

    change(files, "pos.csv", omit, count=True)
    result, raw = run(files)
    assert result["status"] == "incomplete"
    assert result["kpis"]["retail"]["status"] == "partial"
    assert result["kpis"]["retail"]["value"] is None
    assert result["kpis"]["revenue"]["value"] is None
    assert (
        result["kpis"]["retail"]["gaps"][0]["missing_lookup_key"]
        == "active_pos_event:pos:POS:T-CYLINDER:1"
    )
    assert "identity:pos_event:EVENT-T-CYLINDER" in raw
