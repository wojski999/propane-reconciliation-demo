# Cloud deployment readiness (issue #20, PR #21)

Date: 2026-11-12 (Europe/Warsaw). Cezar task, one draft PR, no merge, no deployment.

## Milestones

- Official docs checked first (curl of AWS/Azure/GitHub pages; WebSearch was not
  permitted in this run). App Runner is closed to new customers; Lightsail Nano
  (USD 7/month) chosen for AWS, Container Apps Consumption (free grant) for Azure.
- Spec committed before code: `785e9ef`.
- Image `9abba5b`: build stage runs `--scenario showcase`; nginx-unprivileged serves
  it as uid 101 on 8080 with `/healthz`. Served `index.html` is byte-identical to
  `samples/showcase-report.html`. 82.4 MB unpacked, about 23 MB compressed.
- Templates, workflows, Make targets and structural tests: `aa5ff00`; runbook,
  OIDC trust files and lesson: `e93a4bd`. CI green on `e93a4bd`.
- Independent reviewer (fresh-context agent) reproduced a-d and requested changes:
  pipefail masking in the deploy step, environment not limited to `main`, missing
  image preflight, Azure role assignment by app ID, wrong Bicep code in the lesson.
  All fixed in the follow-up commit with tests; re-review requested on the new head.

## Resume notes

Remaining after this run belongs to the owner: merge decision, then the steps in
`docs/CLOUD.md` and the "verify after access" list. Nothing was deployed.
