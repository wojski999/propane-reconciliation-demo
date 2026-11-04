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
