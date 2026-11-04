# Compatibility contract

Phase A has no stable business format, persistent database, HTTP API or external
integration. The only installed command is `propane-smoke` with optional
`--output PATH`, default `artifacts/smoke.html`, UTF-8 static HTML, success exit 0,
filesystem failure exit 1 and argparse usage failure exit 2. It replaces the chosen
output file and never presents an audit verdict. Keep this behavior or document an
explicit migration/replacement in the changing PR and README.

The `propane_demo` package is internal; no public calculation API is promised.
The in-memory `smoke_sample` table is disposable and has no migration contract.
Future persistent schemas require versioned migrations and rollback evidence when
introduced. Do not invent backward compatibility with the planned business CLI.

`make check`, the PR `check` job, HTML artifact name `foundation-smoke-report` and
`.ai/agentic.config.json` are team tooling contracts: update their consumers and
document changes together. Never weaken line/branch gates as a compatibility fix.
Skills are vendored with lock hashes and relative Claude symlinks; preserve them
when updating the collection. Local customizations belong under `.ai/skills/`.


Step 2 adds an internal `ingest(read_file)` Python API and disposable in-memory
SQLite source-import tables. Every call starts empty and returns a connection
owned by its caller. It introduces no persistent schema or migration obligation.
The smoke CLI, its errors and artifact, and `make check` remain unchanged. Future
persistence still requires versioned migration and rollback tests before use.


Step 4 extends the internal detached input/result with source eligibility,
per-asset inventory worksheets, consolidation and alerts. `reconcile_database`
persists C09 alerts into the existing disposable schema; it adds no migration or
business CLI. Blank CSV gallon basis is retained as C11 missing support, while
unknown nonblank bases remain invalid C10 input. Smoke command, exits, static
artifact and validation commands are unchanged. The literal C12 finding ID now
includes the already reviewed posting-mapping primary key, an internal identity
contract refinement with unchanged amounts.
