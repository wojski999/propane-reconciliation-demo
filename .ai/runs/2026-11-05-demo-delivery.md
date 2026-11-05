# Demo delivery evidence

Date: 2026-11-05 (Europe/Warsaw). Scope: the approved synthetic propane demo.
All six implementation issues are merged. This documentation closeout still
requires its own independent review and green PR CI; it does not claim its own merge.

## Visible delivery history

- Spec: PR #1. Foundation: PR #2. Independent-review guard corrections: PR #3.
- Issue #4 / PR #10: deterministic fixtures, contracts and independent oracle.
- Issue #5 / PR #11: atomic SQLite imports, validation and immutable provenance.
- Issue #6 / PR #12: deterministic billing/payment/accounting/POS checks.
- Issue #7 / PR #14: signed inventory, freshness and missing-data propagation.
- Issue #8 / PR #15: KPI arithmetic, offline evidence report and CLI.
- Issue #9 / PR #16: optional narrative, safe fallback, samples and business README.

Every implementation PR merged only after successful current-head CI and
independent review; business PRs received a second independent risk-high review.
Review requests, findings, remediation commits and verdicts remain on GitHub.
No main force-push, direct base-branch push, admin bypass or live accounting write.

## Final application evidence

PR #16 merged as `379699a63fe0ce9a7f413d4d303c77fd44e68002`.
Reviewed head: `9348b0d6a674efee12fa5862bc889d27df119fc6`.

- CI [42012369302](https://github.com/wojski999/propane-reconciliation-demo/actions/runs/42012369302)
  completed successfully on that head; the actual clean, issues and smoke HTML
  artifacts were downloaded and checked by the second reviewer.
- [Primary review](https://github.com/wojski999/propane-reconciliation-demo/pull/16#issuecomment-6655876965)
  approved code `8d757cc`; the later commit only recorded that review.
- [Second narrative-safety review and static QA](https://github.com/wojski999/propane-reconciliation-demo/pull/16#issuecomment-6656023678)
  approved the exact final head. Clean HTML: 382 references, zero missing;
  issues HTML: 98 references, zero missing. No remote assets or executable scripts.
- Parent reproduction after accepting the reviewed branch: `timeout 900 make check`,
  exit 0; Ruff lint/format passed; **1661 passed in 382.21 s**;
  **2069/2069 application lines**, **954/954 branch exits**, independent exact
  100% gates. No coverage exclusions. Python 3.12.3; editable import path verified
  to point to the parent's own checkout. The optional pip reinstall was unavailable
  in that venv; the existing correct editable installation supplied the gate.
- Offline and mocked transport tests only. No live or paid Claude API request,
  no credential read and no real client data were used.
- Independent QA here is static HTML/evidence QA, not a visual browser sign-off.
  No-browser/static pytest E2E was the owner's selected pipeline configuration.

After installing Python 3.12 development dependencies, run the demo with:

```sh
python -m propane_demo --scenario issues --output output
```

Exit 2 is expected for the planted incomplete evidence; inspect `output/report.html`.
Use `--scenario clean` for exit 0 and zero findings/alerts. Exit 1 is fatal failure.
Clean totals: 655.005 US gallons, net revenue 1250.02 USD, AR 860.01 USD;
unapplied cash 25.01 USD remains separate. Claude never supplies these numbers.

## Remaining scope and honest limits

Only issue [#13](https://github.com/wojski999/propane-reconciliation-demo/issues/13)
remains open: decide delivery over-allocation/double-billing policy before extending
rules. It is not a missing acceptance item of the approved demo and is not C12
shared-journal aggregation. Both policies require agreement before real integration.

Other non-blocking review observations remain documented, not silently implemented:
shared summary journals compare each mapping conservatively; some independent
inventory diagnostics can be masked by uncertain endpoint evidence; CreditMemo-only
refunds can lack C05 original-sale support; unknown credit capacity conservatively
withholds affected disclosures. Narrative citations do not prove sentence truth;
source keys in finding IDs need pseudonymization for any real-data use. A provider's
JSON `failure` key can choose a fallback reason, but cannot change numerical results.
Unavailable summary deltas may display `None`; the report and narrative payload
label unknown values explicitly. None of these is claimed as production readiness.

## Closeout discipline

README remains business-facing; PLAN and standards reflect completed steps.
The approved spec is moved under `specs/implemented/` with its original URL kept
as a section index, preserving reviewed links without duplicating requirements.
This final PR changes documentation only. CI and independent review still gate it.
GitHub process/CI evidence is visible; no server-side ruleset protection is claimed.

Closeout branch validation: `timeout 900 make check` completed with exit 0;
1661 tests passed, 2069/2069 lines and 954/954 branch exits. The 37 local
documentation link targets checked all exist; `git diff --check` is clean.
