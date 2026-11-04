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

## Resume notes

Foundation implementation complete locally. Verify a committed fresh checkout,
open Phase A PR with om-open-pr, wait for current-head green CI and inspect the
HTML artifact. Final independent review and merge are separate responsibilities.
No business implementation step is complete or claimed by this run.
