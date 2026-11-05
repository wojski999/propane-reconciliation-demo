# Keep public QA evidence portable

Date: 2026-11-05. Issue #18 review.

A design-tool JSON report contained absolute host filenames. Its findings were
useful, but the filenames disclosed a machine/worktree layout and did not resolve
for other readers. Before committing tool-generated QA evidence to a public repo,
normalize file references to repository-relative paths, verify those targets exist,
and scan all newly added evidence for host paths. Keep the original finding text
and be explicit when an artifact describes a pre-correction run.

The report-presentation tests now verify the committed detector artifact contains
five findings whose file paths are relative, contain no traversal and resolve in
the repository. This checks the public artifact without rerunning the detector or
claiming that old warnings are current results.
