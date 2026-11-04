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
