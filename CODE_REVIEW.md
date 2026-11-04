# Code review

Read the approved business spec, relevant issue, `AGENTS.md`,
`.ai/specs/2026-11-04-engineering-standards.md`, `SDLC.md` and
`BACKWARD_COMPATIBILITY.md`. Review the current head, not only the PR description.

Prioritize correctness, synthetic-data safety, provenance and contracts. Verify
scope first: Phase A is a smoke fixture, not the full generator/import/rules/report.
Review the explicit validation and safe filesystem failure behavior, parameterized
SQL and HTML escaping. Inspect every new dependency and the enforced import graph.
Future calculations require independent hand-calculated expected values; coverage
alone is not a correctness oracle. All new application code needs meaningful tests
and 100% line and branch coverage without exclusions.

Run `make check`; check current-head CI and download/inspect the static HTML
artifact. No browser automation is required or claimed. Verify that the artifact
states no audit/KPIs were evaluated. Check that application discovery includes new
modules and that local validation still matches CI.

- Blocker: secrets/data exposure, unapproved scope, wrong financial result,
  bypassed validation/coverage, red required check, unsafe integration write.
- Major: missing unhappy-path tests, dependency violation, misleading report state,
  broken CLI contract or missing source evidence.
- Minor: localized clarity/style issue with no incorrect behavior.

Post actionable findings with file/line, consequence and a concrete fix. Request
changes for blockers/majors; re-review the new head. Approve only independently
of the authoring task. Report exact checked SHA and limitations. An approve verdict
comment from an independent agent is distinct from GitHub native human approval.
Do not invent approval when GitHub rejects self-review. Keep one pipeline state:
`review` -> `changes-requested` or `merge-queue`; QA remains a separate gate when
`needs-qa` is present. Authors cannot apply `qa-approved`. Never merge as part of
this foundation implementation task.
