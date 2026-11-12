.PHONY: check container-smoke validate-infra deploy-aws destroy-aws deploy-azure destroy-azure

IMAGE ?= ghcr.io/wojski999/propane-reconciliation-demo:main
STACK := propane-reconciliation-demo
AWS_REGION ?= eu-central-1
AZURE_RESOURCE_GROUP ?= propane-reconciliation-demo
CFN_LINT ?= cfn-lint
BICEP ?= bicep

check:
	python -m ruff check .
	python -m ruff format --check .
	python -m coverage run -m pytest
	python -m coverage report
	python -m coverage json -o coverage.json
	python scripts/check_coverage.py coverage.json

container-smoke:
	bash scripts/container_smoke.sh

# Offline, credential-free validation; Bicep warnings are treated as errors.
validate-infra:
	$(CFN_LINT) deploy/aws/template.json
	@out="$$($(BICEP) build deploy/azure/main.bicep --stdout 2>&1 >/dev/null)"; \
	if [ -n "$$out" ]; then echo "$$out" >&2; exit 1; fi; \
	echo "bicep: deploy/azure/main.bicep built with no errors or warnings"

deploy-aws:
	aws cloudformation deploy --region $(AWS_REGION) --stack-name $(STACK) \
	  --template-file deploy/aws/template.json \
	  --parameter-overrides Image=$(IMAGE) --no-fail-on-empty-changeset
	aws cloudformation describe-stacks --region $(AWS_REGION) --stack-name $(STACK) \
	  --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text

destroy-aws:
	aws cloudformation delete-stack --region $(AWS_REGION) --stack-name $(STACK)
	aws cloudformation wait stack-delete-complete --region $(AWS_REGION) --stack-name $(STACK)

deploy-azure:
	az deployment group create --resource-group $(AZURE_RESOURCE_GROUP) --name $(STACK) \
	  --template-file deploy/azure/main.bicep --parameters image=$(IMAGE) \
	  --query properties.outputs.url.value --output tsv

destroy-azure:
	az resource delete --resource-group $(AZURE_RESOURCE_GROUP) --name $(STACK) \
	  --resource-type Microsoft.App/containerApps --api-version 2026-07-01
	az resource delete --resource-group $(AZURE_RESOURCE_GROUP) --name $(STACK)-env \
	  --resource-type Microsoft.App/managedEnvironments --api-version 2026-07-01
	az deployment group delete --resource-group $(AZURE_RESOURCE_GROUP) --name $(STACK)
