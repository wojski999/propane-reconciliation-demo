# Issue #18 review remediation

Date: 2026-11-05. Reviewed implementation: c56ab74. Review record: ef6cd7f.
This correction addresses the blocking finding and the actionable presentation
minors; it does not change calculations, thresholds or unavailable semantics.

## Findings addressed

1. Replaced all five absolute detector file references with repository-relative
   paths. Historical warning descriptions and snippets are preserved. Added a
   test verifying the five relative targets exist and contain no traversal.
2. Group the two QuickBooks manifests into one business-system row using the
   worst member state and oldest coverage. Keep individual import states in
   Technical details. The owner-directed five-row grouping supersedes the initial
   separate-label approach.
3. On phone widths, each status-row span is a block; the time starts below the
   status with a small vertical gap. No data is hidden.
4. Extraction and coverage timestamps share the same America/Denver formatter,
   including explicit MST/MDT labels and missing-time text. Summer and winter
   formatting have test coverage.
5. The duplicate card states the computed record count and asks whether it is a
   repeated import or duplicate sale; it does not invent a monetary impact.
6. The detector artifact remains a pre-correction record. Its old line-height
   warning is already documented as corrected; no clean rerun is claimed.

## Verification

Initial targeted report suite: 16 tests passed. All committed sample reports
regenerated. Final full gate and browser evidence are recorded below once complete.
Existing audit rules and KPI algorithms stay unchanged; owner-approved fixture
and additive exposure metadata changes are described below. Updated
screenshots cover the same 1440×1000 desktop and 390×844 phone viewports.
Independent re-review is required for the changed renderer; prior approval is not
claimed for this correction. No push, PR, deployment or merge in this step.

## Owner visual review incorporated before the next gate

The owner added six visual requirements while the initial remediation gate was
running. That obsolete test process was stopped by its exact PID; the expanded
change receives a fresh full gate. Showcase fixture metadata names Rio Grande Ranch,
the retail counter, numbered receipts/delivery/credit and the South yard bulk tank.
Closed card titles omit raw IDs. Exposure estimates are computed in a separate
pure module and retain source refs: approximately $200 unbilled at list price,
$20 potential duplicate net sales, $10 settlement difference and a $150 unusual
credit. Inventory has no supplied unit cost, so its 30-gallon variance explicitly
has no dollar valuation. No selling price is presented as inventory cost.

The showcase now has four high findings plus one medium credit. The credit changes
AR from 860.01 to 810.01 under the unchanged engine; revenue stays 1290.02 and
volume stays 600.005 + 55.000 = 655.005 gallons. Presentation rounds gallons; exact
worksheets remain available. One small note replaces four repeated missing prior-day
comparisons, using the owner's allowed alternative to adding unvalidated history.

Five system rows show worst member status and oldest known coverage; the complete
11-manifest table remains technical. Morning source extraction times precede a
06:30 Denver cutoff. Exact-24-hour grace controls move with that cutoff without
changing quantities or thresholds. The sample narrative's binding digest is
refreshed for the additive exposure field; narrative claims are unchanged.

Final owner-directed browser checks: all four PNGs recaptured and opened, at
1440×1000 and 390×844. Five grouped rows, mobile status/time separation, human
card names, whole gallons, one comparison note and visible high/medium priorities
confirmed. No horizontal overflow. Card source links and worksheet links reveal
collapsed technical ancestors; raw records expand. Palette unchanged from the
recorded AA checks. Extra direct DST probes on 2026-03-08 and 2026-11-01 both
produce a complete showcase with the same five findings and 810.01 USD AR.
The native workflow route address.done -> tests -> review was read from Cezar;
independent Claude Opus 5.5 re-review will follow without a duplicate child task.

## Final frozen-source validation

`PATH="$PWD/.venv/bin:$PATH" timeout 900 make check` exited 0: Ruff lint/format
passed, 1698 tests passed in 398.87 seconds, exact independent gates 2244/2244
application lines and 1038/1038 branch exits. No exclusions or bypasses. Rules,
KPIs and rule_inputs have no diff; the new exposure estimator has no IO/network
and passes the expanded purity allowlist and source-bound arithmetic tests.

Final print/keyboard checks also passed after owner changes. All nine checked
text/background pairs exceed 4.5:1; both reports retain their headline and four
KPI tiles in print. Temporary print PDFs are not shipped. Host-path scan passes
for all changed text artifacts. Detector finding content is unchanged apart from
its five relative filenames. The four refreshed PNGs and browser proof JSON are
ready for independent re-review; no author approval, publication or merge claimed.
