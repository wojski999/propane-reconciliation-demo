"""Business-reader presentation over authoritative computed results."""

import copy
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from test_business_report import Document, run

from propane_demo import business, report
from propane_demo.generator import DEFAULT_DATE, DEFAULT_SEED, generate
from propane_demo.presentation import prior_changes


@pytest.mark.parametrize("scenario", ["clean", "showcase", "issues", "P05", "P06"])
def test_business_reader_sections_preserve_computed_evidence(scenario):
    result, raw = run(generate(scenario))
    before = copy.deepcopy((result, raw))
    text = report.render(result, raw)
    front, technical = text.split('<details class="technical"', 1)
    assert (result, raw) == before
    assert "Needs attention today" in front and "money flow" in front
    assert "Data sources" in front and "last updated Nov 04, 2026" in front
    assert "America/Denver" in front
    assert front.count("See calculation") == 5
    assert front.count("See source records") == len(result["checks"]["findings"])
    assert front.count("Prior business day comparison is not available") == 1
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
        "last updated time unavailable" in front
        and "covered through not available" in front
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
    prior = business.baseline(DEFAULT_SEED, DEFAULT_DATE)
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
            result,
            raw,
            narrative_status=narrative,
            changes=prior_changes(result, prior),
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
    status = report.business_sections(result, raw).split('id="data-sources"')[1]
    assert status.count("QuickBooks · ") == 1
    assert status.count("<li>") == 5
    assert "covered through Nov 04, 2026 12:00 AM MST" in status
    assert "last updated Nov 04, 2026 06:12 AM MST" in status
    assert "QuickBooks · 6:12 AM" in status
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


def test_prior_day_changes_compare_only_complete_consecutive_values():
    prior = business.baseline(DEFAULT_SEED, DEFAULT_DATE)
    result, _ = run(generate("showcase"))
    changes = prior_changes(result, prior)
    # Clean Nov 2 baseline: +$40 duplicate sale, -$50 applied credit, volume flat.
    assert {k: v["change"] for k, v in changes.items()} == {
        "delivered": "0.000",
        "retail": "0.000",
        "total_gallons": "0.000",
        "revenue": "40.00",
        "AR": "-50.00",
    }
    assert changes["AR"]["prior_business_date"] == "2026-11-02"
    assert prior_changes(result, None) == {}
    assert prior_changes(result, result) == {}  # Not the prior business day.
    assert prior_changes(result, prior | {"gallon_basis": "observed"}) == {}
    other = copy.deepcopy(prior)
    other["kpis"]["AR"]["value"] = None
    other["kpis"]["retail"]["unit"] = "USD"
    del other["kpis"]["revenue"]
    assert set(prior_changes(result, other)) == {"delivered", "total_gallons"}
    issues, _ = run(generate("issues"))
    assert prior_changes(issues, prior) == {}
    assert business.baseline(DEFAULT_SEED, date(2020, 1, 1)) is None
    assert report.change_text(None) == ""
    assert report.change_text(changes["delivered"]) == "No change vs. Nov 2"
    assert report.change_text(changes["revenue"]) == "▲ $40.00 vs. Nov 2"
    assert report.change_text(changes["AR"]) == "▼ $50.00 vs. Nov 2"
    text = report.render(result, run(generate("showcase"))[1], changes=changes)
    front, technical = text.split('<details class="technical"', 1)
    assert "▼ $50.00 vs. Nov 2" in front and "▲ $40.00 vs. Nov 2" in front
    assert "Prior business day comparison is not available" not in front
    assert "&quot;prior&quot;: &quot;860.01&quot;" in technical
    assert (
        "Baseline: the synthetic clean scenario on the prior business day" in technical
    )


def test_mockup_v2_shell_flow_table_drawer_and_pilot_controls():
    result, raw = run(generate("showcase"))
    text = report.render(result, raw)
    front = text.split('<details class="technical"', 1)[0]
    parsed = Document(text)
    assert len(parsed.ids) == len(set(parsed.ids))
    assert all(link[1:] in parsed.ids for link in parsed.links)
    # Sidebar, top bar and inactive controls are visibly marked, never faked.
    assert front.count("<small>Pilot</small>") == 6
    assert front.count('aria-disabled="true"') == 6 + 2 + 2 * 5
    assert "Pilot features · not active in this demo" in front
    assert front.count("Pilot feature · not saved") == 5
    assert 'Exceptions<span class="n">5</span>' in front
    assert "Tue, Nov 3" in front and "Data as of 6:30 AM" in front
    assert "About <b>$380.00</b> across 4 flagged items needs a decision" in front
    assert "not booked amounts" in front
    assert '<span class="b" aria-disabled="true">Mark as resolved</span>' in front
    # Money flow: authoritative KPIs, AR cash allocations and the C07 difference.
    for value in ("600 gal", "$1,290.02", "$300.00", "$460.00"):
        assert f'<p class="v">{value}</p>' in front
    assert "2 payment allocations since Oct 26" in front
    assert "10 completed deliveries" in front and "21 sales lines" in front
    assert '<span class="chip ok">All matched</span>' in front
    assert 'href="#x-0">Not billed · ~$200.00</a>' in front
    assert 'href="#x-1">Possible duplicate · ~$20.00</a>' in front
    assert 'href="#x-2">Deposit differs · $10.00</a>' in front
    assert 'href="#x-4">Credit to review · $150.00</a>' in front
    assert "30 gal unexplained" in front and "5 of 5 tanks and trucks" in front
    # Table: filters, systems, right-aligned impacts; first drawer is the default.
    assert 'href="#attention">All 5</a><a href="#f-high">High 4</a>' in front
    assert '<a href="#f-medium">Medium 1</a>' in front
    assert "Cargas → QuickBooks" in front and "Card processor → QuickBooks" in front
    assert '<td class="src">Tank readings</td>' in front
    assert front.count('<aside class="card drawer"') == 5
    assert (
        "No matching record</strong><br>Searched QuickBooks invoice lines "
        "for delivery #1042 to Rio Grande Ranch." in front
    )
    assert "QuickBooks · invoice line" in front and "Looked up by" not in front
    assert "Flags any delivered gallons left unbilled after the grace period" in front
    assert '<span class="tag">C01</span>' in front and "threshold 0.001" not in front
    assert "<dt>Customer</dt><dd>Rio Grande Ranch</dd>" in front
    assert "<dt>Delivered</dt><dd>Nov 2, 6:00 PM MT</dd>" in front
    assert "<dt>Gallons</dt><dd>100.0</dd>" in front
    assert "<dt>Invoice</dt><dd>—</dd>" in front
    assert "customer_id" not in front and "2026-11-03T01:00:00" not in front
    assert "See deposit</a>" in front
    style = text.split("</style>", 1)[0]
    assert ".split:not(:has(.drawer:target)) .drawer:first-child" in style
    assert "#f-high:target~.tbl tr.row:not(.s-high){display:none}" in style
    assert ".split:has(#x-4:target) .r-4 td" in style
    assert "@media(max-width:760px)" in style and "@media print" in style
    assert "Data sources" in front and "Tank readings · 5:50 AM" in front


def test_unavailable_flow_and_inventory_never_show_partial_amounts():
    result, raw = run(generate("issues"))
    front = report.business_sections(result, raw)
    assert front.count("Not fully checked") == 5  # Four stages plus inventory.
    assert '<p class="v unavailable">POS import failed; QuickBooks' in front
    assert "$" not in front.split('class="flow">')[1].split("</section>")[0]
    assert '<a href="#f-critical">Critical 1</a>' in front
    clean, clean_raw = run(generate("clean"))
    front = report.business_sections(clean, clean_raw)
    assert "Reconciled" in front and front.count("All matched") == 4
    assert "No business exceptions found" in front and "<table>" not in front
    assert '<p class="v">$470.00</p>' in front
    assert "1 card deposit dated Oct 29 in QuickBooks" in front
    clean["freshness"] = [
        s for s in clean["freshness"] if s["source"] not in {"readings", "inventory"}
    ]
    del clean["kpis"]["AR"]["opening_cutoff"]
    front = report.business_sections(clean, clean_raw)
    assert "2 payment allocations</p>" not in front
    assert "2 payment allocations <a" in front and "· readings" not in front


def test_impact_amounts_systems_times_and_record_cards():
    result, raw = run(generate("showcase"))
    by_check = {f["check_id"]: f for f in result["prioritized_findings"]}
    assert report.impact_amount(by_check["C01"], result) == ("~$200.00", 200)
    assert report.impact_amount(by_check["C08"], result) == ("30 gal", None)
    assert report.impact_amount(by_check["C05"], result)[0] == "$150.00"
    bare = {"finding_id": "x", "source_refs": [], "actual": "1"}
    assert report.impact_amount(bare | {"check_id": "C04", "delta": "-2.50"}, result)[
        1
    ] == Decimal("2.50")
    assert report.impact_amount(
        bare | {"check_id": "C05", "delta": "5.00"}, result
    ) == (
        "—",
        None,
    )
    assert report.impact_amount(bare | {"check_id": "C09", "delta": None}, result) == (
        "—",
        None,
    )
    assert report.system_name("manifest:QBO-OK", result) == "QuickBooks"
    assert report.system_name("weird:thing", result) == "weird"
    assert report.short_time(None, result["display_as_of"]) == "time unavailable"
    assert (
        report.short_time("2026-11-04T04:10:00+00:00", result["display_as_of"])
        == "Nov 3, 9:10 PM"
    )
    finding = by_check["C07"] | {"source_refs": ["file:pos.csv#1", "run:x:y"]}
    cards = report.record_cards(finding, result, raw | {"run:x:y": {"raw": "text"}})
    assert cards.count('<div class="doc">') == 2 and "<dl>" not in cards
    assert "<strong>y</strong>" in cards


def test_hostile_record_fields_and_labels_are_escaped_in_drawers():
    result, raw = run(generate("showcase"))
    ref = result["prioritized_findings"][0]["source_refs"][0]
    raw[ref]["raw"]["customer_id"] = "<b onmouseover=x>"
    result["run"]["report_labels"][ref] = "<i>label</i>"
    text = report.business_sections(result, raw)
    assert "<b onmouseover" not in text and "&lt;b onmouseover=x&gt;" in text
    assert "<i>label" not in text and "&lt;i&gt;label&lt;/i&gt;" in text


def test_card_deposits_are_linked_active_and_unavailable_when_unchecked():
    from propane_demo.ingestion import ingest
    from propane_demo.presentation import card_deposits
    from propane_demo.rule_inputs import from_database, reconcile_database

    db = ingest(generate("showcase").__getitem__)
    try:
        inputs, checks = from_database(db), reconcile_database(db)
    finally:
        db.close()
    # Hand check: deposit DEP-SHORT totals 46000 cents for card batch B-SETTLED.
    assert card_deposits(inputs, checks) == {
        "value": "460.00",
        "count": 1,
        "dates": ["2026-10-29"],
        "source_refs": ["qbo:Deposit:DEP-SHORT"],
    }
    records = inputs["records"]
    records["qbo:Deposit:DEP-SHORT"]["status"] = "void"
    records["pos:batch:B-EMPTY"] = {"qbo_deposit_id": ""}
    assert card_deposits(inputs, checks) == {
        "value": "0.00",
        "count": 0,
        "dates": [],
        "source_refs": [],
    }
    checks["not_evaluated"]["C07:x"] = {"status": "not_evaluated"}
    assert card_deposits(inputs, checks) is None
    result, raw = run(generate("showcase"))
    result["card_deposits"] = {
        "value": "900.00",
        "count": 2,
        "dates": ["2026-11-02", "2026-11-03"],
        "source_refs": ["qbo:Deposit:DEP-SHORT", "qbo:Deposit:X"],
    }
    assert report.stage_value(None, result)[2] == (
        "2 card deposits dated Nov 2, Nov 3 in QuickBooks"
    )
    result["card_deposits"] = {
        "value": "0.00",
        "count": 0,
        "dates": [],
        "source_refs": [],
    }
    assert report.stage_value(None, result) == (
        "$0.00",
        "",
        "0 card deposits in QuickBooks",
        None,
    )
    result["card_deposits"] = None
    assert report.stage_value(None, result)[1] == " unavailable"


def test_business_field_formatting_thresholds_and_unnamed_missing_records():
    labels = {"pos:customer:C-9": "Mesa Diner"}
    assert report.field_value("customer", "C-9", "pos:POS:T-1:1", labels) == (
        "Mesa Diner"
    )
    assert report.field_value("customer", "C-8", "pos:POS:T-1:1", labels) == "C-8"
    assert report.field_value("text", None, "x", {}) == "—"
    assert report.field_value("usd", "1234.5", "x", {}) == "$1,234.50"
    assert report.field_value("gal", "1234.56", "x", {}) == "1,234.6"
    assert report.field_value("time", "2026-07-04T19:05:00+00:00", "x", {}) == (
        "Jul 4, 1:05 PM MT"
    )
    assert report.field_value("text", "valid", "x", {}) == "valid"

    def limit(check, threshold):
        return report.threshold_text({"check_id": check, "threshold": threshold})

    assert limit("C03", "1") == "more than one record with the same reference"
    assert limit("C09", "24") == "source coverage older than 24 hours"
    assert limit("C08", "6.000") == "differences over 6.0 gal"
    assert limit("C05", "100.00") == "credits or discounts over $100.00"
    assert limit("C05", "original required") == (
        "credits or refunds without the original sale"
    )
    assert limit("C07", "0.01") == "differences over $0.01"
    result, raw = run(generate("issues"))
    finding = {
        "check_id": "C11",
        "source_refs": [],
        "missing_reference": {
            "system": "identity",
            "type": "customer/item",
            "lookup_key": "customer:UNKNOWN",
        },
    }
    cards = report.record_cards(finding, result, raw)
    assert "Searched Mappings customer and item mappings." in cards
    finding["missing_reference"]["type"] = "Odd.Type"
    assert "Searched Mappings odd.type." in report.record_cards(finding, result, raw)
