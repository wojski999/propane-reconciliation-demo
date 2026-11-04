"""Step-4 raw boundary tests and independent signed inventory arithmetic."""

import csv
import io
import json
from datetime import date, datetime, timedelta
from decimal import Decimal as D

import pytest

from propane_demo.generator import generate
from propane_demo.ingestion import ingest
from propane_demo.rule_inputs import reconcile_database


def exports(scenario="clean", day=date(2026, 11, 3)):
    files = generate(scenario, business_date=day)
    return {
        name: list(csv.DictReader(io.StringIO(raw.decode())))
        if name.endswith(".csv")
        else json.loads(raw)
        for name, raw in files.items()
    }


def imported(data):
    files = {}
    for name, value in data.items():
        if name.endswith(".csv"):
            out = io.StringIO(newline="")
            writer = csv.DictWriter(out, fieldnames=list(value[0]))
            writer.writeheader()
            writer.writerows(value)
            files[name] = out.getvalue().encode()
        else:
            files[name] = json.dumps(value).encode()
    for manifest in data["manifests.json"]:
        name = manifest["file_id"]
        if name.endswith(".csv"):
            manifest["row_count"] = str(len(data[name]))
    files["manifests.json"] = json.dumps(data["manifests.json"]).encode()
    return ingest(files.__getitem__)


def compute(data):
    db = imported(data)
    try:
        return reconcile_database(db)
    finally:
        db.close()


def findings(result, check):
    return [f for f in result["findings"] if f["check_id"] == check]


def shift(value, **kwargs):
    return (datetime.fromisoformat(value) + timedelta(**kwargs)).isoformat()


def test_signed_worksheet_and_whole_business_transfer_elimination():
    result = compute(exports("P08"))
    sheet = result["inventory"]["BULK-A"]
    assert (
        sheet["expected"],
        sheet["observed"],
        sheet["delta"],
        sheet["tolerance"],
    ) == ("1050.000", "1020.000", "-30.000", "6.000")
    assert [(c["kind"], c["gallons"]) for c in sheet["contributions"]] == [
        ("opening", "1000.000"),
        ("customer_delivery", "-100.000"),
        ("purchase", "200.000"),
        ("retail_sale", "-50.000"),
    ]
    assert all(
        c["source_refs"]
        for s in result["inventory"].values()
        for c in s["contributions"]
    )
    for s in result["inventory"].values():
        assert sum(D(c["gallons"]) for c in s["contributions"]) == D(s["expected"])
        assert D(s["observed"]) - D(s["expected"]) == D(s["delta"])
    whole = result["consolidation"]
    assert (whole["expected"], whole["observed"], whole["delta"]) == (
        "3245.000",
        "3220.000",
        "-25.000",
    )
    assert whole["eliminated_transfers"] == [
        "inventory:movement:M-TRANSFER-IN",
        "inventory:movement:M-TRANSFER-OUT",
    ]
    assert not any(c["kind"].startswith("transfer") for c in whole["contributions"])
    cylinder = next(
        c
        for c in result["inventory"]["ISOLATED"]["contributions"]
        if c["kind"] == "retail_sale"
    )
    assert cylinder["gallons"] == "-5.000"
    assert "identity:fill:CYLINDER" in cylinder["source_refs"]


@pytest.mark.parametrize(
    "gap,uncertainty,closing,uncertain,exception",
    [
        (60, "2.500", "1005.000", False, False),
        (60, "2.500", "1005.001", False, True),
        (60, "2.500", "994.999", False, True),
        (60, "2.501", "1005.001", True, False),
        (61, "2.500", "1005.001", True, False),
    ],
)
@pytest.mark.parametrize(
    "day", [date(2026, 3, 8), date(2026, 11, 1), date(2026, 11, 3)]
)
def test_raw_endpoint_uncertainty_and_tolerance_boundaries(
    day, gap, uncertainty, closing, uncertain, exception
):
    data = exports(day=day)
    row = next(r for r in data["readings.csv"] if r["reading_id"] == "R-BOUNDARY-CLOSE")
    row.update(
        gallons=closing,
        uncertainty_gallons=uncertainty,
        observed_at=shift(data["run.json"]["window_end"], minutes=-gap),
    )
    result = compute(data)
    found = findings(result, "C08")
    assert bool(found) == (uncertain or exception)
    if found:
        assert found[0]["status"] == ("sensor_uncertain" if uncertain else "exception")
        assert found[0]["severity"] == ("medium" if uncertain else "high")
        assert (found[0]["actual"] is None) == uncertain
    assert result["inventory"]["BOUNDARY"]["tolerance"] == "5.000"
    assert bool("C08:BOUNDARY" in result["not_evaluated"]) == uncertain


@pytest.mark.parametrize("quality", ["uncertain", "invalid"])
def test_quality_never_reports_shortage(quality):
    data = exports("P08")
    data["readings.csv"][1]["quality"] = quality
    result = compute(data)
    f = findings(result, "C08")[0]
    assert f["status"] == "sensor_uncertain" and f["actual"] is None
    assert result["consolidation"]["status"] == "unavailable"


@pytest.mark.parametrize(
    "hours,seconds,stale", [(24, 0, False), (24, 1, True), (25, 0, True)]
)
def test_watermark_not_fresh_extraction_and_persistence(hours, seconds, stale):
    data = exports()
    m = data["manifests.json"][0]
    m["covered_through"] = shift(
        data["run.json"]["as_of"], hours=-hours, seconds=-seconds
    )
    db = imported(data)
    try:
        result = reconcile_database(db)
        assert result == reconcile_database(db)
        assert len(findings(result, "C09")) == int(stale)
        assert db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == int(stale)
        assert bool("C01" in result["not_evaluated"]) == stale
        assert not findings(result, "C01")
        if stale:
            assert "C04:pos" in result["not_evaluated"]
            assert "C05:pos:POS:T-REFUND:1" in result["not_evaluated"]
            assert result["freshness_evaluated"] is True
    finally:
        db.close()


@pytest.mark.parametrize("seconds,failed", [(300, False), (301, True)])
def test_raw_future_extraction_limit_uses_c10_no_second_root(seconds, failed):
    data = exports("P10")
    data["manifests.json"][0]["extracted_at"] = shift(
        data["run.json"]["as_of"], seconds=seconds
    )
    result = compute(data)
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["check_id"] == ("C10" if failed else "C09")
    assert not findings(result, "C01")


@pytest.mark.parametrize(
    "source",
    [
        "qbo",
        "qbo_updates",
        "cargas",
        "readings",
        "pos",
        "settlements",
        "inventory",
        "prices",
        "identity",
        "ar",
    ],
)
def test_each_isolated_stale_source_suppresses_dependencies_without_false_counterparts(
    source,
):
    data = exports()
    m = next(m for m in data["manifests.json"] if m["source"] == source)
    m["covered_through"] = shift(data["run.json"]["as_of"], hours=-25)
    result = compute(data)
    assert [f["check_id"] for f in result["findings"]] == ["C09"]
    assert len(result["alerts"]) == 1
    assert result["not_evaluated"]


@pytest.mark.parametrize(
    "source",
    [
        "qbo",
        "cargas",
        "readings",
        "pos",
        "settlements",
        "inventory",
        "prices",
        "identity",
        "ar",
    ],
)
def test_each_isolated_failure_has_one_c10_root(source):
    data = exports()
    m = next(m for m in data["manifests.json"] if m["source"] == source)
    m.update(
        status="failed",
        error_code="EXTRACTION_FAILED",
        covered_through=shift(data["run.json"]["as_of"], hours=-25),
    )
    result = compute(data)
    assert [f["check_id"] for f in result["findings"]] == ["C10"]
    assert len(result["alerts"]) == 1
    assert result["not_evaluated"]


@pytest.mark.parametrize(
    "mutation,kind",
    [
        ("basis", "gallon_basis"),
        ("missing_basis", "gallon_basis"),
        ("unknown_fill", "sku_fill_gallons"),
        ("missing_pos", "movement_source"),
        ("missing_event", "pos_event"),
        ("missing_movement", "inventory_movement"),
        ("quantity", "movement_quantity_basis"),
        ("missing_pair", "transfer_pair"),
        ("pair_quantity", "transfer_pair"),
        ("pair_basis", "transfer_pair"),
        ("pair_asset", "transfer_pair"),
        ("duplicate_outflow", "unique_outflow"),
    ],
)
def test_inventory_missing_support_through_real_import(mutation, kind):
    data = exports()
    movements = data["movements.csv"]
    if mutation in {"basis", "missing_basis"}:
        data["readings.csv"][1]["gallon_basis"] = (
            "observed" if mutation == "basis" else ""
        )
    elif mutation == "unknown_fill":
        data["identity.json"]["sku_fill_gallons"] = {}
    elif mutation == "missing_pos":
        data["pos.csv"] = [
            r for r in data["pos.csv"] if r["transaction_id"] != "T-CYLINDER"
        ]
    elif mutation == "missing_event":
        data["identity.json"]["pos_events"] = [
            r
            for r in data["identity.json"]["pos_events"]
            if r["pos_id"] != "T-CYLINDER:1"
        ]
    elif mutation == "missing_movement":
        movements[:] = [m for m in movements if m["movement_id"] != "M-RETAIL"]
    elif mutation == "quantity":
        movements[1]["quantity"] = "99.999"
    elif mutation == "missing_pair":
        movements[:] = [m for m in movements if m["movement_type"] != "transfer_in"]
    elif mutation.startswith("pair_"):
        inbound = next(m for m in movements if m["movement_type"] == "transfer_in")
        inbound[
            {
                "pair_quantity": "quantity",
                "pair_basis": "gallon_basis",
                "pair_asset": "counterparty_asset_id",
            }[mutation]
        ] = {
            "pair_quantity": "49.000",
            "pair_basis": "observed",
            "pair_asset": "ISOLATED",
        }[mutation]
    else:
        movements.append(dict(movements[1], movement_id="DUPLICATE"))
    result = compute(data)
    assert not findings(result, "C10")
    assert any(f["missing_reference"]["type"] == kind for f in findings(result, "C11"))
    assert not any(f["status"] == "exception" for f in findings(result, "C08"))
    assert result["consolidation"]["status"] == "unavailable"
    assert result["not_evaluated"]["KPI:inventory"]["status"] == "unavailable"


def test_pos_delivery_representation_contributes_zero_and_is_not_sold_twice():
    data = exports()
    retail = next(
        m for m in data["movements.csv"] if m["movement_type"] == "retail_sale"
    )
    data["movements.csv"].append(
        dict(
            retail,
            movement_id="M-POS-DELIVERY",
            source_id="T-DELIVERY:1",
            quantity="100.000",
        )
    )
    result = compute(data)
    assert result["findings"] == []
    sheet = result["inventory"]["BULK-A"]
    assert sheet["expected"] == "1050.000"
    zero = next(
        c for c in sheet["contributions"] if c["kind"] == "represented_delivery"
    )
    assert zero["gallons"] == "0.000"
    assert "identity:pos_event:EVENT-DELIVERY" in zero["source_refs"]


def test_multiple_stale_qbo_manifests_deduplicate_atomic_source_and_c10_wins():
    data = exports("P10")
    update = next(m for m in data["manifests.json"] if m["source"] == "qbo_updates")
    update["covered_through"] = shift(data["run.json"]["as_of"], hours=-26)
    result = compute(data)
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["source_refs"] == ["manifest:UPDATES-OK"]
    update.update(status="failed", error_code="EXTRACTION_FAILED")
    result = compute(data)
    assert [f["check_id"] for f in result["findings"]] == ["C10"]


def test_literal_oracle_promotes_reviewed_posting_mapping_only():
    from test_rules import ORACLE

    finding = ORACLE["scenarios"]["wrong-clearing"]["findings"][0]
    assert finding["source_refs"] == [
        "identity:posting:POST-I-PAY",
        "qbo:JournalEntry:JE-UNBALANCED:1",
    ]
    assert (finding["actual"], finding["expected"], finding["delta"]) == (
        "90.00",
        "100.00",
        "-10.00",
    )


@pytest.mark.parametrize(
    "mutation,kind",
    [
        ("opening", "opening_reading"),
        ("ambiguous", "ambiguous_reading"),
        ("window", "movement_window"),
        ("asset", "movement_asset_source"),
        ("source", "movement_asset_source"),
        ("delivery_basis", "movement_quantity_basis"),
        ("pos_delivery_missing", "delivery_movement"),
    ],
)
def test_additional_raw_support_gaps_have_no_guessed_inventory(mutation, kind):
    data = exports()
    if mutation == "opening":
        data["readings.csv"] = [
            r for r in data["readings.csv"] if r["reading_id"] != "R-OPEN"
        ]
    elif mutation == "ambiguous":
        data["readings.csv"].append(dict(data["readings.csv"][0], reading_id="R-TIED"))
    elif mutation in {"window", "asset", "delivery_basis"}:
        row = next(r for r in data["deliveries.csv"] if r["ticket_id"] == "D-OUT")
        if mutation == "window":
            row["delivered_at"] = shift(data["run.json"]["window_start"], seconds=-1)
        elif mutation == "asset":
            row["tank_id"] = "ISOLATED"
        else:
            row["gallon_basis"] = "observed"
    elif mutation == "source":
        data["movements.csv"][1]["source_system"] = "pos"
    else:
        event = next(
            e
            for e in data["identity.json"]["pos_events"]
            if e["pos_id"] == "T-RETAIL:1"
        )
        event["delivery_id"] = "MISSING"
    result = compute(data)
    assert not findings(result, "C10")
    assert any(f["missing_reference"]["type"] == kind for f in findings(result, "C11"))
    assert result["inventory"]["BULK-A"]["status"] == "not_evaluated"
    assert result["consolidation"]["status"] == "unavailable"


@pytest.mark.parametrize("source", ["delivery", "pos"])
def test_cancelled_void_source_is_not_an_inventory_outflow(source):
    data = exports()
    if source == "delivery":
        next(r for r in data["deliveries.csv"] if r["ticket_id"] == "D-OUT")[
            "status"
        ] = "cancelled"
    else:
        next(r for r in data["pos.csv"] if r["transaction_id"] == "T-RETAIL")[
            "status"
        ] = "void"
    result = compute(data)
    sheet = result["inventory"]["BULK-A"]
    assert sheet["expected"] == ("1150.000" if source == "delivery" else "1100.000")
    assert sheet["status"] == "evaluated"


def test_observed_basis_has_no_invented_temperature_conversion():
    data = exports()
    for row in data["readings.csv"]:
        if row["asset_id"] == "BOUNDARY":
            row["gallon_basis"] = "observed"
            row["temperature_f"] = "110.000"
    result = compute(data)
    assert not findings(result, "C08")
    assert findings(result, "C11")[0]["missing_reference"]["type"] == "gallon_basis"
    assert result["inventory"]["BOUNDARY"]["expected"] == "1000.000"
    assert result["consolidation"]["status"] == "unavailable"


def test_blocked_worksheet_preserves_signed_known_inputs_and_clean_has_no_alerts():
    result = compute(exports("issues"))
    sheet = result["inventory"]["BULK-A"]
    assert sheet["expected"] is None and sheet["status"] == "not_evaluated"
    assert sorted(c["gallons"] for c in sheet["ledger_inputs"]) == [
        "-100.000",
        "-50.000",
        "200.000",
    ]
    clean = compute(exports())
    assert clean["findings"] == clean["alerts"] == []
    assert clean["not_evaluated"] == {} and clean["freshness_evaluated"] is True
    assert all(s["status"] == "evaluated" for s in clean["inventory"].values())


def test_stale_source_gap_preserves_microsecond_precision_and_worst_manifest_order():
    data = exports("P10")
    for m in data["manifests.json"]:
        if m["source"] in {"qbo", "qbo_updates"}:
            m["covered_through"] = shift(
                data["run.json"]["as_of"], hours=-25, microseconds=-1
            )
    result = compute(data)
    assert len(result["alerts"]) == 1
    assert D(findings(result, "C09")[0]["actual"]) > 25


def test_transfer_with_unknown_asset_fails_both_endpoints_before_any_verdict():
    data = exports()
    for m in data["movements.csv"]:
        if m["movement_type"] == "transfer_in":
            m["asset_id"] = "UNKNOWN"
        elif m["movement_type"] == "transfer_out":
            m["counterparty_asset_id"] = "UNKNOWN"
    result = compute(data)
    assert any(
        f["missing_reference"]["type"] == "transfer_pair"
        for f in findings(result, "C11")
    )
    assert result["inventory"]["DEPOT"]["status"] == "not_evaluated"


def test_unmeasured_mapping_is_explicitly_excluded():
    data = exports()
    data["identity.json"]["assets"].append(
        {
            "mapping_id": "UNMEASURED",
            "source_id": "UNMEASURED",
            "asset_id": "UNMEASURED",
        }
    )
    result = compute(data)
    assert "UNMEASURED" not in result["inventory"]
    assert result["findings"] == []


def test_weaker_second_watermark_cannot_replace_worst_root():
    data = exports("P10")
    update = next(m for m in data["manifests.json"] if m["source"] == "qbo_updates")
    update["covered_through"] = shift(data["run.json"]["as_of"], hours=-24, seconds=-1)
    result = compute(data)
    assert result["alerts"][0]["source_refs"] == ["manifest:QBO-STALE"]
    assert len(result["alerts"]) == 1


def test_optional_missing_meter_ticket_retains_real_delivery_evidence():
    data = exports("P08")
    next(r for r in data["deliveries.csv"] if r["ticket_id"] == "D-OUT")[
        "meter_ticket_id"
    ] = ""
    result = compute(data)
    f = findings(result, "C08")[0]
    assert "cargas:delivery:D-OUT" in f["related_refs"]
    assert not any(k.startswith("cargas:meter_ticket:") for k in f["related_refs"])
    assert f["delta"] == "-30.000"


@pytest.mark.parametrize("seconds,uncertain", [(3600, False), (3601, True)])
def test_late_endpoint_exact_hour_and_just_over_through_ingestion(seconds, uncertain):
    data = exports()
    end = data["run.json"]["window_end"]
    late = shift(end, seconds=seconds)
    data["run.json"]["as_of"] = late
    manifest = next(m for m in data["manifests.json"] if m["source"] == "readings")
    for key in ["expected_window_end", "covered_through", "extracted_at"]:
        manifest[key] = late
    row = next(r for r in data["readings.csv"] if r["reading_id"] == "R-CLOSE")
    row["observed_at"] = late
    result = compute(data)
    assert not findings(result, "C10")
    assert bool(findings(result, "C08")) == uncertain
    assert result["inventory"]["BULK-A"]["status"] == (
        "sensor_uncertain" if uncertain else "evaluated"
    )


def test_unrounded_tolerance_is_not_equal_to_rounded_displayed_delta():
    data = exports()
    rows = {r["reading_id"]: r for r in data["readings.csv"]}
    rows["R-BOUNDARY-OPEN"]["gallons"] = "1000.101"
    rows["R-BOUNDARY-CLOSE"]["gallons"] = "1005.102"
    result = compute(data)
    f = findings(result, "C08")[0]
    assert (f["delta"], f["threshold"]) == ("5.001", "5.000505")


@pytest.mark.parametrize("ambiguous", [False, True])
def test_missing_or_ambiguous_asset_mapping_never_disappears_or_double_counts(
    ambiguous,
):
    data = exports()
    mappings = data["identity.json"]["assets"]
    if ambiguous:
        mappings.append(dict(mappings[0], mapping_id="AMBIGUOUS", asset_id="BOUNDARY"))
    else:
        mappings[:] = [m for m in mappings if m["asset_id"] != "BULK-A"]
    result = compute(data)
    assert any(
        f["missing_reference"]["type"] == "asset_mapping"
        for f in findings(result, "C11")
    )
    assert result["consolidation"]["status"] == "unavailable"


def test_combined_missing_customer_item_and_asset_are_distinct_root_evidence():
    data = exports()
    row = next(r for r in data["deliveries.csv"] if r["ticket_id"] == "D-OUT")
    row.update(customer_id="UNKNOWN", item_id="UNKNOWN", tank_id="UNKNOWN")
    result = compute(data)
    missing = findings(result, "C11")
    assert {f["missing_reference"]["type"] for f in missing} >= {
        "customer/item",
        "asset_mapping",
    }
    assert len({f["finding_id"] for f in missing}) == len(missing)
    asset = next(
        f for f in missing if f["missing_reference"]["type"] == "asset_mapping"
    )
    assert asset["source_refs"] == ["cargas:delivery:D-OUT", "manifest:IDENTITY-OK"]
    assert not findings(result, "C02")
