"""Strict fictional boundary schema; financial values become scaled integers."""

import re
from datetime import date, datetime
from decimal import Decimal

from propane_demo.contracts import CSV_FIELDS, QBO_ENTITIES


class Invalid(ValueError):
    """Safe machine code and input pointer, never raw exception text."""

    def __init__(self, code, pointer=""):
        self.code, self.pointer = code, pointer
        super().__init__(code)


def require(condition, code="SCHEMA"):
    if not condition:
        raise Invalid(code)


def text(value):
    require(isinstance(value, str) and bool(value.strip()))
    return value


def identifier(value):
    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+", text(value))), "IDENTIFIER")
    return value


def instant(value):
    try:
        result = datetime.fromisoformat(text(value))
    except ValueError:
        raise Invalid("TIMESTAMP") from None
    require(result.tzinfo is not None, "TIMESTAMP")
    return result


def day(value):
    try:
        return date.fromisoformat(text(value))
    except ValueError:
        raise Invalid("DATE") from None


def integer(value):
    require(isinstance(value, str) and bool(re.fullmatch(r"0|[1-9][0-9]*", value)))
    require(len(value) <= 19, "INTEGER_RANGE")
    result = int(value)
    require(result <= 2**63 - 1, "INTEGER_RANGE")
    return result


def scaled(value, places):
    require(
        isinstance(value, str) and bool(re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value)),
        "DECIMAL",
    )
    # Bound length before Decimal arithmetic; never silently round imports.
    require(len(value) <= 24, "DECIMAL_RANGE")
    number = Decimal(value) * 10**places
    require(number == number.to_integral_value(), "PRECISION")
    require(-(2**63) <= number <= 2**63 - 1, "DECIMAL_RANGE")
    return int(number)


MONEY = set(
    "unit_price net_amount discount_amount tax_amount gross_amount gross refunds "
    "fees net Amount TotalAmt Balance UnappliedAmt UnitPrice DiscountAmount "
    "AppliedAmount TotalTax amount".split()
)
QUANTITY = set("gallons quantity Qty uncertainty_gallons capacity_gallons".split())
ENUMS = {
    "gallon_basis": {"observed", "net_60F"},
    "unit": {"gallon", "each", "cylinder"},
    "quality": {"valid", "uncertain", "invalid"},
    "movement_type": {
        "purchase",
        "transfer_in",
        "transfer_out",
        "customer_delivery",
        "retail_sale",
    },
    "tender": {"card", "cash", "account"},
    "PostingType": {"Debit", "Credit"},
    "Classification": {
        "delivery",
        "service",
        "retail",
        "cylinder",
        "deposit",
        "container_deposit",
    },
}


def normalize(value, key=""):
    """One recursive representation: exact source strings or scaled integers."""
    if key in MONEY:
        return scaled(value, 2)
    if key in QUANTITY:
        return scaled(value, 3)
    if key in {"approved_discount_pct", "temperature_f"}:
        return scaled(value, 3)
    if key in ENUMS:
        require(value in ENUMS[key], "ENUM")
    if isinstance(value, dict):
        return {k: normalize(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    require(value is None or type(value) in {str, int, bool}, "TYPE")
    return value


def fields(row, required):
    require(isinstance(row, dict))
    require(set(required) <= row.keys())
    for name in required:
        require(row[name] is not None)


def ref(value):
    fields(value, ["value"])
    identifier(value["value"])


def links(rows):
    require(isinstance(rows, list))
    for link in rows:
        fields(link, ["TxnId", "TxnType"])
        identifier(link["TxnId"])
        require(link["TxnType"] in QBO_ENTITIES, "REFERENCE")


def qbo(entity, row):
    fields(row, ["Id", "SyncToken", "MetaData"])
    identifier(row["Id"])
    integer(row["SyncToken"])
    fields(row["MetaData"], ["LastUpdatedTime"])
    instant(row["MetaData"]["LastUpdatedTime"])
    if entity in {"Customer", "Item"}:
        require("Line" not in row)
        for key in (
            ("DisplayName", "CustomerClass")
            if entity == "Customer"
            else ("Name", "Classification")
        ):
            text(row[key])
    else:
        fields(row, ["TxnDate", "EventAt", "TotalAmt", "Line", "LinkedTxn"])
        day(row["TxnDate"])
        instant(row["EventAt"])
        links(row["LinkedTxn"])
        if entity not in {"JournalEntry", "Deposit"}:
            ref(row["CustomerRef"])
            text(row["PaymentRefNum" if entity == "Payment" else "DocNumber"])
        if entity == "Invoice":
            scaled(row["Balance"], 2)
        if entity == "Payment":
            scaled(row["UnappliedAmt"], 2)
        if entity == "CreditMemo":
            scaled(row["AppliedAmount"], 2)
        if entity == "RefundReceipt" and "RevenueEvent" in row:
            identifier(row["RevenueEvent"])
        if "TxnTaxDetail" in row:
            fields(row["TxnTaxDetail"], ["TotalTax", "TaxLine"])
            require(isinstance(row["TxnTaxDetail"]["TaxLine"], list))
            for tax_line in row["TxnTaxDetail"]["TaxLine"]:
                fields(tax_line, ["Amount"])
        require(
            isinstance(row["Line"], list) and (entity == "Payment" or bool(row["Line"]))
        )
        seen = set()
        for line in row["Line"]:
            fields(line, ["Id", "Amount"])
            identifier(line["Id"])
            require(line["Id"] not in seen, "DUPLICATE_KEY")
            seen.add(line["Id"])
            if entity == "Payment":
                links(line["LinkedTxn"])
            elif entity in {"JournalEntry", "Deposit"}:
                detail = line[entity + "LineDetail"]
                ref(detail["AccountRef"])
                if entity == "JournalEntry":
                    require(detail["PostingType"] in ENUMS["PostingType"], "ENUM")
                elif "TxnId" in detail:
                    links([detail])
            else:
                require(line["DetailType"] == "SalesItemLineDetail")
                detail = line["SalesItemLineDetail"]
                fields(detail, ["ItemRef", "Qty", "UnitPrice", "TaxCodeRef"])
                ref(detail["ItemRef"])
                ref(detail["TaxCodeRef"])
    if "status" in row:
        require(row["status"] in {"active", "void"}, "ENUM")
    return normalize(row)


CSV_KEYS = {
    "deliveries.csv": ("cargas", "delivery", "ticket_id"),
    "readings.csv": ("cargas", "reading", "reading_id"),
    "pos.csv": ("pos", "POS", "transaction_id"),
    "settlements.csv": ("pos", "batch", "batch_id"),
    "movements.csv": ("inventory", "movement", "movement_id"),
    "prices.csv": ("prices", "price", "price_id"),
}
OPTIONAL_CSV = set(
    "truck_id external_invoice_id meter_ticket_id original_transaction_id "
    "settlement_batch_id inventory_asset_id approval_id counterparty_asset_id "
    "transfer_id qbo_deposit_id".split()
)


def csv_row(name, row):
    require(set(row) == set(CSV_FIELDS[name]), "CSV_SCHEMA")
    for key, value in row.items():
        require(isinstance(value, str), "CSV_SCHEMA")
        if key not in OPTIONAL_CSV:
            text(value)
        if value and (key.endswith("_id") or key == "external_reference"):
            for component in value.split(":") if key == "source_id" else [value]:
                identifier(component)
    if "status" in row:
        allowed = (
            {"completed", "cancelled"}
            if name == "deliveries.csv"
            else {"captured", "pending", "void", "refunded"}
        )
        require(row["status"] in allowed, "ENUM")
    if name == "prices.csv":
        require(day(row["effective_from"]) < day(row["effective_to"]), "INTERVAL")
    result = normalize(row)
    for key in {"gallons", "uncertainty_gallons", "capacity_gallons"} & row.keys():
        require(result[key] >= 0, "NEGATIVE")
    if name == "movements.csv":
        require(result["quantity"] > 0, "NEGATIVE")
        if row["movement_type"].startswith("transfer_"):
            text(row["transfer_id"])
            text(row["counterparty_asset_id"])
    if name == "readings.csv":
        require(result["gallons"] <= result["capacity_gallons"], "CAPACITY")
    if name == "prices.csv":
        require(0 <= result["approved_discount_pct"] <= 100000, "PERCENT")
    return result


def timestamps(value):
    """Only event instants, not effective-price or posting dates."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {
                "LastUpdatedTime",
                "EventAt",
                "delivered_at",
                "observed_at",
                "occurred_at",
                "settled_at",
                "as_of",
            }:
                yield instant(child)
            else:
                yield from timestamps(child)
    elif isinstance(value, list):
        for child in value:
            yield from timestamps(child)
