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
    assert "Data status" in front and "Last updated Nov 04, 2026" in front
    assert "America/Denver" in front
    assert front.count('<article class="kpi">') == 4
    assert front.count("See source records") == len(result["checks"]["findings"])
    assert front.count("Prior business day comparisons are not computed") == 1
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


def test_showcase_independent_five_exception_oracle_and_totals():
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
        ("C05", "150.00", "100.00", "50.00"),
    ]
    assert {k: s["value"] for k, s in result["kpis"].items()} == {
        "delivered": "600.005",
        "retail": "55.000",
        "total_gallons": "655.005",
        "revenue": "1290.02",
        "AR": "810.01",
    }
    text = report.render(result, run(generate("showcase"))[1])
    assert (
        "Tuesday, Nov 3: 5 items need your attention. All sources up to date." in text
    )
    assert "Delivery #1042 to Rio Grande Ranch" in text
    assert "$1,290.02" in text and "30 gal below" in text


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
    result, raw = run(generate("P01"))
    raw[result["prioritized_findings"][0]["source_refs"][0]]["raw"]["customer_id"] = (
        "<script>alert(1)</script>"
    )
    assert "<script>" not in report.render(result, raw)


def test_money_impact_uses_computed_delta_and_no_invented_total():
    assert report.formatted("1234567.89", "USD") == "$1,234,567.89"
    assert report.formatted("-30.000", "gal") == "-30 gal"
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
        "Tank reading is 30 gal above the expected amount."
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
    assert "POS: source import failed</h3>" in text
    assert "QuickBooks: source coverage is out of date</h3>" in text
    assert "manifest:POS-FAILED</h3>" not in text
    assert "manifest:QBO-STALE</h3>" not in text


def test_source_status_labels_and_consistent_denver_times():
    result, raw = run(generate("showcase"))
    status = report.business_sections(result, raw).split('<section id="data-status">')[
        1
    ]
    assert status.count("QuickBooks</strong>") == 1
    assert status.count("<li>") == 5
    assert "Covered through Nov 04, 2026 12:00 AM MST" in status
    assert "Last updated Nov 04, 2026 06:12 AM MST" in status
    assert "2026-11-04T00:00:00-07:00" not in status
    assert report.denver_time("2026-07-04T07:00:00+00:00") == (
        "Jul 04, 2026 01:00 AM MDT"
    )
    assert report.denver_time(None) == "time unavailable"
    assert report.denver_time(None, "not available") == "not available"


def test_duplicate_card_uses_computed_record_count_without_inventing_money():
    result, raw = run(generate("showcase"))
    finding = next(f for f in result["prioritized_findings"] if f["check_id"] == "C03")
    assert report.impact(finding).startswith("2 records share a source or external")
    assert "$" not in report.impact(finding)
    assert report.impact(finding) in report.business_sections(result, raw)


def test_detector_evidence_uses_existing_repository_relative_paths():
    root = Path(__file__).resolve().parents[1]
    records = json.loads(
        (root / ".ai/qa/2026-11-05-report/design-detector.json").read_text()
    )
    assert len(records) == 5
    for record in records:
        path = Path(record["file"])
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert (root / path).is_file()


def test_owner_showcase_readability_and_no_raw_identifiers_in_closed_cards():
    result, raw = run(generate("showcase"))
    assert [f["severity"] for f in result["prioritized_findings"]] == ["high"] * 4 + [
        "medium"
    ]
    text = report.business_sections(result, raw)
    assert "600 gal" in text and "55 gal" in text
    assert "Approximately $200.00 not billed" in text
    assert "Potential duplicate net sales: $20.00" in text
    assert "No unit cost is supplied" in text
    assert "Credit #3105 for Rio Grande Ranch" in text
    for title in text.split("<h3>")[1:]:
        title = title.split("</h3>")[0]
        assert not any(
            raw_id in title
            for raw_id in (
                "D-MISSING",
                "CE-C1",
                "T-DUP-A",
                "POS-C1",
                "R-CLOSE",
                "BULK-A",
            )
        )
    assert "600.005" in report.render(result, raw)  # Exact worksheet stays available.
    assert report.formatted("12345.6", "US gallons") == "12,346 gal"


def test_grouped_sources_keep_worst_state_and_oldest_known_watermark():
    result, _ = run()
    result["freshness"] = [
        {
            "source": "qbo",
            "status": "success",
            "extracted_at": "2026-11-04T06:20:00-07:00",
            "covered_through": "2026-11-04T00:00:00-07:00",
        },
        {
            "source": "qbo",
            "status": "stale",
            "extracted_at": "2026-11-04T06:10:00-07:00",
            "covered_through": "2026-11-02T23:00:00-07:00",
        },
    ]
    assert report.source_groups(result) == [
        {
            "label": "QuickBooks",
            "status": "stale",
            "extracted_at": "2026-11-04T06:10:00-07:00",
            "covered_through": "2026-11-02T23:00:00-07:00",
        }
    ]
    result["freshness"][0]["status"] = "failed"
    assert report.source_groups(result)[0]["status"] == "failed"


@pytest.mark.parametrize("labels", [[], {"one": 1}, {"": "name"}])
def test_invalid_fixture_display_labels_are_rejected(labels):
    from propane_demo.ingestion import ingest
    from propane_demo.validation import Invalid

    files = generate("clean")
    control = json.loads(files["run.json"])
    control["report_labels"] = labels
    files["run.json"] = json.dumps(control).encode()
    with pytest.raises(Invalid):
        ingest(files.__getitem__)
