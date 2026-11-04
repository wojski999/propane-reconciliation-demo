"""Hand-calculated expectations independent of production KPI algorithms."""

import copy
from datetime import date
from decimal import Decimal

import pytest
from test_rules import inputs

from propane_demo.kpis import KPIs, Worksheet, calculate
from propane_demo.rules import reconcile


def values(data=None, checks=None):
    data = inputs() if data is None else data
    return calculate(data, reconcile(data) if checks is None else checks)


def isolated(data):
    return KPIs(data, {"not_evaluated": {}})


def test_clean_hand_calculated_worksheet():
    k = values()
    # Delivery 100+100+50+100+50+20+30+50+.005+100; retail 50+1*5.
    assert {n: s["value"] for n, s in k.items()} == {
        "delivered": "600.005",
        "retail": "55.000",
        "total_gallons": "655.005",
        # Invoice net 860.01 + receipt net 490.01 - refund net 100.
        "revenue": "1250.02",
        # Opening 0 + gross invoices 1260.01 - credit 100 - cash 100 - cash 200.
        "AR": "860.01",
    }
    assert all(s["status"] == "complete" for s in k.values())
    assert k["AR"]["unapplied_cash"]["value"] == "25.01"
    assert k["AR"]["unapplied_credits"]["value"] == "0.00"
    assert all(c["delta"] == "0.00" for c in k["AR"]["reported_balance_comparisons"])
    # Discounts already net; no duplicate POS or container deposit revenue.
    assert any(
        c["kind"] == "container_deposit_excluded" and c["amount"] == "0.00"
        for c in k["revenue"]["contributions"]
    )


@pytest.mark.parametrize(
    "day,delivered,total",
    [
        (date(2026, 3, 8), "500.005", "555.005"),
        (date(2026, 11, 1), "600.005", "655.005"),
    ],
)
def test_dst_cutoff_independent_volume_and_posting_date(day, delivered, total):
    k = values(inputs(business_date=day))
    assert k["delivered"]["value"] == delivered
    assert k["total_gallons"]["value"] == total
    # I-GRACE retains the explicit posting date even if EventAt is before midnight.
    assert k["revenue"]["value"] == "1250.02"


@pytest.mark.parametrize("basis", ["", "observed"])
def test_unmeasured_fraction_delivery_never_infers_basis(basis):
    data = inputs()
    data["records"]["cargas:delivery:D-FRACTION"]["gallon_basis"] = basis
    k = values(data)
    assert k["delivered"]["status"] == "partial"
    assert k["delivered"]["value"] is None
    assert k["delivered"]["known_value"] == "600.000"
    assert "D-FRACTION" in k["delivered"]["gaps"][0]["missing_lookup_key"]
    assert k["total_gallons"]["value"] is None


def test_half_open_delivery_boundaries_cancelled_and_no_qbo_double_count():
    data = inputs()
    r = data["records"]["cargas:delivery:D-FRACTION"]
    r["delivered_at"] = data["run"]["window_end"]
    assert isolated(data).volumes()["delivered"]["value"] == "600.000"
    r["delivered_at"] = data["run"]["window_start"]
    assert isolated(data).volumes()["delivered"]["value"] == "600.005"
    data["records"]["cargas:delivery:D-CANCELLED"]["status"] = "completed"
    assert isolated(data).volumes()["delivered"]["value"] == "700.005"


@pytest.mark.parametrize(
    "mutation,key",
    [
        ("customer", "delivered"),
        ("item", "delivered"),
        ("pos_event", "retail"),
        ("fill", "retail"),
        ("pos_item", "retail"),
        ("delivery", "retail"),
    ],
)
def test_missing_volume_support_retains_known_contributions(mutation, key):
    data = inputs()
    r = data["records"]
    if mutation == "customer":
        del r["identity:customer:CUSTOMER-1"]
    elif mutation == "item":
        del r["identity:item:ITEM-1"]
    elif mutation == "pos_event":
        del r["identity:pos_event:EVENT-T-RETAIL"]
    elif mutation == "fill":
        del r["identity:fill:CYLINDER"]
    elif mutation == "pos_item":
        del r["qbo:Item:CYLINDER"]
    else:
        del r["cargas:delivery:D-OUT"]
    result = isolated(data).volumes()[key]
    assert result["value"] is None and result["gaps"]
    assert result["status"] in {"partial", "unavailable"}


@pytest.mark.parametrize("scope", ["delivered", "retail", "revenue", "AR"])
def test_blocked_source_never_zero(scope):
    data = inputs()
    k = calculate(
        data,
        {
            "not_evaluated": {
                "KPI:" + scope: {
                    "source_refs": ["manifest:MISSING"],
                    "missing_lookup_key": "failed_source",
                }
            }
        },
    )
    assert k[scope]["value"] is None
    assert k[scope]["status"] == "unavailable"


def test_revenue_posting_window_tax_deposit_discount_and_void():
    data = inputs()
    r = data["records"]
    # $22 gross contains $2 tax; net line remains $20. $10 deposit excluded.
    # Changing tax and discount metadata must not subtract either from net again.
    r["qbo:SalesReceipt:SR-TAX"]["TxnTaxDetail"]["TotalTax"] = 99999
    r["qbo:SalesReceipt:SR-DISCOUNT"]["Line"][0]["DiscountAmount"] = 3000
    r["qbo:Invoice:I-VOID"]["TotalAmt"] = 8000
    assert isolated(data).revenue()["value"] == "1250.02"
    r["qbo:Invoice:I-PRICE"]["TxnDate"] = "2026-11-02"
    assert isolated(data).revenue()["value"] == "1050.02"
    del r["qbo:Item:SERVICE"]
    assert isolated(data).revenue()["value"] is None


def test_adjustment_event_dedup_and_cash_refund_of_prior_credit():
    data = inputs()
    r = data["records"]
    credit = r["qbo:CreditMemo:CM-BOUNDARY"]
    refund = copy.deepcopy(credit)
    credit.update(TxnDate="2026-11-03", RevenueEvent="same")
    refund.update(Id="RR-OTHER", RevenueEvent="same", TxnDate="2026-11-03")
    r["qbo:RefundReceipt:RR-OTHER"] = refund
    # Credit $100 reduces revenue once; refund is the same adjustment.
    assert isolated(data).revenue()["value"] == "1150.02"
    credit["TxnDate"] = "2026-11-02"
    assert isolated(data).revenue()["value"] == "1250.02"
    refund["LinkedTxn"] = [{"TxnId": "CM-BOUNDARY", "TxnType": "CreditMemo"}]
    refund.pop("RevenueEvent")
    assert isolated(data).revenue()["value"] == "1250.02"
    refund["LinkedTxn"][0]["TxnId"] = "MISSING"
    assert isolated(data).revenue()["value"] is None


def test_conflicting_adjustment_event_not_guessed():
    data = inputs()
    r = data["records"]
    refund = r["qbo:RefundReceipt:RR-BOUNDARY"]
    duplicate = copy.deepcopy(refund)
    duplicate["TotalAmt"] = 11000
    r["qbo:RefundReceipt:OTHER"] = duplicate
    result = isolated(data).revenue()
    assert result["status"] == "partial" and result["value"] is None
    refund["LinkedTxn"] = []
    assert any(
        "original_sale" in g["missing_lookup_key"]
        for g in isolated(data).revenue()["gaps"]
    )


@pytest.mark.parametrize(
    "mode", ["missing_event", "missing_qbo", "void_qbo", "wrong_entity"]
)
def test_revenue_missing_conflicting_crosswalk(mode):
    data = inputs()
    r = data["records"]
    if mode == "missing_event":
        del r["identity:pos_event:EVENT-T-RETAIL"]
    elif mode == "missing_qbo":
        del r["qbo:SalesReceipt:SR-RETAIL"]
    elif mode == "void_qbo":
        r["qbo:SalesReceipt:SR-RETAIL"]["status"] = "void"
    else:
        r["identity:pos_event:EVENT-T-RETAIL"]["qbo_entity"] = "Invoice"
    assert isolated(data).revenue()["value"] is None


def test_ar_credit_payment_crosslink_is_not_cash_or_second_credit():
    data = inputs()
    r = data["records"]
    pay = copy.deepcopy(r["qbo:Payment:PAY-APPLIED"])
    pay.update(
        Id="PAY-CREDIT",
        EventAt="2026-11-03T10:00:00+00:00",
        TotalAmt=10000,
        UnappliedAmt=0,
    )
    pay["Line"][0]["LinkedTxn"] = [
        {"TxnType": "Invoice", "TxnId": "I-CREDIT"},
        {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"},
    ]
    r["qbo:Payment:PAY-CREDIT"] = pay
    result = isolated(data).ar()
    assert result["value"] == "860.01"
    assert result["unapplied_cash"]["value"] == "25.01"
    assert result["unapplied_credits"]["value"] == "0.00"
    assert any(
        c["kind"] == "credit_application" and c["amount"] == "0.00"
        for c in result["contributions"]
    )
    # Only $50 recorded on CM; remaining $50 applied by Payment, no cash.
    r["qbo:CreditMemo:CM-BOUNDARY"]["AppliedAmount"] = 5000
    assert isolated(data).ar()["value"] == "860.01"
    r["qbo:CreditMemo:CM-BOUNDARY"]["AppliedAmount"] = 0
    assert isolated(data).ar()["value"] == "860.01"


def test_ar_opening_and_late_events_order_and_balance_not_additive():
    data = inputs()
    r = data["records"]
    r["ar:snapshot:AR-OPEN"]["balances"][0]["amount"] = 5000
    r["qbo:Invoice:I-PRICE"]["Balance"] = 999999
    result = isolated(data).ar()
    assert result["value"] == "910.01"
    assert any(c["delta"] == "9799.99" for c in result["reported_balance_comparisons"])
    # Payment exactly cutoff applies; later than cutoff does not.
    r["qbo:Payment:PAY-DELIVERY"]["EventAt"] = data["run"]["as_of"]
    assert isolated(data).ar()["value"] == "910.01"
    r["qbo:Payment:PAY-DELIVERY"]["EventAt"] = "2026-11-04T07:00:00.000001+00:00"
    assert isolated(data).ar()["value"] == "1110.01"


@pytest.mark.parametrize(
    "mode",
    [
        "snapshot",
        "customer",
        "cutoff",
        "credit_target",
        "payment_target",
        "credit_link",
        "credit_no_invoice",
        "credit_over",
        "credit_multi",
    ],
)
def test_ar_missing_or_conflicting_history(mode):
    data = inputs()
    r = data["records"]
    if mode == "snapshot":
        del r["ar:snapshot:AR-OPEN"]
    elif mode == "customer":
        r["ar:snapshot:AR-OPEN"]["balances"] = []
    elif mode == "cutoff":
        r["ar:snapshot:AR-OPEN"]["as_of"] = "2026-11-05T07:00:00+00:00"
    elif mode == "credit_target":
        r["qbo:CreditMemo:CM-BOUNDARY"]["LinkedTxn"] = []
    else:
        line = r["qbo:Payment:PAY-APPLIED"]["Line"][0]
        if mode == "payment_target":
            line["LinkedTxn"][0]["TxnId"] = "UNKNOWN"
        elif mode == "credit_link":
            line["LinkedTxn"].append({"TxnType": "CreditMemo", "TxnId": "UNKNOWN"})
        elif mode == "credit_no_invoice":
            line["LinkedTxn"] = [{"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"}]
        else:
            line["LinkedTxn"] = [
                {"TxnType": "Invoice", "TxnId": "I-CREDIT"},
                {"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"},
            ]
            if mode == "credit_over":
                line["Amount"] = 10001
            else:
                line["LinkedTxn"].append({"TxnType": "CreditMemo", "TxnId": "OTHER"})
    result = isolated(data).ar()
    assert result["value"] is None and result["gaps"]


def test_reordering_is_deterministic_and_does_not_mutate_input():
    data = inputs()
    original = copy.deepcopy(data)
    result = values(data)
    assert data == original
    data["records"] = dict(reversed(list(data["records"].items())))
    assert values(data) == result


def test_empty_complete_sheet_and_partial_zero_are_distinct():
    sheet = Worksheet("USD")
    assert sheet.result()["value"] == "0.00"
    sheet.add("known_zero", Decimal(0), ["source:zero"])
    sheet.gap("missing", ["source:manifest"])
    assert sheet.result()["value"] is None
    assert sheet.result()["status"] == "partial"


def test_conflicting_pos_money_and_credit_targets():
    data = inputs()
    data["records"]["pos:POS:T-RETAIL:1"]["gross_amount"] = 999
    assert isolated(data).revenue()["value"] is None
    data = inputs()
    credit = data["records"]["qbo:CreditMemo:CM-BOUNDARY"]
    credit["AppliedAmount"] = 10001
    assert isolated(data).ar()["value"] is None
    credit["AppliedAmount"] = 10000
    credit["LinkedTxn"][0]["TxnId"] = "MISSING"
    assert isolated(data).ar()["value"] is None


def test_stale_qbo_item_classification_invalidates_retail():
    k = values(inputs("P10"))
    assert k["retail"]["status"] == "unavailable"
    assert (
        k["retail"]["gaps"][0]["missing_lookup_key"] == "fresh_qbo_item_classification"
    )


def test_unlinked_payment_line_is_unapplied_not_an_invoice_reduction():
    data = inputs()
    row = data["records"]["qbo:Payment:PAY-UNAPPLIED"]
    row["Line"] = [{"Id": "1", "Amount": 1, "LinkedTxn": []}]
    result = isolated(data).ar()
    assert result["value"] == "860.01"
    assert result["unapplied_cash"]["value"] == "25.01"


def test_refund_with_credit_link_and_matching_event_is_settlement_only():
    data = inputs()
    r = data["records"]
    credit = r["qbo:CreditMemo:CM-BOUNDARY"]
    credit["RevenueEvent"] = "same-event"
    refund = r["qbo:RefundReceipt:RR-BOUNDARY"]
    refund["RevenueEvent"] = "same-event"
    refund["LinkedTxn"] = [{"TxnType": "CreditMemo", "TxnId": "CM-BOUNDARY"}]
    # Today's $100 refund settles yesterday's $100 credit: do not reduce again.
    assert isolated(data).revenue()["value"] == "1350.02"
    refund["TotalAmt"] = 10001
    assert isolated(data).revenue()["value"] is None
    refund["TotalAmt"] = 10000
    credit["status"] = "void"
    assert isolated(data).revenue()["value"] is None


def test_equal_gross_adjustment_events_with_different_net_are_partial():
    data = inputs()
    r = data["records"]
    refund = copy.deepcopy(r["qbo:RefundReceipt:RR-BOUNDARY"])
    refund["Line"][0]["Amount"] = 9000
    r["qbo:RefundReceipt:OTHER"] = refund
    assert isolated(data).revenue()["value"] is None


def test_cross_customer_payment_cannot_supply_known_ar():
    data = inputs()
    r = data["records"]
    r["ar:snapshot:AR-OPEN"]["balances"].append({"customer_id": "OTHER", "amount": 0})
    r["qbo:Payment:PAY-APPLIED"]["CustomerRef"] = {"value": "OTHER"}
    result = isolated(data).ar()
    assert result["value"] is None
    assert result["gaps"][0]["missing_lookup_key"].startswith("same_customer")
