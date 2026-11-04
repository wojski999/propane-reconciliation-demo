"""Independent source arithmetic and chronology, not production rule engines."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from test_generator import ORACLE, dataset

from propane_demo.generator import business_window

DAYS = [
    date(2026, 11, 3),
    date(2026, 11, 4),
    date(2026, 3, 8),
    date(2026, 3, 9),
    date(2026, 11, 1),
    date(2026, 11, 2),
]


def keyed(rows, key):
    return {r[key]: r for r in rows}


def bind(finding, actual, expected, threshold):
    assert tuple(
        map(D, [finding[k] for k in ["actual", "expected", "delta", "threshold"]])
    ) == (actual, expected, actual - expected, threshold)


@pytest.mark.parametrize(
    "scenario",
    [
        "P01",
        "P02",
        "P03",
        "P04",
        "P05",
        "P06",
        "P07",
        "P08",
        "P10",
        "P13",
        "raw-repeat",
        "wrong-clearing",
    ],
)
def test_numeric_oracle_is_bound_to_sources(scenario):
    d = dataset(scenario)
    q, p = d["qbo.json"], d["policies.json"]
    invoices = keyed(q["Invoice"], "Id")
    findings = ORACLE["scenarios"][scenario]["findings"]
    money = D(p["price_tolerance"])
    match scenario:
        case "P01":
            row = keyed(d["deliveries.csv"], "ticket_id")["D-MISSING"]
            allocated = sum(
                (
                    D(a["gallons"])
                    for a in d["identity.json"]["allocations"]
                    if a["delivery_id"] == row["ticket_id"]
                ),
                D(0),
            )
            bind(findings[0], D(row["gallons"]) - allocated, D(0), D(".001"))
        case "P02":
            row = invoices["I-ORPHAN"]["Line"][0]
            allocated = sum(
                (
                    D(a["gallons"])
                    for a in d["identity.json"]["allocations"]
                    if a["invoice_id"] == "I-ORPHAN"
                ),
                D(0),
            )
            bind(
                findings[0],
                D(row["SalesItemLineDetail"]["Qty"]) - allocated,
                D(0),
                D(".001"),
            )
        case "P03":
            rows = [r for r in d["pos.csv"] if r["external_reference"] == "EXT-DUP"]
            bind(findings[0], D(len(rows)), D(1), D(1))
        case "raw-repeat":
            row = q["Invoice"][0]
            bind(findings[0], D(q["Invoice"].count(row)), D(1), D(1))
        case "P04":
            row = invoices["I-PRICE"]["Line"][0]
            delivery = keyed(d["deliveries.csv"], "ticket_id")["D-PRICE"]
            price = keyed(d["prices.csv"], "price_id")["PRICE-BASE"]
            bind(
                findings[0],
                D(row["Amount"]),
                D(delivery["gallons"]) * D(price["unit_price"]),
                money,
            )
        case "P05":
            pos = keyed(d["pos.csv"], "transaction_id")["T-DISCOUNT"]
            pct = (
                D(pos["discount_amount"])
                / (D(pos["quantity"]) * D(pos["unit_price"]))
                * 100
            )
            limit = D(p["discount_limit_pct"])
            bind(findings[0], pct, limit, limit)
            limit = D(p["credit_limit"])
            bind(findings[1], D(q["CreditMemo"][0]["TotalAmt"]), limit, limit)
        case "P06":
            pay = keyed(q["Payment"], "Id")
            excess = pay["PAY-EXCESS"]
            invoice = invoices[excess["Line"][0]["LinkedTxn"][0]["TxnId"]]
            # Replay only events strictly before this payment, never today's Balance.
            balance = D(invoice["TotalAmt"])
            for credit in q["CreditMemo"]:
                if credit["EventAt"] < excess["EventAt"] and any(
                    r["TxnId"] == invoice["Id"] for r in credit["LinkedTxn"]
                ):
                    balance -= D(credit["AppliedAmount"])
            for prior in q["Payment"]:
                if prior["EventAt"] < excess["EventAt"]:
                    balance -= sum(
                        (
                            D(line["Amount"])
                            for line in prior["Line"]
                            if any(
                                r["TxnId"] == invoice["Id"] for r in line["LinkedTxn"]
                            )
                        ),
                        D(0),
                    )
            bind(findings[0], D(excess["Line"][0]["Amount"]), balance, money)
            bind(findings[1], D(pay["PAY-UNAPPLIED"]["UnappliedAmt"]), D(0), money)
        case "P07":
            batch = d["settlements.csv"][0]
            rows = [
                r for r in d["pos.csv"] if r["settlement_batch_id"] == batch["batch_id"]
            ]
            gross = sum(D(r["gross_amount"]) for r in rows if r["status"] == "captured")
            refunds = -sum(
                D(r["gross_amount"]) for r in rows if r["status"] == "refunded"
            )
            assert (gross, refunds) == (D(batch["gross"]), D(batch["refunds"]))
            deposit = keyed(q["Deposit"], "Id")[batch["qbo_deposit_id"]]
            actual = sum(D(line["Amount"]) for line in deposit["Line"])
            assert actual == D(deposit["TotalAmt"])
            bind(findings[0], actual, gross - refunds - D(batch["fees"]), money)
        case "P08":
            readings = keyed(d["readings.csv"], "reading_id")
            opening = D(readings["R-OPEN"]["gallons"])
            movements = [r for r in d["movements.csv"] if r["asset_id"] == "BULK-A"]
            inbound = sum(
                D(r["quantity"])
                for r in movements
                if r["movement_type"] in ["purchase", "transfer_in"]
            )
            outbound = sum(
                D(r["quantity"])
                for r in movements
                if r["movement_type"] not in ["purchase", "transfer_in"]
            )
            tolerance = max(
                D(p["inventory_min_gallons"]),
                D(p["inventory_pct"]) * (opening + inbound),
            )
            bind(
                findings[0],
                D(readings["R-CLOSE"]["gallons"]),
                opening + inbound - outbound,
                tolerance,
            )
        case "P10":
            end = datetime.fromisoformat(d["run.json"]["window_end"])
            covered = datetime.fromisoformat(d["manifests.json"][0]["covered_through"])
            bind(
                findings[0],
                D((end - covered).total_seconds()) / 3600,
                D(p["source_max_hours"]),
                D(p["source_max_hours"]),
            )
        case "P13":
            lines = q["JournalEntry"][0]["Line"]
            debit = sum(
                D(r["Amount"])
                for r in lines
                if r["JournalEntryLineDetail"]["PostingType"] == "Debit"
            )
            credit = sum(
                D(r["Amount"])
                for r in lines
                if r["JournalEntryLineDetail"]["PostingType"] == "Credit"
            )
            bind(findings[0], debit, credit, money)
        case "wrong-clearing":
            entry = q["JournalEntry"][0]
            mapping = d["identity.json"]["posting_map"][0]
            expected = sum(
                D(r["Amount"]) for r in invoices[entry["ExternalRef"]]["Line"]
            )
            actual = sum(
                D(r["Amount"])
                for r in entry["Line"]
                if r["JournalEntryLineDetail"]["AccountRef"]["value"]
                == mapping["account_id"]
            )
            bind(findings[0], actual, expected, money)


@pytest.mark.parametrize("day", DAYS)
@pytest.mark.parametrize("scenario", ["clean", "issues"])
def test_readings_bracket_movements_and_sources(day, scenario):
    d = dataset(scenario, business_date=day)
    start, end = business_window(day)
    for movement in d["movements.csv"]:
        readings = sorted(
            (r for r in d["readings.csv"] if r["asset_id"] == movement["asset_id"]),
            key=lambda r: r["observed_at"],
        )
        instant = datetime.fromisoformat(movement["occurred_at"])
        assert start <= instant < end
        assert datetime.fromisoformat(readings[0]["observed_at"]) <= instant
        assert instant < datetime.fromisoformat(readings[-1]["observed_at"])
        if movement["source_system"] == "cargas":
            source = keyed(d["deliveries.csv"], "ticket_id")[movement["source_id"]]
            assert source["delivered_at"] == movement["occurred_at"]
        if movement["source_system"] == "pos" and scenario == "clean":
            source = keyed(d["pos.csv"], "transaction_id")[
                movement["source_id"].split(":")[0]
            ]
            assert source["occurred_at"] == movement["occurred_at"]
    for row in d["readings.csv"]:
        anchor = start if row["reading_id"].endswith("OPEN") else end
        expected = (
            timedelta(hours=1) if "BOUNDARY" in row["reading_id"] else timedelta(0)
        )
        assert abs(datetime.fromisoformat(row["observed_at"]) - anchor) == expected


@pytest.mark.parametrize("day", DAYS)
def test_settlement_chronology_history_and_business_grace(day):
    d = dataset(business_date=day)
    start, end = business_window(day)
    batch = d["settlements.csv"][0]
    settled = datetime.fromisoformat(batch["settled_at"])
    deposit = d["qbo.json"]["Deposit"][0]
    assert settled < datetime.fromisoformat(deposit["EventAt"]) < start
    for row in d["pos.csv"]:
        if row["settlement_batch_id"] == batch["batch_id"]:
            assert datetime.fromisoformat(row["occurred_at"]) < settled
    for entity, ident in [("SalesReceipt", "SR-BATCH"), ("RefundReceipt", "RR-BATCH")]:
        row = keyed(d["qbo.json"][entity], "Id")[ident]
        assert datetime.fromisoformat(row["EventAt"]) < settled
    local = settled.astimezone(ZoneInfo("America/Denver"))
    due = local
    count = 0
    while count < d["policies.json"]["settlement_grace_business_days"]:
        due += timedelta(days=1)
        count += due.weekday() < 5
    assert due < end.astimezone(ZoneInfo("America/Denver"))
    for manifest in d["manifests.json"]:
        if manifest["file_id"] in ["prices.csv", "identity.json", "empty.json"]:
            continue
        content = d[manifest["file_id"]]
        records = (
            sum(content.values(), [])
            if manifest["file_id"] == "qbo.json"
            else content["records"]
            if manifest["file_id"] == "updates.json"
            else [content]
            if isinstance(content, dict)
            else content
        )
        for row in records:
            for field in [
                "EventAt",
                "delivered_at",
                "observed_at",
                "occurred_at",
                "settled_at",
                "as_of",
            ]:
                if field in row:
                    assert manifest["expected_window_start"] <= row[field]
                    assert row[field] <= manifest["expected_window_end"]
    assert d["qbo.json"]["Customer"][0] == d["updates.json"]["records"][0]


def test_strict_ar_chronology_void_and_delivery_cash_link():
    for scenario in ["clean", "P05", "P06"]:
        d = dataset(scenario)
        q = d["qbo.json"]
        invoices = keyed(q["Invoice"], "Id")
        for credit in q["CreditMemo"]:
            for ref in credit["LinkedTxn"]:
                assert invoices[ref["TxnId"]]["EventAt"] < credit["EventAt"]
        for payment in q["Payment"]:
            for line in payment["Line"]:
                for ref in line["LinkedTxn"]:
                    assert invoices[ref["TxnId"]]["EventAt"] < payment["EventAt"]
        assert invoices["I-VOID"]["Balance"] == invoices["I-VOID"]["TotalAmt"] == "0.00"
        replay = sum(D(r["TotalAmt"]) for r in q["Invoice"])
        replay -= sum(D(r["AppliedAmount"]) for r in q["CreditMemo"])
        replay -= sum(D(line["Amount"]) for r in q["Payment"] for line in r["Line"])
        assert replay == sum(D(r["Balance"]) for r in q["Invoice"])
        crosswalk = next(
            r for r in d["identity.json"]["pos_events"] if r["pos_id"] == "T-DELIVERY:1"
        )
        pay = keyed(q["Payment"], "Id")[crosswalk["payment_id"]]
        assert pay["Line"][0]["LinkedTxn"][0]["TxnId"] == crosswalk["qbo_id"] == "I-OUT"
        assert D(pay["TotalAmt"]) == D(invoices["I-OUT"]["TotalAmt"])
        assert invoices["I-OUT"]["Balance"] == "0.00"


def test_pos_failure_suppresses_both_dependent_assets():
    for scenario in ["P11", "issues"]:
        assert {"C08:BULK-A", "C08:ISOLATED"} <= set(
            ORACLE["scenarios"][scenario]["not_evaluated"]
        )


def test_packaged_sources_have_no_precomputed_answers():
    root = Path(__file__).resolve().parents[1]
    template = json.loads((root / "src/propane_demo/data/template.json").read_text())
    assert "boundary_cases.json" not in template["clean"]
    assert "expected_net" not in json.dumps(template)
    for path in (root / "src").rglob("*.py"):
        text = path.read_text()
        assert "expected_findings" not in text
        assert "tests/" not in text
    assert list((root / "src/propane_demo/data").iterdir()) == [
        root / "src/propane_demo/data/template.json"
    ]


def timestamps(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from timestamps(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from timestamps(item, (*path, index))
    elif isinstance(value, str) and "T" in value and value.endswith("+00:00"):
        yield path, datetime.fromisoformat(value)


@pytest.mark.parametrize("scenario", ["clean", "issues"])
@pytest.mark.parametrize("day", DAYS)
def test_every_timestamp_preserves_intended_day_membership(scenario, day):
    baseline = dataset(scenario)
    shifted = dataset(scenario, business_date=day)
    base_start, base_end = business_window(date(2026, 11, 3))
    start, end = business_window(day)

    def before_in_after(t, a, b):
        return -1 if t < a else 0 if t < b else 1

    original = dict(timestamps(baseline))
    for path, instant in timestamps(shifted):
        # Exactly 24 elapsed hours is deliberately independent of local-day length.
        grace = (
            path[0] == "deliveries.csv"
            and shifted[path[0]][path[1]]["ticket_id"] == "D-GRACE"
            or path[0] == "qbo.json"
            and path[1] in ["Invoice", "Payment"]
            and shifted[path[0]][path[1]][path[2]]["Id"] in ["I-GRACE", "PAY-GRACE"]
        )
        if grace and path[-1] in ["delivered_at", "EventAt"]:
            assert end - instant == timedelta(hours=24)
        elif path == ("manifests.json", 0, "covered_through") and scenario == "issues":
            assert end - instant == timedelta(hours=25)
        else:
            assert before_in_after(instant, start, end) == before_in_after(
                original[path], base_start, base_end
            ), path


@pytest.mark.parametrize(
    "scenario,actual,delta", [("P07", "461.00", "-9.00"), ("P13", "101.00", "11.00")]
)
def test_known_consistent_oracle_mutations_are_rejected(
    monkeypatch, scenario, actual, delta
):
    finding = ORACLE["scenarios"][scenario]["findings"][0]
    monkeypatch.setitem(finding, "actual", actual)
    monkeypatch.setitem(finding, "delta", delta)
    with pytest.raises(AssertionError):
        test_numeric_oracle_is_bound_to_sources(scenario)


def test_package_data_allowlist_is_exact():
    import tomllib

    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    assert config["tool"]["setuptools"]["package-data"] == {
        "propane_demo": ["data/template.json"]
    }


@pytest.mark.parametrize("scenario", ["P01", "P02", "P06"])
@pytest.mark.parametrize("day", DAYS)
def test_numeric_grace_exceptions_are_really_aged(scenario, day):
    d = dataset(scenario, business_date=day)
    _, end = business_window(day)
    if scenario == "P01":
        instant = d["deliveries.csv"][-1]["delivered_at"]
    elif scenario == "P02":
        instant = d["qbo.json"]["Invoice"][-1]["EventAt"]
    else:
        instant = d["qbo.json"]["Payment"][-1]["EventAt"]
    assert end - datetime.fromisoformat(instant) > timedelta(hours=24)


def test_all_clean_refunds_follow_the_original_sale():
    q = dataset()["qbo.json"]
    for refund in q["RefundReceipt"]:
        for ref in refund["LinkedTxn"]:
            original = keyed(q[ref["TxnType"]], "Id")[ref["TxnId"]]
            assert original["EventAt"] < refund["EventAt"]


@pytest.mark.parametrize("scenario", ["P09", "P14"])
def test_remaining_numeric_fields_are_source_bound(scenario):
    d = dataset(scenario)
    finding = ORACLE["scenarios"][scenario]["findings"][0]
    if scenario == "P14":
        refund = d["qbo.json"]["RefundReceipt"][-1]
        assert D(finding["actual"]) == D(refund["Line"][0]["Amount"])
    else:
        opening = keyed(d["readings.csv"], "reading_id")["R-TRUCK-OPEN"]
        inbound = sum(
            D(r["quantity"])
            for r in d["movements.csv"]
            if r["asset_id"] == "TRUCK-A" and r["movement_type"] == "transfer_in"
        )
        assert D(finding["threshold"]) == max(
            D(d["policies.json"]["inventory_min_gallons"]),
            D(d["policies.json"]["inventory_pct"]) * (D(opening["gallons"]) + inbound),
        )


def test_combined_numeric_findings_are_independently_bound():
    d = dataset("issues")
    findings = keyed(ORACLE["scenarios"]["issues"]["findings"], "check_id")
    end = datetime.fromisoformat(d["run.json"]["window_end"])
    covered = datetime.fromisoformat(d["manifests.json"][0]["covered_through"])
    limit = D(d["policies.json"]["source_max_hours"])
    bind(findings["C09"], D((end - covered).total_seconds()) / 3600, limit, limit)
    reading = keyed(d["readings.csv"], "reading_id")["R-TRUCK-OPEN"]
    inbound = sum(
        D(r["quantity"])
        for r in d["movements.csv"]
        if r["asset_id"] == "TRUCK-A" and r["movement_type"] == "transfer_in"
    )
    assert D(findings["C08"]["threshold"]) == max(
        D(d["policies.json"]["inventory_min_gallons"]),
        D(d["policies.json"]["inventory_pct"]) * (D(reading["gallons"]) + inbound),
    )


def assert_source_chronology(d, scenario):
    as_of = datetime.fromisoformat(d["run.json"]["as_of"])
    future = as_of + timedelta(minutes=d["policies.json"]["future_max_minutes"])
    for manifest in d["manifests.json"]:
        start, end, covered, extracted = (
            datetime.fromisoformat(manifest[k])
            for k in [
                "expected_window_start",
                "expected_window_end",
                "covered_through",
                "extracted_at",
            ]
        )
        assert start <= covered <= end <= extracted <= as_of
        stale = scenario in ["P10", "issues"] and manifest["file_id"] == "qbo.json"
        if stale:
            assert as_of - covered == timedelta(hours=25)
        for path, instant in timestamps(d[manifest["file_id"]]):
            assert start <= instant <= end, (manifest["file_id"], path)
            assert instant <= extracted
            assert instant <= future
            if not stale:
                assert instant <= covered


@pytest.mark.parametrize("day", DAYS)
@pytest.mark.parametrize("scenario", ["clean", "issues", "P10"])
def test_source_chronology(day, scenario):
    assert_source_chronology(dataset(scenario, business_date=day), scenario)


@pytest.mark.parametrize("scenario", ["clean", "issues", "P10"])
def test_original_future_closing_reading_is_rejected(scenario):
    d = dataset(scenario)
    close = keyed(d["readings.csv"], "reading_id")["R-BOUNDARY-CLOSE"]
    close["observed_at"] = (
        datetime.fromisoformat(d["run.json"]["window_end"]) + timedelta(hours=1)
    ).isoformat()
    # Even widening the window, as in the original fix, cannot hide future data.
    manifest = keyed(d["manifests.json"], "file_id")["readings.csv"]
    manifest["expected_window_end"] = close["observed_at"]
    with pytest.raises(AssertionError):
        assert_source_chronology(d, scenario)


def test_oracle_semantic_metadata():
    # Catalogue severity plus explicit scenario meaning, independent of oracle values.
    for scenario, entry in ORACLE["scenarios"].items():
        d = dataset(scenario)
        for f in entry["findings"]:
            check = f["check_id"]
            severity = "critical" if check == "C10" else "high"
            if (
                check == "C05"
                and scenario != "P14"
                or check == "C06"
                and "qbo:Payment:PAY-UNAPPLIED" in f["source_refs"]
                or check == "C08"
                and scenario in ["P09", "issues"]
            ):
                severity = "medium"
            assert f["severity"] == severity
            missing = None
            if check == "C01":
                row = keyed(d["deliveries.csv"], "ticket_id")["D-MISSING"]
                missing = dict(
                    system="qbo",
                    type="Invoice.Line",
                    lookup_key=f"delivery:{row['ticket_id']}",
                )
            elif check == "C02":
                row = keyed(d["qbo.json"]["Invoice"], "Id")["I-ORPHAN"]
                missing = dict(
                    system="cargas",
                    type="delivery",
                    lookup_key=f"invoice:{row['Id']}:{row['Line'][0]['Id']}",
                )
            elif check == "C11":
                if "cargas:delivery:D-NO-MAPPING" in f["source_refs"]:
                    row = keyed(d["deliveries.csv"], "ticket_id")["D-NO-MAPPING"]
                    missing = dict(
                        system="identity",
                        type="customer/item",
                        lookup_key=f"customer:{row['customer_id']};item:{row['item_id']}",
                    )
                else:
                    row = keyed(d["readings.csv"], "reading_id")["R-NO-READING-OPEN"]
                    missing = dict(
                        system="cargas",
                        type="closing_reading",
                        lookup_key=f"asset:{row['asset_id']};boundary:{d['run.json']['window_end']}",
                    )
            elif scenario == "P14":
                row = d["qbo.json"]["RefundReceipt"][-1]
                missing = dict(
                    system="qbo", type="original_sale", lookup_key=f"refund:{row['Id']}"
                )
            assert f.get("missing_reference") == missing
    d = dataset("P07")
    batch = d["settlements.csv"][0]
    deposit = keyed(d["qbo.json"]["Deposit"], "Id")[batch["qbo_deposit_id"]]
    refs = {"policy:POLICY-1", f"pos:fee:{batch['batch_id']}:fees"}
    refs.update(
        f"pos:POS:{r['transaction_id']}:{r['line_id']}"
        for r in d["pos.csv"]
        if r["settlement_batch_id"] == batch["batch_id"]
    )
    refs.update(f"qbo:Deposit:{deposit['Id']}:{r['Id']}" for r in deposit["Line"][1:])
    refs.update(
        f"qbo:{detail['TxnType']}:{detail['TxnId']}"
        for line in deposit["Line"]
        if "TxnId" in (detail := line["DepositLineDetail"])
    )
    assert set(ORACLE["scenarios"]["P07"]["findings"][0]["related_refs"]) == refs


@pytest.mark.parametrize(
    "scenario,field,value",
    [
        ("P08", "severity", "medium"),
        ("P07", "related_refs", []),
        ("P12", "missing_reference", {"lookup_key": "invented"}),
    ],
)
def test_oracle_metadata_mutations_are_rejected(monkeypatch, scenario, field, value):
    finding = ORACLE["scenarios"][scenario]["findings"][0]
    if field == "related_refs":
        value = finding[field][1:]
    monkeypatch.setitem(finding, field, value)
    with pytest.raises(AssertionError):
        test_oracle_semantic_metadata()


# Explicit scenario evidence semantics: ticket/allocation, approval/original,
# AR snapshot, contributing movements, failed row and journal account context.
RELATED_EXPECTATIONS = {
    "P01": ["cargas:meter_ticket:MT-D-MISSING"],
    "P02": ["qbo:Item:LPG-DELIVERY"],
    "P03": ["pos:external_reference:EXT-DUP"],
    "P04": [
        "cargas:meter_ticket:MT-D-PRICE identity:allocation:A-PRICE policy:POLICY-1"
    ],
    "P05": [
        "identity:approval:APP-DISCOUNT policy:POLICY-1 "
        "prices:price:PRICE-DISCOUNT qbo:SalesReceipt:SR-DISCOUNT:1",
        "identity:approval:APP-CREDIT policy:POLICY-1 qbo:Invoice:I-CREDIT",
    ],
    "P06": ["ar:snapshot:AR-OPEN qbo:Invoice:I-PAY", "ar:snapshot:AR-OPEN"],
    "P08": [
        "cargas:delivery:D-OUT cargas:meter_ticket:MT-D-OUT "
        "inventory:movement:M-OUT inventory:movement:M-PURCHASE "
        "inventory:movement:M-RETAIL policy:POLICY-1 pos:POS:T-RETAIL:1"
    ],
    "P09": [
        "inventory:movement:M-TRANSFER-IN "
        "inventory:movement:M-TRANSFER-OUT policy:POLICY-1"
    ],
    "P10": ["file:qbo.json policy:POLICY-1"],
    "P11": ["file:pos.csv:row:2"],
    "P12": ["policy:POLICY-1", "policy:POLICY-1"],
    "P13": [
        "identity:posting:POST-I-PAY policy:POLICY-1 qbo:Invoice:I-PAY "
        "qbo:account:CLEARING qbo:account:REVENUE"
    ],
    "P14": ["identity:approval:APP-REFUND policy:POLICY-1"],
    "raw-repeat": ["qbo:Invoice:I-PRICE qbo:version:I-PRICE:0"],
    "wrong-clearing": [
        "policy:POLICY-1 qbo:Invoice:I-PAY "
        "qbo:JournalEntry:JE-UNBALANCED:2 qbo:account:CLEARING "
        "qbo:account:REVENUE"
    ],
}


def test_all_related_evidence_matches_scenario_semantics():
    expectations = dict(RELATED_EXPECTATIONS)
    expectations["issues"] = [
        RELATED_EXPECTATIONS[s][i]
        for s, i in [("P09", 0), ("P10", 0), ("P11", 0), ("P12", 0), ("P12", 1)]
    ]
    for scenario, groups in expectations.items():
        findings = ORACLE["scenarios"][scenario]["findings"]
        assert len(findings) == len(groups)
        for finding, expected in zip(findings, groups, strict=True):
            assert finding["related_refs"] == sorted(expected.split())


def assert_suppression_and_alert_contract():
    """Independent test-only scenario contract, never production dependencies."""
    expected = {
        "P10": {
            "C04:pos",
            "C05:pos:POS:T-REFUND:1",
            "C01",
            "C02",
            "C03:qbo",
            "C04:qbo",
            "C05:qbo",
            "C06",
            "C07",
            "C12",
            "KPI:revenue",
            "KPI:AR",
        },
        "P11": {
            "C03:pos",
            "C04:pos",
            "C05:pos",
            "C07",
            "C08:BULK-A",
            "C08:ISOLATED",
            "KPI:retail",
            "KPI:revenue",
        },
    }
    for scenario, scopes in expected.items():
        entry = ORACLE["scenarios"][scenario]
        assert set(entry["not_evaluated"]) == scopes
        manifests = dataset(scenario)["manifests.json"]
        m = next(
            m
            for m in manifests
            if m["file_id"] == ("qbo.json" if scenario == "P10" else "pos.csv")
        )
        check = "C09" if scenario == "P10" else "C10"
        if scenario == "P10":
            assert datetime.fromisoformat(m["extracted_at"]) - datetime.fromisoformat(
                m["covered_through"]
            ) == timedelta(hours=25)
        else:
            assert m["status"] == "failed" and m["error_code"] == "CSV_SCHEMA"
        assert entry["alerts"] == [check + "|manifest:" + m["manifest_id"]]
    singles = [ORACLE["scenarios"][f"P{i:02}"] for i in range(1, 15)]
    combined = set().union(*(set(entry["not_evaluated"]) for entry in singles))
    # Failed POS already blocks the entire C05:pos scope in the combined run.
    combined.remove("C05:pos:POS:T-REFUND:1")
    assert set(ORACLE["scenarios"]["issues"]["not_evaluated"]) == combined
    assert set(ORACLE["scenarios"]["issues"]["alerts"]) == set().union(
        *(set(entry["alerts"]) for entry in singles)
    )
    for scenario, entry in ORACLE["scenarios"].items():
        d = dataset(scenario)
        for finding in entry["findings"]:
            assert finding["business_date"] == d["run.json"]["business_date"]
            assert finding["rule_version"] == d["policies.json"]["version"]


def test_suppression_and_alert_contract():
    assert_suppression_and_alert_contract()


@pytest.mark.parametrize(
    "scope",
    [
        "C02",
        "C06",
        "C07",
        "C12",
        "KPI:AR",
        "KPI:delivered",
        "KPI:inventory",
        "KPI:retail",
        "KPI:revenue",
    ],
)
def test_dropped_combined_unavailable_scope_rejected(monkeypatch, scope):
    entry = ORACLE["scenarios"]["issues"]
    monkeypatch.setitem(
        entry, "not_evaluated", [x for x in entry["not_evaluated"] if x != scope]
    )
    with pytest.raises(AssertionError):
        assert_suppression_and_alert_contract()


@pytest.mark.parametrize(
    "scenario,field,value",
    [
        ("P10", "alerts", []),
        ("P11", "not_evaluated", ["C12"]),
    ],
)
def test_alert_and_unrelated_suppression_mutations_rejected(
    monkeypatch, scenario, field, value
):
    entry = ORACLE["scenarios"][scenario]
    if field == "not_evaluated":
        value = entry[field] + value
    monkeypatch.setitem(entry, field, value)
    with pytest.raises(AssertionError):
        assert_suppression_and_alert_contract()


@pytest.mark.parametrize(
    "field,value",
    [
        ("business_date", "2020-01-01"),
        ("rule_version", "other"),
    ],
)
def test_finding_run_metadata_mutations_rejected(monkeypatch, field, value):
    finding = ORACLE["scenarios"]["P11"]["findings"][0]
    monkeypatch.setitem(finding, field, value)
    with pytest.raises(AssertionError):
        assert_suppression_and_alert_contract()
