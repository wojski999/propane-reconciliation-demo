"""Business-reader presentation over authoritative computed results."""

import copy
import json
from pathlib import Path

import pytest
from test_business_report import Document, run

from propane_demo import report
from propane_demo.generator import generate


@pytest.mark.parametrize("scenario", ["clean", "showcase", "issues", "P05", "P06"])
def test_business_reader_sections_preserve_computed_evidence(scenario):
    result, raw = run(generate(scenario))
    before = copy.deepcopy((result, raw))
    text = report.render(result, raw)
    front, technical = text.split('<details class="technical"', 1)
    assert (result, raw) == before
    assert "Needs attention today" in front and "Your business at a glance" in front
    assert "Data status" in front and "Last updated Nov 04, 2026 12:00 AM MST" in front
    assert "America/Denver" in front
    assert front.count('<article class="kpi">') == 4
    assert front.count("See source records") == len(result["checks"]["findings"])
    assert "Prior business day comparison not computed" in front
    for key in ("delivered", "retail", "revenue", "AR"):
        sheet = result["kpis"][key]
        assert (
            (report.formatted(sheet["value"], sheet["unit"]) in front)
            if sheet["value"] is not None
            else (report.unavailable_reason(sheet, result) in front)
        )
    assert "Signed calculation worksheets" in technical
    assert "Immutable source evidence" in technical
    assert "Source digest" in technical
    assert "Rule version" in technical
    assert "<summary>Technical details" in technical
    assert not technical.startswith(" open")
    parsed = Document(text)
    assert len(parsed.ids) == len(set(parsed.ids))
    assert all(link[1:] in parsed.ids for link in parsed.links)
    assert not parsed.assets and "script" not in parsed.tags
    assert text.count("<h1>") == 1


def test_showcase_independent_four_exception_oracle_and_totals():
    result, _ = run(generate("showcase"))
    assert result["status"] == "complete"
    assert result["alerts"] == []
    assert all(s["status"] == "success" for s in result["freshness"])
    # Independent hand calculations from the four planted source mutations:
    # 100 unbilled gal; 2 same-reference sales; $460 - $470 deposit; 1020 - 1050 gal.
    assert [
        (f["check_id"], f["actual"], f["expected"], f["delta"])
        for f in result["prioritized_findings"]
    ] == [
        ("C01", "100.000", "0.000", "100.000"),
        ("C03", "2", "1", "1"),
        ("C07", "460.00", "470.00", "-10.00"),
        ("C08", "1020.000", "1050.000", "-30.000"),
    ]
    assert {k: s["value"] for k, s in result["kpis"].items()} == {
        "delivered": "600.005",
        "retail": "55.000",
        "total_gallons": "655.005",
        "revenue": "1290.02",
        "AR": "860.01",
    }
    text = report.render(result, run(generate("showcase"))[1])
    assert (
        "Tuesday, Nov 3: 4 items need your attention. All sources up to date." in text
    )
    assert "D-MISSING · CE-C1" in text
    assert "$1,290.02" in text and "30.000 gal below" in text


def test_unavailable_is_not_replaced_by_known_contributions():
    result, raw = run(generate("issues"))
    for sheet in result["kpis"].values():
        assert sheet["value"] is None
        sheet["known_value"] = "987654321.00"
    front = report.business_sections(result, raw)
    assert "987,654,321" not in front and "987654321" not in front
    assert "POS import failed" in front
    assert "QuickBooks coverage is out of date" in front
    assert "Totals unavailable: Delivered gallons" in front
    assert "Required source records or mappings are missing" in front
    assert "Report incomplete" in front
    assert "No dollar or gallon conclusion" in front


def test_missing_times_unknown_sources_and_hostile_record_text():
    result, raw = run()
    result["freshness"] = [
        {
            "source": '<img src=x onerror="bad">',
            "status": "failed",
            "source_refs": ["manifest:X"],
        },
        {"source": "qbo", "status": "stale", "source_refs": ["manifest:Y"]},
    ]
    sheet = {"gaps": [{"source_refs": ["manifest:X", "manifest:Y"]}]}
    assert "import failed" in report.unavailable_reason(sheet, result)
    front = report.business_sections(result, raw)
    assert (
        "Last updated time unavailable" in front
        and "Covered through not available" in front
    )
    assert "<img" not in front and "&lt;img" in front
    finding = {"source_refs": ["one", "two", "three", "four", "five", "six"]}
    records = {
        "one": {"raw": {"Id": "I-X", "CustomerRef": {"value": "<script>bad</script>"}}},
        "two": {"raw": []},
        "three": {"raw": {}},
        "four": {
            "raw": {"Id": "I-X", "CustomerRef": {"value": "<script>bad</script>"}}
        },
        "five": {"raw": {"transaction_id": "T-1", "customer_id": "C-1"}},
        "six": {"raw": {"reading_id": "R-1", "asset_id": "TANK-1"}},
    }
    assert report.record_context(finding, records).count("I-X") == 1
    assert "T-1 · C-1" in report.record_context(finding, records)
    assert "TANK-1" in report.record_context(finding, records)
    assert report.record_context({"source_refs": ["missing"]}, {}) == "missing"
    result, raw = run(generate("P01"))
    raw[result["prioritized_findings"][0]["source_refs"][0]]["raw"]["customer_id"] = (
        "<script>alert(1)</script>"
    )
    assert "<script>" not in report.render(result, raw)


def test_money_impact_uses_computed_delta_and_no_invented_total():
    assert report.formatted("1234567.89", "USD") == "$1,234,567.89"
    assert report.formatted("-30.000", "gal") == "-30.000 gal"
    for check in ("C04", "C06", "C12"):
        assert report.impact({"check_id": check, "delta": "-10.00"}).startswith(
            "-$10.00"
        )


def test_committed_samples_are_deterministic():
    from propane_demo.narrative import build

    root = Path(__file__).resolve().parents[1] / "samples"
    for scenario in ("clean", "issues", "showcase"):
        result, raw = run(generate(scenario))
        kwargs = (
            {
                "illustrative": json.loads(
                    (root / "issues-illustrative-narrative.json").read_text()
                )
            }
            if scenario == "issues"
            else {}
        )
        narrative = build(result, **kwargs)
        assert (root / f"{scenario}-report.html").read_text() == report.render(
            result, raw, narrative_status=narrative
        )
        assert json.loads((root / f"{scenario}-results.json").read_text()) == result
        assert (root / f"{scenario}-summary.txt").read_text() == report.summary(
            result
        ) + "\n"


def test_directional_inventory_and_deposit_impact():
    assert report.impact({"check_id": "C08", "delta": "30.000"}) == (
        "Tank reading is 30.000 gal above the expected amount."
    )
    assert report.impact({"check_id": "C07", "delta": "10.00"}) == (
        "Deposit is $10.00 above the expected amount."
    )
    assert report.impact(
        {
            "check_id": "C05",
            "delta": "50.00",
            "actual": "150.00",
            "source_refs": ["qbo:CreditMemo:CM-1:1"],
        }
    ) == ("$150.00 adjustment flagged for review.")


def test_repeated_manifest_failure_is_explained_once():
    source = {
        "source": "qbo",
        "status": "failed",
        "source_refs": ["manifest:QBO"],
    }
    sheet = {"gaps": [{"source_refs": ["manifest:QBO"]}]}
    assert report.unavailable_reason(sheet, {"freshness": [source, source]}) == (
        "QuickBooks import failed"
    )


def test_source_failure_cards_name_the_business_system():
    result, raw = run(generate("issues"))
    text = report.business_sections(result, raw)
    assert "Source import failed: POS</h3>" in text
    assert "Source coverage is out of date: QuickBooks</h3>" in text
    assert "manifest:POS-FAILED</h3>" not in text
    assert "manifest:QBO-STALE</h3>" not in text
    assert (
        report.record_context(
            {"source_refs": ["manifest:UNKNOWN"]}, {"manifest:UNKNOWN": {"raw": {}}}
        )
        == "Source records"
    )
