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
