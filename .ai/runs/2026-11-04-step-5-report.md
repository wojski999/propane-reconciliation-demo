# Step 5 — reproducible KPI evidence report

Source doc: .ai/specs/2026-11-04-propane-reconciliation-demo.md
Scope: issue #8, section 11 step 5 only. Existing isolated Cezar branch.
Parent owns independent financial review, static-report QA and merge.

## Goal and approach

Generate synthetic inputs, import fresh SQLite, run all checks and pure KPI math,
then export deterministic computed JSON, alerts, offline summary and one standalone
HTML evidence report. Preserve smoke and exact coverage gates. No live narrative,
real integration, C12 policy expansion, network or accounting writes.

KPI arithmetic uses scaled validated source values; posting dates select revenue,
local half-open instants select volumes, timestamp/stable-ID replay selects AR.
Missing support retains known contributions with explicit partial/unavailable state.
Every displayed reference resolves to immutable raw input or an explicit missing key.

## Risks

Payment credit links are not cash; credit/refund events must not reduce revenue
twice. QBO net lines already contain discounts. Absent basis is never inferred,
including unmeasured assets. Rendering and filesystem failure must not masquerade
as a complete report. Self-contained HTML has no remote assets or scripts.

## Progress

### Phase 1: computation

- [ ] 1.1 Add pure KPI worksheets and independent hand-calculated tests.

### Phase 2: report and command

- [ ] 2.1 Add evidence report, safe CLI, offline summary and E2E tests.

### Phase 3: delivery

- [ ] 3.1 Verify exact oracle, full coverage, CI artifact and publish one PR.
