# PR 15 F1-c remediation

Scope: issue #8 only, comments 6641486855 and 6641487117 at 400b26a.

## Response map

- Primary F1-c: shared pre-exclusion original-sale validation rejects conflicting
  Invoice/SalesReceipt links for direct, event and combined identities.
- Financial F1-c: identical same-event refund economic payloads with credit intent
  conservatively gap both worksheets and consume neither; different native IDs
  do not prove two refunds. Standalone adjustment dedup remains unchanged.
- Financial optional validation: CreditMemo.RevenueEvent uses the existing scalar
  identifier validator, including list rejection via safe atomic C10 isolation.
- Shared capacity: exact ordered AR capacity/allocation gaps propagate to revenue,
  including both payment/refund orders and partial cumulative refunds.

## Verification plan

Fresh owned Python 3.12 environment; timeout 300 make check; exact independent
100% line and branch coverage. Raw prior/same-day matrix covers CM40/CM20,
standalone controls, distinct refunds, other invoice/cash-sale conflicts and all
three link representations. Exact status, values, gap refs and HTML anchor closure
are asserted. Existing customer/void/future/opening and ordered-capacity regressions
remain. Independent oracle and committed samples are unchanged. Targeted mutations
must detect sale-validation and duplicate-identity regressions separately.
Parent owns both fresh reviews, current-head QA and merge; no author approval.

## Local frozen-source evidence

Task-owned fresh Python 3.12.3 venv, editable pinned dev install. With both CI
artifact variables, `timeout 300 make check` exited 0: Ruff clean; **768 passed in
127.50 seconds; 1940/1940 lines and 884/884 branch exits**, independently checked.
No exclusions or gate changes. Business artifact is byte-identical to the committed
clean sample. Existing exact 18-scenario and sample reproducibility tests pass.

Temporary mutation probes each failed the new intended assertions: disabling
sale-link validation: 12 failures; disabling identical-refund ambiguity: 12
failures; disabling shared capacity-gap propagation: 4 failures (4 valid controls
pass). Restored kpis.py byte-for-byte, SHA-256
56f6b885002c7f40b9b5e70fe28134fd3081ccd9fe16e5321d10aa5cc7f63d24.
Post-restoration targeted tests and remote current-head CI/artifact verification
are reported on the same PR and to the parent after publication. No independent
review/QA approval is claimed by this author.
