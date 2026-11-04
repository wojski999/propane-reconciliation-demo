# Verify coverage gates without display rounding

A scaffold initially had no measured branch exits. The independent gate refused
to claim branch coverage. Add real boundary validation when justified by the input
contract, test both outcomes and retain nonzero measurement checks. Never add a
meaningless branch just to make a metric nonempty.

A combined percentage alone obscures which dimension was measured. Check missing
lines and missing branches separately from coverage JSON. Keep negative tests with
one missing line and one missing branch, including percentages rounding to 100%.
