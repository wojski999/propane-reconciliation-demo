The morning report now includes an optional final Claude narrative without changing
its deterministic calculations. Default commands remain offline even with provider
environment values present. Explicit --narrative sends only allowlisted computed
results through one standard-library HTTPS request; failures use a visible,
deterministic fallback. Generated text is escaped and citation-checked, with an
explicit warning that sentence accuracy is not verified.

Computed summaries now include KPI values, quality, finding IDs and warnings.
Clean and issues samples reproduce current results; the issues illustration is
explicitly authored, not a live API response, and bound to the full result digest.
CI additionally publishes issues-evidence-report while retaining existing artifacts.
That artifact uses offline fallback; the committed issues sample separately shows
the authored illustration with identical computed results.
README covers the no-key demo, expected incomplete exits, financial limitations,
optional provider cost and client ownership. Historical plan/standards statuses
are updated without claiming step 6 has merged.

Closes #9

Spec: approved .ai/specs/2026-11-04-propane-reconciliation-demo.md, section 11 step 6.

Validation: exact local/CI make check in an owned Python 3.12 environment; final
counts and coverage evidence are recorded in 2026-11-05-step-6-narrative.md:
**1661 tests passed (418.66s), 2069/2069 lines and 954/954 branch exits**,
Ruff lint/format clean.
All 18 numerical scenario oracles are unchanged. Tests cover adapter success,
missing environment, timeout/auth/rate/network/provider errors, malformed/empty
output, unsupported citations, payload minimization, stale digests and hostile HTML.
No live or paid API request was made. Existing smoke and business exits remain.

Limitations: no semantic proof of generated text, real integrations, accounting
writes or new C12 policy. Independent review, current-head CI and static-report QA
remain required before owner merge. The native workflow owns its human gate and
PR opening; this body is prepared for that stage, not publication evidence.
