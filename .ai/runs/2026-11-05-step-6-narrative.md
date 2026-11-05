# Step 6 — optional final narrative

Date: 2026-11-05. Scope: issue #9, approved business spec section 11 step 6.
Base: main 87e0671 (step 5 / PR #15 merged). Implementation only; native workflow
owns independent review, human gate and PR opening. Parent retains final review,
current-head CI/artifact QA and merge. No live API call or credentials were used.

## Plan and scope

- [x] Read approved spec, fixture contracts, standards, lifecycle and lessons.
- [x] Add optional minimized computed-result adapter with injected offline client.
- [x] Expose safe fallback reasons, citation checks, escaping and digest binding.
- [x] Extend deterministic summary, matching clean/issues artifacts and README.
- [x] Freeze and run complete make check in an owned Python 3.12 environment.
- [x] Prepare implementation commit and native PR body with Closes #9.

No numerical accounting rule, financial oracle, real integration or smoke contract
change is included. Default execution is offline regardless of environment keys;
--narrative explicitly opts into one provider request. Either missing environment
value keeps execution offline. Standard-library HTTPS avoids a runtime SDK/retry
policy. Official Messages contract: https://platform.claude.com/docs/en/api/messages/create.
Transport uses a 15-second socket timeout, no redirects or automatic retries.

## Safety and evidence design

An allowlist exports only status, finding IDs/severities/preformatted deltas and
thresholds, KPI values/units/quality, coverage and quality-warning codes. Source
rows, raw evidence, customer metadata, record explanations, run IDs and credentials
are excluded. API credentials are used only in transport headers. Prompt prohibits
calculations, altered numbers, inferred causes, invented remedies and false verdicts.
Response shape and bracketed citation IDs are checked; semantic truth is not proven.
HTML states those limits and escapes all text. Narratives never enter results.json
or pure calculations. summary.txt always contains deterministic computed results.

A digest over the full computed result binds source identity and calculated report
values. Both illustrative loading and HTML consumption reject stale digests.
Committed issues text is authored illustration, not claimed live Claude output.
All 18 exact numerical finding/alert/eligibility oracles remain unchanged. Literal
exit codes include 2 for P09 uncertain inventory and P14 unsupported refund revenue,
in addition to missing/stale source and supporting-data scenarios. No status-derived
exit assertion is used.

## Validation

Targeted development run identified two incorrect newly written exit expectations
(P09/P14), an inverted safety-text assertion and samples not yet regenerated.
The existing arithmetic was retained; expectations were corrected to the documented
incomplete-evidence contract and samples regenerated from the actual computation.
The final complete gate below supersedes this intermediate development run.

Independent review, GitHub CI and QA are pending; no all-merged claim is made.

## Final boundary review before frozen gate

Preformatted payloads explicitly say Not available for absent KPI/delta values,
never JSON null or an invented zero. Removed the old placeholder renderer text
parameter: computed summary always comes from deterministic summary(result).
Only the separate optional narrative panel accepts bound text. Targeted offline
adapter run: 53 tests pass, 74/74 application statements and 30/30 branch exits
for narrative.py. No line/branch exclusions. The first full gate was intentionally
stopped before completion for these changes; it is not reported as a pass.
The final gate uses timeout 900: the large coverage suite was still in the
business-report permutation matrix after several minutes on the shared host.

Recursive provider JSON is also classified as malformed with a computed fallback,
using an actual deeply nested response fixture. A hostile injected client mutates
its detached payload without changing any authoritative calculation value.
The final frozen-source gate begins after these probes. Earlier interrupted runs
are not validation evidence. CI's issues artifact uses disabled/offline fallback;
the committed issues report intentionally demonstrates the digest-bound authored
illustration instead. Their numerical results are identical; narrative status/text
are intentionally different and must not be mistaken for a provenance mismatch.

## Final frozen-source evidence

Owned Python 3.12.3 editable environment. Exact local/CI command: `make check`
(with the owned environment on PATH, timeout 900, and SMOKE_ARTIFACT,
BUSINESS_ARTIFACT, ISSUES_ARTIFACT set to the three artifact destinations).
Ruff lint and format passed. **1661 tests passed in 418.66 seconds**.
Independent exact gates: **2069/2069 application lines and 954/954 branch exits**.
No exclusions, partial-branch pragmas, test deletion or gate weakening.
All three real E2E artifacts were produced. README local sample links resolve;
clean has zero findings/alerts, issues has five findings/two source alerts.
Committed clean/illustrative issues reports and summaries reproduce current code.
No changes to rules.py, kpis.py or the exact numerical scenario oracle.

Implementation is ready for the native independent check/review and owner gate.
The prepared PR body is 2026-11-05-step-6-pr-body.md in this run directory.
No PR, remote push, base merge, independent approval, CI pass or QA sign-off is
claimed by this implementation step. The source business spec remains active.
