"""Invariants of the cloud deployment artifacts (image, templates, workflows).

These files are not Python application code, so they are checked structurally:
a broken port, health path, trigger or permission would otherwise only surface
after the owner supplies cloud access.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8080
HEALTH = "/healthz"

# Handler permissions published in the AWS::Lightsail::Container resource schema
# (aws-cloudformation-resource-providers-lightsail, create/read/update/delete).
LIGHTSAIL_HANDLER_ACTIONS = {
    "lightsail:CreateContainerService",
    "lightsail:CreateContainerServiceDeployment",
    "lightsail:DeleteContainerService",
    "lightsail:GetContainerServices",
    "lightsail:TagResource",
    "lightsail:UntagResource",
    "lightsail:UpdateContainerService",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def final_stage(dockerfile: str) -> str:
    return dockerfile.rsplit("\nFROM ", 1)[1]


def test_image_runs_pinned_bases_as_non_root_with_health_check():
    dockerfile = read("Dockerfile")
    bases = re.findall(r"^FROM (\S+)", dockerfile, flags=re.MULTILINE)
    assert len(bases) == 2
    assert all(re.search(r"@sha256:[0-9a-f]{64}$", base) for base in bases)
    runtime = final_stage(dockerfile)
    user = re.findall(r"^USER (\S+)", runtime, flags=re.MULTILINE)
    assert user and user[-1].split(":")[0] not in {"0", "root"}
    assert f"EXPOSE {PORT}" in runtime
    assert f"http://127.0.0.1:{PORT}{HEALTH}" in runtime
    assert "--scenario showcase" in dockerfile
    assert not re.search(r"^(ENV|ARG) ", dockerfile, flags=re.MULTILINE)


def test_build_context_is_an_allowlist():
    lines = read(".dockerignore").split("\n")
    assert "*" in lines
    allowed = {line[1:] for line in lines if line.startswith("!")}
    assert allowed == {"pyproject.toml", "src/", "deploy/nginx.conf"}


def test_nginx_serves_health_and_strict_headers():
    conf = read("deploy/nginx.conf")
    assert f"listen {PORT};" in conf
    assert re.search(rf"location = {HEALTH} \{{[^}}]*return 200", conf)
    assert "default-src 'none'" in conf
    assert "server_tokens off;" in conf


def test_aws_template_runs_one_nano_container_on_the_health_path():
    template = json.loads(read("deploy/aws/template.json"))
    assert set(template["Parameters"]) == {"Image"}
    assert "Default" not in template["Parameters"]["Image"]
    resources = template["Resources"]
    assert [r["Type"] for r in resources.values()] == ["AWS::Lightsail::Container"]
    props = resources["Demo"]["Properties"]
    assert (props["Power"], props["Scale"]) == ("nano", 1)
    deployment = props["ContainerServiceDeployment"]
    (container,) = deployment["Containers"]
    assert container["Ports"] == [{"Port": str(PORT), "Protocol": "HTTP"}]
    endpoint = deployment["PublicEndpoint"]
    assert endpoint["ContainerName"] == container["ContainerName"]
    assert endpoint["ContainerPort"] == PORT
    assert endpoint["HealthCheckConfig"]["Path"] == HEALTH
    assert template["Outputs"]["Url"]["Value"] == {"Fn::GetAtt": ["Demo", "Url"]}


def test_aws_policy_is_exactly_the_stack_and_handler_actions():
    policy = json.loads(read("deploy/aws/deployer-policy.json"))
    stack, lightsail = policy["Statement"]
    assert all(s["Effect"] == "Allow" for s in policy["Statement"])
    assert stack["Resource"].endswith(":stack/propane-reconciliation-demo/*")
    assert all(a.startswith("cloudformation:") for a in stack["Action"])
    assert "*" not in "".join(stack["Action"])
    assert set(lightsail["Action"]) == LIGHTSAIL_HANDLER_ACTIONS


def test_azure_template_scales_to_zero_on_the_health_path():
    bicep = read("deploy/azure/main.bicep")
    assert f"targetPort: {PORT}" in bicep
    assert bicep.count(f"path: '{HEALTH}'") == 2
    assert "minReplicas: 0" in bicep
    assert "maxReplicas: 1" in bicep
    assert "allowInsecure: false" in bicep
    assert "logAnalytics" not in bicep
    assert "secret" not in bicep.lower()


def test_azure_role_is_group_scoped_without_authorization_writes():
    role = json.loads(read("deploy/azure/deployer-role.json"))
    (scope,) = role["AssignableScopes"]
    assert scope.endswith("/resourceGroups/propane-reconciliation-demo")
    assert "SUBSCRIPTION_ID" in scope
    assert all(
        a != "*" and not a.startswith("Microsoft.Authorization")
        for a in role["Actions"]
    )
    assert not role["DataActions"]


def test_deploy_workflow_is_manual_oidc_and_checks_secrets_first():
    workflow = read(".github/workflows/deploy.yml")
    trigger = workflow.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  (\w+):", trigger, flags=re.MULTILINE) == [
        "workflow_dispatch"
    ]
    assert "id-token: write" in workflow
    steps = workflow.split("    steps:\n", 1)[1]
    preflight = steps.index("Preflight")
    assert (
        preflight
        < steps.index("actions/checkout")
        < steps.index("configure-aws-credentials")
    )
    assert preflight < steps.index("azure/login")
    for long_lived in (
        "aws-access-key-id",
        "aws-secret-access-key",
        "client-secret",
        "creds:",
    ):
        assert long_lived not in workflow
    uses = re.findall(r"uses: (\S+)", workflow)
    assert uses and all(re.search(r"@[0-9a-f]{40}$", ref) for ref in uses)


def test_image_publishing_is_limited_to_main():
    workflow = read(".github/workflows/container.yml")
    jobs = workflow.split("\njobs:\n", 1)[1]
    publish = jobs.split("\n  publish:\n", 1)[1]
    assert jobs.count("packages: write") == publish.count("packages: write") == 1
    assert "github.ref == 'refs/heads/main'" in publish
    assert "make container-smoke" in jobs and "make validate-infra" in jobs


def test_make_targets_use_the_committed_templates():
    makefile = read("Makefile")
    for target in ("deploy-aws", "destroy-aws", "deploy-azure", "destroy-azure"):
        assert re.search(rf"^{target}:$", makefile, flags=re.MULTILINE)
    assert "--template-file deploy/aws/template.json" in makefile
    assert "--template-file deploy/azure/main.bicep" in makefile


def test_oidc_trust_is_bound_to_this_repository_environment():
    subject = "repo:wojski999/propane-reconciliation-demo:environment:cloud-deploy"
    assert "environment: cloud-deploy" in read(".github/workflows/deploy.yml")
    (statement,) = json.loads(read("deploy/aws/github-trust-policy.json"))["Statement"]
    condition = statement["Condition"]["StringEquals"]
    assert condition["token.actions.githubusercontent.com:sub"] == subject
    assert condition["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    credential = json.loads(read("deploy/azure/github-federated-credential.json"))
    assert credential["subject"] == subject
    assert credential["audiences"] == ["api://AzureADTokenExchange"]
