# Source chronology and independently bound oracles

Two independent PR #10 reviews found that the fixture arithmetic ignored time:
all inventory movements preceded opening readings, batch sales followed settlement,
and end-relative offsets moved boundary readings across DST. Correct arithmetic
alone cannot establish a satisfiable clean fixture. Anchor day-boundary events to
start/end explicitly, keep historical grace examples separate, and assert source
movement bracketing, refund/payment ordering, manifest coverage and business-day
grace on ordinary, transition and adjacent dates.

A second cause was a self-consistent but source-unbound numeric oracle. Checking
actual minus expected equals delta accepts wrong answers such as P07 461/-9 or
P13 101/+11. Independently calculate every numeric comparison from generated
records and policy fields and assert all four oracle fields. Retain negative
mutation tests that prove those internally consistent false answers fail. Package
only source data; keep boundary expected answers and findings outside application
inputs, with a tested exact package-data allowlist and source-access guard.


Follow-up reviews found a missed future-source invariant: widening the expected
window did not make a reading after extraction possible. Boundary tolerance is
not permission to include future observations. Check every nested source timestamp
against its window, watermark, extraction and run as-of. A planted stale watermark
may exempt only that watermark comparison, never extraction/future checks. Keep a
regression restoring the original future closing reading even with the widened
window. Bind severity, missing lookup keys and complete related evidence as well
as arithmetic; deleting one valid related reference must fail independently.
