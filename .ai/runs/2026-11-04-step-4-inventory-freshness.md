# Step 4 — inventory and source eligibility

Source doc: .ai/specs/2026-11-04-propane-reconciliation-demo.md
Scope: issue #7, section 11 step 4 only. Reuse Cezar isolated worktree.
Parent owns two independent Claude reviews, QA and merge. No KPI arithmetic,
HTML, narrative, real integrations or accounting policy expansion.

## Implementation plan

Keep rules pure and derive dependencies from validated records. Evaluate actual
manifest coverage before business comparisons; combine C09 with persisted C10
roots. Produce signed per-asset inventory worksheets and basis-safe consolidation,
with explicit unavailable/uncertain states. Extend C11 and future KPI eligibility
without computing KPIs. Preserve smoke CLI, artifact and exact coverage gates.

## Risks

Source failures must suppress only dependent comparisons, never fabricate missing
counterparts. Ledger/source representations must count once. Missing bases/fills
are evidence gaps, not conversions. Consolidation must not hide offsetting asset
exceptions or uncertain readings. Oracle metadata adaptation is limited to the
already reviewed C12 posting mapping primary refs; business values remain fixed.

## Progress

### Phase 1: deterministic computation

- [x] 1.1 Detach manifests/alerts and derive source/scope dependencies.
- [x] 1.2 Evaluate C09 and propagate C10/C11 eligibility before comparisons.
- [x] 1.3 Implement C08 signed worksheets and consolidation.

### Phase 2: verification and delivery

- [x] 2.1 Full exact 18-scenario oracle and adversarial raw-ingestion tests.
- [x] 2.2 Fresh Python 3.12 make check with 100% line/branch coverage.
- [x] 2.3 Publish one PR via om-open-pr and verify current-head CI.

## Verification notes

The first stable full suite passed 548 tests with every application line covered;
raw adversarial probes exposed and fixed paired-transfer cascading verdicts.
Additional tests now preserve sub-milligal tolerance precision and exercise both
sides of the endpoint freshness boundary. Final full gate and CI evidence follow.

P10 eligibility metadata explicitly adds the verified POS customer-class and
refund-approval dependencies on QBO. The reviewed C12 mapping primary-ref change
is now literal oracle metadata. All numeric business oracle values are unchanged.
No future freshness scope injection remains in the 18-scenario acceptance test.

C10 failure provenance now consistently uses the persisted root alert, including
QBO's shared update source, rather than listing rollback siblings as new failures.

## Local gate

Fresh task-owned Python 3.12.3 virtual environment, editable installation with
pinned dev dependencies. `PATH=/tmp/propane-step4-9300419a-venv/bin:$PATH timeout
300 make check` passes Ruff lint/format and **556 tests in 73.07 seconds**.
Independent exact coverage gates: **1409/1409 application lines, 652/652 branch
exits**, no missing/partial branches or exclusions. Full exact 18-scenario findings,
alerts and eligibility oracle; no injected freshness. Explanation wording is not
an arithmetic oracle; every other finding field is checked exactly.

Raw-import inventory evidence includes P08 opening 1000, purchases +200, delivery
-100 and retail -50 = expected 1050; observed 1020, delta -30, tolerance 6.
Whole measured-business expected 3245 and P08 observed 3220 (delta -25 including
the legitimate +5 BOUNDARY tolerance example); paired 50-gallon DEPOT/TRUCK
transfers eliminate. Unknown/ambiguous supporting data never supplies a verdict.

Three temporary mutation probes failed targeted tests as required: reversed
outflow signs (1 failure), extraction in place of coverage watermark (2 failures),
and retaining transfers in consolidation (1 failure). Original rules restored
byte-for-byte before make check. Smoke CLI, workflow and artifact remain intact.

A combined customer/item plus asset-mapping omission probe exposed another C11
identity collision. The asset-mapping root now includes its existing identity
manifest, retaining both precise lookup failures without a fabricated record.
Current-head CI and parent-owned independent reviews/QA remain publication gates.

## Publication

[PR #14](https://github.com/wojski999/propane-reconciliation-demo/pull/14) is ready,
Closes #7, with review/feature/needs-qa/priority-medium/risk-high labels; issue
implementation lock is released. Initial implementation SHA
118e6fa62792f7971d9e8244fb2d0bbdf6da84b2 passed the
[Check workflow](https://github.com/wojski999/propane-reconciliation-demo/actions/runs/41891002243),
including the foundation-smoke-report artifact. This delivery-record-only commit
is followed by a final-head CI check; its exact SHA/workflow are reported in the
PR comment and Cezar report to avoid a self-referential hash in this document.
Parent owns two independent Claude reviews, current-head artifact QA and merge.
No self-approval, merge, main push, or real integration was performed.
