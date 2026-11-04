# Engineering standards

Date: 2026-11-04. Status: proposed standards for review in the foundation PR.
The owner authorized Phase A implementation with the stack below; independent
review and merge remain pending. This document does not claim separate approval
of every engineering choice.

## Layout and naming

Python 3.12, standard-library SQLite and HTML; no framework, ORM, DI container or
runtime dependencies. Use one `src/propane_demo/` package, snake_case modules,
functions, variables, tables and columns; PascalCase types and UPPER_CASE constants.
Use Decimal for money/quantity arithmetic when introduced; floats are not financial
values. Add real modules when needed, never empty speculative layers.

Current graph: `cli -> smoke -> standard library`. CLI owns arguments, filesystem
output and exit status. Smoke owns only a synthetic infrastructure marker and its
HTML. `tests/test_architecture.py` inspects every application module, rejects
undeclared modules/import edges, relative imports and direct dynamic imports.
Do not bypass this enforcement using importlib, exec or plugin loaders. Future
rules must be pure: no CLI, persistence, rendering or network imports; declare
and test new edges in the same PR.

## Validation and errors

Use explicit boundary validation with standard-library types and ValueError for
invalid values; use the same validated representation downstream. Do not introduce
a second schema library or scattered coercion. Business schemas and record-level
validation belong to the first two implementation issues, not this smoke fixture.
The current CLI accepts only an output path; argparse rejects invalid arguments.
Catch expected boundary failures, emit a safe error and nonzero status. Never
catch broad Exception to report success. The smoke CLI catches OSError and exits 1;
usage errors exit 2. No stale audit result or financial verdict is produced.
SQLite smoke state is in-memory and discarded. Persistent schema/migration and
atomic import design are deferred to the import issue; no simulated migrations.

## Security minimum

Only synthetic data. Never commit credentials, exports, personal information,
environment files or generated databases. No remote calls in default execution or
CI. Parameterize SQL; escape every source/generated string in HTML. No remote
assets, executable source HTML or integration write endpoints. Workflow permissions
are read-only and actions pinned to commit SHAs. Never log raw exception details.
Run with no secrets. A future optional narrative adapter must remain outside rules.

## Validation and review checklist

`make check` is the complete local and CI gate: Ruff lint and format, pytest under
coverage, the coverage report, and separate exact line/branch gates. Coverage scans
all of `src`, including unimported modules. No bypass exclusions or partial-branch
pragmas. Scripts and tests are linted; gate behavior is tested with one missing
line and one missing branch independently, including values that round to 100%.

Review each PR for approved scope, deterministic behavior, missing/invalid/stale
input behavior, meaningful boundaries and error tests, exact provenance, escaping,
no secrets/network, dependency direction, green checks and artifact evidence.
Coverage is a safety requirement, not proof of business correctness.

## Add a new check

1. Link the issue to the approved spec rule, policy and acceptance criteria.
2. Define inputs, applicability, threshold boundary, severity, evidence and unavailable
   state before code. Write an independent hand-calculated oracle.
3. Add a pure function and tests for clean, issue, exact boundary, just-over boundary,
   missing, invalid and stale evidence; preserve source IDs and deterministic order.
4. Add import/report wiring only after the rule is tested; declare dependency edges.
5. Run `make check`, inspect HTML evidence and request independent review.

## Requirement to evidence map

| Requirement | Implementation | Evidence | Deferred |
|---|---|---|---|
| Layout | src package | Installed CLI E2E | Business modules |
| Validation | argparse | Invalid option test | Source contracts |
| Errors | Safe OSError | mkdir/write tests | Import alerts |
| Dependencies | AST allowlist | Architecture test | New real edges |
| Security | SQL parameters, escaping | Hostile label test | Optional API |
| Quality | make check | CI and HTML artifact | Audit acceptance |
