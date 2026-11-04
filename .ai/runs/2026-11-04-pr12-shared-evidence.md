# PR 12 shared evidence remediation

## Scope and response map

Read complete independent re-reviews [6638403517](https://github.com/wojski999/propane-reconciliation-demo/pull/12#issuecomment-6638403517) and [6638404727](https://github.com/wojski999/propane-reconciliation-demo/pull/12#issuecomment-6638404727) on head 55a1dd9. This task merged that PR head into its fork and delivers additive commits to the same PR. No main merge, duplicate PR, self-approval or QA sign-off.

- Both blocking findings: C12 primary refs now include the posting mapping key;
  C07 linked-line primary refs include the batch key. Shared journals/accounts and
  deposits no longer cause distinct supported comparisons to collide. The emit
  collision guard and identical-only deduplication remain unchanged.
- Regression matrix: two and three mappings sharing a balanced 50/50 journal;
  two and three settlement batches sharing a deposit with a 500-to-490 line change.
  Tests mutate generated raw files, ingest successfully without C10, detach from
  SQLite, reconcile, assert precise hand-calculated findings and preserve unrelated
  P05 findings. They resolve native and derived evidence, assert unique IDs, and
  repeat after reversing detached records/occurrences and raw export rows.
- Primary nonblocking links nit: absent targets mark only the links scope not
  evaluated; an independently computable settlement amount remains visible.
- Accounting nonblocking tolerance nit: bridge eligibility derives cents from
  price_tolerance. Three tests use 0.05 tolerance and a 0.03 price difference while
  independently detecting declared, allocation and delivered-amount differences.
- Optional tax component-key nit is deferred: the existing immutable pointer
  contract and raw resolution test remain unchanged. It does not block either
  independent review and is not necessary to fix shared evidence collisions.

## Compatibility and limits

Internal C12 finding identity now promotes the existing mapping evidence from
related to primary; the oracle comparison test explicitly adapts that metadata.
The independent oracle file and all source templates remain unchanged. C07 linked
line IDs now include batch evidence. No new accounting rule or cross-batch netting.
No inventory/freshness checks, KPIs, report, narrative, or integrations introduced.
Delivery over-allocation/double billing remains a separate follow-up for the parent
orchestrator to file; it must not be added to this PR.

## Verification

Fresh task-owned Python 3.12 virtual environment with editable dev installation.
Final make-check and current-head CI results are recorded in the response comment.
Two fresh independent reviews and QA remain the parent task's responsibility.

Final local gate: Ruff lint/format pass, **477 passed in 54.15s**;
**1141/1141 application lines and 514/514 branch exits** (independent exact gates).
No exclusions or missing/partial branches. Three temporary mutation probes each
failed the targeted suite: reverting C12 mapping identity (2 failures), reverting
C07 batch identity (2 failures), restoring fixed one-cent eligibility (3 failures).
Production source was restored byte-for-byte afterward. Oracle, source templates,
CLI, smoke, Makefile, pyproject and CI workflow diffs are empty.
