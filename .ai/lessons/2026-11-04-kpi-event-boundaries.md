# KPI event boundaries and evidence output

Step 5 uses distinct accounting posting dates for revenue and ordered event
instants for cutoff AR. A source net line already contains its explicit discount;
subtracting metadata again undercounts revenue. Credit allocations referenced by
Payment are not new cash. Hand-calculated tests plus two temporary mutation probes
caught both errors independently; production source was restored before the gate.

Volume support must include unmeasured deliveries: a blank D-FRACTION basis cannot
hide behind an inventory asset exclusion. Mark delivered/total volume partial,
retain known contributions and the precise delivery/basis lookup. A stale QBO
source also prevents classifying each-count POS items using stale Item support.

Evidence refs for source failures can use file:pos.csv:row:2, while occurrences
use file IDs and JSON/CSV pointers. Resolve both to preserved immutable bytes;
never invent a missing file when the failed physical input was retained. All
18 generated scenarios now prove raw support for every emitted reference.

A browser inspection found a real narrow-screen overflow from the source digest.
Wrap long document strings; hiding overflow would lose evidence. At the inspected
500-pixel viewport the final document's client and scroll widths match. Report
alerts sort by severity independently of canonical machine alert IDs. Check full
coverage again after the final source/render change; a previous passing import
in an already-running test process does not validate later edits.
