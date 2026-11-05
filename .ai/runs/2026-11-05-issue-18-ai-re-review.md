# AI re-review — issue #18 business-first report and showcase

- Reviewed commit: `df4fed918ba392de4504514fcb9d9cd17ab8a981` (branch `cez/48514b5a`)
- Base: `origin/main` at `36753cd`; 38 files changed (3 commits)
- Method: `om-code-review` (built-in checklist, `CODE_REVIEW.md`,
  `BACKWARD_COMPATIBILITY.md`, `SDLC.md`), issue #18 "Done when" list, approved spec
  and engineering standards. Follows the review at `c56ab74`
  (`2026-11-05-issue-18-ai-review.md`).
- Verdict: **approve** (minors and nits only)

## Validation gate

Python 3.12.3 virtual environment in this worktree; the editable install resolves
`propane_demo` to this worktree's `src/`.

| Command | Result |
| --- | --- |
| `timeout 600 make check` | PASS (exit 0) |
| ruff check / ruff format --check | PASS |
| pytest | 1698 passed in 406.70s |
| coverage (independent checker) | 2244/2244 lines, 1038/1038 branches, 100% |

The gate left the working tree clean (samples remain byte-identical).

## Previous findings

- Major (absolute host paths in QA evidence): fixed; `file` values are repo-relative.
- Duplicate QuickBooks row: fixed by grouping five business systems with worst state.
- Mobile state/time run-together: fixed; verified in `showcase-mobile.png`.
- Raw ISO coverage time: fixed; both times use Denver formatting.
- Duplicate card without a dollar figure: now an evidence-bound estimate.

## Behavior verified

- Rules, KPIs, thresholds and complete/unavailable semantics are unchanged.
  New: `presentation.exposures` (pure, no I/O, architecture-tested) adds an optional
  `exposure_estimates` field to results; additive only. It values C01 at the single
  effective list price only with unique customer/item mappings and C04 evaluated,
  and C03 only for POS duplicates with one identical net amount; otherwise nothing.
  Estimates are labelled "not KPI totals" and never feed KPI tiles.
- `run.json` gains optional, validated `report_labels` (additive input contract).
- Showcase: complete, all sources fresh, five exceptions (C01, C03, C07, C08 high;
  C05 medium) with hand-calculated oracle values and totals; fixture updated.
- Issues sample: every KPI tile shows a plain reason, never a partial total; the
  headline names the failed and stale sources and the unavailable totals.
- One `<h1>`, unique ids, internal links resolve, no scripts or external assets,
  all source text escaped; technical report kept intact inside collapsed `<details>`.
- Pages workflow: least-privilege permissions, pinned action SHAs, publishes only
  committed samples with `index.html` = showcase; no repository settings changed.
- README: first link is the Pages showcase, plus the standalone sample.

## Findings

### Minor

1. `src/propane_demo/report.py` `source_groups`: the status strip omits price list,
   mappings and opening receivables. A failed price import shows an all-green strip
   (the headline and technical details still report it). Consider a sixth
   "Supporting records" row with the worst state.
2. `src/propane_demo/report.py` `impact`: a C05 discount finding without a credit
   memo or refund falls back to the technical `explanation` text. Consider a plain
   sentence with the computed delta.

### Nit

3. `formatted()` rounds gallons with Decimal's default half-even (e.g. 2.5 → 2);
   harmless for display, but half-up would match the estimate rounding.
4. Run records mention the owner's preview delivery path in general terms (no paths
   or secrets); consistent with earlier records on `main`.

## Limitations

- Screenshots were inspected from the committed PNGs; this review did not run a
  browser. CI and the PR body are checked by the publisher step.
