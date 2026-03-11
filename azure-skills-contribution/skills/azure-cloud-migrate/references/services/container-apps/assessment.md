# Azure Container Apps — Assessment Framework

Shared assessment phase for all migrations targeting Azure Container Apps.
Run this assessment **before** any code migration to produce `assessment.md` in the output directory.

## Assessment Workflow

```
1. Inventory source workloads
2. Analyze each workload against ACA compatibility matrix
3. Classify: Direct Map | Needs Adaptation | Blocker
4. Generate assessment report with recommendations
```

## Step 1 — Inventory Source Workloads

Extract and catalog every workload from the source platform:

| Field | Description |
|-------|-------------|
| Name | Workload / service name |
| Type | Deployment, Job, CronJob, StatefulSet, Fargate Task, Cloud Run Service, etc. |
| Image | Container image and tag |
| CPU | Requested / limit CPU |
| Memory | Requested / limit memory |
| GPU | GPU type and count (if any) |
| Replicas | Current / desired replica count |
| Ports | Exposed container ports |
| Ingress | External (public) or internal only |
| Storage | Persistent volumes, file mounts |
| Env Vars | Count and source (inline, ConfigMap, Secret, SSM, etc.) |
| Dependencies | Other services this workload calls |
| Scale Config | Autoscaling rules (HPA, target tracking, KEDA, etc.) |

## Step 2 — Compatibility Analysis

For each workload, evaluate against ACA constraints from `global-rules.md`:

### Compute Compatibility

| Check | Pass Criteria | Action if Fail |
|-------|---------------|----------------|
| CPU ≤ 4 cores | Fits Consumption profile | Use Dedicated workload profile |
| Memory ≤ 8 Gi | Fits Consumption profile | Use Dedicated workload profile |
| No privileged mode | `privileged: false` or absent | **Blocker** — refactor to non-privileged |
| No host networking | `hostNetwork: false` or absent | **Blocker** — refactor networking approach |
| Linux container | Image is Linux-based | **Blocker** — ACA is Linux-only |
| Image < 8 Gi | Compressed image under 8 Gi | Optimize image size |
| ≤ 10 containers | Pod/task has ≤ 10 containers | Split into multiple apps |

### Networking Compatibility

| Check | Pass Criteria | Action if Fail |
|-------|---------------|----------------|
| Single ingress port | Workload exposes 1 port | Split into multiple apps or use TCP mode |
| HTTP/HTTPS/gRPC/TCP | Protocol is supported | **Blocker** for UDP workloads |
| No NetworkPolicy deps | Or can use VNet NSGs instead | Document NSG requirements |
| Service discovery | Uses DNS-based discovery | Replace with `<app-name>` internal DNS |

### Storage Compatibility

| Check | Pass Criteria | Action if Fail |
|-------|---------------|----------------|
| No hostPath volumes | No host-mounted paths | Refactor to Azure Files or EmptyDir |
| No CSI drivers | No custom CSI volumes | Replace with Azure-native storage |
| PVC type compatible | ReadWriteMany or no PVC | Evaluate Azure Files for RWO workloads |
| Ephemeral storage ≤ 8 Gi | Fits ACA limits | Use Azure Files for overflow |

### Configuration and Secrets

| Check | Pass Criteria | Action if Fail |
|-------|---------------|----------------|
| Env vars extractable | All env var values resolved | Flag unresolved refs in report |
| Secrets identified | All secrets cataloged | Plan Key Vault migration |
| No file-based config | Or can convert to env vars | Mount via Azure Files or App Configuration |

### Scaling Compatibility

| Check | Pass Criteria | Action if Fail |
|-------|---------------|----------------|
| Scale-to-zero acceptable | Workload tolerates cold start | Set min replicas ≥ 1 |
| Max replicas ≤ 300 | Fits Consumption limits | Use Dedicated profile for higher scale |
| Scaling metric supported | HTTP, CPU, memory, KEDA, or custom | Map to ACA scale rules |

### Workload Type Mapping

| Source Type | ACA Target | Notes |
|-------------|------------|-------|
| Long-running service (Deployment, Fargate Service, Cloud Run Service) | Container App | Primary migration target |
| Scheduled job (CronJob, CloudWatch Event + Lambda, Cloud Scheduler + Cloud Run Job) | ACA Job (Schedule) | Cron-triggered |
| Event-driven job (K8s Job, Fargate Task, Cloud Run Job) | ACA Job (Event) | Triggered by queue, event, etc. |
| Batch job (one-shot) | ACA Job (Manual) | Triggered via API |
| DaemonSet | ❌ No equivalent | Refactor to per-app sidecar or external agent |
| StatefulSet | ⚠️ Partial | No stable network IDs. Use external state store. |

## Step 3 — Classification

Assign each workload a migration classification:

| Classification | Meaning | Action |
|----------------|---------|--------|
| ✅ Direct Map | All checks pass. Can migrate as-is. | Proceed to code migration. |
| ⚠️ Needs Adaptation | Some checks fail but have clear workarounds. | Document adaptations needed, then migrate. |
| ❌ Blocker | Fundamental incompatibility. | Refactor before migration or exclude from scope. |

## Step 4 — Generate Assessment Report

Write `assessment.md` in the output directory with this structure:

```markdown
# Migration Assessment — [Source Platform] to Azure Container Apps

**Source**: [Platform name, cluster/project/account identifier]
**Date**: [Assessment date]
**Workloads analyzed**: [Count]

## Summary

| Classification | Count |
|---------------|-------|
| ✅ Direct Map | X |
| ⚠️ Needs Adaptation | Y |
| ❌ Blocker | Z |

## Workload Details

### [Workload Name]

**Type**: [Source type] → **[ACA target type]**
**Classification**: [✅ / ⚠️ / ❌]

| Property | Source Value | ACA Value | Status |
|----------|-------------|-----------|--------|
| Image | nginx:1.25 | nginx:1.25 | ✅ |
| CPU | 500m | 0.5 | ✅ |
| Memory | 1Gi | 1Gi | ✅ |
| Ingress | LoadBalancer:80 | External:80 | ✅ |
| Volume | hostPath:/data | — | ❌ Refactor needed |

**Adaptations needed**:
- Replace hostPath volume with Azure Files mount
- Move secrets to Azure Key Vault

**Blockers**: None

## Recommendations

1. [Specific recommendation based on findings]
2. [Infrastructure prerequisites — e.g., create ACA environment, ACR, Key Vault]
3. [Suggested migration order based on dependencies]

## Next Steps

- Resolve blockers for [workload names]
- Proceed to code migration for ✅ and ⚠️ workloads
```

## Dependency Mapping

During assessment, build a dependency graph:
- Which workloads call which other workloads?
- What external services are used (databases, caches, queues)?
- What is the suggested migration order? (Migrate dependencies first, or use dual-running during transition.)

> **Rule**: Always migrate shared infrastructure (ACA environment, ACR, Key Vault, storage accounts) before migrating workloads. Suggest this order in the assessment report.
