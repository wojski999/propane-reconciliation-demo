"""Independent exposure estimates and conservative unsupported-source behavior."""

import copy

import pytest
from test_rules import inputs

from propane_demo.presentation import exposures
from propane_demo.rules import reconcile


def test_exposure_estimates_are_separate_exact_and_evidence_bound():
    data = inputs("showcase")
    before = copy.deepcopy(data)
    estimates = exposures(data, reconcile(data))
    assert data == before
    assert estimates["C01|cargas:delivery:D-MISSING"]["value"] == "200.00"
    assert (
        "prices:price:PRICE-BASE"
        in estimates["C01|cargas:delivery:D-MISSING"]["source_refs"]
    )
    assert estimates["C03|pos:POS:T-DUP-A:1|pos:POS:T-DUP-B:1"]["value"] == "20.00"
    assert len(estimates) == 2  # No invented inventory cost or calculated audit total.


@pytest.mark.parametrize(
    "support", ["customer", "item", "qbo_customer", "price", "two_prices", "stale"]
)
def test_unbilled_estimate_requires_unambiguous_fresh_effective_price_support(support):
    data = inputs("P01")
    checks = reconcile(data)
    records = data["records"]
    if support in {"customer", "item", "qbo_customer", "price"}:
        key = {
            "customer": "identity:customer:CUSTOMER-1",
            "item": "identity:item:ITEM-1",
            "qbo_customer": "qbo:Customer:C-1",
            "price": "prices:price:PRICE-BASE",
        }[support]
        del records[key]
    elif support == "two_prices":
        records["prices:price:OTHER"] = records["prices:price:PRICE-BASE"]
    else:
        checks["not_evaluated"]["C04:qbo"] = {"status": "not_evaluated"}
    assert exposures(data, checks) == {}


def test_duplicate_estimate_does_not_value_repeat_import_or_inconsistent_amounts():
    data = inputs("raw-repeat")
    assert exposures(data, reconcile(data)) == {}
    data = inputs("P03")
    checks = reconcile(data)
    data["records"]["pos:POS:T-DUP-B:1"]["net_amount"] = 2100
    assert exposures(data, checks) == {}


def test_unbilled_estimate_rounds_cents_half_up_without_changing_quantities():
    data = inputs("P01")
    checks = reconcile(data)
    finding = checks["findings"][0]
    finding["delta"] = "0.005"
    data["records"]["prices:price:PRICE-BASE"]["unit_price"] = 100
    assert exposures(data, checks)[finding["finding_id"]]["value"] == "0.01"


def test_unrelated_blocked_check_does_not_invent_a_price_gap():
    data = inputs("P01")
    checks = reconcile(data)
    checks["not_evaluated"]["C08"] = {"status": "not_evaluated"}
    assert next(iter(exposures(data, checks).values()))["value"] == "200.00"


def test_non_pos_duplicate_has_no_assumed_net_sale_exposure():
    data = inputs()
    assert (
        exposures(
            data,
            {
                "findings": [
                    {
                        "check_id": "C03",
                        "status": "exception",
                        "source_refs": ["qbo:Invoice:I-PRICE"],
                    }
                ],
                "not_evaluated": {},
            },
        )
        == {}
    )


def test_unbilled_estimate_uses_effective_price_not_fixture_answer():
    data = inputs("P01")
    checks = reconcile(data)
    data["records"]["prices:price:PRICE-BASE"]["unit_price"] = 300
    assert next(iter(exposures(data, checks).values()))["value"] == "300.00"
