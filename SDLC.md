# Software delivery process

The committed `.ai/agentic.config.json` selects GitHub, base branch `main`, specs
in `.ai/specs`, the default label taxonomy and a QA gate. Tracker operations and
label guards are defined in `.ai/trackers/github.md`. Existing PRs keep their
current target branch. Read AGENTS and the relevant spec/lessons/run before work.

## Roles and lifecycle

The owner decides scope. The author implements; an independent reviewer examines
the current diff and tests. The maintainer owns labels, process and merge gates.
The QA reviewer inspects static HTML and E2E evidence; no browser is provisioned.

1. Intake: `om-prepare-issue` records problem, expected outcome, acceptance criteria,
   scope exclusions and the approved spec link in GitHub Issues.
2. Triage: `om-verify-in-repo` checks current main and existing PRs/claims. Do not
   duplicate completed or active work.
3. Claim: assign the automation user, apply `in-progress` through the label guard
   and post a claim comment. Back off when another active claim exists.
4. Implement: `om-auto-fix-issue` makes the smallest tested change, one ordered
   business issue at a time. Plan nontrivial work and retain run/resume notes.
5. Validate: run `make check` — exactly the PR CI command. It runs Ruff lint/format,
   pytest under branch coverage, coverage report, JSON and independent exact 100%
   line and branch gates. No exclusions or pragma bypasses.
6. Deliver: `om-open-pr` commits, pushes and opens/reuses one ready PR, linking the
   issue/spec, scope, validation, compatibility and remaining limitations. Release
   the issue claim on success or failure; do not leave abandoned locks.
7. Review: `om-code-review` applies CODE_REVIEW and engineering standards. Fix
   requested changes in the same PR and re-review the new head until approved.
8. QA: a `needs-qa` static-report PR waits for independent artifact/E2E inspection
   and `qa-approved`. Record `QA head: <sha>`; a later push requires fresh sign-off.
9. Merge: require green current-head CI and independent approved review, plus
   current-head QA approval when needed. The Phase A author does not merge.
10. Housekeeping: reconcile linked issues, record lessons and run evidence; move
    completed specs to implemented only after merge. The full business spec stays
    active until its entire scope is implemented.

## Labels and gates

Pipeline labels are mutually exclusive: `review`, `changes-requested`, `qa`,
`qa-failed`, `merge-queue`, `blocked`, `do-not-merge`. New PRs start in `review`;
review requests changes or routes approval to `merge-queue`. Only a QA reviewer
uses `qa` while testing; pass returns to `merge-queue`, failure to `qa-failed`.
A queue label is routing, never evidence that merge gates passed.

Category labels are additive: bug, feature, refactor, security, dependencies,
documentation. Choose one priority (low/medium/high/extreme) and one risk
(low/medium/high); absent values mean medium. Priority is urgency; risk is blast
radius. Money, auth, migrations or broad shared changes require high risk and a
second reviewer, plus relevant failure, isolation or migration tests.

Meta labels: `needs-qa`, `skip-qa`, `qa-approved`, `qa-self-verified`, `in-progress`,
`ci-monitoring`. Never combine needs-qa and skip-qa. Skip QA only for low-risk,
non-user-facing work. Authors never grant qa-approved. This project requires an
independent reviewer for sign-off and does not use the self-QA exception.
Blocked, do-not-merge, qa-failed, an active QA tester or red checks prevent merge.
All label changes use tracker existence guards and one updated rationale comment.

When work is fully reported and only CI remains, release in-progress and use
ci-monitoring; it is not a claim. Watch at most the configured 40 minutes, then
report pending check names and stop claiming follow-up. Remove ci-monitoring
when the result is reported. Do not treat an empty checks list as green: verify
workflow runs exist for the head SHA and are completed successfully too.

## Approval, queues and compatibility

The owner explicitly authorized implementation and the Python 3.12 / SQLite /
plain HTML / pytest+coverage / Ruff stack on 2026-11-04. Phase A is foundation
only; the six business issues in spec section 11 remain subsequent work.
A separate agent's explicit current-head approve verdict on the PR is acceptable
when shared-account GitHub self-approval is rejected. Never claim that a verdict
comment is native human approval. The config's default
`automerge.requireIndependentReview: false` controls an *additional native human*
review requirement; it never waives this repository's independent review rule.

Default queue labels (cez-autofix, automerge and automerge-signal labels) are
available for installed skills; their presence does not start a worker. Queue
eligibility retains skill defaults and only human-confirmed items are eligible.
This setup installs no worker, scheduler, merge automation or deployment workflow.
A child implementation task cannot gain merge permission from the config alone.

Respect BACKWARD_COMPATIBILITY before changing CLI, artifacts or tooling. Static
HTML pytest E2E and its downloadable artifact are the current acceptance evidence;
no browser test or screenshot pass is claimed. If interactive UI is introduced,
re-run setup with a real browser descriptor before browser-dependent QA.

## Maintenance

Keep config, this document, CI and Makefile aligned. Re-run
`om-setup-agent-pipeline` on toolchain/taxonomy changes; it preserves existing docs
and labels unless explicitly updated. Use `.ai/skills/<exact-skill-name>/SKILL.md`
for project extensions; do not edit installed skills. Optional product-layer
setup is `om-setup-discovery-pipeline`, outside Phase A.
