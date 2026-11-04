"""Require independently complete line and branch coverage, without rounding."""

import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    totals = json.load(source)["totals"]
for kind, measured, missed in (
    ("line", "num_statements", "missing_lines"),
    ("branch", "num_branches", "missing_branches"),
):
    if totals[measured] == 0 or totals[missed] != 0:
        sys.exit(f"FAIL: {kind} coverage must be 100% with nonzero measured coverage")
    print(f"PASS: {kind} coverage 100% ({totals[measured]} measured)")
