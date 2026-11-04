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
