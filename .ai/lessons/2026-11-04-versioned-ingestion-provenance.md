# Versioned ingestion must test current lines and raw pointers

A transaction update removed a line correctly, but replaying its older parent
version initially resurrected that line because line-level upserts saw no current
row. Compare the parent version before changing current children, while retaining
all historical versions and raw occurrence pointers. Keep a regression that replays
the old physical file after the update, and asserts the removed line stays absent.

Source atomicity must include base QBO and its required update stream. Test both
late failures after writes and stream failures: normalized records, typed numeric
cells, versions and occurrences roll back together; original raw bytes and a failed
manifest plus one source alert survive outside the source savepoint.

Test provenance by resolving every saved pointer against the original source,
including root JSON objects and scalar fill-volume mappings. A plausible pointer
or a reconstructed wrapper is not the original raw value. Whole-file immutable
bytes preserve exact formatting; record JSON preserves structural values.

A missing supporting reference is different from malformed source schema. P14
intentionally omits refund support: do not turn an approved future C05/C11 fixture
into C10 by requiring optional support during import. Validate syntax when present.


## Review follow-up: inspect raw boundaries, not only normalized fixtures

PR #11 independent comments 6636119372 and 6636151215 exposed gaps despite 100%
coverage: nontransaction Line shapes, decoder recursion, optional support fields,
CSV duplicate evidence, physical line numbers, stale child references and synthetic
manifest namespaces. Exact coverage does not replace adversarial source probes.
Use an explicit optional-field allowlist, wrap row failures with their pointer,
resolve CSV evidence against original physical bytes (end-line for multiline),
and test healthy-source survival alongside full rollback. Compare failure-only
availability sets exactly to the test-only oracle; do not silently change it.
