# PR 15 F1-f remediation

## Scope and response map

Issue #8 / PR #15 only. Financial review 6643131642 requires persistence of
uncertain capacity for negative CreditMemo.AppliedAmount. Primary review
6643130445 approved F1-e; both reviews must be renewed on the resulting head.

The numeric rejection path now marks the credit key unresolved when AppliedAmount
is negative or exceeds abs(TotalAmt), preserving the existing applied_credit_invoice
gap. Existing refund, Payment and final residual handling inherit this registry;
revenue consumes the same capacity gaps independently of opening AR. No negative
amount is normalized to zero, no rejected amount consumes capacity, and a later
valid Payment cannot erase uncertainty. Non-numeric invoice-support behavior is
unchanged to retain prior accepted contracts and F1-a…e regressions.

CreditMemo early-exit audit: source eligibility/snapshot returns remain separate
from revenue's QBO-only replay; void/future parents never establish spendable
capacity; missing opening customer cannot affect the independent capacity replay.
Within the CreditMemo numeric branch there is one rejection site before continue:
both lower (<0) and upper (>abs(total)) boundary failures persist uncertainty.
Zero skips application; valid positive values retain max(applied, seen).

Non-blocking header Payment.LinkedTxn note: document that only Payment.Line links
are normalized allocation sources; header links remain evidence, without invented
processing or a new ingestion incompatibility.

## Verification plan

128-case raw ingestion → compute → render (both signs of TotalAmt): negative -25/-10/-0.01; zero; positive exact
remaining capacity; one cent over; fully applied and one-cent overapplied credits;
both opening states, direct/event identity, Payment before/after refund. Exact
capacity/allocation gap keys and evidence anchor closure asserted. Separate unit
cases assert an invalid credit exposes no residual while an independent healthy
credit retains 7.00. Retain every prior matrix, oracle, fixture and sample.

A fresh task-owned Python 3.12 venv is used. Full make check uses a 600-second
bound and both CI artifact environment variables. No exclusions or gate changes.
Results and current-head CI/artifact checks are appended below after completion.

Targeted gate: 740 passed in 71.61s (prior 672 plus initial new matrix and units);
final expanded 128-case matrix plus 4 isolated units: 132 passed in 12.52s.
Mutation removing only the two-line fix fails the first negative-applied raw case:
old revenue complete versus required partial. Fixed source restored before full gate.

First full gate: 1583 passed in 376.27s; coverage correctly rejected the old
negative-residual fallback (one missed line/branch). That fallback is unreachable
after numeric overapplication is persistently unresolved: refunds and Payment
lines already reject excess before consumption. Removed the redundant fallback,
keeping the registry gap and every coverage requirement; rerunning the full gate.

Final fresh Python 3.12 make check: exit 0; 1583 passed in 381.95s (0:06:21). Ruff lint/format
clean. Exact independent gates: 1964/1964 lines and 910/910 branches, both PASS.
Local business HTML SHA256 1eeda59a93abc7d71f78a85bb7f3d6c85dfd9bf76ac6ea40a04e5b10436f2082
matches the committed clean sample; smoke SHA256 bf7bd0e20fd7df3e137aa81daeea3dfc35cd55fdcf39fee035af0d80e28bcee6.
No fixture/oracle/sample or coverage exclusion changes.
