"""Pure, evidence-bound exposure estimates; never financial KPI totals or postings."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo


def exposures(inputs, checks):
    records = inputs["records"]
    estimates = {}
    for finding in checks["findings"]:
        refs = finding["source_refs"]
        if finding["check_id"] == "C01" and not any(
            scope.startswith("C04") for scope in checks["not_evaluated"]
        ):
            row = records[refs[0]]
            customers = [
                (k, v)
                for k, v in records.items()
                if k.startswith("identity:customer:")
                and v["cargas"] == row["customer_id"]
            ]
            items = [
                (k, v)
                for k, v in records.items()
                if k.startswith("identity:item:") and v["cargas"] == row["item_id"]
            ]
            if len(customers) != 1 or len(items) != 1:
                continue
            customer_key = "qbo:Customer:" + customers[0][1]["qbo"]
            customer = records.get(customer_key)
            if customer is None:
                continue
            day = (
                datetime.fromisoformat(row["delivered_at"])
                .astimezone(ZoneInfo("America/Denver"))
                .date()
                .isoformat()
            )
            prices = [
                (k, p)
                for k, p in records.items()
                if k.startswith("prices:price:")
                and p["item_id"] == items[0][1]["qbo"]
                and p["customer_class"] == customer["CustomerClass"]
                and p["unit"] == "gallon"
                and p["gallon_basis"] == row["gallon_basis"]
                and p["effective_from"] <= day < p["effective_to"]
            ]
            if len(prices) != 1:
                continue
            amount = (
                Decimal(finding["delta"]) * Decimal(prices[0][1]["unit_price"]) / 100
            )
            estimates[finding["finding_id"]] = {
                "value": str(amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)),
                "kind": "unbilled_at_list_price",
                "source_refs": sorted(
                    [*refs, prices[0][0], customers[0][0], items[0][0], customer_key]
                ),
            }
        if (
            finding["check_id"] == "C03"
            and finding["status"] == "exception"
            and all(ref.startswith("pos:POS:") for ref in refs)
        ):
            amounts = {records[ref]["net_amount"] for ref in refs}
            if len(amounts) == 1:
                amount = Decimal(finding["delta"]) * Decimal(amounts.pop()) / 100
                estimates[finding["finding_id"]] = {
                    "value": str(
                        amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                    ),
                    "kind": "possible_duplicate_net_sales",
                    "source_refs": refs,
                }
    return estimates
