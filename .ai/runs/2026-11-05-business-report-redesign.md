# Business-reader morning report — issue #18

Date: 2026-11-05. Implementation step of the approved implement-review-pr workflow.

## Approved scope and plan

The owner approved the presentation redesign in issue #18. This extends the
implemented demo's presentation and synthetic samples; calculations, policy,
thresholds, result JSON, unavailable semantics and original evidence remain
unchanged. One PR closes #18; this implementation step does not merge or change
repository settings.

1. Read the issue, approved specification, standards, lessons and current renderer.
2. Add a business-first headline, four KPI tiles, priority action cards and source
   status; retain the previous full report in a collapsed technical disclosure.
3. Compose P01/P03/P07/P08 as a complete fresh-data showcase, binding it to the
   existing independent source-derived oracle and new explicit numeric assertions.
4. Regenerate all committed samples; stage committed samples for GitHub Pages,
   copying showcase-report.html to index.html, with least-privilege pinned actions.
5. Verify exact samples, full coverage gate, desktop/mobile rendering, disclosure
   interactions, evidence anchors, print and accessibility; hand off to independent
   review, workflow validation and PR publication. No author QA approval.

## Design direction and references

Impeccable context and craft-floor guidance read. Read/Operate surface: daytime
owner review, restrained financial document, system fonts, white surfaces, dark
ink, labeled status colors and native disclosures. The approved issue supplies
layout, copy purpose and interaction choices, so no speculative brand or assets
are introduced. Reference patterns reviewed:

- [Intuit reporting overview](https://quickbooks.intuit.com/learn-support/en-us/help-article/product-setup/use-reports-center-categories-insights-information/L2KcVzxB7_US_en_US): business overview and money owed.
- [GOV.UK summary list](https://design-system.service.gov.uk/components/summary-list/): scannable facts and last-update metadata.
- [GitHub custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages): artifact/deployment separation, Pages environment and scoped permissions.

No external visual assets, JavaScript, runtime dependency or new calculation.
The original technical document is preserved inside one native details section;
Chrome opens its ancestors when navigating to an evidence/calculation fragment.
Per-source rows deliberately retain distinct manifests (including updates), rather
than hiding an individual failure behind a combined green system status.

## Business invariants

Showcase has four high-priority findings: 100.000 unbilled gallons, two duplicate
sale IDs, a -10.00 USD settlement difference and -30.000 gallon inventory difference.
All feeds fresh, no alerts or unavailable scopes, exit 0. The unbilled delivery is
aged, outside the current delivery day. Two duplicate receipts add $40 to recorded
revenue; presentation does not silently reverse them. KPI totals: 600.005 delivery
gallons, 55.000 retail gallons, 655.005 total gallons, 1290.02 USD net revenue and
860.01 USD AR. Comparisons are explicitly not computed; no prior-day calculation
or trend is invented. Partial known amounts never become a KPI total.

## Verification and handoff

Initial focused suite: 282 passed. Browser matrix: Chromium through the existing
VPS CDP endpoint, isolated context; 1440×1000 and 390×844, showcase and issues.
No horizontal overflow; source disclosure opens; calculation anchor opens the
technical disclosure. Browser context closed after capture. Four committed PNGs
and browser-checks.json live in .ai/qa/2026-11-05-report/; the PR publisher should
embed relative/raw branch image links to all four. Refresh captures after final
source changes. Author evidence is not independent QA approval.

An initial full-gate attempt caught redundant rendering of the raw C09 repeating
hour fraction in a new card disclosure. The redundant JSON was removed; the
existing technical readable duration and source links remain. Its exact
microsecond regression passes. Final full-gate evidence is appended below.

Pages is intentionally not enabled by automation. Owner selects GitHub Actions
in Pages settings after merge. No deployment or external URL availability is
claimed until that happens. Later workflow steps own independent review and PR.

### Final visual evidence

Final captures taken after the source-system card titles and typography changes.
Both reports: 1440×1000 desktop and 390×844 mobile; no horizontal overflow,
working native card disclosures, source-record links and worksheet links opening
collapsed technical ancestors. Keyboard Tab reaches the navigation. All nine
text/background palette pairs exceed 4.5:1. Print-media checks retain the headline
and four KPI tiles; temporary print PDFs were inspected by generation checks and
are not shipped. This is scoped author verification, not a full screen-reader audit.

Impeccable's detector ran once: tight-leading warning corrected by 1.3 line height
for headings/numeric values. Remaining cadence warnings come from existing safety
limitations in the preserved technical text; passed to independent review.
Its JSON is a pre-correction record, not a claimed clean final detector result.

PR publisher: embed all four committed image links (relative to the PR branch):

- `.ai/qa/2026-11-05-report/showcase-desktop.png`
- `.ai/qa/2026-11-05-report/showcase-mobile.png`
- `.ai/qa/2026-11-05-report/issues-desktop.png`
- `.ai/qa/2026-11-05-report/issues-mobile.png`

The step-3 independent reviewer should inspect those images and the current diff,
verify the money/unavailable constraints, run make check, and score the approved
issue's business-reader requirements. The step-4 publisher owns one PR closing #18,
image embeds, labels and current-head CI. No PR or merge is claimed by step 1.

Preview delivery: 24 explicitly scoped files copied to the existing project's
issue-18 preview inbox on the VPS. HTTP verification toward the Mac mini preview
server timed out (HTTP 000); iCloud upload and MacBook availability remain
unconfirmed. No live preview availability is claimed. Repository/PR artifacts
remain authoritative, and the publisher has all four PNGs in this branch.

## Final implementation gate

Frozen-source `PATH="$PWD/.venv/bin:$PATH" timeout 900 make check` exited 0.
Python 3.12.3; Ruff check and format passed; 1678 tests passed in 401.26 seconds.
Independent exact gates: 2170/2170 application lines and 998/998 branch exits,
with no exclusions or bypasses. New presentation regressions: 13 tests; the
additional exact-duration regression also passed. Existing clean/issues result
JSON and summary bytes, rules, KPIs, ingestion and computation boundary have no
diff. All sample HTML is deterministically reproduced by tests.

All four final PNGs were opened and visually inspected. Source-system failures
use POS/QuickBooks names, unavailable KPI tiles contain reasons, and the showcase
identifies the actual batch/deposit instead of a line number. No live API,
production or credential access, repository-setting mutation, push or merge.
Implementation step complete; downstream validation/review/publication remain
the workflow's responsibility. The one PR must close #18 and link all four PNGs.
