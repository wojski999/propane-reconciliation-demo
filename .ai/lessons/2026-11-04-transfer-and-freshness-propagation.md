# Gate both transfer endpoints before comparing inventory

A raw-input test removed the inbound half of a paired transfer. Checking transfer
support only while computing the outgoing asset left the receiving asset free to
report an invented excess. Validate pairs across the ledger first, reuse one C11
root for the pair, and block both affected assets before any comparison. Retain
signed known ledger inputs in blocked worksheets without manufacturing a total.

Freshness must reuse actual source dependencies, including record-level support.
A stale QBO feed also invalidates POS pricing through customer class and a POS
refund's QBO approval. These dependencies existed for C10 in step 3; injecting
only the old oracle's coarse stale scopes hid them. Use actual manifests and the
same unavailable-source pathway, and test independent stale/failed sources through
real ingestion. Update the explicit eligibility oracle when a verified dependency
was missing; never tune business findings or numbers to the implementation.

A second combined-input probe found that missing customer/item and missing asset
mapping shared a delivery-only C11 identity. The asset-mapping diagnosis includes
the existing identity manifest in primary evidence so both independent omissions
survive with distinct IDs. Keep a real-ingestion regression with both omissions;
an exception collision guard is useful only if ordinary incomplete data cannot
trigger it. Never manufacture a missing counterpart to distinguish the findings.

Two independent PR 14 reviews found a second evidence boundary: a present ledger
outflow cannot be silently dropped when its source is cancelled/void. That is
conflicting support, with both record refs and the expected source status in C11,
not a shortage. Test status-only raw mutations with the same ledger amounts.
Keep present incompatible sensor endpoints distinct from absent measurement
basis: approved C08 requires medium sensor uncertainty for the former, C11 for
the latter. Do not let a local fixture contract override the approved rule.
