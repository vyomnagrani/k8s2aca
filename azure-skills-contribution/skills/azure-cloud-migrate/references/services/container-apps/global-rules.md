# Azure Container Apps — Global Migration Rules

Rules that apply to **every** migration targeting Azure Container Apps, regardless of source platform.

## Resource Limits

### Consumption Workload Profile (Default)
| Resource | Min | Max |
|----------|-----|-----|
| CPU (cores) | 0.25 | 4 |
| Memory (Gi) | 0.5 | 8 |
| Ephemeral storage | — | 8 Gi |
| Max replicas | 0 | 300 |

### Dedicated Workload Profile
Use when source workload exceeds Consumption limits (>4 vCPU or >8 Gi memory).
Dedicated profiles support up to 32+ vCPU and 256+ Gi depending on SKU.

> **Rule**: If source container requests >4 vCPU or >8 Gi, set `workloadProfileName` in Bicep and flag in assessment.

### GPU Workload Profile
| SKU | Max GPUs | Notes |
|-----|----------|-------|
| A100 | 4 | Requires Dedicated GPU profile |
| T4 | 4 | Requires Dedicated GPU profile |

> **Rule**: If source workload uses `nvidia.com/gpu` or equivalent, map to ACA GPU profile. Ask user to select SKU if ambiguous.

## Container Constraints

- **No privileged containers.** ACA runs containers as non-root by default. If source uses `securityContext.privileged: true`, flag as blocker.
- **No host networking.** ACA does not expose host network namespace. `hostNetwork: true` is unsupported.
- **No host path volumes.** `hostPath` volumes are unsupported. Map to Azure Files, Azure Blob, or EmptyDir.
- **Init containers supported.** ACA supports init containers natively — map them directly.
- **Multi-container pods → Multi-container apps.** ACA supports multiple containers per app (sidecar pattern). Map pod sidecars to ACA sidecar containers.
- **Max 10 containers per app** (including init containers).
- **Max image size: 8 Gi** per container image (compressed, in registry).

## Ingress

- ACA provides a built-in HTTPS ingress with auto TLS. No separate Ingress controller needed.
- **External ingress** = publicly accessible FQDN (auto-generated or custom domain).
- **Internal ingress** = accessible only within the Container Apps environment (replaces ClusterIP).
- Only **one port per app** exposed via ingress. If source exposes multiple ports, split into multiple container apps or use TCP ingress (preview).
- Supported transports: `http`, `http2`, `tcp` (preview for non-HTTP workloads).
- gRPC: Set transport to `http2`.
- WebSocket: Supported natively over `http` transport.

## Networking

- Container Apps in the same **environment** can communicate via `<app-name>` DNS (replaces K8s service DNS).
- For service-to-service calls, replace `<service>.<namespace>.svc.cluster.local` with `<app-name>`.
- ACA environments can be deployed into a custom VNet for private networking.
- NSG rules on the VNet subnet apply. Ensure ACA infrastructure subnet requirements are met.

## Storage

| Source Volume Type | ACA Equivalent | Notes |
|-------------------|----------------|-------|
| emptyDir | EmptyDir | Direct mapping. Ephemeral, per-replica. |
| azureFile / NFS | Azure Files | Requires storage account linked to environment. |
| PVC (ReadWriteOnce) | Azure Files | ACA does not support block storage. Evaluate if Azure Files (SMB/NFS) works. |
| PVC (ReadWriteMany) | Azure Files | Good fit — Azure Files supports shared access. |
| configMap volume | Environment variables | Inline values as env vars or mount as Azure Files. |
| secret volume | ACA secrets | Use ACA secrets (env var or volume mount) or Azure Key Vault references. |
| hostPath | ❌ Unsupported | Refactor to use Azure Files or Blob Storage. |
| CSI drivers | ❌ Unsupported | ACA does not support CSI. Use Azure-native storage. |

## Secrets and Configuration

- **ACA secrets** are set at the container app level and referenced as env vars or volume mounts.
- For sensitive values, prefer **Azure Key Vault references** (`secretRef` pointing to Key Vault).
- For shared configuration across apps, use **Azure App Configuration**.
- Never hardcode secrets in Bicep. Use Key Vault references or `securestring` parameters.

## Identity and Auth

- Use **Managed Identity** (system-assigned or user-assigned) for all Azure service access.
- Replace K8s ServiceAccount + RBAC with Azure RBAC role assignments on the managed identity.
- Replace AWS IAM roles / GCP service accounts with Azure Managed Identity.
- For workload-to-workload auth, use Managed Identity + Entra ID tokens, or Dapr service invocation.
- ACA supports built-in authentication (Easy Auth) for external-facing apps — consider for frontend apps.

## Scaling

- ACA supports auto-scaling based on HTTP traffic, CPU, memory, KEDA scalers, and custom metrics.
- **Min replicas = 0** is supported (scale to zero) — not available on K8s without KEDA.
- **Max replicas = 300** on Consumption profile.
- If source uses HPA, map scaling thresholds to ACA scale rules.
- If source uses KEDA, ACA natively supports KEDA scalers — map directly.

## Jobs (Batch/Cron Workloads)

- K8s CronJobs and Jobs → ACA Jobs.
- ACA Jobs support: Manual trigger, Schedule trigger (cron), Event-driven trigger.
- Jobs run to completion and do not have ingress.
- Max execution time: 2 hours (configurable up to 24 hours on Dedicated profiles).

## Dapr Integration

- If source uses a service mesh (Istio, Linkerd, Consul), evaluate **Dapr** as the ACA-native alternative.
- Dapr provides: service invocation, pub/sub, state management, bindings, observability.
- Dapr is enabled per-app in ACA — no separate infrastructure to manage.
- Not a 1:1 service mesh replacement. Dapr focuses on application-level concerns, not network-level policies.

## Observability

- ACA integrates with **Azure Monitor** and **Application Insights**.
- Container stdout/stderr → Azure Monitor Log Analytics (automatic).
- For structured logging, configure Application Insights SDK in app code.
- Replace Prometheus/Grafana with Azure Monitor managed Prometheus + Azure Managed Grafana, or use Application Insights.

## Deployment

- All migration output uses **Bicep** as the deployment format.
- Use `az deployment group create` to deploy Bicep templates.
- For multi-app deployments, use Bicep modules (one module per container app).
- Always deploy the ACA **environment** first, then container apps into it.
- Use `az containerapp show` to verify deployment status after creation.

## What ACA Does NOT Support

Flag these as **blockers** requiring refactoring:

| Feature | Notes |
|---------|-------|
| DaemonSets | No equivalent. Refactor to per-app sidecars or external agents. |
| StatefulSets with stable network IDs | ACA replicas do not have stable hostnames. Use external state stores. |
| Custom CRDs / Operators | No equivalent. Refactor to application-level logic or Azure services. |
| NetworkPolicy (fine-grained) | ACA environment provides network isolation. Use VNet NSGs for coarse control. |
| Pod Security Policies / Standards | ACA enforces its own container sandbox. No user-configurable pod security. |
| Host-level access (sysctl, /proc) | Fully sandboxed. No host access. |
| Windows containers | ACA supports Linux containers only. |
