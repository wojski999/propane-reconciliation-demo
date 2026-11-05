# Issue #18 — mockup v2 implementation (PR #19)

Date: 2026-11-05. Acceptance spec: the owner's PR #19 comment (mockup v2) plus
issue #18. Design reference: `.ai/design/2026-11-05-report-mockup-v2*`.

## What changed

- `report.py`: the business layer now follows mockup v2: dark sidebar with a
  synthetic brand and exception count, top bar (breadcrumb, business-day pill,
  "Data as of" pill), greeting with the computed headline and the sum of
  computed dollar impacts, "Yesterday's money flow" (four stages), three KPI
  cards, exceptions table with priority filters and a detail drawer, data-source
  pills with a "Technical details" disclosure that wraps every existing
  technical section unchanged.
- Row selection, the default-open first drawer and the priority filters use
  `:target` and `:has()` only; there is no JavaScript.
- Inactive controls (Export PDF, Send to team, Mark as resolved, Assign, the six
  pilot navigation items) are `aria-disabled` and visibly labelled as pilot
  features.
- Prior business day comparison: `presentation.prior_changes` compares two
  authoritative runs. The prior day is the clean synthetic scenario on
  business date - 1, computed by the same pipeline (`business.baseline`). Only
  complete values with the same unit and gallon basis on consecutive days are
  compared. The comparison JSON is in Technical details.

## Decisions where the data cannot support the mockup literally

- No conversion bars or "% of previous stage": the stages come from different
  worksheets, periods and units (delivered gallons on the business day, net
  revenue on the business day, AR cash allocations since the AR opening cutoff,
  card settlement reconciliation). The card says so in one line.
- "Paid" is the AR worksheet's allocated cash.
- "Deposited" (coordinator review, 13:58 Warsaw): the headline is the deposited
  amount, the $10 difference only in the chip. The synthetic data has no
  deposit dated on the business day; the only card deposit (DEP-SHORT) is dated
  Oct 29. `presentation.card_deposits` therefore sums active QuickBooks
  deposits linked to card settlement batches ($460.00, "1 card deposit dated
  Oct 29") and returns None when C07 is not fully evaluated. A "deposits on
  Nov 3" figure would be $0.00 and contradict the chip.
- Bulk tank inventory shows the computed C08 unexplained gallons, the number of
  tank/truck checks evaluated and the reading time; there is no inventory total
  in the computed results.
- No close (x) button in the drawer, because without JavaScript it could not
  close a drawer that is open by default.

## Coordinator review fixes (2026-11-05)

- Drawer record cards show business labels and formatting (Customer, Delivered
  in Mountain Time, Gallons to one decimal, Invoice "—"); raw values stay under
  "Raw record" and "See source records". Customer names come from synthetic
  showcase labels (`cargas:customer:CE-C1`, `pos:customer:POS-C1`).
- Missing-record card: "Searched QuickBooks invoice lines for delivery #1042 to
  Rio Grande Ranch."; the lookup key stays in the raw evidence.
- Threshold line in plain English ("Flags any delivered gallons left unbilled
  after the grace period") with the rule id as a small tag.

## Verification

- Browser checks (Playwright Chromium, `v2-browser-checks.json`): no horizontal
  scroll at 1440 px or 390 px, sidebar hidden on mobile, drawer selection,
  priority filter, "See calculation" opening Technical details, and print
  showing every drawer, all pass for showcase and issues.
- Contrast (`v2-contrast.json`): all 14 text/background pairs reach 4.5:1 or more.
- Screenshots: `showcase-*.png`, `issues-*.png`, and the comparisons
  `mockup-v2-vs-showcase-{desktop,mobile}.png` in `.ai/qa/2026-11-05-report/`.
- Calculations: `samples/*-results.json` and `*-summary.txt` unchanged.

## Review follow-up (6f0bc995, approve)

Addressed the optional findings: the decision sum now reads "across N flagged items ... (estimates and differences, not booked amounts)"; "Mark as resolved" uses the muted inactive style; the technical prior-day section states the synthetic clean baseline. PR title and `feature` label set; the PR stays draft for the owner visual approval.
