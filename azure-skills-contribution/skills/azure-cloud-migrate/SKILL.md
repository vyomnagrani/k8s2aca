---
name: azure-cloud-migrate
description: |
  Assess and migrate cross-cloud workloads to Azure. Generates assessment reports and converts
  code from AWS, GCP, Kubernetes, or other providers to Azure services.
  WHEN: migrate Lambda to Azure Functions, migrate AWS to Azure, Lambda migration assessment,
  convert AWS serverless to Azure, migration readiness report, migrate from AWS, migrate from GCP,
  migrate Kubernetes to Azure Container Apps, migrate K8s to ACA, migrate Fargate to ACA,
  migrate Cloud Run to ACA, Kubernetes to Container Apps, AKS to ACA, ECS migration,
  container migration, containerized workload migration.
license: MIT
metadata:
  author: Microsoft
  version: 1.0.0
---

# Azure Cloud Migrate

This skill handles assessment and code migration of existing cloud workloads to Azure.

## Rules

- Follow phases sequentially — do not skip
- Generate assessment before any code migration
- Load the scenario reference and follow its rules
- Use `mcp_azure_mcp_get_bestpractices` and `mcp_azure_mcp_documentation` MCP tools
- Use the latest supported runtime for the target service
- Destructive actions require `ask_user` — global-rules

## Migration Scenarios

| Source | Target | Reference |
|--------|--------|-----------|
| AWS Lambda | Azure Functions | services/functions/lambda-to-functions.md |
| Kubernetes / AKS | Azure Container Apps | services/container-apps/k8s-to-container-apps.md |
| AWS Fargate / ECS | Azure Container Apps | services/container-apps/fargate-to-container-apps.md |
| GCP Cloud Run | Azure Container Apps | services/container-apps/cloudrun-to-container-apps.md |

No matching scenario? Use `mcp_azure_mcp_documentation` and `mcp_azure_mcp_get_bestpractices` tools.

### Container Apps Shared References

All Container Apps migration scenarios share these references:
- **Global rules**: services/container-apps/global-rules.md — ACA constraints, limits, unsupported features
- **Assessment**: services/container-apps/assessment.md — Compatibility analysis framework
- **Code migration**: services/container-apps/code-migration.md — Bicep templates, output structure, deployment

Load the scenario-specific reference first, then consult shared references as needed.

## Output Directory

All output goes to `<source-folder>-azure/` at workspace root. Never modify the source directory.

## Steps

1. Create `<source-folder>-azure/` at workspace root
2. **Assess** — Analyze source, map services, generate report → `assessment.md`
3. **Migrate** — Convert code using target programming model → `code-migration.md`
4. **Ask User** — "Migration complete. Test locally or deploy to Azure?"
5. Hand off to `azure-prepare` for infrastructure, testing, and deployment

Track progress in `migration-status.md` — see `workflow-details.md`.
