"""Independent fixture oracle plus hand-calculated adversarial rule examples."""

import copy
import json
from datetime import date
from pathlib import Path

import pytest

from propane_demo.contracts import SCENARIOS
from propane_demo.generator import generate
from propane_demo.ingestion import ingest
from propane_demo.rule_inputs import from_database
from propane_demo.rules import Engine, reconcile

ORACLE = json.loads(
    (Path(__file__).parent / "fixtures/expected_findings.json").read_text()
)
IMPLEMENTED = {"C01", "C02", "C03", "C04", "C05", "C06", "C07", "C12"}


def inputs(scenario="clean", business_date=date(2026, 11, 3), blocked=None):
    db = ingest(generate(scenario, business_date=business_date).__getitem__)
    try:
        return from_database(db, blocked)
    finally:
        db.close()


def actual(data, check=None):
    findings = reconcile(data)["findings"]
    return [f for f in findings if check is None or f["check_id"] == check]


def numbers(finding):
    return tuple(finding[k] for k in ("actual", "expected", "delta", "threshold"))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_exact_independent_oracle_applicable_subset(scenario):
    # This step does NOT implement C09. Inject the explicitly known future
    # freshness scopes to test its dependency boundary on P10/combined data.
    blocked = {
        scope: {"status": "not_evaluated", "source_refs": ["manifest:QBO-STALE"]}
        for scope in ORACLE["scenarios"]["P10"]["not_evaluated"]
    }
    data = inputs(scenario, blocked=blocked if scenario in {"P10", "issues"} else None)
    expected = [
        f
        for f in ORACLE["scenarios"][scenario]["findings"]
        if f["check_id"] in IMPLEMENTED
        or (
            f["check_id"] == "C11"
            and f["source_refs"] == ["cargas:delivery:D-NO-MAPPING"]
        )
    ]
    found = actual(data)

    # Explanation wording is intentionally not an oracle algorithm. Every other
    # section-5 field is compared exactly, including ALL related refs/missing keys.
    def substantive(rows):
        return [{k: v for k, v in f.items() if k != "explanation"} for f in rows]

    assert substantive(found) == substantive(expected)
    assert all(f["explanation"] for f in found)
    result = reconcile(data)
    assert result["freshness_evaluated"] is False
    assert {
        scope for scope in result["not_evaluated"] if scope.split(":")[0] in IMPLEMENTED
    } == {
        scope
        for scope in ORACLE["scenarios"][scenario]["not_evaluated"]
        if scope.split(":")[0] in IMPLEMENTED
    }


@pytest.mark.parametrize(
    "day", [date(2026, 3, 8), date(2026, 11, 1), date(2026, 3, 9), date(2026, 11, 2)]
)
def test_clean_dst_and_adjacent_days(day):
    assert actual(inputs(business_date=day)) == []


def test_price_cent_threshold_and_half_up():
    data = inputs()
    key = "qbo:SalesReceipt:SR-PRICE-BOUNDARY"
    row = data["records"][key]
    row["TotalAmt"] = row["Line"][0]["Amount"] = 2002
    assert numbers(actual(data, "C04")[0]) == ("20.02", "20.00", "0.02", "0.01")
    row["TotalAmt"] = row["Line"][0]["Amount"] = 1
    row["Line"][0]["SalesItemLineDetail"].update(Qty=5, UnitPrice=100)
    data["records"]["prices:price:PRICE-SERVICE"]["unit_price"] = 100
    # Isolate this price example: other sale lines deliberately retain old prices.
    e = Engine(data)
    p = e.price(key, "SERVICE", "standard", "each", "net_60F", row["EventAt"])
    assert p[1]["unit_price"] == 100
    findings = actual(data, "C04")
    assert not any(key + ":1" in f["source_refs"] for f in findings)


def test_void_cancelled_and_legitimate_equal_values():
    data = inputs("P03")
    for key in ["pos:POS:T-DUP-A:1", "pos:POS:T-DUP-B:1"]:
        data["records"][key]["status"] = "void"
    assert actual(data) == []
    data = inputs("P01")
    data["records"]["cargas:delivery:D-MISSING"]["status"] = "cancelled"
    assert actual(data) == []


def test_split_combined_partial_allocations_and_grace():
    data = inputs()
    # Advance past grace, and remove 1 gallon from one half of split billing.
    data["run"]["as_of"] = "2026-11-06T07:00:00+00:00"
    data["records"]["identity:allocation:A-SPLIT-A"]["gallons"] -= 1000
    found = actual(data, "C01")
    split = next(f for f in found if "cargas:delivery:D-SPLIT" in f["source_refs"])
    assert numbers(split) == ("1.000", "0.000", "1.000", "0.001")
    assert {
        "identity:allocation:A-SPLIT-A",
        "identity:allocation:A-SPLIT-B",
        "qbo:Invoice:I-SPLIT-A:1",
        "qbo:Invoice:I-SPLIT-B:1",
    } <= set(split["related_refs"])
    assert not any("COMB" in f["finding_id"] for f in found)


def test_missing_price_ambiguous_price_customer_and_item_no_guess():
    data = inputs()
    del data["records"]["prices:price:PRICE-SERVICE"]
    found = actual(data)
    assert any(
        f["check_id"] == "C11" and f["missing_reference"]["type"] == "effective_price"
        for f in found
    )
    assert not any(f["check_id"] == "C04" for f in found)
    data = inputs()
    data["records"]["prices:price:SECOND"] = copy.deepcopy(
        data["records"]["prices:price:PRICE-SERVICE"]
    )
    assert any(f["check_id"] == "C11" for f in actual(data))
    del data["records"]["qbo:Customer:C-1"]
    assert all(f["check_id"] == "C11" for f in actual(data))
    data = inputs("P02")
    del data["records"]["qbo:Item:LPG-DELIVERY"]
    assert actual(data, "C02") == []
    assert any(f["missing_reference"]["type"] == "Item" for f in actual(data, "C11"))


def test_invoice_gross_and_tax_bridges():
    data = inputs()
    row = data["records"]["qbo:SalesReceipt:SR-TAX"]
    row["TotalAmt"] = 2202
    assert numbers(actual(data, "C04")[0]) == ("22.02", "22.00", "0.02", "0.01")
    row["TotalAmt"] = 2200
    row["TxnTaxDetail"]["TaxLine"][0]["Amount"] = 198
    assert numbers(actual(data, "C04")[0]) == ("2.00", "1.98", "0.02", "0.01")


def test_pos_gross_bridge_and_discount_approval():
    data = inputs()
    row = data["records"]["pos:POS:T-TAX:1"]
    row["gross_amount"] = 2202
    assert numbers(actual(data, "C04")[0]) == ("22.02", "22.00", "0.02", "0.01")
    data = inputs()
    del data["records"]["identity:approval:APP-DISCOUNT"]
    assert actual(data, "C04") == []
    assert any(
        f["missing_reference"]["type"] == "discount_approval"
        for f in actual(data, "C11")
    )
    data = inputs("P05")
    data["records"]["identity:approval:APP-DISCOUNT"]["approved_discount_pct"] = 10000
    assert any(
        f["missing_reference"]["type"] == "approved_discount_pct"
        for f in actual(data, "C11")
    )


def test_adjustments_missing_approval_original_void_zero_and_negative():
    data = inputs()
    del data["records"]["identity:approval:APP-CREDIT"]
    found = actual(data, "C05")
    assert found[0]["threshold"] == "approval required"
    data["records"]["qbo:CreditMemo:CM-BOUNDARY"]["TotalAmt"] = 0
    assert actual(data, "C05") == []
    data = inputs()
    data["records"]["qbo:RefundReceipt:RR-BOUNDARY"]["TotalAmt"] = -10001
    assert numbers(actual(data, "C05")[0]) == ("100.01", "100.00", "0.01", "100.00")
    data["records"]["qbo:RefundReceipt:RR-BOUNDARY"]["status"] = "void"
    assert actual(data, "C05") == []


def test_historical_ar_prior_credit_then_two_payments_and_order():
    data = inputs()
    r = data["records"]
    # I-CREDIT 200 less credit 100; payments 80 then 30 -> excess 10,
    # regardless of today's reported balance (or source iteration order).
    r["qbo:Invoice:I-CREDIT"]["Balance"] = 999999
    template = copy.deepcopy(r["qbo:Payment:PAY-APPLIED"])
    for ident, amount, event in [
        ("AA", 8000, "2026-11-03T04:00:00+00:00"),
        ("BB", 3000, "2026-11-03T04:00:00+00:00"),
    ]:
        row = copy.deepcopy(template)
        row.update(Id=ident, TotalAmt=amount, EventAt=event)
        row["Line"][0].update(
            Amount=amount, LinkedTxn=[{"TxnType": "Invoice", "TxnId": "I-CREDIT"}]
        )
        r["qbo:Payment:" + ident] = row
    expected = actual(data, "C06")
    assert len(expected) == 1
    assert numbers(expected[0]) == ("30.00", "20.00", "10.00", "0.01")
    assert "qbo:CreditMemo:CM-BOUNDARY" in expected[0]["related_refs"]
    assert "qbo:Payment:AA:1" in expected[0]["related_refs"]
    data["records"] = dict(reversed(list(r.items())))
    assert actual(data, "C06") == expected


def test_ar_missing_snapshot_balance_target_credit_and_unlinked():
    data = inputs()
    del data["records"]["ar:snapshot:AR-OPEN"]
    assert actual(data, "C06") == []
    assert actual(data, "C11")[0]["missing_reference"]["lookup_key"] == "opening_ar"
    data = inputs()
    data["records"]["ar:snapshot:AR-OPEN"]["balances"] = []
    assert actual(data, "C06") == []
    assert all(f["check_id"] == "C11" for f in actual(data))
    data = inputs()
    pay = data["records"]["qbo:Payment:PAY-APPLIED"]
    pay["Line"][0]["LinkedTxn"] = [{"TxnType": "Invoice", "TxnId": "MISSING"}]
    assert (
        actual(data, "C11")[0]["missing_reference"]["lookup_key"]
        == "qbo:Invoice:MISSING"
    )
    pay["Line"][0]["LinkedTxn"] = []
    assert numbers(actual(data, "C06")[0]) == ("100.00", "0.00", "100.00", "0.01")


def test_credit_payment_links_do_not_double_apply():
    data = inputs()
    r = data["records"]
    pay = r["qbo:Payment:PAY-APPLIED"]
    pay["Line"][0]["LinkedTxn"] = [
        {"TxnType": "Invoice", "TxnId": "I-CREDIT"},
        {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"},
    ]
    # The full 100 credit is already applied; no new cash or double reduction.
    assert actual(data, "C06") == []
    pay["Line"][0]["LinkedTxn"][1]["TxnId"] = "MISSING"
    assert actual(data, "C11")[0]["missing_reference"]["type"] == "credit_application"


@pytest.mark.parametrize(
    "now,due",
    [
        ("2026-11-02T19:00:00+00:00", False),
        ("2026-11-03T19:00:00+00:00", False),
        ("2026-11-03T19:00:01+00:00", True),
    ],
)
def test_weekend_business_day_grace_over_dst(now, due):
    data = inputs()
    data["run"]["as_of"] = now
    e = Engine(data)
    assert e.settlement_due("2026-10-30T18:00:00+00:00") is due


def test_missing_batch_support_deposit_link_and_reconciliation():
    data = inputs()
    r = data["records"]
    del r["qbo:Deposit:DEP-SHORT"]
    f = actual(data, "C07")[0]
    assert f["actual"] is None and f["expected"] == "470.00"
    assert f["missing_reference"]["lookup_key"] == "DEP-SHORT"
    data = inputs()
    r = data["records"]
    r["qbo:Deposit:DEP-SHORT"]["Line"][0]["DepositLineDetail"]["TxnId"] = "SR-ORIGINAL"
    assert actual(data, "C07") == []
    assert (
        actual(data, "C11")[0]["missing_reference"]["lookup_key"]
        == "qbo:SalesReceipt:SR-BATCH;qbo:SalesReceipt:SR-ORIGINAL"
    )
    data = inputs()
    r = data["records"]
    del r["identity:pos_event:EVENT-T-BATCH"]
    assert any(
        f["missing_reference"]["type"] == "pos_event" for f in actual(data, "C11")
    )
    data = inputs()
    for row in data["records"].values():
        if "settlement_batch_id" in row:
            row["settlement_batch_id"] = ""
    assert any(
        f["missing_reference"]["type"] == "batch_transactions"
        for f in actual(data, "C11")
    )


def test_batch_components_and_deposit_line_total_checked_independently():
    data = inputs()
    data["records"]["pos:batch:B-SETTLED"]["gross"] = 50002
    assert numbers(actual(data, "C07")[0]) == ("500.02", "500.00", "0.02", "0.01")
    data = inputs()
    data["records"]["qbo:Deposit:DEP-SHORT"]["Line"][0]["Amount"] = 49998
    assert numbers(actual(data, "C07")[0]) == ("470.00", "469.98", "0.02", "0.01")


def test_configured_posting_missing_and_unconfigured_native_invoices():
    data = inputs()
    r = data["records"]
    del r["qbo:JournalEntry:JE-UNBALANCED"]
    f = actual(data, "C11")[0]
    assert f["source_refs"] == ["identity:posting:POST-I-PAY"]
    assert f["missing_reference"]["type"] == "configured_posting"
    del r["identity:posting:POST-I-PAY"]
    assert actual(data) == []
    data = inputs()
    data["records"]["identity:posting:POST-I-PAY"]["account_id"] = "MISSING"
    assert actual(data, "C11")[0]["missing_reference"]["type"] == "clearing_account"


def test_no_input_mutation_and_deterministic_repeat():
    data = inputs("P06")
    before = copy.deepcopy(data)
    assert reconcile(data) == reconcile(data)
    assert data == before


def test_failure_scopes_suppress_missing_mapping_cascades():
    files = generate()
    files["identity.json"] = b"{}"
    db = ingest(files.__getitem__)
    try:
        data = from_database(db)
    finally:
        db.close()
    assert actual(data) == []
    assert "C01" in reconcile(data)["not_evaluated"]


def test_declared_line_arithmetic_and_delivery_allocation_bridges():
    data = inputs()
    r = data["records"]
    r["qbo:Invoice:I-PRICE"]["Line"][0]["SalesItemLineDetail"]["UnitPrice"] = 201
    assert numbers(actual(data, "C04")[0]) == ("200.00", "201.00", "-1.00", "0.01")
    data = inputs()
    data["records"]["identity:allocation:A-SPLIT-A"]["net_amount"] = 3998
    assert numbers(actual(data, "C04")[0]) == ("40.00", "39.98", "0.02", "0.01")
    data = inputs()
    data["records"]["cargas:delivery:D-SPLIT"]["net_amount"] = 10500
    found = actual(data, "C04")
    assert len(found) == 2
    assert {numbers(f) for f in found} == {
        ("40.00", "42.00", "-2.00", "0.01"),
        ("60.00", "63.00", "-3.00", "0.01"),
    }
    data = inputs()
    data["records"]["cargas:delivery:D-SPLIT"]["gallons"] = 0
    assert any(
        f["missing_reference"]["type"] == "positive_billable_volume"
        for f in actual(data, "C11")
    )
    data = inputs()
    del data["records"]["cargas:delivery:D-SPLIT"]
    assert any(
        f["missing_reference"]["lookup_key"] == "cargas:delivery:D-SPLIT"
        for f in actual(data, "C11")
    )


def test_discount_not_crosswalked_qbo_event_and_missing_original_credit():
    data = inputs("P05")
    del data["records"]["identity:pos_event:EVENT-T-DISCOUNT"]
    assert len(actual(data, "C05")) == 3
    data = inputs()
    data["records"]["qbo:CreditMemo:CM-BOUNDARY"]["LinkedTxn"] = []
    assert (
        actual(data, "C05")[0]["missing_reference"]["lookup_key"]
        == "credit:CM-BOUNDARY"
    )
    assert any(
        f["missing_reference"]["type"] == "credit_invoice" for f in actual(data, "C11")
    )
    data["records"]["qbo:CreditMemo:CM-BOUNDARY"]["AppliedAmount"] = 0
    assert actual(data, "C11") == []


def test_standalone_pos_refund_original_approval_and_limit():
    data = inputs()
    r = data["records"]
    del r["identity:pos_event:EVENT-REFUND"]
    row = r["pos:POS:T-REFUND:1"]
    assert actual(data, "C05")[0]["threshold"] == "approval required"
    row["approval_id"] = "APP-REFUND"
    assert actual(data, "C05") == []
    row["gross_amount"] = -10001
    assert numbers(actual(data, "C05")[0]) == ("100.01", "100.00", "0.01", "100.00")
    row["original_transaction_id"] = "MISSING"
    assert actual(data, "C05")[0]["severity"] == "high"
    row["gross_amount"] = 0
    assert actual(data, "C05") == []


def test_credit_ambiguous_mixed_or_repeated_allocation_no_guess():
    data = inputs()
    r = data["records"]
    pay = r["qbo:Payment:PAY-APPLIED"]
    pay["Line"][0]["LinkedTxn"] = [
        {"TxnType": "Invoice", "TxnId": "I-CREDIT"},
        {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"},
    ]
    pay["Line"][0]["Amount"] = 10001
    assert actual(data, "C06") == []
    assert actual(data, "C11")[0]["missing_reference"]["type"] == "credit_allocation"
    pay["Line"][0]["Amount"] = 10000
    pay["Line"][0]["LinkedTxn"].append(
        {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"}
    )
    assert actual(data, "C11")[0]["missing_reference"]["type"] == "credit_allocation"


def test_raw_duplicates_updates_and_no_similarity_matching():
    data = inputs()
    data["blocked"]["C03:qbo"] = {"status": "not_evaluated"}
    assert actual(data, "C03") == []
    data = inputs()
    row = copy.deepcopy(data["records"]["qbo:Payment:PAY-APPLIED"])
    row["Id"] = "DIFFERENT"
    data["records"]["qbo:Payment:DIFFERENT"] = row
    assert len(actual(data, "C03")) == 1
    row["PaymentRefNum"] = ""
    assert actual(data, "C03") == []


def test_settlement_not_due_pending_excluded_and_required_links():
    data = inputs()
    data["records"]["pos:batch:B-SETTLED"]["settled_at"] = data["run"]["as_of"]
    assert actual(data, "C07") == []
    data = inputs()
    data["records"]["pos:POS:T-PENDING:1"]["settlement_batch_id"] = "B-SETTLED"
    assert actual(data, "C07") == []
    # Delivery-linked tender uses Payment, not Invoice as the deposit cash link.
    data = inputs()
    r = data["records"]
    r["pos:POS:T-DELIVERY:1"]["settlement_batch_id"] = "B-SETTLED"
    found = actual(data, "C11")
    assert any(
        f["missing_reference"]["lookup_key"] == "qbo:Payment:PAY-DELIVERY"
        for f in found
    )


def test_posting_operational_payment_batch_missing_and_credit_sign():
    data = inputs()
    e = Engine(data)
    assert e.operational("PAY-DELIVERY") == ("qbo:Payment:PAY-DELIVERY", 20000)
    assert e.operational("B-SETTLED") == ("pos:batch:B-SETTLED", 47000)
    assert e.operational("MISSING") is None
    data["records"]["identity:posting:POST-I-PAY"]["external_ref"] = "MISSING"
    assert actual(data, "C11")[0]["missing_reference"]["type"] == "configured_posting"
    data = inputs()
    row = data["records"]["qbo:JournalEntry:JE-UNBALANCED"]
    row["Line"][0]["JournalEntryLineDetail"]["PostingType"] = "Credit"
    assert len(actual(data, "C12")) == 2


def test_pos_missing_customer_and_no_discount_approval():
    data = inputs()
    data["records"]["pos:POS:T-RETAIL:1"]["customer_id"] = "UNKNOWN"
    assert any(
        f["missing_reference"]["type"] == "customer" for f in actual(data, "C11")
    )
    data = inputs()
    data["records"]["pos:POS:T-DISCOUNT:1"]["approval_id"] = ""
    assert any(
        f["missing_reference"]["lookup_key"].startswith("approval_for:")
        for f in actual(data, "C11")
    )


def test_exact_gallon_grace_and_allocation_thresholds():
    data = inputs("P01")
    row = data["records"]["cargas:delivery:D-MISSING"]
    row["gallons"] = 1
    assert actual(data, "C01") == []
    row["gallons"] = 2
    assert numbers(actual(data, "C01")[0]) == ("0.002", "0.000", "0.002", "0.001")
    row["delivered_at"] = "2026-11-03T07:00:00+00:00"
    assert actual(data, "C01") == []
    row["delivered_at"] = "2026-11-03T06:59:59+00:00"
    assert len(actual(data, "C01")) == 1
    data = inputs("P02")
    row = data["records"]["qbo:Invoice:I-ORPHAN"]
    row["Line"][0]["SalesItemLineDetail"]["Qty"] = 1
    assert actual(data, "C02") == []
    row["Line"][0]["SalesItemLineDetail"]["Qty"] = 2
    assert numbers(actual(data, "C02")[0])[:3] == ("0.002", "0.000", "0.002")


def test_unapplied_and_excess_one_cent_pass_two_cent_fail():
    data = inputs()
    r = data["records"]
    r["qbo:Payment:PAY-UNAPPLIED"]["UnappliedAmt"] = 2
    assert numbers(actual(data, "C06")[0]) == ("0.02", "0.00", "0.02", "0.01")
    data = inputs()
    pay = data["records"]["qbo:Payment:PAY-APPLIED"]
    pay["Line"][0]["Amount"] = 10001
    assert actual(data, "C06") == []
    pay["Line"][0]["Amount"] = 10002
    assert numbers(actual(data, "C06")[0]) == ("100.02", "100.00", "0.02", "0.01")


def test_journal_tolerance_is_per_entry_not_global():
    data = inputs()
    r = data["records"]
    row = r["qbo:JournalEntry:JE-UNBALANCED"]
    row["Line"][1]["Amount"] = 9999
    assert actual(data, "C12") == []
    row["Line"][1]["Amount"] = 9998
    opposite = copy.deepcopy(row)
    opposite["Id"] = "OPPOSITE"
    opposite["Line"][0]["Amount"] = 9998
    opposite["Line"][1]["Amount"] = 10000
    r["qbo:JournalEntry:OPPOSITE"] = opposite
    found = actual(data, "C12")
    assert len(found) == 2
    assert {f["delta"] for f in found} == {"0.02", "-0.02"}


def test_accounting_uses_operational_net_excluding_tax_and_unrelated_journals():
    data = inputs()
    r = data["records"]
    r["identity:posting:POST-I-PAY"]["external_ref"] = "SR-TAX"
    for line in r["qbo:JournalEntry:JE-UNBALANCED"]["Line"]:
        line["Amount"] = 2000
    assert actual(data, "C12") == []
    assert Engine(data).operational("SR-TAX") == ("qbo:SalesReceipt:SR-TAX", 2000)


def test_valid_empty_optional_and_business_inputs():
    data = inputs()
    # Successful empty streams are ordinary evidence, not failed/missing feeds.
    data["records"] = {
        k: v for k, v in data["records"].items() if k.startswith("ar:snapshot:")
    }
    data["occurrences"] = []
    assert actual(data) == []


def test_deposit_opposite_line_errors_cannot_net_to_zero():
    data = inputs()
    row = data["records"]["qbo:Deposit:DEP-SHORT"]
    row["Line"][0]["Amount"] -= 1000
    row["Line"][1]["Amount"] += 1000
    found = actual(data, "C07")
    assert len(found) == 2
    assert {f["delta"] for f in found} == {"-10.00", "10.00"}


def test_missing_meter_ticket_and_unlinked_credit_are_not_invented():
    data = inputs("P01")
    data["records"]["cargas:delivery:D-MISSING"]["meter_ticket_id"] = ""
    assert actual(data, "C01")[0]["related_refs"] == []
    data = inputs()
    pay = data["records"]["qbo:Payment:PAY-APPLIED"]
    pay["Line"][0]["LinkedTxn"] = [{"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"}]
    assert actual(data, "C06") == []


def test_independent_adjustment_scope_block_and_missing_crosswalk_target():
    data = inputs("P05")
    data["blocked"]["C05:pos"] = {"status": "not_evaluated", "source_refs": []}
    found = actual(data, "C05")
    assert {f["source_refs"][0] for f in found} == {
        "qbo:CreditMemo:CM-UNUSUAL:1",
        "qbo:SalesReceipt:SR-DISCOUNT:1",
    }
    data = inputs()
    data["records"]["identity:pos_event:EVENT-T-DISCOUNT"]["qbo_id"] = "MISSING"
    assert actual(data) == []  # crosswalk not needed for standalone valid sale price


def test_extra_missing_deposit_link_prevents_comparison():
    data = inputs()
    data["records"]["qbo:Deposit:DEP-SHORT"]["Line"][2]["DepositLineDetail"].update(
        TxnType="Payment", TxnId="MISSING"
    )
    assert actual(data, "C07") == []
    assert (
        actual(data, "C11")[0]["missing_reference"]["lookup_key"]
        == "qbo:Payment:MISSING"
    )


def test_multiline_one_pos_transaction_is_not_business_duplicate():
    data = inputs()
    row = copy.deepcopy(data["records"]["pos:POS:T-EQUAL-A:1"])
    row["line_id"] = "2"
    data["records"]["pos:POS:T-EQUAL-A:2"] = row
    assert actual(data, "C03") == []


def test_financial_products_do_not_use_default_decimal_precision():
    data = inputs()
    row = data["records"]["pos:POS:T-EQUAL-A:1"]
    row["quantity"] = 9_000_000_000_000_000_000
    data["records"]["prices:price:PRICE-SERVICE"]["unit_price"] = (
        9_000_000_000_000_000_000
    )
    found = actual(data, "C04")
    target = next(f for f in found if "pos:POS:T-EQUAL-A:1" in f["source_refs"])
    assert target["expected"] == "810000000000000000000000000000000.00"


def test_unusual_discount_does_not_disappear_when_approval_missing():
    data = inputs("P05")
    del data["records"]["identity:approval:APP-DISCOUNT"]
    found = actual(data)
    assert any(f["finding_id"] == "C05|pos:POS:T-DISCOUNT:1" for f in found)
    assert any(f["check_id"] == "C11" for f in found)
    # Independent QBO adjustment detection needs no price-list source.
    data["blocked"].update({"C04:qbo": {}, "C05:pos": {}})
    assert any(
        f["finding_id"] == "C05|qbo:SalesReceipt:SR-DISCOUNT:1" for f in actual(data)
    )


def test_unlinked_cash_is_one_unapplied_payment_with_all_line_evidence():
    data = inputs()
    pay = data["records"]["qbo:Payment:PAY-APPLIED"]
    pay["UnappliedAmt"] = 10000
    pay["Line"][0]["LinkedTxn"] = []
    found = actual(data, "C06")
    assert len(found) == 1
    assert found[0]["source_refs"] == ["qbo:Payment:PAY-APPLIED"]
    assert found[0]["related_refs"] == [
        "ar:snapshot:AR-OPEN",
        "qbo:Payment:PAY-APPLIED:1",
    ]


def test_pos_declared_unit_price_arithmetic_not_just_effective_price():
    data = inputs()
    row = data["records"]["pos:POS:T-EQUAL-A:1"]
    row["unit_price"] = 2100
    found = actual(data, "C04")
    assert len(found) == 1
    assert numbers(found[0]) == ("20.00", "21.00", "-1.00", "0.01")


def test_fractional_percent_above_limit_remains_visible():
    data = inputs()
    row = data["records"]["pos:POS:T-DISCOUNT:1"]
    row.update(unit_price=1000000, discount_amount=100001)
    found = next(
        f for f in actual(data, "C05") if f["source_refs"] == ["pos:POS:T-DISCOUNT:1"]
    )
    assert numbers(found) == ("10.0001", "10.00", "0.0001", "10.00")


def test_void_deposit_and_configured_journal_are_not_evidence():
    data = inputs()
    data["records"]["qbo:Deposit:DEP-SHORT"]["status"] = "void"
    assert actual(data, "C07")[0]["missing_reference"]["type"] == "Deposit"
    data = inputs()
    data["records"]["qbo:JournalEntry:JE-UNBALANCED"]["status"] = "void"
    assert actual(data, "C12") == []
    assert actual(data, "C11")[0]["missing_reference"]["type"] == "configured_posting"


def test_tax_line_without_optional_id_uses_immutable_source_pointer():
    files = generate()
    qbo = json.loads(files["qbo.json"])
    row = next(r for r in qbo["SalesReceipt"] if r["Id"] == "SR-TAX")
    del row["TxnTaxDetail"]["TaxLine"][0]["Id"]
    row["TxnTaxDetail"]["TaxLine"][0]["Amount"] = "1.98"
    files["qbo.json"] = json.dumps(qbo).encode()
    db = ingest(files.__getitem__)
    try:
        data = from_database(db)
    finally:
        db.close()
    found = actual(data, "C04")
    assert len(found) == 1
    assert (
        "file:qbo.json#/SalesReceipt/5/TxnTaxDetail/TaxLine/0"
        in found[0]["related_refs"]
    )


def test_qbo_failure_suppresses_pos_price_without_missing_customer_cascade():
    files = generate()
    files["qbo.json"] = b"bad"
    db = ingest(files.__getitem__)
    try:
        data = from_database(db)
    finally:
        db.close()
    assert actual(data) == []
    assert reconcile(data)["not_evaluated"]["C04:pos"]["source_refs"] == [
        "manifest:QBO-OK"
    ]


def test_pos_failure_suppresses_configured_batch_posting_but_not_journal_balance():
    data = inputs("P11")
    data["records"]["identity:posting:POST-I-PAY"]["external_ref"] = "B-SETTLED"
    assert actual(data) == []
    assert "C12:identity:posting:POST-I-PAY" in reconcile(data)["not_evaluated"]


def test_price_discrepancy_preserves_discount_approval_evidence():
    data = inputs()
    row = data["records"]["pos:POS:T-DISCOUNT:1"]
    row.update(net_amount=8998, gross_amount=8998)
    found = actual(data, "C04")
    assert "identity:approval:APP-DISCOUNT" in found[0]["related_refs"]
    data = inputs()
    row = data["records"]["qbo:SalesReceipt:SR-DISCOUNT"]
    row["TotalAmt"] = row["Line"][0]["Amount"] = 8998
    found = actual(data, "C04")
    assert "identity:approval:APP-DISCOUNT" in found[0]["related_refs"]


def test_nonzero_opening_customer_ar_is_not_invented_invoice_residual():
    data = inputs()
    r = data["records"]
    r["ar:snapshot:AR-OPEN"]["balances"][0]["amount"] = 12345
    r["qbo:Invoice:I-PAID"]["EventAt"] = "2026-10-25T07:00:00+00:00"
    assert actual(data, "C06") == []
    found = actual(data, "C11")
    assert len(found) == 1
    assert found[0]["missing_reference"] == {
        "system": "qbo",
        "type": "invoice_balance",
        "lookup_key": "qbo:Invoice:I-PAID",
    }
