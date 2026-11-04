# Foundation setup run

Date: 2026-11-04. Scope: Phase A only, pending independent review and merge.

## Goal and approval

Deliver a minimal tested Python foundation, safety net and project skill pipeline.
The owner explicitly approved implementing the business spec and selected stack;
approval is recorded in the spec. Engineering choices are reviewable in this PR.

## Evidence

- Main audit: documentation-only commit `3f540e6`, specification PR #1.
- Python 3.12.3; editable install with pinned pytest 8.4.2, coverage 7.10.7,
  Ruff 0.14.3 and setuptools 80.9.0.
- `SMOKE_ARTIFACT=artifacts/smoke.html make check`: 15 tests passed, 27/27
  statements and 2/2 branch exits covered; Ruff lint/format passed.
- Negative tests independently fail each gate for one missing line/branch even
  where display rounding could report 100%.
- Synthetic marker written/read in temporary SQLite, escaped in static HTML,
  exercised through the installed CLI; safe mkdir/write failure tests.
- Project installation used `npx --yes skills add open-mercato/skills --skill '*'`
  with `--agent codex claude-code --yes`. Lock hashes and relative symlinks retained. Installed 74 skills; source HEAD observed
  at installation: `75cf3146fd31aa6fa53af0866c076e5b7a3d9179`.
- Pipeline detection: main, Makefile and Python toolchain. Owner-delegated answers
  applied, custom no-browser descriptor installed, existing labels preserved and
  31 missing default labels created. Cross-skill check: `SKILL_COVERAGE_OK`. No worker or merge workflow installed.

- Fresh archive of committed `cb121f4` installed into a new venv and passed
  `make check`: 15 tests, 27/27 lines, 2/2 branches, Ruff passed.
- Verified all 74 SKILL.md files and relative Claude symlink targets.
- GitHub rulesets query returned `[]`; no server-side merge protection configured.
- Reviewed copied tracker descriptor and removed its branch-protection bypass
  example; this project never uses admin bypass. Installed upstream skills remain intact.

## Delivery evidence

PR #2: https://github.com/wojski999/propane-reconciliation-demo/pull/2
Baseline head `a78aba0213c0d1aef3b275a056b13640ff58f183` passed workflow
41845784755 and check job 126628784033. Artifact `foundation-smoke-report`
(id 13331945804) downloaded and inspected: 268-byte HTML matches local generation,
contains the synthetic marker and no-audit disclaimer, with no remote assets.
Final documentation update triggers the same CI gate; final-head evidence is
recorded in the PR follow-up to avoid recursive evidence-only commits.

## Resume notes

Phase A delivered as PR #2; final-head CI follow-up is recorded on the PR.
Independent review, QA sign-off and any merge remain separate responsibilities.
No business implementation step is complete or claimed by this run.
