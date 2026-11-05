# AI review — issue #18 business-first report and showcase

- Reviewed commit: `c56ab74b15411574e910a4f9b24009ff58214f0c` (branch `cez/48514b5a`)
- Base: `origin/main` at `36753cd`; 24 files changed
- Method: `om-code-review` (built-in checklist, `CODE_REVIEW.md`,
  `BACKWARD_COMPATIBILITY.md`, `SDLC.md`), issue #18 "Done when" list, approved spec
  and engineering standards
- Verdict: **request changes** (one major finding, easy fix)

## Validation gate

Fresh Python 3.12 virtual environment with an editable install that resolves
`propane_demo` to this worktree's `src/`.

| Command | Result |
| --- | --- |
| `timeout 600 make check` | PASS (exit 0) |
| ruff check / ruff format --check | PASS |
| pytest | 1678 passed |
| coverage (independent checker) | 2170/2170 lines, 998/998 branches, 100% |

## Behavior verified

- Calculation code unchanged; the only non-presentation changes are the additive
  `showcase` scenario (`contracts.py`, `generator.py` = P01+P03+P07+P08 mutations).
- Headline, KPI tiles, cards and the strip derive from computed results. Unavailable
  KPIs show plain reasons; `known_value` is never shown (tested with a hostile value).
- Showcase is complete, all sources fresh, 4 high-severity exceptions across
  billing (C01), duplicates (C03), settlement (C07) and inventory (C08), with
  hand-calculated oracle values. Fixture `expected_findings.json` matches.
- Technical report is preserved inside a collapsed `<details>`; one `<h1>`, unique ids,
  internal links resolve, no scripts/external assets; all text escaped.
- Committed samples are byte-for-byte deterministic against the renderer (tested).
- Pages workflow: build `contents: read`, deploy-only `pages: write`/`id-token: write`.
  Pinned SHAs were verified to match checkout v4.2.2, upload-pages-artifact v3.0.1 and
  deploy-pages v4.0.5. It does not change repository settings.

## Findings

### Major

1. `.ai/qa/2026-11-05-report/design-detector.json:8,18,28,38,48`: the committed QA
   evidence contains absolute host paths that expose the agent machine's user and
   worktree layout. `origin/main` has no such paths; this public repo would gain the
   first. Fix: rewrite `file` values to repo-relative paths
   (e.g. `samples/showcase-report.html`) and search all new `.ai/qa/` files again.

### Minor

2. `src/propane_demo/report.py` data status loop: QuickBooks is listed twice because
   `freshness` contains two `qbo` manifests. Business readers see a duplicate row.
   Fix: label each manifest distinctly or group rows by system with the worst state.
3. `src/propane_demo/report.py` data status `<li>`: on phone widths (≤40rem) the state
   and "Last updated" text run together ("Up to dateLast updated", visible in
   `showcase-mobile.png`). Fix: add a separator or a block/margin rule for `.state`.
4. `src/propane_demo/report.py` data status: "Covered through" shows raw ISO
   (`2026-11-04T00:00:00-07:00`) while "Last updated" is formatted. Fix: use the same
   Denver formatting.
5. `src/propane_demo/report.py` `impact()`: the C03 duplicate card shows a generic
   explanation with no dollar figure, while the README cites $40. The finding has no
   computed amount (delta is a count), so this is acceptable. Consider a plain
   "2 sale records share one external reference" impact line.

### Nit

6. `design-detector.json` still reports a 1.28× line height warning; harmless.

## Limitations

- Screenshots were inspected from the committed PNGs; this review did not run a browser.
- No PR exists yet; CI and the PR description (embedded screenshots) are checked by the
  publisher step.
