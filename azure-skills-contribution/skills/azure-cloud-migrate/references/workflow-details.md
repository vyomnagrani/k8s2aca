# Workflow Details

## Status Tracking

Maintain a `migration-status.md` file in the output directory (`<source-folder>-azure/`):

```markdown
# Migration Status

| Phase | Status | Notes |
|-------|--------|-------|
| Assessment | ⬜ Not Started | |
| Code Migration | ⬜ Not Started | |
```

Update status: ⬜ Not Started → 🔄 In Progress → ✅ Complete → ❌ Failed

## Error Handling

### General Errors

| Error | Cause | Remediation |
|-------|-------|-------------|
| Unsupported runtime | Source runtime not available in target Azure service | Check target service's supported languages documentation |
| Missing service mapping | Source service has no direct Azure equivalent | Use closest Azure alternative, document in assessment |
| Code migration failure | Incompatible patterns or dependencies | Review scenario-specific guide |
| azd init refuses non-empty directory | azd requires clean directory for template init | Use temp directory approach: init in empty dir, copy files back |

### Azure Functions Errors

For scenario-specific errors (e.g., Azure Functions binding issues, trigger configuration), see the error table in `services/functions/lambda-to-functions.md`.

### Azure Container Apps Errors

| Error | Cause | Remediation |
|-------|-------|-------------|
| CPU/memory ratio invalid | ACA Consumption enforces 1:2 CPU-to-memory ratio | Round up CPU to meet memory or round down memory to match CPU. See ratio table in `services/container-apps/k8s-to-container-apps.md`. |
| Image pull failed | Private image not in ACR, or ACR credentials not configured | Import image to ACR using `az acr import`. Ensure ACA has ACR pull access (admin or managed identity). |
| Ingress port conflict | ACA supports only one ingress port per app | Split workload into multiple container apps, or use TCP transport mode for non-HTTP. |
| Privileged container blocked | ACA does not support privileged containers | Refactor to run as non-root. Remove `securityContext.privileged: true`. |
| Volume mount failed | Unsupported volume type (hostPath, CSI) | Replace with Azure Files, Azure Blob, or EmptyDir. See volume mapping in `services/container-apps/global-rules.md`. |
| Exec probe not supported | ACA only supports HTTP and TCP probes | Add an HTTP health endpoint to the application, then use HTTP probe. |
| Environment too large for Consumption | Workload needs >4 CPU or >8 Gi memory | Use Dedicated workload profile. Set `workloadProfileName` in Bicep. |
| GPU SKU not available | ACA GPU profiles have limited region availability | Check ACA GPU availability by region. Use `az containerapp env workload-profile list-supported`. |
| Secret reference failed | Key Vault URL wrong or managed identity lacks RBAC | Verify Key Vault URL format. Assign `Key Vault Secrets User` role to the app's managed identity. |
| Service discovery broken | Inter-service URL still uses source platform format | Replace with ACA internal DNS: `http://<app-name>` for same-environment apps. |
| Deployment failed — subnet | ACA environment VNet subnet too small or misconfigured | ACA requires a `/23` or larger subnet. Check subnet delegation and available IPs. |
| Bicep validation failed | Invalid Bicep syntax or incorrect API version | Run `az bicep build --file main.bicep` to validate. Use API version `2024-03-01` or later. |
| Cron expression invalid | AWS 6-field cron used in ACA (expects 5-field) | Drop the year field. Replace `?` with `*`. Standard cron: `min hour day month weekday`. |
| Scale rule auth failed | KEDA scaler missing connection string or identity | Provide secret reference for KEDA auth parameter. Check `services/container-apps/code-migration.md`. |
