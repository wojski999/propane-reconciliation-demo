# PR 15 F1-d remediation

Scope: issue #8 only; financial review comment 6642030434 on dd1d898.
The existing PR head was fast-forwarded into the task fork before additive changes.

## Response map

- F1-d: revenue now invokes the existing ordered replay in an internal QBO-only
  capacity mode. It bypasses opening-AR source eligibility and snapshot lookup,
  using validated QBO customer identities and ordered CreditMemo/Payment/refund
  records. Both worksheets share the actual capacity/allocation logic; no copied
  arithmetic, invented opening balance or published synthetic AR worksheet.
- The same refund_credit_capacity / credit_allocation / credit_capacity gaps and
  source refs reach revenue, regardless of AR availability. Revenue does not also
  copy normal AR gaps, so no duplicate capacity gaps are emitted. Normal AR keeps
  its original opening/customer/source requirements and event window.
- Credit at/before opening is explicitly unsupported for settlement capacity:
  opening_credit_capacity names the existing credit/refund. The replay can still
  prove original-total overflow, but never calls an unknown opening residual healthy.
- Raw JSON regression matrix: CM40, RR15 then RR24/RR25/RR26, with normal opening,
  invalid opening source, and credit exactly at opening cutoff. Below/exact limits
  stay complete at 1250.02 when QBO suffices despite unavailable AR; overflow is
  partial with the exact RR-B gap and CM-X/RR-A/RR-B refs. Boundary credit is always
  partial with explicit missing residual support. HTML anchors and raw refs close.
- Financial nonblocking note: README now explains identical same-event refunds
  are conservatively ambiguous even at distinct times. No identity-policy change.
- No #9 narrative/API work, other accounting expansion, oracle or sample changes,
  exclusions or validation-gate changes. Parent owns both fresh same-head reviews,
  independent QA and merge; this author grants neither approval nor QA labels.

## Mutation evidence

An isolated copy of the application replaced only
`self.ar(capacity_only=True)` with the previous `self.ar()` dependency. The nine
new raw regressions produced **4 failed, 5 passed**: invalid opening plus RR15+26
incorrectly became complete, and all three opening-boundary cases lost their
required gaps. Original source was never mutated while the full gate was running.

## Validation

Fresh task-owned Python 3.12.3 venv, pinned editable dev install. Focused KPI/report
suite: 215 passed. Full make-check and current-head CI/artifact results follow
below and in the author response after publication.

Full frozen-source gate with both CI artifact variables: `timeout 300 make check`
exit 0; Ruff lint/format clean; **777 passed in 135.07 seconds; 1948/1948
application lines and 890/890 branch exits**, independently checked. No exclusions.
The clean business artifact is byte-identical to samples/clean-report.html (SHA256
1eeda59a93abc7d71f78a85bb7f3d6c85dfd9bf76ac6ea40a04e5b10436f2082).
The baseline oracle, sample outputs and generator have no diff. Remote CI and
artifact evidence is recorded in the PR response after the additive push.
