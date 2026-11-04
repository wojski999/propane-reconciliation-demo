# Step 1: deterministic fixtures

Approved scope: issue #4, section 11 step 1 only. Existing smoke remains unchanged.

## Plan

1. Finalize entity-specific source contracts, fictional policies and evidence IDs.
2. Build clean data and independent P01–P14, raw-repeat, wrong-clearing, combined scenarios.
3. Freeze independent hand-calculated oracle and verify fixture arithmetic, precision,
   reproducibility, boundary dates and dependency direction without running checks.
4. Run make check, open one PR with Closes #4, wait for current-head CI.

Independent reviews (including risk-high second review), QA and merge belong to
parent. No ingestion, business checks, KPIs or business report are implemented.

## Implementation evidence

- All four implementation steps above completed locally; PR/CI delivery follows.
- Pure generator returns 15 ordered UTF-8 source files; no oracle/application link.
- 18 exact scenarios: clean, P01–P14, raw-repeat, wrong-clearing, issues.
- Combined issues: five future findings, two alerts, explicit suppression/cascades.
- `make check`: 83 tests passed; Ruff lint/format passed; 92/92 measured lines and
  36/36 branch exits covered independently, with no exclusions.
- Tests verify arithmetic, source references, entity differences, isolation,
  reproducibility across processes/TZ/hash seeds, date/seed limits, DST and raw repeat.
- Existing smoke CLI, workflow and artifact unchanged; no ingestion/check verdicts.
- P05 explicitly approves 15% while unusual review threshold stays 10%, avoiding
  an unintended C04 cascade. Raw-repeat and wrong-clearing stay separate from issues.

## Resume notes

Implementation ready for PR delivery and current-head CI. Parent owns fresh
independent reviews including high-risk second reviewer, artifact QA and merge.
The business spec remains active; issues #5–#9 were not implemented.
