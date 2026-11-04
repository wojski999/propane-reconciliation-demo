# PR 15 F1-e remediation

Scope: issue #8 only; full reviews 6642378922 and 6642380582 at 179cc9c.

## Response map

Both required F1-e findings use one rejection path for line validation, preserving
existing invoice/customer gaps and adding the exact credit_allocation key and
line/all-credit evidence. An unresolved-key registry survives credits that appear
later. Rejected amounts consume nothing; later refunds and residual disclosure
inherit uncertainty. Missing opening-customer Payment skips use the same helper.
QBO-only revenue replay remains independent of opening AR. Valid shared-credit
max(AppliedAmount, payment applications), native links and cash handling remain.

## Early-exit audit

AR source/snapshot early returns are independent of revenue's QBO-only replay.
Adjustment conflicts contain only CreditMemo/RefundReceipt identities, never
Payment lines. Standalone refunds have no allocation to preserve. Invoice and
CreditMemo parent continues do not contain Payment allocations. Missing opening
customer is handled before its Payment parent continue. All invoice, amount,
non-invoice link and credit validation failures converge on the rejection helper.
Unlinked cash remains unapplied and does not acquire a synthetic credit gap.

## Verification

Fresh task-owned Python 3.12 environment; raw matrix exercises no/void/unknown/
later/foreign/two invoices/SalesReceipt and valid control, both opening states,
both refund/payment orders, 14/15/16 refund against CM40/payment25, and normal,
unknown, ambiguous, zero, void, later and AppliedAmount25 credits. Each case runs
real ingestion, compute and render with evidence closure. A separate healthy
credit must remain a known contribution where its own support permits it.
Full gate, mutation and current-head CI/artifact results are recorded in the
PR response and final task report. Parent owns two independent same-head reviews
and QA/merge; this author grants none.

Raw matrix: 672 passed in 71.83 seconds. Replacing only kpis.py with the reviewed
179cc9c source made the same matrix fail: 10 intended failures and 1 valid control
before maxfail=10 stopped the probe. Fixed source restored byte-for-byte before
full validation. Missing-opening-customer and later-valid-line unit probes both
pass; the latter proves uncertainty cannot be cleared by subsequent valid links.

## Frozen-source full gate

Task-owned fresh Python 3.12.3 venv and pinned editable dev install. Both artifact
environment variables set. Two `timeout 300 make check` attempts hit wall-time
limits without reported test failures; no partial run is claimed green. Retaining
all 672 Cartesian cases, `timeout 420 make check` exits 0: **1451 passed in
330.29 seconds**, Ruff lint/format clean; **1964/1964 application lines and 910/910
branch exits**, independent exact gates both PASS. No source exclusions, gate
changes, prior assertion changes or oracle/sample changes. The requested 300-second
local wall bound was exceeded and is disclosed; all checks did finish under a
bounded longer run. Current-head CI has its existing ten-minute job bound.
