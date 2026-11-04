# Step 2 — atomic ingestion

Approved scope: issue #5 only; section 11 step 2. Dependency PR #10 is merged.
No reconciliation engines, KPI computation, report or narrative changes.

## Plan

- Validate typed source records, metadata, references and physical counts.
- Preserve raw bytes and occurrence provenance; normalize scaled integer records
  with namespaced keys, version history, exact-repeat evidence and current view.
- Use fresh in-memory SQLite per run; source savepoints include QBO updates.
  Preserve failure manifests and deduplicated C10 alerts outside rollback.
- Derive unavailable scopes from source dependencies; retain missing lookup refs
  for future C11. Staleness engines remain step 4.
- Strengthen oracle metadata/suppression binding for PR #10 follow-up.
- Run fresh Python 3.12 environment, timeout 300 make check, exact coverage gates;
  open one PR via om-open-pr and wait for current-head CI. Parent reviews/QA.

## Evidence

All plan steps completed locally. Delivery/CI evidence follows on the PR.

- Fresh Python 3.12.3 venv, pinned development dependencies, timeout 300 make check:
  PASS 336 tests; Ruff lint and format pass; exact 573/573 application lines and
  240/240 branch exits, zero missing/partial branches and no exclusions.
- Every named generator scenario imported; only P11/issues fail POS as expected.
  P11 persists exactly C10|manifest:POS-FAILED, critical CSV_SCHEMA, exact
  file:pos.csv:row:2 evidence, zero POS normalized rows and healthy QBO rows.
- QBO base/update group rollback, late-write rollback, two failures/one alert,
  physical-file idempotency, exact repeated occurrences, latest source versions,
  deleted current lines under older replay, numeric namespace collisions tested.
- Every normalized raw occurrence pointer resolves against immutable input bytes.
  Typed SQLite INTEGER financial cells include scale/field pointer; exact signed
  integer limits and invalid precision/nonfinite/float inputs tested.
- Missing/unreadable/malformed/authoritatively failed/row-count mismatch versus
  valid empty inputs, missing support, metadata and DST boundaries exercised.
- PR10 nonblocking follow-up binds combined suppression to singles union and
  P10/P11 alerts to source manifests; negative mutations reject dropped C02/C06/
  C07/C12/all KPI scopes, empty P10 alerts, extra P11 C12, changed finding date/version.
- Smoke CLI, errors, report disclaimer, artifact and architecture checks unchanged.

## Validation limits and handoff

This is disposable in-memory storage, not a persistent database migration; therefore
no persistent schema/migration is introduced or simulated. Import complete is not
a business/freshness pass. Stale source watermarks survive for the later C09 engine;
no reconciliation, KPI arithmetic, business CLI/report/narrative or integrations
implemented. Missing valid support remains future C11 evidence. Parent owns two
independent risk-high Claude reviews, current-head artifact QA and merge decision.
Full business spec stays active; do not mark steps 3–6 implemented.


## PR #11 independent-review fixes

Scope: both comments 6636119372 / 6636151215, additive fixes on the same PR.
Merged original head f506a70236fdb44560910f019408f7b50ebbaea5 into the task fork
before edits. No oracle edits, business engines, integrations, QA or self-approval.

- Remove partial-asset escalation of KPI:inventory; assert P11 exact oracle scopes.
- Validate nontransaction Line and supporting JSON keysets/shapes; preserve row
  pointers for identity shape/value/normalization errors. Map parser recursion
  to JSON_SCHEMA and preserve safe manifest-index failure behavior.
- Preserve exact CSV repeats as immutable occurrences without extra current rows,
  versions, scaled values or C10; retain differing-key-content source conflicts.
- Use physical end-line CSV pointers; raw-byte blank-line/multiline regressions.
- Delete removed child reference requirements; Payment v1 removal followed by v0
  replay cannot resurrect current children/references.
- Isolate missing-manifest namespace and close connection on fatal expected errors.

Fresh isolated Python 3.12.3 environment: `timeout 300 make check` passed with
380 tests, Ruff lint/format, exact 600/600 application lines and 240/240 branch
exits; zero exclusions. Nine separate `python -I` adversarial probes passed:
source/manifest decoder recursion, Customer/Item Line strings, real
MISSING-pos.csv collision and P11 inventory eligibility. CI for the pushed SHA
is recorded in the PR response. No app/test oracle edits or gate changes.
Parent owns fresh independent reviews, artifact QA and merge decision.
