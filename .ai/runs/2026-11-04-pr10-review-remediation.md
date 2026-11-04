# PR 10 review remediation

Date: 2026-11-04. Scope: issue #4 source generator/contracts/oracle/tests only.
Parent run 78dedeb0; both independent reviews target bc35bd7. Same PR #10,
additive commits on its existing branch; no new PR, rule engine or issue #5–#9 work.

## Plan and disposition

1. Merge origin/cez/9216e375 into this task branch; read both review comments,
   approved spec, standards, fixture contracts, SDLC and issue #4.
2. Correct temporal source invariants together: current-day inventory movements
   and sources, start/end-relative boundaries, separate historical grace cases,
   pre-settlement batch sales/refund and post-settlement deposit, wider manifests.
3. Bind numeric oracle fields to independently calculated source values; require
   P07 461/-9 and P13 101/+11 mutations to fail. Suppress both POS-backed assets.
4. Fix strict AR/refund order, byte-identical QBO version-0 replay plus manifest,
   zero void amounts, explicit delivery payment linkage and signed deposit bridge.
5. Remove expected_net and packaged boundary answers; add access/package guards.
6. Validate in a fresh Python 3.12.3 environment, build/install wheel, run negative
   probes and current-head CI; respond on same PR and release the author claim.

## Verification

- Fresh /tmp environment; editable install with pinned dev dependencies.
- Ruff lint/format; timeout 300 make check. Final test and independent coverage
  totals: 147 passed, 97/97 application lines and 40/40 branch exits (100% each).
  P07 461/-9 and P13 101/+11 file mutations each produced exit 1 / one failed
  test; restored originals afterward. Installed non-editable wheel contains only
  data/template.json as package data and matches editable issues SHA-256
  493599d35fa694a4f77edcc2c032be25b8b7d64ce75b21d671518bae59424d3e.
  Current-head CI evidence is posted on PR #10.
- All timestamp membership tested for clean/issues at default date plus
  2026-03-08/09 and 2026-11-01/02, with explicit elapsed 24/25-hour exceptions.
- Each current inventory movement is bracketed by the same asset's readings and
  agrees with its delivery/POS source timestamp. Endpoints retain exact distances.
- Numeric comparisons derive actual/expected/delta/threshold from source records
  independently; no application checks or computed report are claimed.
- All 18 scenarios and primary finding IDs retained. P07 related refs include all
  signed deposit bridge lines; failed POS suppresses BULK-A and ISOLATED symmetrically.

## Resume notes

Parent must obtain both fresh independent review verdicts and static-artifact QA
on the final pushed head before considering merge. This task never self-approves
or merges. The business specification remains active and incomplete.


## Remaining findings follow-up (2026-11-04)

Read full comments 6634396390 / 6634398962 and prior response 6634165071.
Merged existing PR branch into task fork before edits; same PR, additive commits.
Closing BOUNDARY reading now end - 1h; readings expected window ends at cutoff.
New recursive source timestamp invariants cover all manifested content (including
nested QBO metadata/update versions) against window, extraction, as-of/future
policy and coverage. Only P10/issues QBO watermark comparison is exempt, with
its exact 25h stale age checked; future-record detection remains unconditional.
Original future closing observation plus widened window is a negative regression
for clean/issues/P10. Metadata tests bind catalogue/scenario severity, all missing
lookup keys from generated identities, P07 complete related refs from source
lines/batch, and remaining related refs from explicit scenario evidence semantics.
Negative regressions change P08 severity, drop one P07 related ref, and replace
P12 missing_reference. No application oracle access or business engines added.
Contract now states DEP-SHORT's explicit posting-date policy across DST and
prior-day advance-invoice revenue versus current-day gallons for future KPI work.

Fresh Python 3.12.3 venv: timeout 300 make check PASS, 181 tests, 97/97 lines,
40/40 branch exits, zero partial branches; Ruff lint/format PASS, no exclusions.
Three actual oracle-file mutation probes (P08 severity high to medium, drop one
P07 related ref, change P12 missing_reference) each fail targeted pytest (exit 1);
original bytes restored. Permanent regressions also reject the original future
closing reading for clean/issues/P10.

Independent timeout-300 chronology probe: PASS 16,437 cases (all 5,479 supported
dates 2020-01-01 through 2034-12-31 x clean/issues/P10). No future source,
window, coverage or extraction ordering failures. Probe uses generated outputs
and the recursive invariant helper, independently of application/oracle logic.
