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

## F1-b event identity correction

Financial review comment 6641172959 reproduced a second route to the same
unapplied-credit defect: event-only RefundReceipt links were deduplicated for
revenue but ignored in AR. The reviewed head 6b194ca was merged before this
additive fix, on the same PR15 / issue #8.

Response map:
- One pure `refund_credit` resolver supplies explicit LinkedTxn/RevenueEvent
  identity to both revenue and AR. Known event-linked credits enter the same
  ordered capacity branch as direct links. Both identities agreeing consume once;
  disagreeing/multiple identities consume neither and expose precise credit gaps.
- Nonvoid, replayed, same-customer support remains mandatory. Known void/future/
  pre-opening identities and unknown direct credit IDs cannot be guessed. Event
  labels without any CreditMemo counterpart remain standalone cash adjustments,
  as in the unchanged clean REFUND-BOUNDARY and REFUND-BATCH fixture contract.
- Hand examples raw -> import -> compute -> evidence -> HTML: credit 20/refund 20
  leaves 0; refund 5 leaves 15; applied 12/refund 8 leaves 0; refund 9 plus applied
  12 or refund 21 gaps. Repeated for direct, event-only and agreeing-both identity,
  with prior-day and same-day credits. Prior-day revenue stays 1250.02; same-day
  credit recognizes 20 once (1230.02); AR stays 860.01 or 848.01 and cash 25.01.
- Raw multiple refunds 30+20 against credit 100 with payment-credit 50 leave zero
  in either ordering. Payment 51 causes a precise second-refund capacity gap when
  first, or a payment allocation gap when last. No negative asserted residual.
- Raw void, ambiguity, unknown direct identity, customer conflict, chronology,
  extraction/as-of and opening boundaries cover both routes. Opposing direct and
  event identities keep all credit unconsumed under partial status. HTML evidence
  links resolve, and settlements cite the credit, payment line and refund refs.
- No business oracle/sample numbers, optional narrative (#9), accounting scope,
  coverage exclusions or gate commands changed. This is author remediation, not
  independent review or QA; parent must obtain both fresh current-head reviews.

Fresh task-owned Python 3.12.3 environment, pinned editable dev install, exact
`timeout 300 make check` with both CI artifact variables: exit 0; **730 passed in
114.17s**, Ruff lint/format clean, **1910/1910 application lines and 862/862 branch
exits** with independent exact gates. Fresh clean report/results/summary remain
byte-identical to committed samples (HTML SHA-256
`1eeda59a93abc7d71f78a85bb7f3d6c85dfd9bf76ac6ea40a04e5b10436f2082`).
Current-head remote CI and artifact proof are recorded in the author PR response
and parent report after push; independent review and QA remain pending.
