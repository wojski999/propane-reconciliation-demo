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
Inspect the [issues report](samples/issues-report.html),
[computed results](samples/issues-results.json),
[computed summary](samples/issues-summary.txt) and
[illustrative narrative](samples/issues-illustrative-narrative.json) together.
The committed illustration is authored, not a live Claude response; its digest
binds it to the exact computed scenario and source digest.

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
`evidence.json`, `summary.txt`, `narrative.json` and `report.html`. Repeating identical offline arguments
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
`issues-evidence-report` independently exposes the incomplete combined scenario.

`propane-smoke --output artifacts/smoke.html` remains the separate infrastructure
sample (default `artifacts/smoke.html`, exit 0/1/argparse 2). It explicitly evaluates
no audit and keeps its original UTF-8 HTML contract.

## Scope and ownership

Synthetic decision support, not a certified audit or accounting correction. No
client records, credentials, accounting writes, vendor adapters or production
access. Real use first requires confirmed exports, identity/posting/tax/timing and
measurement policies, least-privilege permissions and client-owned infrastructure.
Source contracts are fictional, not claims about a vendor's actual export schema.
Issue [#13](https://github.com/wojski999/propane-reconciliation-demo/issues/13)
tracks the separate delivery over-allocation/double-billing policy. C12 shared
summary-journal aggregation also needs an agreed policy before real integration;
it is not the subject of #13. The optional final narrative summarizes computed results only.
Your real accounts, data and provider costs remain under your control.

See the [approved specification](.ai/specs/2026-11-04-propane-reconciliation-demo.md),
[fixture contracts](.ai/specs/2026-11-04-fixture-contracts.md),
[engineering standards](.ai/specs/2026-11-04-engineering-standards.md) and
[contributor rules](AGENTS.md). Each business step has its own issue and PR;
green current-head CI, independent financial/code review and static-report QA
are required before merge.

## Optional Claude narrative

The default command is strictly offline even when environment credentials exist.
Opt in explicitly with `--narrative` after setting both `ANTHROPIC_API_KEY` and
`ANTHROPIC_MODEL` in your own environment. Do not put secrets in commands committed
to this repository. No model is hard-coded. This sends only computed finding IDs,
severities, preformatted KPI/delta/threshold strings, coverage and quality warnings
to the account supplying the key. It never sends raw input records or evidence. Finding IDs can contain synthetic
source keys; replace or pseudonymize those keys before any real-data use.
The standard-library Messages adapter uses HTTPS, a 15-second socket timeout and
one attempt with no retries. Provider usage can incur charges; no live call is
needed to try or test the demo. The response token limit is 1200.

Without either environment value, or on timeout, authentication/rate/network/
provider error, empty/malformed output or unsupported citations, the report uses
the deterministic computed summary. `narrative.json` and HTML expose status and a
safe reason; failure does not change the computed results or business exit code.
Generated text is escaped, labeled AI-generated and untrusted. Only response shape
and cited finding IDs are validated, not sentence accuracy, arithmetic, causes or
remedies. The prompt prohibits calculation, altered totals and unsupported advice;
this is a behavioral instruction, not proof of compliance. Inspect the authoritative
computed evidence before acting. Narratives never feed back into calculations.
Illustrative text is explicitly not live-generated and is rejected for another
digest, including a changed KPI with unchanged source identity.

Real integration would use client-owned repository, deployment, accounts, data,
credentials, billing and revocation, with explicit permission for minimized AI
processing. QBO OAuth's broad scope does not enforce read-only; a future adapter
must restrict operations itself. No real integrations, scheduling, notifications
or accounting writes are implemented here.

## Delivery record

All six implementation steps have merged, each through its own PR with CI and
independent review: [fixtures #10](https://github.com/wojski999/propane-reconciliation-demo/pull/10),
[imports #11](https://github.com/wojski999/propane-reconciliation-demo/pull/11),
[checks #12](https://github.com/wojski999/propane-reconciliation-demo/pull/12),
[inventory #14](https://github.com/wojski999/propane-reconciliation-demo/pull/14),
[report #15](https://github.com/wojski999/propane-reconciliation-demo/pull/15) and
[narrative #16](https://github.com/wojski999/propane-reconciliation-demo/pull/16).
Foundation and validation corrections are in PRs #2 and #3. The final application
gate passes **1661 tests**, **2069/2069 lines** and **954/954 branch exits**.
See the [delivery evidence and remaining limits](.ai/runs/2026-11-05-demo-delivery.md).
