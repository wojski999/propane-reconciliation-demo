# PR 15 F1-g: rejected refund capacity

Scope: issue 8 / PR 15 only; no issue 9, live API, new feature or merge.
Base: ce540a8fea5c1951ca2c3fd623d46826a1c6ec46, merged into the assigned fork.

## Plan and response map

- Audit all shared replay refund exits and preserve uncertainty before rejection.
- Central reject_refund records explicit and actual event-matched candidate keys;
  no consumption or identity is guessed and later replay cannot erase uncertainty.
- Conflict-membership skip now resolves candidates first. Customer coverage,
  identity/not-yet-replayed, customer mismatch, existing uncertainty and capacity
  rejection all use the helper. Standalone/void and out-of-as-of events remain
  excluded. Revenue source errors still return unavailable before replay; opening
  AR errors do not prevent the QBO-only capacity pass.
- Raw sequence matrix covers prior-day direct/event conflict, before-credit,
  foreign customer, two explicit credits, sale conflict, duplicate event members,
  conflicting actual candidate, one-cent rejection and exact/over/void controls.
  Both valid and invalid opening AR are tested. Independent CM-H remains known
  except when explicitly implicated; all rendered evidence anchors resolve.
- Unit composition covers a rejected refund followed by a valid-looking Payment
  and refund in both replay modes, plus missing opening customer coverage.

## Validation

Fresh task-owned Python 3.12.3 venv, editable pinned dev install, both CI artifact
variables and timeout 600 make check: exit 0; 1608 tests passed in 372.42 seconds.
Ruff lint/format pass. Exact application coverage: 1976/1976 lines and 914/914
branches, no exclusions or gate changes. Local clean HTML matches committed sample.

Helper-disabled mutation in an isolated source copy (import path verified): 21
new regression failures and 4 passing controls, 1.93 seconds. Production source
was never mutated. Earlier targeted check: 246 passed / 800 deselected.

Two earlier full attempts were stopped after fixture/assertion corrections; neither
is claimed green. Prior conflict scenarios remain; their expected known residuals
now exclude unresolved credits and retain the original conflict-gap assertions,
with additional capacity gaps. No independent healthy contribution is suppressed.

Current-head CI/artifact comparison follows the authorized additive push.

## Resume

Local validation complete; commit and push additively to the existing PR branch.
Parent retains two fresh independent same-head reviews and QA; no self-approval.
