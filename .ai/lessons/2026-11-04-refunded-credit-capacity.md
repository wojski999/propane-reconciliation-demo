# Refund settlements consume credit capacity

A revenue deduplication test does not prove AR disclosures: a cash refund can
correctly avoid recognizing revenue twice while leaving a fictional unapplied
credit. Test the entire computed KPI and report status through raw ingestion.

Track applied credit (deduplicated against Payment links) and cash refunds against
one shared capacity, in deterministic event order. Refunds consume credit, never
AR or unapplied cash. Include all accepted settlement refs in the remaining-credit
worksheet. Reject unknown, ambiguous, cross-customer and over-capacity allocations
with precise gaps; never assert negative available credit or complete status.

Opening customer AR totals do not establish opening credit residuals. Refuse to
infer them. Test exact opening/as-of boundaries, void credits/refunds, multiple
partial refunds and payment-before/after-refund combinations alongside the unchanged
baseline oracle. Parent reviewers must inspect the new head after remediation.


## F1-b: share event identity across worksheets

The first F1 fix covered LinkedTxn but left the same defect reachable through
RevenueEvent. A revenue-only identity policy cannot justify a complete AR credit
disclosure. Resolve explicit credit identity once, then feed revenue exclusion and
ordered credit-capacity replay from that result. Reject conflicting direct/event
identities without choosing or consuming either. Reuse the regression matrix for
both identities instead of copying divergent policy or testing revenue alone.
Raw regressions must assert all affected values, status and evidence closure for
prior/same-day credits, partial and multiple refunds, payment ordering and gaps.
Standalone refund event labels with no credit counterpart do not invent a credit;
known void/future/multiple matches and unknown direct IDs remain missing support.

## F1-c: resolve economic identity before settlement exclusion

Two fresh reviews found that early credit-settlement exclusion bypassed sale-link
conflicts and duplicate economic payloads. A recognized credit ID does not prove
that the refund belongs to the same original sale, or that different native IDs
are different refunds. Reject contradicted sale links and ambiguous identical
same-event refunds before either revenue exclusion or AR consumption. Preserve
standalone dedup and legitimate differing partial amounts. Propagate ordered
capacity gaps into revenue rather than declaring inconsistent complete KPIs.
Validate optional event identifiers on both adjustment entity types at ingestion;
a list must isolate the source with C10, never fail in downstream grouping.


## F1-d: test invariants across independent source failures

Copying a downstream worksheet's gaps is insufficient when that worksheet can
return early for an unrelated source failure. Replay QBO credit capacity through
the shared calculation independently of opening AR, without fabricating balances.
Regression controls must include below/exact/over capacity, an invalid opening
source, and credit exactly at opening cutoff. Missing opening credit residuals
remain explicit even if the original credit total is known. Mutate back to the old
AR-dependent call to prove that the raw failure-isolation tests detect the defect.
