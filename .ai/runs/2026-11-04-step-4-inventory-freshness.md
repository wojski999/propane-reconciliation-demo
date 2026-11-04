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

- [ ] 1.1 Detach manifests/alerts and derive source/scope dependencies.
- [ ] 1.2 Evaluate C09 and propagate C10/C11 eligibility before comparisons.
- [ ] 1.3 Implement C08 signed worksheets and consolidation.

### Phase 2: verification and delivery

- [ ] 2.1 Full exact 18-scenario oracle and adversarial raw-ingestion tests.
- [ ] 2.2 Fresh Python 3.12 make check with 100% line/branch coverage.
- [ ] 2.3 Publish one PR via om-open-pr and verify current-head CI.
