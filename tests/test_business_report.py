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
    assert result["status"] == "incomplete"
    assert result["checks"]["findings"] == []
    # Yesterday's fully applied credit has no remaining capacity for a refund.
    assert result["kpis"]["AR"]["unapplied_credits"]["value"] is None
    assert result["kpis"]["AR"]["gaps"][0]["missing_lookup_key"].startswith(
        "refund_credit_capacity:"
    )
    # Over-capacity settlement cannot assert complete revenue either.
    assert result["kpis"]["revenue"]["value"] is None
    assert result["kpis"]["AR"]["value"] is None
    assert result["kpis"]["AR"]["known_value"] == "860.01"


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


@pytest.mark.parametrize(
    "refund_amount,applied,left,gap",
    [
        ("20.00", "0.00", "0.00", None),
        ("5.00", "0.00", "15.00", None),
        ("8.00", "12.00", "0.00", None),
        ("9.00", "12.00", None, "refund_credit_capacity:qbo:RefundReceipt:RR-X"),
        ("21.00", "0.00", None, "refund_credit_capacity:qbo:RefundReceipt:RR-X"),
    ],
)
@pytest.mark.parametrize("identity", ["direct", "event", "both"])
@pytest.mark.parametrize("credit_day", ["2026-11-02", "2026-11-03"])
def test_raw_refund_consumes_only_available_credit(
    refund_amount, applied, left, gap, identity, credit_day
):
    files = generate("clean")

    def add(qbo):
        credit = copy.deepcopy(qbo["CreditMemo"][0])
        credit.update(Id="CM-X", TotalAmt="20.00", AppliedAmount=applied)
        credit["Line"][0]["Amount"] = "20.00"
        credit["LinkedTxn"] = [{"TxnType": "Invoice", "TxnId": "I-PAY"}]
        refund = copy.deepcopy(qbo["RefundReceipt"][0])
        refund.update(Id="RR-X", TotalAmt=refund_amount)
        refund["Line"][0]["Amount"] = refund_amount
        refund["LinkedTxn"] = [
            {"TxnType": "CreditMemo", "TxnId": "CM-X"},
            {"TxnType": "Invoice", "TxnId": "I-PAY"},
        ]
        credit["TxnDate"] = credit_day
        if identity != "direct":
            credit["RevenueEvent"] = refund["RevenueEvent"] = "EV-X"
        if identity == "event":
            refund["LinkedTxn"] = [{"TxnType": "Invoice", "TxnId": "I-PAY"}]
        qbo["CreditMemo"].append(credit)
        qbo["RefundReceipt"].append(refund)

    change(files, "qbo.json", add, count=True)
    result, raw = run(files)
    ar = result["kpis"]["AR"]
    assert ar["unapplied_credits"]["value"] == left
    assert ar["unapplied_cash"]["known_value"] == "25.01"
    assert ar["known_value"] == ("848.01" if applied == "12.00" else "860.01")
    assert ar["status"] == ("partial" if gap else "complete")
    assert result["status"] == ("incomplete" if gap else "complete")
    if gap:
        assert gap in [g["missing_lookup_key"] for g in ar["gaps"]]
        assert ar["value"] is None
        assert all(c["computed"] is None for c in ar["reported_balance_comparisons"])
    else:
        assert result["kpis"]["revenue"]["value"] == (
            "1230.02" if credit_day == "2026-11-03" else "1250.02"
        )
        contribution = next(
            c
            for c in ar["unapplied_credits"]["contributions"]
            if "qbo:CreditMemo:CM-X" in c["source_refs"]
        )
        assert contribution["amount"] == left
        assert contribution["source_refs"] == [
            "qbo:CreditMemo:CM-X",
            "qbo:RefundReceipt:RR-X",
        ]
    assert all("missing_lookup_key" not in v for v in raw.values())
    document = Document(report.render(result, raw))
    assert all(link[1:] in document.ids for link in document.links)


@pytest.mark.parametrize(
    "mode,expected,gap",
    [
        ("unknown", None, "refund_credit:"),
        ("ambiguous", None, "refund_credit:"),
        ("cross_customer", None, "same_customer_refund_credit:"),
        ("void_credit", None, "refund_credit:"),
        ("before_credit", None, "refund_credit:"),
        ("at_opening", "100.00", None),
        ("after_asof", "100.00", None),
        ("void_refund", "100.00", None),
        ("at_asof", "0.00", None),
    ],
)
@pytest.mark.parametrize("identity", ["direct", "event"])
def test_raw_refund_identity_void_and_cutoff_support(mode, expected, gap, identity):
    files = generate("clean")

    def mutate(qbo):
        credit = qbo["CreditMemo"][0]
        credit["AppliedAmount"] = "0.00"
        refund = qbo["RefundReceipt"][0]
        refund["LinkedTxn"] = [
            {"TxnType": "Invoice", "TxnId": "I-CREDIT"},
            {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"},
        ]
        if identity == "event":
            credit["RevenueEvent"] = refund["RevenueEvent"] = "EV-BOUNDARY"
            refund["LinkedTxn"].pop()
        if mode == "unknown":
            refund["LinkedTxn"].append({"TxnType": "CreditMemo", "TxnId": "UNKNOWN"})
        elif mode == "ambiguous":
            if identity == "event":
                other = copy.deepcopy(credit)
                other["Id"] = "CM-OTHER"
                qbo["CreditMemo"].append(other)
            else:
                refund["LinkedTxn"].append({"TxnType": "CreditMemo", "TxnId": "OTHER"})
        elif mode == "cross_customer":
            refund["CustomerRef"] = {"value": "OTHER"}
        elif mode == "void_credit":
            credit["status"] = "void"
        elif mode == "before_credit":
            credit["EventAt"] = "2026-11-04T07:00:00+00:00"
        elif mode == "at_opening":
            refund["EventAt"] = "2026-10-26T07:00:00+00:00"
        elif mode == "after_asof":
            refund["EventAt"] = "2026-11-04T07:00:00.000001+00:00"
        elif mode == "void_refund":
            refund["status"] = "void"
        else:
            refund["EventAt"] = "2026-11-04T07:00:00+00:00"

    change(files, "qbo.json", mutate, count=True)
    if mode == "cross_customer":
        change(
            files,
            "opening_ar.json",
            lambda s: s["balances"].append({"customer_id": "OTHER", "amount": "0.00"}),
        )
    result, raw = run(files)
    ar = result["kpis"]["AR"]
    if mode == "after_asof":
        # Raw contract rejects events outside the declared extraction window.
        assert result["alerts"][0]["reason_code"] == "WINDOW"
        assert ar["status"] == "unavailable"
        assert ar["value"] is None
        assert ar["unapplied_credits"]["value"] is None
        assert result["status"] == "incomplete"
        return
    assert result["alerts"] == []  # Remaining cases passed the raw importer.
    assert ar["unapplied_credits"]["value"] == expected
    assert ar["status"] == ("partial" if gap else "complete")
    assert ar["known_value"] == "960.01"
    assert ar["unapplied_cash"]["known_value"] == "25.01"
    if gap:
        assert any(g["missing_lookup_key"].startswith(gap) for g in ar["gaps"])
        assert result["status"] == "incomplete"
    if mode not in {"after_asof", "void_refund"}:
        assert "raw" in raw["qbo:RefundReceipt:RR-BOUNDARY"]


@pytest.mark.parametrize("payment_first", [True, False])
@pytest.mark.parametrize("excess", [False, True])
@pytest.mark.parametrize("credit_day", ["2026-11-02", "2026-11-03"])
def test_raw_event_refunds_and_payment_share_ordered_capacity(
    payment_first, excess, credit_day
):
    files = generate("clean")

    def mutate(qbo):
        credit = qbo["CreditMemo"][0]
        credit.update(
            AppliedAmount="0.00", RevenueEvent="EV-SHARED", TxnDate=credit_day
        )
        refund = qbo["RefundReceipt"][0]
        refund.update(TotalAmt="30.00", RevenueEvent="EV-SHARED")
        refund["Line"][0]["Amount"] = "30.00"
        refund["LinkedTxn"] = [{"TxnType": "Invoice", "TxnId": "I-CREDIT"}]
        other = copy.deepcopy(refund)
        other.update(
            Id="RR-SECOND", EventAt="2026-11-04T06:00:00+00:00", TotalAmt="20.00"
        )
        other["Line"][0]["Amount"] = "20.00"
        qbo["RefundReceipt"].append(other)
        payment = qbo["Payment"][0]
        payment["EventAt"] = (
            "2026-11-03T08:00:00+00:00"
            if payment_first
            else "2026-11-04T07:00:00+00:00"
        )
        payment["TotalAmt"] = "0.00"
        payment["Line"][0]["Amount"] = "51.00" if excess else "50.00"
        payment["Line"][0]["LinkedTxn"] = [
            {"TxnType": "Invoice", "TxnId": "I-CREDIT"},
            {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"},
        ]

    change(files, "qbo.json", mutate, count=True)
    result, raw = run(files)
    ar = result["kpis"]["AR"]
    assert ar["status"] == ("partial" if excess else "complete")
    assert ar["unapplied_credits"]["value"] == (None if excess else "0.00")
    assert ar["unapplied_cash"]["known_value"] == "25.01"
    assert ar["known_value"] == (
        "1009.01" if excess and payment_first else "1060.01" if excess else "1010.01"
    )
    # Credit recognized once, cash settlements never recognize new revenue.
    assert result["kpis"]["revenue"]["value"] == (
        None if excess else "1250.02" if credit_day == "2026-11-03" else "1350.02"
    )
    if excess:
        expected = (
            "refund_credit_capacity:qbo:RefundReceipt:RR-SECOND"
            if payment_first
            else "credit_allocation:qbo:Payment:PAY-APPLIED:1"
        )
        assert expected in [g["missing_lookup_key"] for g in ar["gaps"]]
        assert result["status"] == "incomplete"
    else:
        assert result["status"] == "complete"
        refs = ar["unapplied_credits"]["contributions"][0]["source_refs"]
        assert refs == [
            "qbo:CreditMemo:CM-BOUNDARY",
            "qbo:Payment:PAY-APPLIED:1",
            "qbo:RefundReceipt:RR-BOUNDARY",
            "qbo:RefundReceipt:RR-SECOND",
        ]
    assert all(
        "raw" in raw[k] for k in report.collect_refs(result) if k.startswith("qbo:")
    )
    document = Document(report.render(result, raw))
    assert all(link[1:] in document.ids for link in document.links)


@pytest.mark.parametrize("other_credit", [False, True])
def test_raw_disagreeing_direct_and_event_credit_identity_is_not_consumed(other_credit):
    files = generate("clean")

    def mutate(qbo):
        credit = qbo["CreditMemo"][0]
        credit.update(AppliedAmount="0.00", RevenueEvent="EV-A")
        refund = qbo["RefundReceipt"][0]
        refund["RevenueEvent"] = "EV-B"
        refund["LinkedTxn"] = [
            {"TxnType": "Invoice", "TxnId": "I-CREDIT"},
            {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"},
        ]
        if other_credit:
            other = copy.deepcopy(credit)
            other.update(Id="CM-OTHER", RevenueEvent="EV-B")
            qbo["CreditMemo"].append(other)

    change(files, "qbo.json", mutate, count=True)
    result, raw = run(files)
    ar = result["kpis"]["AR"]
    assert ar["status"] == "partial"
    assert ar["unapplied_credits"]["value"] is None
    assert ar["unapplied_credits"]["known_value"] == (
        "200.00" if other_credit else "100.00"
    )
    assert ar["known_value"] == "960.01"
    assert ar["unapplied_cash"]["known_value"] == "25.01"
    assert result["kpis"]["revenue"]["value"] is None
    assert any(g["missing_lookup_key"].startswith("refund_credit:") for g in ar["gaps"])
    assert result["status"] == "incomplete"
    document = Document(report.render(result, raw))
    assert all(link[1:] in document.ids for link in document.links)


@pytest.mark.parametrize("credit_day", ["2026-11-02", "2026-11-03"])
@pytest.mark.parametrize("identity", ["direct", "event", "both"])
@pytest.mark.parametrize(
    "mode",
    [
        "duplicate40",
        "duplicate20",
        "other_invoice",
        "cash_sale",
        "distinct",
        "standalone",
    ],
)
def test_raw_shared_refund_identity_policy(credit_day, identity, mode):
    files = generate("clean")

    def mutate(qbo):
        credit = copy.deepcopy(qbo["CreditMemo"][0])
        credit.update(
            Id="CM-X",
            TotalAmt="20.00" if mode == "duplicate20" else "40.00",
            AppliedAmount="0.00",
            TxnDate=credit_day,
            EventAt="2026-11-02T12:00:00+00:00",
        )
        credit["Line"][0]["Amount"] = credit["TotalAmt"]
        credit["LinkedTxn"] = [{"TxnType": "Invoice", "TxnId": "I-PAY"}]
        if identity != "direct":
            credit["RevenueEvent"] = "EV-X"
        if mode != "standalone":
            qbo["CreditMemo"].append(credit)
        refund = copy.deepcopy(qbo["RefundReceipt"][0])
        refund.update(Id="RR-X", TotalAmt="20.00", RevenueEvent="EV-X")
        refund["Line"][0]["Amount"] = "20.00"
        refund["LinkedTxn"] = [
            {
                "TxnType": "SalesReceipt" if mode == "cash_sale" else "Invoice",
                "TxnId": "SR-ORIGINAL"
                if mode == "cash_sale"
                else "I-OUT"
                if mode == "other_invoice"
                else "I-PAY",
            }
        ]
        if identity != "event" and mode != "standalone":
            refund["LinkedTxn"].append({"TxnType": "CreditMemo", "TxnId": "CM-X"})
        qbo["RefundReceipt"].append(refund)
        if mode in {"duplicate40", "duplicate20", "distinct", "standalone"}:
            other = copy.deepcopy(refund)
            other["Id"] = "RR-Y"
            if mode == "distinct":
                other["TotalAmt"] = other["Line"][0]["Amount"] = "10.00"
            qbo["RefundReceipt"].append(other)
        qbo["RefundReceipt"].reverse()

    change(files, "qbo.json", mutate, count=True)
    result, raw = run(files)
    revenue, ar = result["kpis"]["revenue"], result["kpis"]["AR"]
    ambiguous = mode not in {"distinct", "standalone"}
    assert result["alerts"] == []
    assert result["status"] == ("incomplete" if ambiguous else "complete")
    for sheet in [revenue, ar, ar["unapplied_credits"], ar["unapplied_cash"]]:
        assert sheet["status"] == ("partial" if ambiguous else "complete")
        assert (sheet["value"] is None) == ambiguous
    assert ar["known_value"] == "860.01"
    assert ar["unapplied_cash"]["known_value"] == "25.01"
    assert ar["unapplied_credits"]["known_value"] == (
        "20.00"
        if mode == "duplicate20"
        else "40.00"
        if ambiguous
        else "10.00"
        if mode == "distinct"
        else "0.00"
    )
    if ambiguous:
        keys = ["qbo:RefundReceipt:RR-X"] + (
            ["qbo:RefundReceipt:RR-Y"] if mode.startswith("duplicate") else []
        )
        expected = [
            {
                "missing_lookup_key": "consistent_adjustment_event:" + key,
                "source_refs": sorted(["qbo:CreditMemo:CM-X", *keys]),
            }
            for key in keys
        ]
        assert revenue["gaps"] == expected
        assert ar["gaps"] == expected
    else:
        assert revenue["value"] == (
            "1230.02"
            if mode == "standalone"
            else "1210.02"
            if credit_day == "2026-11-03"
            else "1250.02"
        )
    document = Document(report.render(result, raw))
    assert len(document.ids) == len(set(document.ids))
    assert all(link[1:] in document.ids for link in document.links)
    assert all(
        "raw" in raw[ref]
        for ref in report.collect_refs(result)
        if ref.startswith("qbo:RefundReceipt:RR-")
    )


@pytest.mark.parametrize("opening", ["valid", "invalid", "credit_at_cutoff"])
@pytest.mark.parametrize("second", ["24.00", "25.00", "26.00"])
def test_raw_revenue_credit_capacity_independent_of_opening_ar(opening, second):
    files = generate("clean")

    def mutate(qbo):
        credit = copy.deepcopy(qbo["CreditMemo"][0])
        credit.update(
            Id="CM-X",
            TotalAmt="40.00",
            AppliedAmount="0.00",
            RevenueEvent="EV-X",
            TxnDate="2026-11-02",
            EventAt="2026-10-26T07:00:00+00:00"
            if opening == "credit_at_cutoff"
            else "2026-11-02T12:00:00+00:00",
            LinkedTxn=[{"TxnType": "Invoice", "TxnId": "I-PAY"}],
        )
        credit["Line"][0]["Amount"] = "40.00"
        qbo["CreditMemo"].append(credit)
        for name, amount, when in [
            ("RR-A", "15.00", "2026-11-03T12:00:00+00:00"),
            ("RR-B", second, "2026-11-03T13:00:00+00:00"),
        ]:
            refund = copy.deepcopy(qbo["RefundReceipt"][0])
            refund.update(
                Id=name,
                TotalAmt=amount,
                RevenueEvent="EV-X",
                EventAt=when,
                LinkedTxn=[{"TxnType": "Invoice", "TxnId": "I-PAY"}],
            )
            refund["Line"][0]["Amount"] = amount
            qbo["RefundReceipt"].append(refund)

    change(files, "qbo.json", mutate, count=True)
    if opening == "invalid":
        change(files, "opening_ar.json", lambda data: data.update(as_of="invalid"))
    result, raw = run(files)
    revenue = result["kpis"]["revenue"]
    partial = second == "26.00" or opening == "credit_at_cutoff"
    assert revenue["status"] == ("partial" if partial else "complete")
    assert revenue["value"] == (None if partial else "1250.02")
    assert revenue["known_value"] == "1250.02"
    if second == "26.00":
        gaps = [
            g
            for g in revenue["gaps"]
            if g["missing_lookup_key"]
            == "refund_credit_capacity:qbo:RefundReceipt:RR-B"
        ]
        assert gaps == [
            {
                "missing_lookup_key": "refund_credit_capacity:qbo:RefundReceipt:RR-B",
                "source_refs": [
                    "qbo:CreditMemo:CM-X",
                    "qbo:RefundReceipt:RR-A",
                    "qbo:RefundReceipt:RR-B",
                ],
            }
        ]
    if opening == "credit_at_cutoff":
        assert any(
            g["missing_lookup_key"] == "opening_credit_capacity:qbo:CreditMemo:CM-X"
            for g in revenue["gaps"]
        )
    if opening == "invalid":
        assert result["kpis"]["AR"]["status"] == "unavailable"
    document = Document(report.render(result, raw))
    assert all(link[1:] in document.ids for link in document.links)
    assert all(
        "raw" in raw[k] for k in report.collect_refs(result) if k.startswith("qbo:")
    )
