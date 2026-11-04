# PR 15 credit refund correction

Scope: issue #8 / spec section 7, financial review F1 at head f8990195.
The existing PR branch was merged into the task fork before additive changes.

## Response map

- Financial review F1: AR replay now includes qualifying nonvoid RefundReceipt
  events in `(opening cutoff, as_of]`. Exactly one already-known same-customer
  CreditMemo is required. Refunds consume available credit after deduplicating
  AppliedAmount/Payment links. Payment allocations also respect refunded capacity.
  No cash-refund AR subtraction, cash reclassification or revenue dedup change.
- Full/partial/over-capacity examples run raw JSON -> atomic import -> compute ->
  evidence -> HTML. They assert credit, AR/cash, complete/incomplete status, precise
  gaps and evidence closure. Additional chronology/void/unknown/ambiguous/customer
  tests exercise missing support and both payment/refund orders.
- Financial notes 1–3: README and fixture contract explicitly disclose POS item
  identity, assumed POS net_60F basis, and opening customer/invoice/credit limits.
- Financial note 5: --as-of help now states >= business-day end.
- Deferred note 4: existing merged C05 same-day credit-only refund missing-original
  behavior is a follow-up candidate, not changed in this focused fix.
- Primary notes: summary KPI/finding IDs and an issues sample remain for #9.
  No live Claude, oracle numeric changes or accounting policy expansion.

## Validation and delivery

Fresh task-owned Python 3.12 environment with pinned dev dependencies. Full exact
`timeout 300 make check`, current-head CI and downloaded artifact checks are
recorded in the PR response and parent report. No coverage exclusions or gate
changes. Clean sample regeneration only if deterministic outputs change. Parent
owns both fresh independent reviews, artifact QA and merge; author does not approve.


Initial full gate passed 672 tests with 1903/1903 lines and 862/862 branches.
Further raw-boundary tests first assumed a post-as-of event reached replay; the
importer correctly rejects it as WINDOW. Corrected that test to require an alert,
unavailable AR and incomplete run. Excluded void/post-cutoff documents are not
required in the used-evidence collection. The explicit cutoff replay test remains
separate. Standalone refunds do not require opening customer AR coverage.
The existing revenue-dedup test now also checks complete KPI status, AR/cash,
zero unapplied credit and both settlement source refs. No code was changed to
relax the importer; the baseline oracle and committed sample remain unchanged.


Final frozen-source validation: task-owned Python 3.12.3, pinned dev install,
`BUSINESS_ARTIFACT=artifacts/business-report.html SMOKE_ARTIFACT=artifacts/smoke.html
PATH=/tmp/propane-refund-1d53-venv/bin:$PATH timeout 300 make check` exited 0:
**682 tests passed, 1903/1903 application lines, 862/862 branch exits**. Ruff lint
and format passed; coverage exclusions and gate commands are unchanged. A fresh
clean CLI run's results, HTML and summary are byte-identical to committed samples;
no regeneration or digest change is needed. Current-head CI/artifact proof follows
in the PR response and Cezar report, avoiding a self-referencing SHA in this commit.
