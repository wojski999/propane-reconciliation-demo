# Bind optional text to computed results, not only source bytes

Date: 2026-11-05. Issue #9.

A source digest alone cannot establish that a stored narrative still matches a
changed calculation or policy. Bind illustrative text to a canonical digest over
the entire computed result, including source digest, and reject mismatches both
on loading and at rendering. Never describe an authored example as a live response.

Prompt prohibitions and valid finding citations do not prove sentence accuracy.
Keep text visibly untrusted, escape it, disclose exactly what was checked and
retain the deterministic summary and computed worksheets as authoritative.
Use an explicit payload allowlist rather than subtracting known private fields.
Default execution must stay offline even on a developer machine with provider
credentials set; require opt-in and test transport with injected fakes only.

Pin scenario exit expectations independently. An uncertainty-only scenario can
contain no failed import yet still require exit 2 because KPI support is incomplete.
Do not derive expected exits from the implementation's own status string.
