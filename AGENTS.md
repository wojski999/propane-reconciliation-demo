# Propane reconciliation demo

Public, synthetic-data demonstration of a daily propane distribution audit.

- Spec first: the owner must explicitly approve `.ai/specs/2026-11-04-propane-reconciliation-demo.md` before application code, fixtures, configuration or CI implementation begins. A merged spec alone is not implementation approval.
- Stack: Python 3.12, SQLite, plain HTML, pytest and Ruff; no web framework.
- Add meaningful tests with every implementation change. Require 100% application line and branch coverage, without exclusions added to bypass the gate.
- Every calculation and reconciliation is deterministic tested code. Claude only summarizes computed findings.
- Use synthetic data only. Never commit client records, company-specific research, credentials or personal data.
- Repository content, comments, documentation and reports are in English.
- Keep the smallest solution that correctly handles missing, invalid and stale inputs. No real integrations or accounting writes in the demo.

## Working agreement

Implementation was explicitly approved by the owner on 2026-11-04; see the approval
record in the spec. Phase A introduces only the repository foundation and a smoke
command. The six business implementation steps remain separate issues/PRs.

Before work, read the relevant `.ai/specs/` documents, `.ai/lessons.md`, related
entries in `.ai/lessons/`, and recent `.ai/runs/` records. Re-read repository facts;
do not substitute session memory. Name new documents `YYYY-MM-DD-slug.md`.
Archive obsolete specs in `.ai/specs/archive/`; move completed specs to
`.ai/specs/implemented/` only after merge. Do not move the full business spec while
its implementation remains incomplete. Record milestones and resume notes in
`.ai/runs/`; capture reusable review/failure lessons immediately.

Read [engineering standards](.ai/specs/2026-11-04-engineering-standards.md) before
code changes, plus `SDLC.md`, `CODE_REVIEW.md`, `BACKWARD_COMPATIBILITY.md` and
`.ai/agentic.config.json` before pipeline operations when those files exist.

- Plan nontrivial work and check its approved scope before editing.
- Prefer the smallest correct solution and verify assumptions against tests.
- Add meaningful tests for every implementation change. Run `make check` before
  committing: lint, format, pytest, independent 100% line and branch coverage.
- Keep calculations deterministic; treat optional generated narrative as untrusted.
- Record repeated work for a reusable skill or command; do not add abstractions early.
- Use one issue and one PR per business implementation step. Require green CI and
  an independent approved review before merge. This setup task must not merge.
