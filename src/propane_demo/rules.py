"""Pure section-11 step-3 checks over validated, scaled source records.

No IO, database, generator, oracle, clock or scenario dependency. Money is Decimal
in cents internally; quantities are thousandths. Only explicit evidence is used.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from zoneinfo import ZoneInfo

D = Decimal
CENT = D(1)


def stamp(value):
    return datetime.fromisoformat(value)


def money(value):
    return format(D(value) / 100, ".2f")


def volume(value):
    return format(D(value) / 1000, ".3f")


def percentage(value):
    whole, _, fraction = format(value, "f").partition(".")
    return whole + "." + fraction.rstrip("0").ljust(2, "0")


def rounded(value):
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)


def linked(row):
    return [f"qbo:{x['TxnType']}:{x['TxnId']}" for x in row.get("LinkedTxn", [])]


def active(row):
    return row.get("status", "") not in {"void", "cancelled", "pending"}


class Engine:
    """A fresh instance per call; no mutation of caller-owned inputs."""

    def __init__(self, inputs):
        self.r = inputs["records"]
        self.run, self.p = inputs["run"], inputs["policy"]
        self.now = stamp(self.run["as_of"])
        self.policy_ref = "policy:" + self.p["policy_id"]
        self.blocked = dict(inputs["blocked"])
        self.unavailable_sources = inputs.get("unavailable_sources", {})
        self.occurrences = inputs["occurrences"]
        self.pointers = inputs["pointers"]
        self.findings = {}
        self.partial = {}

    def rows(self, prefix):
        return [(k, v) for k, v in sorted(self.r.items()) if k.startswith(prefix)]

    def parents(self, entity):
        return [
            (k, v)
            for k, v in self.rows("qbo:" + entity + ":")
            if k.count(":") == 2 and active(v)
        ]

    def allowed(self, scope):
        return scope not in self.blocked

    def emit(
        self,
        check,
        refs,
        actual,
        expected,
        threshold,
        related=(),
        severity="high",
        missing=None,
        status="exception",
        explanation=None,
        formatter=money,
    ):
        refs = sorted(set(refs))
        finding_id = "|".join([check, *refs])
        delta = None if actual is None or expected is None else actual - expected
        self.findings[finding_id] = {
            "finding_id": finding_id,
            "check_id": check,
            "severity": severity,
            "status": status,
            "business_date": self.run["business_date"],
            "rule_version": self.p["version"],
            "actual": None if actual is None else formatter(actual),
            "expected": None if expected is None else formatter(expected),
            "delta": None if delta is None else formatter(delta),
            "threshold": threshold,
            "source_refs": refs,
            "related_refs": sorted(set(related) - set(refs)),
            "missing_reference": missing,
            "explanation": explanation
            or f"{check}: inspect the compared values and evidence.",
        }

    def missing(self, refs, system, kind, key, scope, related=(), severity="medium"):
        self.emit(
            "C11",
            refs,
            None,
            None,
            "required",
            [self.policy_ref, *related],
            severity,
            {"system": system, "type": kind, "lookup_key": key},
            "not_evaluated",
            "Required supporting evidence is absent or ambiguous.",
        )
        self.partial[scope] = {
            "status": "not_evaluated",
            "source_refs": sorted(refs),
            "missing_lookup_key": key,
        }

    def old(self, row, field, hours):
        return self.now - stamp(row[field]) > timedelta(hours=hours)

    def allocations(self):
        return self.rows("identity:allocation:")

    def line_ref(self, allocation):
        return f"qbo:Invoice:{allocation['invoice_id']}:{allocation['line_id']}"

    def mapping(self, key, row):
        customers = [
            k
            for k, v in self.rows("identity:customer:")
            if v["cargas"] == row["customer_id"]
        ]
        items = [
            k for k, v in self.rows("identity:item:") if v["cargas"] == row["item_id"]
        ]
        if len(customers) != 1 or len(items) != 1:
            self.missing(
                [key],
                "identity",
                "customer/item",
                f"customer:{row['customer_id']};item:{row['item_id']}",
                "C01:" + row["ticket_id"],
                severity="high",
            )
            return False
        return True

    def billing(self):
        # Mapping omissions remain diagnosable even when the invoice window is
        # blocked, provided identity and delivery sources themselves survived.
        if {"identity", "cargas"} & self.unavailable_sources.keys():
            return
        deliveries = {}
        for key, row in self.rows("cargas:delivery:"):
            if row["status"] != "completed":
                continue
            if not self.mapping(key, row):
                continue
            deliveries[key] = row
            if not self.allowed("C01") or not self.old(
                row, "delivered_at", self.p["billing_grace_hours"]
            ):
                continue
            allocations = [
                (k, a)
                for k, a in self.allocations()
                if a["delivery_id"] == row["ticket_id"]
            ]
            valid = [
                (k, a)
                for k, a in allocations
                if self.line_ref(a) in self.r
                and active(self.r["qbo:Invoice:" + a["invoice_id"]])
            ]
            unallocated = row["gallons"] - sum(a["gallons"] for _, a in valid)
            if unallocated > 1:
                related = [k for k, _ in allocations]
                related += [self.line_ref(a) for _, a in valid]
                if row["meter_ticket_id"]:
                    related.append("cargas:meter_ticket:" + row["meter_ticket_id"])
                self.emit(
                    "C01",
                    [key],
                    unallocated,
                    0,
                    "0.001",
                    related,
                    missing={
                        "system": "qbo",
                        "type": "Invoice.Line",
                        "lookup_key": "delivery:" + row["ticket_id"],
                    },
                    formatter=volume,
                )
        if not self.allowed("C02"):
            return
        for parent, invoice in self.parents("Invoice"):
            if not self.old(invoice, "EventAt", self.p["billing_grace_hours"]):
                continue
            for line in invoice["Line"]:
                key = parent + ":" + line["Id"]
                detail = line["SalesItemLineDetail"]
                item_ref = "qbo:Item:" + detail["ItemRef"]["value"]
                if item_ref not in self.r:
                    self.missing([key], "qbo", "Item", item_ref, "C02:" + key)
                    continue
                if self.r[item_ref]["Classification"] != "delivery":
                    continue
                allocations = [
                    (k, a) for k, a in self.allocations() if self.line_ref(a) == key
                ]
                valid = [
                    (k, a)
                    for k, a in allocations
                    if "cargas:delivery:" + a["delivery_id"] in deliveries
                ]
                unallocated = detail["Qty"] - sum(a["gallons"] for _, a in valid)
                if unallocated > 1:
                    self.emit(
                        "C02",
                        [key],
                        unallocated,
                        0,
                        "0.001",
                        [
                            item_ref,
                            *[k for k, _ in allocations],
                            *["cargas:delivery:" + a["delivery_id"] for _, a in valid],
                        ],
                        missing={
                            "system": "cargas",
                            "type": "delivery",
                            "lookup_key": "invoice:" + key[12:],
                        },
                        formatter=volume,
                    )

    def duplicates(self):
        groups = defaultdict(list)
        for occurrence in self.occurrences:
            key = occurrence["record_key"]
            # Current child pointers are already represented by their parent.
            source = key.split(":")[0]
            if source == "qbo" and key.count(":") != 2:
                continue
            if source not in {"qbo", "pos", "cargas", "prices"}:
                continue
            if not self.allowed("C03:" + source):
                continue
            groups[(key, occurrence["version"], occurrence["file_id"])].append(
                occurrence["ref"]
            )
        for (key, version, _), refs in groups.items():
            if len(refs) > 1:
                source, _, record_id = key.split(":", 2)
                self.emit(
                    "C03",
                    refs,
                    len(refs),
                    1,
                    "1",
                    [key, f"{source}:version:{record_id}:{version}"],
                    formatter=str,
                )
        groups = defaultdict(list)
        if self.allowed("C03:pos"):
            for key, row in self.rows("pos:POS:"):
                if active(row) and row["external_reference"]:
                    signature = (
                        "pos",
                        row["external_reference"],
                        row["customer_id"],
                        row["status"],
                        row["gross_amount"],
                    )
                    groups[signature].append(key)
        if self.allowed("C03:qbo"):
            for entity, field in [
                ("Invoice", "DocNumber"),
                ("SalesReceipt", "DocNumber"),
                ("Payment", "PaymentRefNum"),
            ]:
                for key, row in self.parents(entity):
                    if row.get(field):
                        groups[
                            (
                                "qbo",
                                row[field],
                                row["CustomerRef"]["value"],
                                entity,
                                row["TotalAmt"],
                            )
                        ].append(key)
        for (source, external, *_), refs in groups.items():
            if len({key.split(":")[2] for key in refs}) > 1:
                self.emit(
                    "C03",
                    refs,
                    len(refs),
                    1,
                    "1",
                    [source + ":external_reference:" + external],
                    formatter=str,
                )

    def price(self, key, item, customer, unit, basis, event):
        day = stamp(event).astimezone(ZoneInfo(self.p["timezone"])).date().isoformat()
        choices = [
            (k, p)
            for k, p in self.rows("prices:price:")
            if (p["item_id"], p["customer_class"], p["unit"], p["gallon_basis"])
            == (item, customer, unit, basis)
            and p["effective_from"] <= day < p["effective_to"]
        ]
        if len(choices) != 1:
            self.missing(
                [key],
                "prices",
                "effective_price",
                f"item:{item};class:{customer};unit:{unit};basis:{basis};date:{day}",
                "C04:" + key,
            )
            return None
        return choices[0]

    def approval(self, approval_id):
        key = "identity:approval:" + approval_id
        return (key, self.r[key]) if key in self.r else None

    def compare(self, check, refs, actual, expected, related=()):
        if abs(actual - expected) > D(self.p["price_tolerance"]) * 100:
            self.emit(
                check,
                refs,
                actual,
                expected,
                self.p["price_tolerance"],
                [self.policy_ref, *related],
            )

    def discount(self, key, amount, base, approval_id, price, related):
        if amount == 0:
            return True
        approval = self.approval(approval_id)
        if not approval or base <= 0:
            self.missing(
                [key],
                "identity",
                "discount_approval",
                approval_id or "approval_for:" + key,
                "C04:" + key,
                related,
            )
            return False
        percent = D(amount) / base * 100
        allowed = min(
            D(price["approved_discount_pct"]) / 1000,
            D(approval[1].get("approved_discount_pct", 0)) / 1000,
        )
        if percent > allowed:
            self.missing(
                [key],
                "identity",
                "approved_discount_pct",
                "approval:" + approval_id + ";percent:" + format(percent, "f"),
                "C04:" + key,
                [approval[0], *related],
            )
            return False
        return True

    def unusual_discount(self, key, discount, base, approval_id, related):
        if base > 0 and D(discount) * 100 / base > D(self.p["discount_limit_pct"]):
            percent = D(discount) * 100 / base
            approval = self.approval(approval_id)
            self.emit(
                "C05",
                [key],
                percent,
                D(self.p["discount_limit_pct"]),
                self.p["discount_limit_pct"],
                [self.policy_ref, *related, *([approval[0]] if approval else [])],
                severity="medium",
                formatter=percentage,
            )

    def sale_prices(self):
        for entity in ("Invoice", "SalesReceipt"):
            if not self.allowed("C04:qbo"):
                break
            for parent, row in self.parents(entity):
                customer = self.r.get("qbo:Customer:" + row["CustomerRef"]["value"])
                if not customer:
                    self.missing(
                        [parent],
                        "qbo",
                        "Customer",
                        row["CustomerRef"]["value"],
                        "C04:" + parent,
                    )
                    continue
                for line in row["Line"]:
                    key = parent + ":" + line["Id"]
                    detail = line["SalesItemLineDetail"]
                    item = detail["ItemRef"]["value"]
                    item_row = self.r.get("qbo:Item:" + item)
                    if not item_row:
                        self.missing([key], "qbo", "Item", item, "C04:" + key)
                        continue
                    mappings = [
                        m for _, m in self.rows("identity:item:") if m["qbo"] == item
                    ]
                    unit = (
                        "gallon"
                        if item_row["Classification"] in {"delivery", "retail"}
                        else "each"
                    )
                    basis = mappings[0]["gallon_basis"] if mappings else self.p["basis"]
                    price = self.price(
                        key,
                        item,
                        customer["CustomerClass"],
                        unit,
                        basis,
                        row["EventAt"],
                    )
                    if not price:
                        continue
                    price_key, p = price
                    base = D(detail["Qty"]) * p["unit_price"] / 1000
                    discount = line.get("DiscountAmount", 0)
                    if not self.discount(
                        key, discount, base, line.get("ApprovalRef", ""), p, [price_key]
                    ):
                        continue
                    expected = rounded(base - discount)
                    allocations = [
                        (k, a) for k, a in self.allocations() if self.line_ref(a) == key
                    ]
                    delivery_refs = [
                        "cargas:delivery:" + a["delivery_id"] for _, a in allocations
                    ]
                    missing = [k for k in delivery_refs if k not in self.r]
                    if missing:
                        self.missing(
                            [key],
                            "cargas",
                            "delivery",
                            ";".join(missing),
                            "C04:" + key,
                            [k for k, _ in allocations],
                        )
                        continue
                    related = [k for k, _ in allocations]
                    approval = self.approval(line.get("ApprovalRef", ""))
                    if approval:
                        related.append(approval[0])
                    related += [
                        "cargas:meter_ticket:" + self.r[k]["meter_ticket_id"]
                        for k in delivery_refs
                        if self.r[k]["meter_ticket_id"]
                    ]
                    # One root price/allocation discrepancy per invoice line.
                    refs = [key, price_key, *delivery_refs]
                    self.compare("C04", refs, line["Amount"], expected, related)
                    if abs(line["Amount"] - expected) <= 1:
                        declared = rounded(
                            D(detail["Qty"]) * detail["UnitPrice"] / 1000 - discount
                        )
                        self.compare("C04", refs, line["Amount"], declared, related)
                        if allocations:
                            finding_id = "|".join(["C04", *sorted(set(refs))])
                            allocated = sum(a["net_amount"] for _, a in allocations)
                            if finding_id not in self.findings:
                                self.compare(
                                    "C04", refs, line["Amount"], allocated, related
                                )
                            deliveries = [self.r[k] for k in delivery_refs]
                            if any(d["gallons"] <= 0 for d in deliveries):
                                self.missing(
                                    [key],
                                    "cargas",
                                    "positive_billable_volume",
                                    ";".join(delivery_refs),
                                    "C04:" + key,
                                    related,
                                )
                            elif finding_id not in self.findings:
                                billable = sum(
                                    D(
                                        self.r["cargas:delivery:" + a["delivery_id"]][
                                            "net_amount"
                                        ]
                                    )
                                    * a["gallons"]
                                    / self.r["cargas:delivery:" + a["delivery_id"]][
                                        "gallons"
                                    ]
                                    for _, a in allocations
                                )
                                self.compare(
                                    "C04",
                                    refs,
                                    line["Amount"],
                                    rounded(billable),
                                    related,
                                )
                tax = row.get("TxnTaxDetail", {})
                tax_refs = [
                    self.pointers[parent] + "/TxnTaxDetail/TaxLine/" + str(i)
                    for i, _ in enumerate(tax.get("TaxLine", []))
                ]
                if "TotalTax" in tax:
                    self.compare(
                        "C04",
                        [parent],
                        tax["TotalTax"],
                        sum(t["Amount"] for t in tax.get("TaxLine", [])),
                        tax_refs,
                    )
                self.compare(
                    "C04",
                    [parent],
                    row["TotalAmt"],
                    sum(line["Amount"] for line in row["Line"])
                    + tax.get("TotalTax", 0),
                    [parent + ":" + line["Id"] for line in row["Line"]] + tax_refs,
                )
        if "qbo" in self.unavailable_sources:
            self.blocked["C04:pos"] = {
                "status": "not_evaluated",
                "source_refs": [self.unavailable_sources["qbo"]],
                "reason": "Customer price class requires QBO customer support.",
            }
        if not self.allowed("C04:pos"):
            return
        for key, row in self.rows("pos:POS:"):
            if row["status"] != "captured":
                continue
            customers = [
                self.r.get("qbo:Customer:" + v["qbo"])
                for _, v in self.rows("identity:customer:")
                if v["pos"] == row["customer_id"]
            ]
            if len(customers) != 1 or not customers[0]:
                self.missing(
                    [key], "identity", "customer", row["customer_id"], "C04:" + key
                )
                continue
            price = self.price(
                key,
                row["item_id"],
                customers[0]["CustomerClass"],
                row["unit"],
                self.p["basis"],
                row["occurred_at"],
            )
            if not price:
                continue
            price_key, p = price
            base = D(row["quantity"]) * p["unit_price"] / 1000
            if self.discount(
                key, row["discount_amount"], base, row["approval_id"], p, [price_key]
            ):
                self.compare(
                    "C04",
                    [key, price_key],
                    row["net_amount"],
                    rounded(base - row["discount_amount"]),
                    ["identity:approval:" + row["approval_id"]]
                    if row["discount_amount"]
                    else [],
                )
            price_finding = "|".join(["C04", *sorted([key, price_key])])
            if price_finding not in self.findings and "C04:" + key not in self.partial:
                self.compare(
                    "C04",
                    [key, price_key],
                    row["net_amount"],
                    rounded(
                        D(row["quantity"]) * row["unit_price"] / 1000
                        - row["discount_amount"]
                    ),
                    ["identity:approval:" + row["approval_id"]]
                    if row["discount_amount"]
                    else [],
                )
            self.compare(
                "C04", [key], row["gross_amount"], row["net_amount"] + row["tax_amount"]
            )

    def discounts(self):
        represented = {
            f"qbo:{e['qbo_entity']}:{e['qbo_id']}"
            for _, e in self.rows("identity:pos_event:")
            if self.allowed("C05:pos") and "pos:POS:" + e["pos_id"] in self.r
        }
        if self.allowed("C05:qbo"):
            for entity in ("Invoice", "SalesReceipt"):
                for parent, row in self.parents(entity):
                    if parent in represented:
                        continue
                    for line in row["Line"]:
                        detail = line["SalesItemLineDetail"]
                        self.unusual_discount(
                            parent + ":" + line["Id"],
                            line.get("DiscountAmount", 0),
                            D(detail["Qty"]) * detail["UnitPrice"] / 1000,
                            line.get("ApprovalRef", ""),
                            [],
                        )
        if not self.allowed("C05:pos"):
            return
        for key, row in self.rows("pos:POS:"):
            if row["status"] != "captured" or not row["discount_amount"]:
                continue
            # POS declared prediscount amount is independent of approval. The
            # effective-price rule separately diagnoses price/support failures.
            related = [
                k
                for k, p in self.rows("prices:price:")
                if p["item_id"] == row["item_id"]
                and p["unit"] == row["unit"]
                and p["effective_from"]
                <= stamp(row["occurred_at"])
                .astimezone(ZoneInfo(self.p["timezone"]))
                .date()
                .isoformat()
                < p["effective_to"]
            ]
            for _, event in self.rows("identity:pos_event:"):
                if "pos:POS:" + event["pos_id"] == key:
                    parent = f"qbo:{event['qbo_entity']}:{event['qbo_id']}"
                    if parent in self.r:
                        related.extend(
                            parent + ":" + line["Id"] for line in self.r[parent]["Line"]
                        )
            self.unusual_discount(
                key,
                row["discount_amount"],
                D(row["quantity"]) * row["unit_price"] / 1000,
                row["approval_id"],
                related,
            )

    def adjustments(self):
        if not self.allowed("C05:qbo"):
            return
        for entity in ("CreditMemo", "RefundReceipt"):
            for parent, row in self.parents(entity):
                amount = abs(row["TotalAmt"])
                if not amount:
                    continue
                originals = [
                    k
                    for k in linked(row)
                    if k in self.r
                    and k.split(":")[1] in {"Invoice", "SalesReceipt"}
                    and active(self.r[k])
                ]
                approval = self.approval(row.get("ApprovalRef", ""))
                related = [
                    self.policy_ref,
                    *originals,
                    *([approval[0]] if approval else []),
                ]
                refs = [parent + ":" + line["Id"] for line in row["Line"]] or [parent]
                if not originals:
                    self.emit(
                        "C05",
                        refs,
                        amount,
                        None,
                        "original required",
                        related,
                        missing={
                            "system": "qbo",
                            "type": "original_sale",
                            "lookup_key": (
                                "refund:" if entity == "RefundReceipt" else "credit:"
                            )
                            + row["Id"],
                        },
                    )
                elif not approval:
                    self.emit(
                        "C05",
                        refs,
                        amount,
                        None,
                        "approval required",
                        related,
                        severity="medium",
                        missing={
                            "system": "identity",
                            "type": "approval",
                            "lookup_key": row.get("ApprovalRef", "")
                            or "approval_for:" + parent,
                        },
                    )
                elif amount > D(self.p["credit_limit"]) * 100:
                    self.emit(
                        "C05",
                        refs,
                        amount,
                        D(self.p["credit_limit"]) * 100,
                        self.p["credit_limit"],
                        related,
                        severity="medium",
                    )

    def pos_refunds(self):
        if not self.allowed("C05:pos"):
            return
        for key, row in self.rows("pos:POS:"):
            if row["status"] != "refunded" or row["gross_amount"] == 0:
                continue
            events = [
                e
                for _, e in self.rows("identity:pos_event:")
                if "pos:POS:" + e["pos_id"] == key
            ]
            if len(events) == 1 and "qbo" in self.unavailable_sources:
                self.blocked["C05:" + key] = {
                    "status": "not_evaluated",
                    "source_refs": [self.unavailable_sources["qbo"]],
                    "reason": "Crosswalked refund approval requires QBO support.",
                }
                continue
            if (
                len(events) == 1
                and f"qbo:{events[0]['qbo_entity']}:{events[0]['qbo_id']}" in self.r
            ):
                continue
            originals = [
                k
                for k, p in self.rows("pos:POS:")
                if p["transaction_id"] == row["original_transaction_id"]
                and p["status"] == "captured"
            ]
            approval = self.approval(row["approval_id"])
            related = [
                self.policy_ref,
                *originals,
                *([approval[0]] if approval else []),
            ]
            amount = abs(row["gross_amount"])
            if not originals or not approval:
                kind = "original_sale" if not originals else "approval"
                self.emit(
                    "C05",
                    [key],
                    amount,
                    None,
                    "original required" if not originals else "approval required",
                    related,
                    severity="high" if not originals else "medium",
                    missing={
                        "system": "pos" if not originals else "identity",
                        "type": kind,
                        "lookup_key": row["original_transaction_id"]
                        if not originals
                        else row["approval_id"],
                    },
                )
            elif amount > D(self.p["credit_limit"]) * 100:
                self.emit(
                    "C05",
                    [key],
                    amount,
                    D(self.p["credit_limit"]) * 100,
                    self.p["credit_limit"],
                    related,
                    severity="medium",
                )

    def payments(self):
        if not self.allowed("C06"):
            return
        snapshots = self.rows("ar:snapshot:")
        if len(snapshots) != 1:
            self.missing(
                ["run:" + self.run["run_id"]],
                "ar",
                "opening_snapshot",
                "opening_ar",
                "C06",
                severity="high",
            )
            return
        snapshot_key, snapshot = snapshots[0]
        start = stamp(snapshot["as_of"])
        opening_customers = {b["customer_id"] for b in snapshot["balances"]}
        balances, history, credits = {}, defaultdict(list), {}
        uncertain = {}
        events = [
            (stamp(row["EventAt"]), key, row)
            for entity in ("Invoice", "CreditMemo", "Payment")
            for key, row in self.parents(entity)
            if start < stamp(row["EventAt"]) <= self.now
        ]
        for _, key, row in sorted(events):
            customer = row["CustomerRef"]["value"]
            if customer not in opening_customers:
                self.missing(
                    [key, snapshot_key],
                    "ar",
                    "customer_balance",
                    "customer:" + customer,
                    "C06:" + key,
                    severity="high",
                )
                continue
            if key.startswith("qbo:Invoice:"):
                balances[key] = row["TotalAmt"]
                continue
            if key.startswith("qbo:CreditMemo:"):
                amount = row.get("AppliedAmount", 0)
                targets = [k for k in linked(row) if k.startswith("qbo:Invoice:")]
                credits[key] = {
                    "amount": amount,
                    "target": targets[0] if len(targets) == 1 else None,
                    "seen": 0,
                    "total": abs(row["TotalAmt"]),
                }
                if not amount:
                    continue
                if len(targets) != 1 or targets[0] not in balances:
                    uncertain.update({target: [key] for target in targets})
                    self.missing(
                        [key, snapshot_key],
                        "qbo",
                        "credit_invoice",
                        ";".join(targets) or "credit:" + row["Id"],
                        "C06:" + key,
                    )
                    continue
                target = targets[0]
                balances[target] -= amount
                history[target].append(key)
                continue
            unlinked = [line for line in row["Line"] if not linked(line)]
            all_links = [target for line in row["Line"] for target in linked(line)]
            unapplied = max(
                row["UnappliedAmt"],
                sum(line["Amount"] for line in unlinked),
                row["TotalAmt"] if not all_links else 0,
            )
            if unapplied > 1 and self.old(
                row, "EventAt", self.p["payment_grace_hours"]
            ):
                self.emit(
                    "C06",
                    [key],
                    unapplied,
                    0,
                    "0.01",
                    [snapshot_key, *[key + ":" + line["Id"] for line in unlinked]],
                    severity="medium",
                )
            for line in sorted(row["Line"], key=lambda x: x["Id"]):
                line_key = key + ":" + line["Id"]
                targets = [k for k in linked(line) if k.startswith("qbo:Invoice:")]
                credit_links = [
                    k for k in linked(line) if k.startswith("qbo:CreditMemo:")
                ]
                if not targets:
                    continue
                if len(targets) != 1 or targets[0] not in balances:
                    uncertain.update({target: [line_key] for target in targets})
                    self.missing(
                        [line_key, snapshot_key],
                        "qbo",
                        "invoice_balance",
                        ";".join(targets),
                        "C06:" + line_key,
                    )
                    continue
                target = targets[0]
                if target in uncertain:
                    self.partial["C06:" + line_key] = {
                        "status": "not_evaluated",
                        "source_refs": sorted(
                            [snapshot_key, target, *uncertain[target]]
                        ),
                        "reason": "Earlier allocation lacks required support.",
                    }
                    continue
                if any(k not in credits for k in credit_links):
                    uncertain[target] = [line_key]
                    self.missing(
                        [line_key, snapshot_key],
                        "qbo",
                        "credit_application",
                        ";".join(credit_links),
                        "C06:" + line_key,
                    )
                    continue
                # A credit already recognized through AppliedAmount is not new
                # cash and cannot reduce the balance again through Payment links.
                already = 0
                if credit_links:
                    if len(credit_links) != 1:
                        uncertain[target] = [line_key]
                        self.missing(
                            [line_key, snapshot_key],
                            "qbo",
                            "credit_allocation",
                            ";".join(credit_links),
                            "C06:" + line_key,
                        )
                        continue
                    credit = credits[credit_links[0]]
                    if credit["seen"] + line["Amount"] > credit["total"] or credit[
                        "target"
                    ] not in {None, target}:
                        uncertain[target] = [line_key]
                        self.missing(
                            [line_key, snapshot_key],
                            "qbo",
                            "credit_allocation",
                            credit_links[0] + ";invoice:" + target,
                            "C06:" + line_key,
                        )
                        continue
                    already = min(
                        line["Amount"], max(0, credit["amount"] - credit["seen"])
                    )
                    credit["seen"] += line["Amount"]
                allocation = max(0, line["Amount"] - already)
                before = balances[target]
                if allocation - before > 1:
                    self.emit(
                        "C06",
                        [line_key],
                        allocation,
                        before,
                        "0.01",
                        [snapshot_key, target, *credit_links, *history[target]],
                    )
                balances[target] -= allocation
                history[target].append(line_key)

    def settlement_due(self, event):
        local = stamp(event).astimezone(ZoneInfo(self.p["timezone"]))
        day = local
        count = 0
        while count < self.p["settlement_grace_business_days"]:
            day += timedelta(days=1)
            if day.weekday() < 5:
                count += 1
        # Compare absolute instants so DST changes do not fabricate grace hours.
        return self.now.astimezone(UTC) > day.astimezone(UTC)

    def settlements(self):
        if not self.allowed("C07"):
            return
        for key, batch in self.rows("pos:batch:"):
            if not self.settlement_due(batch["settled_at"]):
                continue
            pos = [
                (k, p)
                for k, p in self.rows("pos:POS:")
                if p["settlement_batch_id"] == batch["batch_id"]
                and p["status"] in {"captured", "refunded"}
            ]
            if not pos:
                self.missing(
                    [key], "pos", "batch_transactions", batch["batch_id"], "C07:" + key
                )
                continue
            related = [
                self.policy_ref,
                "pos:fee:" + batch["batch_id"] + ":fees",
                *[k for k, _ in pos],
            ]
            expected = sum(p["gross_amount"] for _, p in pos) - batch["fees"]
            deposit_key = "qbo:Deposit:" + batch["qbo_deposit_id"]
            deposit = self.r.get(deposit_key)
            if not deposit or not active(deposit):
                self.emit(
                    "C07",
                    [key],
                    None,
                    expected,
                    "0.01",
                    related,
                    missing={
                        "system": "qbo",
                        "type": "Deposit",
                        "lookup_key": batch["qbo_deposit_id"]
                        or "batch:" + batch["batch_id"],
                    },
                )
                continue
            lines = sorted(deposit["Line"], key=lambda x: x["Id"])
            refs = [deposit_key + ":" + line["Id"] for line in lines]
            links = []
            for line in lines:
                detail = line["DepositLineDetail"]
                if "TxnId" in detail:
                    links.append(f"qbo:{detail['TxnType']}:{detail['TxnId']}")
            expected_links = []
            for pkey, _ in pos:
                events = [
                    e
                    for _, e in self.rows("identity:pos_event:")
                    if "pos:POS:" + e["pos_id"] == pkey
                ]
                if len(events) != 1:
                    self.missing(
                        [key, pkey], "identity", "pos_event", pkey, "C07:" + key
                    )
                    break
                e = events[0]
                expected_links.append(
                    "qbo:Payment:" + e["payment_id"]
                    if "payment_id" in e
                    else f"qbo:{e['qbo_entity']}:{e['qbo_id']}"
                )
            else:
                absent = sorted(
                    set(k for k in expected_links if k not in links or k not in self.r)
                    | set(
                        k for k in links if k not in self.r or k not in expected_links
                    )
                )
                if absent:
                    self.missing(
                        [key, *refs],
                        "qbo",
                        "Deposit.links",
                        ";".join(absent),
                        "C07:" + key,
                        related,
                    )
                    continue
                for line in lines:
                    detail = line["DepositLineDetail"]
                    if "TxnId" in detail:
                        target = f"qbo:{detail['TxnType']}:{detail['TxnId']}"
                        sign = -1 if detail["TxnType"] == "RefundReceipt" else 1
                        self.compare(
                            "C07",
                            [deposit_key + ":" + line["Id"], target],
                            line["Amount"],
                            sign * self.r[target]["TotalAmt"],
                            [key, *related],
                        )
                related.extend([*links, *refs[1:]])
                primary = [key, *refs[:1]]
                self.compare("C07", primary, deposit["TotalAmt"], expected, related)
                self.compare(
                    "C07",
                    [deposit_key],
                    deposit["TotalAmt"],
                    sum(line["Amount"] for line in lines),
                    refs,
                )
                # Compare source batch gross/refunds with actual contributing POS,
                # rather than accepting self-consistent but invented batch totals.
                captured = sum(
                    p["gross_amount"] for _, p in pos if p["status"] == "captured"
                )
                refunds = -sum(
                    p["gross_amount"] for _, p in pos if p["status"] == "refunded"
                )
                for field, observed in [
                    ("gross", captured),
                    ("refunds", refunds),
                    ("net", expected),
                ]:
                    self.compare(
                        "C07",
                        [key, "pos:component:" + batch["batch_id"] + ":" + field],
                        batch[field],
                        observed,
                        related,
                    )

    def operational(self, reference):
        choices = [
            (k, row)
            for entity in ("Invoice", "Payment", "SalesReceipt")
            for k, row in self.parents(entity)
            if row["Id"] == reference
        ]
        choices += [
            (k, row)
            for k, row in self.rows("pos:batch:")
            if row["batch_id"] == reference
        ]
        if len(choices) != 1:
            return None
        key, row = choices[0]
        if key.startswith("qbo:Payment:"):
            for line in row["Line"]:
                credit_links = [
                    k for k in linked(line) if k.startswith("qbo:CreditMemo:")
                ]
                if credit_links and (
                    len(credit_links) != 1
                    or credit_links[0] not in self.r
                    or abs(line["Amount"]) > abs(self.r[credit_links[0]]["TotalAmt"])
                ):
                    return None
            # Credit links are noncash. Only explicitly cash allocations plus
            # unapplied cash count toward a payment clearing posting.
            amount = row["UnappliedAmt"] + sum(
                line["Amount"]
                for line in row["Line"]
                if not any(k.startswith("qbo:CreditMemo:") for k in linked(line))
            )
        elif key.startswith("pos:batch:"):
            amount = (
                sum(
                    p["gross_amount"]
                    for _, p in self.rows("pos:POS:")
                    if p["settlement_batch_id"] == row["batch_id"]
                    and p["status"] in {"captured", "refunded"}
                )
                - row["fees"]
            )
        else:
            amount = sum(line["Amount"] for line in row["Line"])
        return key, amount

    def accounting(self):
        if not self.allowed("C12"):
            return
        mappings = self.rows("identity:posting:")
        for parent, journal in self.parents("JournalEntry"):
            refs = [parent + ":" + line["Id"] for line in journal["Line"]]
            related = [self.policy_ref]
            related += [
                "qbo:account:" + line["JournalEntryLineDetail"]["AccountRef"]["value"]
                for line in journal["Line"]
            ]
            for key, mapping in mappings:
                if mapping["journal_id"] == journal["Id"]:
                    related.append(key)
                    operational = self.operational(mapping["external_ref"])
                    if operational:
                        related.append(operational[0])
            debit = sum(
                line["Amount"]
                for line in journal["Line"]
                if line["JournalEntryLineDetail"]["PostingType"] == "Debit"
            )
            credit = sum(
                line["Amount"]
                for line in journal["Line"]
                if line["JournalEntryLineDetail"]["PostingType"] == "Credit"
            )
            self.compare("C12", refs, debit, credit, related)
        for key, mapping in mappings:
            parent = "qbo:JournalEntry:" + mapping["journal_id"]
            journal = self.r.get(parent)
            operational = self.operational(mapping["external_ref"])
            failures = {
                source: ref
                for source, ref in self.unavailable_sources.items()
                if source in {"pos", "settlements"}
            }
            if failures and (
                operational is None or operational[0].startswith("pos:batch:")
            ):
                self.blocked["C12:" + key] = {
                    "status": "not_evaluated",
                    "source_refs": sorted(failures.values()),
                }
                continue
            if not journal or not active(journal) or not operational:
                self.missing(
                    [key],
                    "qbo",
                    "configured_posting",
                    f"journal:{mapping['journal_id']};external:{mapping['external_ref']}",
                    "C12:" + key,
                )
                continue
            lines = [(parent + ":" + line["Id"], line) for line in journal["Line"]]
            clearing = [
                (k, line)
                for k, line in lines
                if line["JournalEntryLineDetail"]["AccountRef"]["value"]
                == mapping["account_id"]
            ]
            if not clearing:
                self.missing(
                    [key, parent],
                    "qbo",
                    "clearing_account",
                    mapping["account_id"],
                    "C12:" + key,
                )
                continue
            actual = sum(
                line["Amount"]
                * (
                    1
                    if line["JournalEntryLineDetail"]["PostingType"] == "Debit"
                    else -1
                )
                for _, line in clearing
            )
            related = [
                key,
                operational[0],
                *[k for k, _ in lines],
                *[
                    "qbo:account:"
                    + line["JournalEntryLineDetail"]["AccountRef"]["value"]
                    for _, line in lines
                ],
            ]
            self.compare(
                "C12", [k for k, _ in clearing], actual, operational[1], related
            )


def reconcile(inputs):
    """Compute only step-3 findings and evaluation eligibility.

    A caller may pass additional `blocked` scopes from a future freshness engine;
    no C08/C09/KPI result or stale-source completeness is claimed here.
    """
    with localcontext() as context:
        context.prec = 80
        engine = Engine(inputs)
        engine.billing()
        engine.duplicates()
        engine.sale_prices()
        engine.discounts()
        engine.adjustments()
        engine.pos_refunds()
        engine.payments()
        engine.settlements()
        engine.accounting()
        return {
            "findings": sorted(engine.findings.values(), key=lambda f: f["finding_id"]),
            "not_evaluated": dict(sorted((engine.blocked | engine.partial).items())),
            "freshness_evaluated": False,
        }
