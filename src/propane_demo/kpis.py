"""Pure, evidence-bearing KPI worksheets over validated scaled source records."""

from collections import defaultdict
from decimal import Decimal, localcontext

from propane_demo.rules import active, linked, money, payment_cash, stamp, volume

D = Decimal


class Worksheet:
    """Known signed contributions never become an asserted total across a gap."""

    def __init__(self, unit):
        self.unit = unit
        self.contributions = []
        self.gaps = []

    def add(self, kind, amount, refs):
        self.contributions.append(
            {"kind": kind, "amount": D(amount), "source_refs": sorted(set(refs))}
        )

    def gap(self, key, refs):
        self.gaps.append({"missing_lookup_key": key, "source_refs": sorted(set(refs))})

    def result(self):
        formatter = volume if self.unit == "US gallons" else money
        total = sum((c["amount"] for c in self.contributions), D(0))
        return {
            "status": "complete"
            if not self.gaps
            else "partial"
            if self.contributions
            else "unavailable",
            "value": None if self.gaps else formatter(total),
            "known_value": formatter(total),
            "unit": self.unit,
            "contributions": [
                c | {"amount": formatter(c["amount"])} for c in self.contributions
            ],
            "gaps": sorted(
                self.gaps, key=lambda g: (g["missing_lookup_key"], g["source_refs"])
            ),
        }


class KPIs:
    def __init__(self, inputs, checks):
        self.r = inputs["records"]
        self.run = inputs["run"]
        self.p = inputs["policy"]
        self.checks = checks
        self.now = stamp(self.run["as_of"])
        self.root = "run:" + self.run["run_id"]
        self.policy = "policy:" + self.p["policy_id"]

    def rows(self, prefix):
        return [(k, v) for k, v in sorted(self.r.items()) if k.startswith(prefix)]

    def parents(self, entity):
        return [
            (k, v)
            for k, v in self.rows("qbo:" + entity + ":")
            if k.count(":") == 2 and active(v)
        ]

    def refund_credit(self, row):
        """Resolve explicit credit identity once for revenue and AR replay.

        RevenueEvent also labels standalone refunds; only a credit bearing that
        event establishes credit settlement intent. Include void/future candidates
        here so neither can silently turn a settlement into a standalone refund.
        """
        direct = [k for k in linked(row) if k.startswith("qbo:CreditMemo:")]
        event = row.get("RevenueEvent")
        candidates = [
            k
            for k, credit in self.rows("qbo:CreditMemo:")
            if k.count(":") == 2 and event and credit.get("RevenueEvent") == event
        ]
        targets = sorted(set(direct + candidates))
        conflict = bool(
            direct
            and event
            and (
                (candidates and direct != candidates)
                or any(
                    self.r.get(k, {}).get("RevenueEvent") not in {None, event}
                    for k in direct
                )
            )
        )
        return targets, conflict

    def blocked(self, sheet, scope):
        reason = self.checks["not_evaluated"].get("KPI:" + scope)
        if reason:
            sheet.gap(
                reason.get("missing_lookup_key", "eligible_source_window:" + scope),
                reason["source_refs"],
            )
        return reason is not None

    def in_day(self, when):
        return (
            stamp(self.run["window_start"])
            <= stamp(when)
            < stamp(self.run["window_end"])
        )

    def missing_pos_events(self, sheet):
        for key, event in self.rows("identity:pos_event:"):
            target = f"qbo:{event['qbo_entity']}:{event['qbo_id']}"
            qbo = self.r.get(target)
            pos_key = "pos:POS:" + event["pos_id"]
            pos = self.r.get(pos_key)
            relevant = (
                qbo is not None
                and active(qbo)
                and (
                    qbo["TxnDate"] == self.run["business_date"]
                    or self.in_day(qbo["EventAt"])
                )
            )
            if relevant and (pos is None or not active(pos)):
                sheet.gap("active_pos_event:" + pos_key, [key, target])

    def volumes(self):
        delivered, retail = Worksheet("US gallons"), Worksheet("US gallons")
        if not self.blocked(delivered, "delivered"):
            for key, row in self.rows("cargas:delivery:"):
                if row["status"] != "completed" or not self.in_day(row["delivered_at"]):
                    continue
                customers = [
                    (k, v)
                    for k, v in self.rows("identity:customer:")
                    if v["cargas"] == row["customer_id"]
                ]
                items = [
                    (k, v)
                    for k, v in self.rows("identity:item:")
                    if v["cargas"] == row["item_id"]
                ]
                refs = [key, self.policy, *[k for k, _ in customers + items]]
                if len(customers) != 1 or len(items) != 1:
                    delivered.gap(
                        "customer:" + row["customer_id"] + ";item:" + row["item_id"],
                        refs,
                    )
                elif (
                    row["gallon_basis"] != self.p["basis"]
                    or items[0][1]["gallon_basis"] != row["gallon_basis"]
                ):
                    delivered.gap(
                        "delivery:"
                        + row["ticket_id"]
                        + ";gallon_basis:"
                        + self.p["basis"],
                        refs,
                    )
                else:
                    delivered.add("completed_delivery", row["gallons"], refs)
        # Each-count classification uses QBO Item evidence. A stale item source
        # cannot classify an unknown SKU as a service and silently drop volume.
        retail_blocked = self.blocked(retail, "retail")
        qbo_roots = [a for a in self.checks.get("alerts", []) if a["source"] == "qbo"]
        if qbo_roots:
            retail.gap(
                "fresh_qbo_item_classification",
                [ref for a in qbo_roots for ref in a["source_refs"]],
            )
        if not retail_blocked and not qbo_roots:
            self.missing_pos_events(retail)
            for key, row in self.rows("pos:POS:"):
                if row["status"] != "captured" or not self.in_day(row["occurred_at"]):
                    continue
                events = [
                    (k, e)
                    for k, e in self.rows("identity:pos_event:")
                    if e["pos_id"] == key[8:]
                ]
                if len(events) != 1:
                    retail.gap("pos_event:" + key, [key])
                    continue
                event_key, event = events[0]
                refs = [key, event_key, self.policy]
                if "delivery_id" in event:
                    target = "cargas:delivery:" + event["delivery_id"]
                    delivery = self.r.get(target)
                    if (
                        delivery is None
                        or delivery["status"] != "completed"
                        or not self.in_day(delivery["delivered_at"])
                    ):
                        retail.gap("completed_delivery:" + target, refs)
                    else:
                        retail.add("represented_delivery_excluded", 0, [*refs, target])
                    continue
                # Gallon POS lines explicitly declare volume. Each-count requires
                # a fill mapping only for a cylinder SKU, never for service fees.
                if row["unit"] == "gallon":
                    retail.add("retail_gallons", row["quantity"], refs)
                    continue
                item_key = "qbo:Item:" + row["item_id"]
                item = self.r.get(item_key)
                if item is None:
                    retail.gap(item_key, refs)
                    continue
                if item["Classification"] != "cylinder":
                    retail.add("nonvolume_sale_excluded", 0, [*refs, item_key])
                    continue
                fill_key = "identity:fill:" + row["item_id"]
                fill = self.r.get(fill_key)
                if fill is None:
                    retail.gap(fill_key, refs)
                else:
                    retail.add(
                        "explicit_cylinder_fill",
                        D(row["quantity"]) * fill["gallons"] / 1000,
                        [*refs, fill_key, item_key],
                    )
        total = Worksheet("US gallons")
        total.contributions = delivered.contributions + retail.contributions
        total.gaps = delivered.gaps + retail.gaps
        return {
            "delivered": delivered.result(),
            "retail": retail.result(),
            "total_gallons": total.result(),
        }

    def net_lines(self, sheet, key, row, sign):
        for line in row["Line"]:
            item_key = "qbo:Item:" + line["SalesItemLineDetail"]["ItemRef"]["value"]
            item = self.r.get(item_key)
            refs = [key, key + ":" + line["Id"], self.policy]
            refs.extend(target for target in linked(row) if target in self.r)
            if item is None:
                sheet.gap(item_key, refs)
            else:
                excluded = item["Classification"] == "container_deposit"
                # Amount is already net of DiscountAmount; never deduct it twice.
                sheet.add(
                    "container_deposit_excluded"
                    if excluded
                    else "net_sale"
                    if sign == 1
                    else "net_adjustment",
                    0 if excluded else sign * line["Amount"],
                    [*refs, item_key],
                )

    def revenue(self):
        sheet = Worksheet("USD")
        if self.blocked(sheet, "revenue"):
            return sheet.result()
        self.missing_pos_events(sheet)
        # Crosswalks establish POS representation. No POS money is added again.
        represented = defaultdict(list)
        for key, row in self.rows("pos:POS:"):
            if not active(row) or not self.in_day(row["occurred_at"]):
                continue
            events = [
                (k, e)
                for k, e in self.rows("identity:pos_event:")
                if e["pos_id"] == key[8:]
            ]
            if len(events) != 1:
                sheet.gap("pos_event:" + key, [key])
                continue
            ek, event = events[0]
            target = f"qbo:{event['qbo_entity']}:{event['qbo_id']}"
            expected = (
                "RefundReceipt"
                if row["status"] == "refunded"
                else "Invoice"
                if "delivery_id" in event
                else "SalesReceipt"
            )
            if (
                target not in self.r
                or not active(self.r[target])
                or event["qbo_entity"] != expected
            ):
                sheet.gap("nonvoid_" + expected + ":" + target, [key, ek])
            else:
                sheet.add("represented_POS_excluded", 0, [key, ek, target])
                represented[target].append((key, row, ek))
        for target, rows in sorted(represented.items()):
            gross = sum(abs(row["gross_amount"]) for _, row, _ in rows)
            if gross != abs(self.r[target]["TotalAmt"]):
                sheet.gap(
                    "consistent_pos_qbo_event:" + target,
                    [target, *[key for key, _, _ in rows], *[ek for _, _, ek in rows]],
                )
        adjustments = self.parents("CreditMemo") + self.parents("RefundReceipt")
        groups = defaultdict(list)
        for key, row in adjustments:
            # Explicit credit settlement is handled separately below, even when
            # the refund also carries the same RevenueEvent as its credit.
            if key.startswith("qbo:RefundReceipt:") and self.refund_credit(row)[0]:
                continue
            groups[row.get("RevenueEvent") or key].append((key, row))
        excluded = set()
        for group in groups.values():
            group.sort(
                key=lambda kv: (
                    kv[1]["TxnDate"],
                    0 if kv[0].startswith("qbo:CreditMemo:") else 1,
                    kv[0],
                )
            )
            first_key, first = group[0]
            for key, row in group[1:]:
                if (
                    row["TotalAmt"] != first["TotalAmt"]
                    or sorted(linked(row)) != sorted(linked(first))
                    or sorted(
                        (
                            line["SalesItemLineDetail"]["ItemRef"]["value"],
                            line["Amount"],
                        )
                        for line in row["Line"]
                    )
                    != sorted(
                        (
                            line["SalesItemLineDetail"]["ItemRef"]["value"],
                            line["Amount"],
                        )
                        for line in first["Line"]
                    )
                ):
                    sheet.gap("consistent_adjustment_event:" + key, [first_key, key])
                else:
                    excluded.add(key)
                    sheet.add("same_adjustment_excluded", 0, [first_key, key])
        for key, row in self.parents("Invoice") + self.parents("SalesReceipt"):
            if row["TxnDate"] == self.run["business_date"]:
                self.net_lines(sheet, key, row, 1)
        for key, row in adjustments:
            if row["TxnDate"] != self.run["business_date"] or key in excluded:
                continue
            credit_targets, conflict = (
                self.refund_credit(row)
                if key.startswith("qbo:RefundReceipt:")
                else ([], False)
            )
            if credit_targets:
                if (
                    conflict
                    or len(credit_targets) != 1
                    or credit_targets[0] not in self.r
                    or not active(self.r[credit_targets[0]])
                    or stamp(self.r[credit_targets[0]]["EventAt"])
                    > stamp(row["EventAt"])
                    or self.r[credit_targets[0]]["CustomerRef"] != row["CustomerRef"]
                    or abs(row["TotalAmt"]) > abs(self.r[credit_targets[0]]["TotalAmt"])
                ):
                    sheet.gap("recognized_credit:" + ";".join(credit_targets), [key])
                else:
                    sheet.add(
                        "refund_settles_credit_excluded", 0, [key, *credit_targets]
                    )
                continue
            originals = [
                k
                for k in linked(row)
                if k.split(":")[1] in {"Invoice", "SalesReceipt"}
                and k in self.r
                and active(self.r[k])
            ]
            if len(originals) != 1:
                sheet.gap("original_sale:" + key, [key])
                continue
            self.net_lines(sheet, key, row, -1)
        return sheet.result()

    def ar(self):
        sheet = Worksheet("USD")
        cash, credit_left = Worksheet("USD"), Worksheet("USD")
        comparisons = []
        if self.blocked(sheet, "AR"):
            cash.gaps = list(sheet.gaps)
            credit_left.gaps = list(sheet.gaps)
            return sheet.result() | {
                "unapplied_cash": cash.result(),
                "unapplied_credits": credit_left.result(),
                "reported_balance_comparisons": comparisons,
            }
        snapshots = self.rows("ar:snapshot:")
        if len(snapshots) != 1:
            sheet.gap("opening_ar_snapshot", [self.root])
            cash.gaps = list(sheet.gaps)
            credit_left.gaps = list(sheet.gaps)
            return sheet.result() | {
                "unapplied_cash": cash.result(),
                "unapplied_credits": credit_left.result(),
                "reported_balance_comparisons": comparisons,
            }
        sk, snapshot = snapshots[0]
        cutoff = stamp(snapshot["as_of"])
        if cutoff > self.now or snapshot["as_of"] != self.p["opening_ar_cutoff"]:
            sheet.gap(
                "opening_ar_cutoff:" + self.p["opening_ar_cutoff"], [sk, self.policy]
            )
        customers = {b["customer_id"] for b in snapshot["balances"]}
        for balance in snapshot["balances"]:
            sheet.add("opening_AR", balance["amount"], [sk])
        balances, credits = {}, {}
        events = sorted(
            (stamp(row["EventAt"]), key, row)
            for entity in ("Invoice", "CreditMemo", "Payment", "RefundReceipt")
            for key, row in self.parents(entity)
            if cutoff < stamp(row["EventAt"]) <= self.now
        )
        for _, key, row in events:
            # A sale link alone never establishes credit settlement identity.
            targets, conflict = (
                self.refund_credit(row)
                if key.startswith("qbo:RefundReceipt:")
                else ([], False)
            )
            if key.startswith("qbo:RefundReceipt:") and not targets:
                continue
            if row["CustomerRef"]["value"] not in customers:
                sheet.gap("opening_customer:" + row["CustomerRef"]["value"], [key, sk])
                continue
            if key.startswith("qbo:Invoice:"):
                balances[key] = row["TotalAmt"]
                sheet.add("invoice_gross", row["TotalAmt"], [key])
                continue
            if key.startswith("qbo:CreditMemo:"):
                targets = [k for k in linked(row) if k.startswith("qbo:Invoice:")]
                applied = row.get("AppliedAmount", 0)
                credits[key] = {
                    "applied": applied,
                    "seen": 0,
                    "refunded": 0,
                    "refs": [key],
                    "total": abs(row["TotalAmt"]),
                    "target": targets[0] if len(targets) == 1 else None,
                }
                if applied:
                    if (
                        len(targets) != 1
                        or targets[0] not in balances
                        or self.r[targets[0]]["CustomerRef"] != row["CustomerRef"]
                        or applied < 0
                        or applied > abs(row["TotalAmt"])
                    ):
                        sheet.gap("applied_credit_invoice:" + key, [key, sk])
                    else:
                        balances[targets[0]] -= applied
                        sheet.add("applied_credit", -applied, [key, targets[0]])
                continue
            if key.startswith("qbo:RefundReceipt:"):
                if conflict or len(targets) != 1 or targets[0] not in credits:
                    sheet.gap("refund_credit:" + ";".join(targets), [key])
                    continue
                credit = credits[targets[0]]
                amount = abs(row["TotalAmt"])
                if self.r[targets[0]]["CustomerRef"] != row["CustomerRef"]:
                    sheet.gap("same_customer_refund_credit:" + key, [key, *targets])
                elif (
                    max(credit["applied"], credit["seen"]) + credit["refunded"] + amount
                    > credit["total"]
                ):
                    sheet.gap("refund_credit_capacity:" + key, [key, *credit["refs"]])
                else:
                    credit["refunded"] += amount
                    credit["refs"].append(key)
                continue
            unapplied, _ = payment_cash(row)
            # Any cash line without an Invoice or CreditMemo allocation remains
            # unapplied, even if a non-invoice transaction is referenced.
            unapplied = max(
                unapplied,
                sum(
                    line["Amount"]
                    for line in row["Line"]
                    if not any(
                        target.startswith(("qbo:Invoice:", "qbo:CreditMemo:"))
                        for target in linked(line)
                    )
                ),
            )
            cash.add("unapplied_cash", unapplied, [key])
            for line in sorted(row["Line"], key=lambda line: line["Id"]):
                lk = key + ":" + line["Id"]
                targets = [k for k in linked(line) if k.startswith("qbo:Invoice:")]
                credit_links = [
                    k for k in linked(line) if k.startswith("qbo:CreditMemo:")
                ]
                if not targets:
                    if credit_links:
                        sheet.gap("credit_application_invoice:" + lk, [lk])
                    continue
                if len(targets) != 1 or targets[0] not in balances:
                    sheet.gap("payment_invoice:" + ";".join(targets), [lk, sk])
                    continue
                if self.r[targets[0]]["CustomerRef"] != row["CustomerRef"]:
                    sheet.gap("same_customer_payment_invoice:" + lk, [lk, targets[0]])
                    continue
                amount = line["Amount"]
                if amount < 0 or any(
                    not target.startswith(("qbo:Invoice:", "qbo:CreditMemo:"))
                    for target in linked(line)
                ):
                    sheet.gap("single_invoice_cash_or_credit_allocation:" + lk, [lk])
                    continue
                if credit_links:
                    if len(credit_links) != 1 or credit_links[0] not in credits:
                        sheet.gap("credit_application:" + ";".join(credit_links), [lk])
                        continue
                    credit = credits[credit_links[0]]
                    if (
                        credit["target"] not in {None, targets[0]}
                        or self.r[credit_links[0]]["CustomerRef"] != row["CustomerRef"]
                        or max(credit["applied"], credit["seen"] + amount)
                        + credit["refunded"]
                        > credit["total"]
                    ):
                        sheet.gap("credit_allocation:" + lk, [lk, *credit_links])
                        continue
                    already = min(amount, max(0, credit["applied"] - credit["seen"]))
                    credit["seen"] += amount
                    credit["refs"].append(lk)
                    amount -= already
                balances[targets[0]] -= amount
                sheet.add(
                    "credit_application" if credit_links else "allocated_cash",
                    -amount,
                    [lk, targets[0], *credit_links],
                )
        for key, credit in sorted(credits.items()):
            remaining = (
                credit["total"]
                - max(credit["applied"], credit["seen"])
                - credit["refunded"]
            )
            if remaining < 0:
                sheet.gap("credit_capacity:" + key, credit["refs"])
            else:
                credit_left.add("unapplied_credit", remaining, credit["refs"])
        for key, balance in sorted(balances.items()):
            comparisons.append(
                {
                    "source_refs": [key],
                    "status": "partial" if sheet.gaps else "complete",
                    "computed": None if sheet.gaps else money(balance),
                    "reported": money(self.r[key]["Balance"]),
                    "delta": None
                    if sheet.gaps
                    else money(self.r[key]["Balance"] - balance),
                }
            )
        cash.gaps = list(sheet.gaps)
        credit_left.gaps = list(sheet.gaps)
        return sheet.result() | {
            "opening_cutoff": snapshot["as_of"],
            "unapplied_cash": cash.result(),
            "unapplied_credits": credit_left.result(),
            "reported_balance_comparisons": comparisons,
        }


def calculate(inputs, checks):
    """No IO or scenario/oracle access; repeatable pure arithmetic only."""
    with localcontext() as context:
        context.prec = 80
        engine = KPIs(inputs, checks)
        return engine.volumes() | {"revenue": engine.revenue(), "AR": engine.ar()}
