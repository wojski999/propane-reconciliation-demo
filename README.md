# Propane reconciliation demo

Start your morning with the transactions that need attention: missing bills,
duplicates, settlement differences and unexplained inventory changes. This public
demo generates fictional QBO-shaped, Cargas-style and POS inputs, reconciles them
locally and produces an inspectable report. It connects to no real systems.

## Try the sample

Requires Python 3.12 and Make. Install the pinned development tools once:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Generate, import into fresh SQLite, reconcile and write the report in one command:

```sh
python -m propane_demo --scenario issues --output output
```

Open `output/report.html` directly in a browser. No server, API key, JavaScript,
external assets or network is needed after installation. The combined issues
scenario deliberately contains a failed POS feed and stale QBO coverage: its
**exit 2 and incomplete status are expected**, not a clean financial conclusion.
Use `--scenario clean` for a complete run with zero findings and zero alerts.
[Committed clean sample](samples/clean-report.html) and
[matching computed summary](samples/clean-summary.txt) need no installation.

Other scenarios: `P01`–`P14`, `raw-repeat`, `wrong-clearing`. Each runs independently.
Defaults are fixed: seed `20261104`, business date `2026-11-03`, cutoff at that
America/Denver day's end. For an explicit reproducible cutoff:

```sh
python -m propane_demo --scenario clean --business-date 2026-11-03 \
  --seed 20261104 --as-of 2026-11-04T07:00:00+00:00 --output output
```

Cutoff must include a UTC offset and be at or after business-day end. Changing it
can make source coverage stale; it never silently moves source watermarks. Business
days follow Denver's local midnight boundaries, including 23/25-hour DST days.
Revenue uses explicit accounting posting dates rather than inferred event dates.

## What the morning report shows

The report starts with complete/incomplete state and source alerts, then delivered,
retail and total gallons, net revenue and cutoff accounts receivable. Prioritized
exceptions link to raw evidence. Source windows, extraction times, coverage
watermarks, rule versions, evaluated/not-evaluated counts and signed inventory
and financial worksheets make limitations visible. Partial figures have no
asserted total; known contributions remain inspectable.

Clean hand calculation: **600.005 delivered + 55.000 retail = 655.005 US gallons**;
**$1,250.02 net revenue**; **$860.01 AR**, with **$25.01 unapplied cash** separate.
The report states the gallon basis. Cylinder counts require explicit fill mappings;
POS delivery representations are excluded from retail. QBO net sale lines already
contain discounts. Taxes and container deposits are excluded from revenue;
credit/refund event crosswalks prevent recognizing one adjustment twice.
AR starts from its opening snapshot and replays gross invoices, applied credits
and cash allocations by timestamp/stable ID. Credit application through Payment
is not new cash. Nonvoid refunds explicitly linked to one known same-customer
credit consume its available balance through cutoff; they reduce neither AR nor
unapplied cash. Applied/Payment-linked credit and refunds cannot exceed that credit.
Revenue checks that shared capacity from QBO records even when opening AR is
unavailable. Credit at or before the opening cutoff needs explicit residual
support. Identical refunds sharing one event are flagged for review, even at
different times: separate native IDs do not prove distinct settlements.
Reported Invoice.Balance is a comparison, never an added movement.

Demo assumptions: POS item IDs equal QBO Item IDs (an explicit synthetic identity
contract). POS gallon quantities are assumed to share the policy's `net_60F`
basis; POS supplies no independent basis measurement or temperature conversion.
Total gallons relies on that assumption, rather than proving physical equivalence.
Opening AR contains customer totals, not invoice or credit residuals. Allocations
to pre-opening invoices/credits and customers absent from the opening snapshot
therefore make AR incomplete; missing support is never inferred from current Balance.

Output includes original synthetic `inputs/`, `results.json`, `alerts.json`,
`evidence.json`, `summary.txt` and `report.html`. Repeating identical arguments
produces identical bytes. Files in the selected output directory are replaced;
choose a separate directory to retain a run. SQLite is fresh and in-memory each
time; no persistent cache or migration is introduced. Computed artifacts are
written before HTML; a rendering failure preserves them where possible and
removes the previous report before attempting the new one.

Exit **0** means complete execution, even with business exceptions. Exit **2**
means incomplete source/support evidence; affected conclusions are not asserted.
Exit **1** means fatal configuration, rendering or filesystem failure, with a safe
error and no claim of a successful report.

## How to trust the numbers

```sh
make check
```

CI runs this exact command: Ruff lint/format, pytest, and independent exact **100%
application line and branch coverage** gates. Tests compare all 18 scenarios with
a separate exact oracle, hand-calculated KPI answers, adverse cutoffs/allocations,
source rollback, hostile HTML escaping, offline references and failure exits.
CI uploads the real clean business report as `business-evidence-report`; the
existing `foundation-smoke-report` artifact is retained.

`propane-smoke --output artifacts/smoke.html` remains the separate infrastructure
sample (default `artifacts/smoke.html`, exit 0/1/argparse 2). It explicitly evaluates
no audit and keeps its original UTF-8 HTML contract.

## Scope and ownership

Synthetic decision support, not a certified audit or accounting correction. No
client records, credentials, accounting writes, vendor adapters or production
access. Real use first requires confirmed exports, identity/posting/tax/timing and
measurement policies, least-privilege permissions and client-owned infrastructure.
Source contracts are fictional, not claims about a vendor's actual export schema.
C12 summary-journal aggregation and double-billing policy are separate follow-up
work (#13). Live optional Claude narrative belongs to step 6 (#9); this step uses
only a deterministic offline computed-results summary and never reads API keys.
Your real accounts, data and provider costs remain under your control.

See the [approved specification](.ai/specs/2026-11-04-propane-reconciliation-demo.md),
[fixture contracts](.ai/specs/2026-11-04-fixture-contracts.md),
[engineering standards](.ai/specs/2026-11-04-engineering-standards.md) and
[contributor rules](AGENTS.md). Each business step has its own issue and PR;
green current-head CI, independent financial/code review and static-report QA
are required before merge.
