# Derive rule dependencies from actual supporting evidence

Step-3 adversarial tests exposed two dependencies absent from the coarse source
scope list. POS effective pricing reads the QBO customer's price class, and a
crosswalked POS refund obtains its approval from the QBO refund. QBO source rollback
must suppress those calculations instead of emitting missing-customer or approval
findings. Configured batch clearing also needs POS/settlement inputs; per-entry
journal balance remains independently calculable. Keep precise per-record scopes.

A second probe caught a provenance overwrite: QBO and updates share one atomic
source, so a source->manifest dictionary built from every failed manifest selected
the last rollback manifest instead of the root failure. Use the persisted C10
alert's source reference for the primary failure reason. Test the exact manifest,
not just that a not-evaluated state exists.

Full fixture oracle equality and 100% coverage alone did not expose these paths.
Retain source-boundary adversarial tests, missing optional tax-line IDs with real
raw pointers, large Decimal products, fractional percent excesses, multiline POS
identity and offsetting deposit lines alongside the independent financial oracle.
