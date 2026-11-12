# Cloud deployment readiness: AWS and Azure

Date: 2026-11-12. Status: active, implementation in the same PR. Requested by the
owner as a Cezar task (one run, draft PR, no merge). This spec was written and
committed before any container, template or workflow code.

## Problem

The owner needs real, verifiable evidence of AWS and Azure work: the same public
synthetic demo reachable over HTTPS in each cloud. No cloud accounts or
credentials exist yet. This change only prepares the deployment; it does not
deploy. After the owner supplies access, deployment to each cloud must be one
command and must produce a public HTTPS address.

## Scope

- One container image for both clouds that serves the committed, deterministic
  `showcase` scenario output (synthetic data only), generated at image build time
  by the existing business CLI.
- Infrastructure as code for AWS and Azure, one deploy and one destroy command per
  cloud, credentials only from the environment or a CLI login.
- A GitHub Actions workflow that builds and validates the image and templates on
  every PR, publishes the image to GHCR on `main`, and a separate manual
  (`workflow_dispatch`) deployment workflow that logs in with OIDC and refuses to
  run without configured secrets.
- Owner instructions in `docs/CLOUD.md`, in Polish at the owner's explicit
  request (an intentional exception to the English-content rule for this one
  owner-facing runbook).

Out of scope: an actual deployment, account creation, custom domains, databases,
CDN, monitoring/log workspaces, extra environments, container registries in the
clouds, persistent state and any change to application behaviour.

## Decisions (checked 2026-11-12 against official documentation)

### Serving: static output behind nginx in one image

The demo is a CLI that writes a self-contained, script-free HTML report plus its
synthetic inputs and computed JSON. The image builds it in a Python 3.12 stage
(`python -m propane_demo --scenario showcase`, exit 0) and serves the directory
with `nginxinc/nginx-unprivileged` (runs as uid 101, port 8080). `/healthz`
returns 200 from nginx. Python `http.server` was rejected because its official
documentation says it is not recommended for production. No application code
changes; the existing CLI and `make check` contracts are unchanged.

### AWS: Amazon Lightsail container service, Nano power, scale 1

- App Runner is closed to new customers ("AWS App Runner is no longer open to new
  customers"): https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html
- ECS Express Mode (AWS's App Runner replacement) and plain ECS Fargate provision an
  Application Load Balancer for HTTPS, which alone costs more than Lightsail:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html
- Lightsail container services give a default HTTPS domain, a public endpoint
  health check, and accept images from a public registry, so no ECR is needed:
  https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html,
  https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services-deployments.html
- Price: Nano (0.25 shared vCPU, 512 MB) is USD 7/month: https://aws.amazon.com/lightsail/pricing/
  It is not an always-free service; new accounts receive up to USD 200 Free Tier
  credits valid for 6 months: https://aws.amazon.com/free/free-tier-faqs/

### Azure: Azure Container Apps, Consumption plan, scale 0 to 1

- External ingress gives a default HTTPS `*.azurecontainerapps.io` address.
- Monthly free grant per subscription: 180,000 vCPU-s, 360,000 GiB-s, 2 million
  requests; no charges while scaled to zero; health probe requests are not billed:
  https://learn.microsoft.com/en-us/azure/container-apps/billing,
  https://azure.microsoft.com/en-us/pricing/details/container-apps/
- 0.25 vCPU / 0.5 GiB allows about 200 active hours per month inside the grant.
- The environment is created without a Log Analytics workspace (log destination
  omitted), so no monitoring cost: https://learn.microsoft.com/en-us/azure/templates/microsoft.app/managedenvironments
- The built-in "Container Apps Contributor" role cannot create managed
  environments, so the deployer gets a custom role scoped to one resource group:
  https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/containers

### Image registry: GitHub Container Registry (public package)

Both services pull a public image, so one image serves both clouds and no cloud
registry is created. A GHCR package inherits repository access but not its
visibility, so the owner makes it public once:
https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility

### Infrastructure as code: native templates (CloudFormation JSON, Bicep)

Terraform was considered (one tool), but it needs a state file. Local state breaks
destroy from GitHub Actions; a remote backend adds an S3 bucket and a storage
account that the demo does not need. CloudFormation stacks and Azure deployments
keep state in the cloud, so deploy and destroy are idempotent from any machine.
Both are validated offline without credentials: `cfn-lint` for the CloudFormation
template and `bicep build` for Bicep. The AWS template is JSON so standard-library
tests can inspect it. Least-privilege AWS actions come from the resource handler
schema of `AWS::Lightsail::Container`:
https://github.com/aws-cloudformation/aws-cloudformation-resource-providers-lightsail

Destroy: AWS deletes the CloudFormation stack. Azure runs a Complete-mode
deployment of an empty template into the dedicated resource group, which deletes
every resource in it while the deployer stays scoped to that group.

### GitHub Actions authentication: OIDC only

AWS: IAM OIDC identity provider and a role trusting only this repository's
`cloud-deploy` environment:
https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
Azure: app registration with a federated credential for the same subject:
https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure
The deploy workflow is `workflow_dispatch` only; a preflight job fails before any
cloud step when the required secrets are absent. Secrets hold role/client IDs so
account identifiers never appear in the repository.

## Acceptance criteria

1. `docker build` succeeds; the running container answers `GET /` and
   `GET /healthz` with HTTP 200, runs as a non-root user and contains no secrets.
2. Both templates validate offline (`cfn-lint`, `bicep build`) with no errors, in
   CI and locally.
3. `make check` and the existing `check` CI job stay green; new tests are not skipped.
4. A secret scan of the diff (gitleaks) finds nothing.
5. `docs/CLOUD.md` lists exact owner steps, exact permissions, one deploy and one
   destroy command per cloud, and a cost table with sources and check date.
6. An independent reviewer reproduces 1–4 and posts a verdict on the PR.

Cannot be proven without accounts (listed in the PR and `docs/CLOUD.md`): the real
deployment, the public HTTPS address, sufficiency of the listed permissions and
actual billing.
