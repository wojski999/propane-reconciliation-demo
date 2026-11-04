# PR 12 independent-review remediation

Date: 2026-11-04. Scope: issue #6, approved specification section 11 step 3.
Starting reviewed head: 23bcdc9e1c850e7dc79440fdf4e451be9b8371bf.
Both full independent reviews were read before editing:
[primary review](https://github.com/wojski999/propane-reconciliation-demo/pull/12#issuecomment-6638007783)
and [accounting review](https://github.com/wojski999/propane-reconciliation-demo/pull/12#issuecomment-6638030051).
The PR branch was merged into the task fork; delivery uses additive commits on
that same PR branch. No main merge, duplicate PR, self-approval or QA sign-off.

## Finding-to-response map

1. Both reviews, C02: existing unmapped completed deliveries reuse the root C11
   and mark each dependent invoice line not evaluated. Single and split invoice
   regressions assert no false missing-counterpart C02.
2. Both reviews, C04: tax uses the immutable TotalTax JSON pointer; gross retains
   the parent ref. Combined discrepancies survive with distinct IDs. Real ingestion
   tests resolve the tax pointer into retained input JSON, including tax lines
   without IDs. Fixture contract documents raw and derived component resolution.
3. Primary review, emit: differing full findings with the same ID raise a stable
   explicit ValueError without replacing the earlier result. Identical findings
   deduplicate. Tests exercise both; canonical Item lookups deduplicate one root
   reached by C02 and C04.
4. Accounting review, C07: independently computable amount checks survive absent,
   omitted and foreign links. Missing targets yield C11; existing foreign or
   omitted expected links yield high C07. No cross-batch netting. Tests combine
   multiple batch/deposit/link amount discrepancies without ID collisions and
   test an additional existing foreign linked line, not just a replacement.
5. Accounting review, C06: new excess equals allocation minus max(prior signed
   balance, zero). Replay retains its signed balance and prior events. Tests cover
   110 against 100 then 5 (new excess 5), zero and one-cent new allocations after
   negative replay, and a zero new credit cross-reference after a 0.02 excess.
6. Accounting review, C12: C06/C12 share linked cash plus unapplied cash; unlinked
   lines and UnappliedAmt are alternative descriptions, not additive. A 25 unlinked
   line plus 25 unapplied and a 25 clearing posting produces no C12.
7. Accounting review, explicit approval: a 10% discount against 5% approval on a
   100 sale is computable C04 (-5) for POS and QBO, not missing-support C11.
8. Accounting review, opening customer: unapplied cash runs before the AR customer
   coverage guard; missing customer support still produces an independent C11.
9. Accounting review, ambiguous basis: differing mapped gallon bases produce C11,
   no arbitrary first mapping/price comparison.
10. Accounting review, clearing sign: documented the minimal existing debit-positive
    demo assumption; no speculative side configuration or production policy.
11. Primary minor: negative purity tests inject forbidden import and forbidden call,
    and require the guard to reject each. Primary nit: check-specific explanations.

## Verification

Fresh task-owned Python 3.12.3 virtual environment, editable install of pinned dev
requirements. `timeout 300 make check` uses the unchanged CI gate and no coverage
exclusions. The final local result and exact-head CI are recorded below/on PR.
Independent oracle and fixture files are unchanged.

Eight temporary source mutations were independently detected (pytest exit 1) by
targeted regressions: remove C02 support gate; reuse C04 bridge ID; disable collision
error; suppress C07 amount check on absent links; restore negative-balance C06
comparison; double-count C12 unlinked cash; ignore explicit approval cap; guess
first ambiguous basis. Each mutation was restored immediately. The full final gate
runs on restored production source, not on mutated code.

## Follow-up and limits

**Separate follow-up: delivery over-allocation / double billing.** Literal C01/C02
check uncovered volume, not excessive allocations. A second full invoice allocation
against one delivery can remain clean. The parent must track a separate approved
rule/threshold/evidence and regression; this remediation deliberately does not
expand issue #6 into that new check.

No inventory/C09 detection, KPIs/HTML, narrative or integrations were added. Static
smoke behavior and tooling contracts remain unchanged. Two fresh independent
Claude reviews on the final head and independent QA remain the parent's work.

Final restored-source local gate: **469 passed**; Ruff lint/format pass;
**1141/1141 application lines** and **514/514 branch exits**, zero missing lines
or partial branches. `git diff --check` passes. Mutation experiment: all eight
mutants detected, then restored. No oracle/source fixture changes.
