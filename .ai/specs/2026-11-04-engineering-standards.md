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

Current graph: `cli -> smoke -> standard library`;
`generator -> contracts -> standard library`;
`ingestion -> validation / generator / contracts -> standard library`;
`validation -> contracts -> standard library`;
`rule_inputs -> ingestion / rules -> ...`; `rules -> standard library` only.
The rules import allowlist excludes IO, persistence, CLI, rendering and network;
the boundary adapter detaches validated scaled values from SQLite. Generator reads packaged synthetic
source templates only. The independent expected oracle stays under tests and is
never an application input. Do not read test boundary answers or configured
expected amounts in checks; derive every comparison from source records.
The package-data allowlist contains only data/template.json and is tested. See the fixture contracts dated 2026-11-04.
CLI owns arguments, filesystem
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
SQLite smoke state is in-memory and discarded. Step-2 ingestion uses a fresh in-memory schema for every invocation and source
savepoints; no persistent migration format is introduced. Raw bytes and failure
manifests survive source rollback. No simulated migrations.

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

## Step-5 dependency extension

`__main__ -> business`; `business -> generator / ingestion / rule_inputs / kpis /
report / contracts`; `kpis -> rules` (pure helpers only); `report -> standard library`.
The purity allowlist and banned IO/dynamic-call tests apply to kpis as well as rules.
The business command owns files and safe exits, while kpis returns only detached
worksheets. Rendering accepts computed results and immutable evidence, escapes
all dynamic text and uses hashed local IDs. No application layer reads the oracle,
network or optional narrative credentials. Existing smoke remains separate.
