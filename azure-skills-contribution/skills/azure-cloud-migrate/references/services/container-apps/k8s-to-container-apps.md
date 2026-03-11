# Kubernetes / AKS to Azure Container Apps Migration

Detailed guide for migrating workloads from Kubernetes (self-hosted or AKS) to Azure Container Apps.

## Overview — Resource Mapping

| Kubernetes Resource | ACA Equivalent | Notes |
|-------------------|----------------|-------|
| Deployment | Container App | Primary workload type |
| ReplicaSet | Container App (template) | Managed by ACA revision system |
| Pod | Container App (single replica) | Set minReplicas=1, maxReplicas=1 |
| Service (ClusterIP) | Internal ingress | `external: false`, access via `<app-name>` DNS |
| Service (LoadBalancer) | External ingress | `external: true`, auto TLS FQDN |
| Service (NodePort) | External ingress | Map to external ingress |
| Ingress / IngressClass | ACA ingress + custom domains | Built-in ingress, no controller needed |
| ConfigMap | Environment variables / Azure App Configuration | Inline env vars for simple cases |
| Secret | ACA secrets / Key Vault references | Prefer Key Vault for production |
| PersistentVolumeClaim | Azure Files volume mount | ACA environment-level storage |
| HorizontalPodAutoscaler | ACA scale rules | HTTP, CPU, memory, KEDA, or custom |
| CronJob | ACA Job (Schedule trigger) | Cron expression maps directly |
| Job | ACA Job (Manual trigger) | One-shot execution |
| DaemonSet | ❌ No equivalent | Refactor to sidecar or external agent |
| StatefulSet | ⚠️ Container App + external state | No stable pod identity. Use external DB/cache. |
| NetworkPolicy | ⚠️ VNet NSGs | Coarse-grained only via subnet NSGs |
| ServiceAccount + RBAC | Managed Identity + Azure RBAC | Assign roles to app's managed identity |
| Namespace | ACA Environment | One environment = one isolation boundary |
| Helm Chart | Bicep module | Convert chart values to Bicep parameters |

## Phase 1 — Source Discovery

### AKS Clusters
```bash
# List AKS clusters
az aks list --query "[].{name:name, location:location, resourceGroup:resourceGroup}" -o table

# Get credentials for a cluster
az aks get-credentials --resource-group <rg> --name <cluster> --overwrite-existing
```

### Self-Hosted Kubernetes
```bash
# List available contexts
kubectl config get-contexts

# Switch to target context
kubectl config use-context <context-name>
```

### Export Source Manifests

```bash
# List namespaces
kubectl get namespaces

# Export all resources in a namespace
kubectl get all -n <namespace> -o yaml > namespace-export.yaml

# Export specific resource types
kubectl get deployments,services,ingress,configmaps,secrets,hpa -n <namespace> -o yaml > workloads.yaml

# Export a single deployment with its service
kubectl get deployment <name> -n <namespace> -o yaml > deployment.yaml
kubectl get service <name> -n <namespace> -o yaml > service.yaml
```

> **Rule**: Always export ConfigMaps and Secrets referenced by workloads. Without them, env var migration will have gaps.

### Helm-Managed Workloads
```bash
# List Helm releases
helm list -n <namespace>

# Get rendered manifests for a release
helm get manifest <release-name> -n <namespace> > helm-manifest.yaml

# Get values used for the release
helm get values <release-name> -n <namespace> > helm-values.yaml
```

## Phase 2 — Resource Conversion Rules

### Deployment → Container App

**Container spec mapping:**

| K8s Field | ACA Bicep Field | Conversion |
|-----------|-----------------|------------|
| `spec.template.spec.containers[].image` | `template.containers[].image` | Direct copy |
| `spec.template.spec.containers[].name` | `template.containers[].name` | Direct copy |
| `resources.requests.cpu` | `template.containers[].resources.cpu` | Convert millicores: `500m` → `0.5` |
| `resources.requests.memory` | `template.containers[].resources.memory` | Keep Gi format. Convert Mi: `512Mi` → `0.5Gi` |
| `resources.limits.cpu` | Use for resource allocation | ACA uses requests (not limits) for allocation |
| `ports[].containerPort` | `configuration.ingress.targetPort` | Only the primary port. One port per app. |
| `env[]` | `template.containers[].env[]` | See env var rules below |
| `volumeMounts[]` | `template.containers[].volumeMounts[]` | See volume rules below |
| `livenessProbe` | `template.containers[].probes[]` | Map type, path, port. Set `type: 'liveness'` |
| `readinessProbe` | `template.containers[].probes[]` | Map type, path, port. Set `type: 'readiness'` |
| `startupProbe` | `template.containers[].probes[]` | Map type, path, port. Set `type: 'startup'` |

**CPU conversion:**
```
K8s millicores → ACA cores
100m  → 0.25 (ACA minimum)
250m  → 0.25
500m  → 0.5
1000m → 1.0
2000m → 2.0
4000m → 4.0 (Consumption max)
```
> If CPU > 4 cores, use Dedicated workload profile and set `workloadProfileName`.

**Memory conversion:**
```
K8s Mi → ACA Gi
128Mi  → 0.5Gi (ACA min for 0.25 CPU)
256Mi  → 0.5Gi
512Mi  → 0.5Gi
1024Mi → 1Gi
2048Mi → 2Gi
8192Mi → 8Gi (Consumption max)
```

**CPU-to-memory ratios (Consumption profile):**

| CPU (cores) | Allowed Memory |
|-------------|---------------|
| 0.25 | 0.5Gi |
| 0.5 | 1Gi |
| 0.75 | 1.5Gi |
| 1.0 | 2Gi |
| 1.25 | 2.5Gi |
| 1.5 | 3Gi |
| 1.75 | 3.5Gi |
| 2.0 | 4Gi |
| 2.25 | 4.5Gi |
| 2.5 | 5Gi |
| 3.0 | 6Gi |
| 3.5 | 7Gi |
| 4.0 | 8Gi |

> **Rule**: ACA enforces a 1:2 CPU-to-memory ratio on Consumption. Round up CPU to meet memory needs, or round down memory to match CPU.

### Multi-Container Pods → Multi-Container Apps

K8s pods with sidecars map to ACA multi-container apps:

```bicep
template: {
  // Init containers run first, in order
  initContainers: [
    {
      name: 'init-db'
      image: 'busybox'
      command: ['sh', '-c', 'until nc -z db 5432; do sleep 1; done']
    }
  ]
  // All containers run concurrently (main + sidecars)
  containers: [
    {
      name: 'main-app'
      image: 'myapp:latest'
      resources: { cpu: json('0.5'), memory: '1Gi' }
    }
    {
      name: 'log-sidecar'
      image: 'fluent-bit:latest'
      resources: { cpu: json('0.25'), memory: '0.5Gi' }
    }
  ]
}
```

> **Rule**: Total CPU and memory across all containers in one app must fit within ACA limits. Sum container resources to check.

### Service → Ingress

| K8s Service Type | ACA Ingress | Bicep |
|-----------------|-------------|-------|
| `LoadBalancer` | External | `external: true` |
| `NodePort` | External | `external: true` |
| `ClusterIP` | Internal | `external: false` |
| `ExternalName` | N/A | Use env var with target URL |
| `Headless` (clusterIP: None) | ⚠️ No direct equivalent | Each pod is a separate ACA app, or use Dapr |

**Port mapping:**
- K8s Service `port` → not needed in ACA (ingress auto-routes).
- K8s Service `targetPort` → ACA `configuration.ingress.targetPort`.
- If the Service has multiple ports, migrate the primary port to ACA ingress. Document additional ports in the migration report; they may need separate apps or TCP ingress.

### Ingress → Custom Domains

```bicep
configuration: {
  ingress: {
    external: true
    targetPort: 80
    customDomains: [
      {
        name: 'app.example.com'
        certificateId: managedCert.id
        bindingType: 'SniEnabled'
      }
    ]
  }
}
```

> **Rule**: For each K8s Ingress host rule, create a custom domain entry. ACA provides free managed certificates for custom domains.

### ConfigMap → Environment Variables

**Direct values:**
```yaml
# K8s ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  DATABASE_HOST: "db.example.com"
  LOG_LEVEL: "info"
```
→
```bicep
env: [
  { name: 'DATABASE_HOST', value: 'db.example.com' }
  { name: 'LOG_LEVEL', value: 'info' }
]
```

**ConfigMap key references:**
```yaml
# K8s: env from configMapKeyRef
env:
  - name: DB_HOST
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: DATABASE_HOST
```
→ Resolve the value from the ConfigMap and inline it as an ACA env var.

> **Rule**: If a ConfigMap has many keys (>10), consider using Azure App Configuration instead of inlining all values. Document this recommendation in the migration report.

### Secret → ACA Secrets / Key Vault

**K8s Secret → ACA inline secret:**
```yaml
# K8s Secret (base64 encoded)
apiVersion: v1
kind: Secret
metadata:
  name: db-creds
data:
  password: cGFzc3dvcmQxMjM=  # base64 of "password123"
```
→
```bicep
configuration: {
  secrets: [
    { name: 'db-password', value: dbPasswordParam }  // from secure Bicep parameter
  ]
}
// Container env:
env: [
  { name: 'DB_PASSWORD', secretRef: 'db-password' }
]
```

**K8s Secret → Key Vault reference (preferred for production):**
```bicep
configuration: {
  secrets: [
    {
      name: 'db-password'
      keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/db-password'
      identity: 'system'
    }
  ]
}
```

> **Rule**: Always prefer Key Vault references over inline secret values. Generate a Key Vault Bicep module if any secrets are detected.

### HPA → Scale Rules

```yaml
# K8s HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```
→
```bicep
template: {
  scale: {
    minReplicas: 2
    maxReplicas: 10
    rules: [
      {
        name: 'cpu-scaling'
        custom: {
          type: 'cpu'
          metadata: {
            type: 'Utilization'
            value: '70'
          }
        }
      }
    ]
  }
}
```

**KEDA scalers in K8s → ACA custom scale rules:**
ACA natively supports KEDA. If the source uses KEDA ScaledObjects, map them directly to ACA custom scale rules using the same KEDA metadata.

### CronJob → ACA Job

```yaml
# K8s CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-cleanup
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: cleanup
            image: cleanup:latest
          restartPolicy: Never
```
→ Use the ACA Job Bicep template from `code-migration.md` with `triggerType: 'Schedule'` and `cronExpression: '0 2 * * *'`.

### Volumes → ACA Storage

```bicep
// Environment-level storage
resource storage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: environment
  name: 'shared-files'
  properties: {
    azureFile: {
      accountName: storageAccountName
      accountKey: storageAccountKey
      shareName: 'appdata'
      accessMode: 'ReadWrite'
    }
  }
}

// App-level volume mount
template: {
  volumes: [
    { name: 'shared-files', storageName: 'shared-files', storageType: 'AzureFile' }
  ]
  containers: [
    {
      name: 'app'
      image: 'myapp:latest'
      volumeMounts: [
        { volumeName: 'shared-files', mountPath: '/data' }
      ]
    }
  ]
}
```

| K8s Volume Type | ACA Migration |
|----------------|---------------|
| `emptyDir` | `EmptyDir` volume — direct map |
| `azureFile` | Azure Files — direct map |
| `azureDisk` | ⚠️ Azure Files (no block storage in ACA) |
| `persistentVolumeClaim` | Azure Files — create storage account + file share |
| `configMap` | Env vars or Azure Files mount |
| `secret` | ACA secrets (env var or volume mount) |
| `hostPath` | ❌ Refactor to Azure Files or EmptyDir |
| `nfs` | Azure Files (NFS protocol) |
| `csi` | ❌ No CSI support. Use Azure-native storage. |

### Probes → ACA Probes

```bicep
probes: [
  {
    type: 'liveness'
    httpGet: {
      path: '/healthz'
      port: 8080
    }
    initialDelaySeconds: 10
    periodSeconds: 30
  }
  {
    type: 'readiness'
    httpGet: {
      path: '/ready'
      port: 8080
    }
    initialDelaySeconds: 5
    periodSeconds: 10
  }
  {
    type: 'startup'
    tcpSocket: {
      port: 8080
    }
    initialDelaySeconds: 0
    periodSeconds: 5
    failureThreshold: 30
  }
]
```

Supported probe types: `httpGet`, `tcpSocket`. Exec probes are **not supported** in ACA — convert to HTTP health endpoints or TCP checks.

## Phase 3 — Namespace-Level Migration

When migrating an entire K8s namespace:

1. **One ACA environment per namespace** (or per logical application group).
2. **One container app per Deployment** in the namespace.
3. **Update service-to-service URLs**: Replace `<svc>.<namespace>.svc.cluster.local` with `<app-name>`.
4. **Shared ConfigMaps/Secrets**: If multiple Deployments reference the same ConfigMap, resolve values and set on each app (or use Azure App Configuration for shared config).
5. **Preserve dependency order**: Deploy apps that are dependencies first. Use Bicep `dependsOn` if needed.

## Phase 4 — Deployment

After generating all Bicep files:

1. Ask user: "Migration files are ready. Deploy to Azure now or review first?"
2. If deploying:
   - Create resource group (use source cluster location as default)
   - Run `az deployment group create` with `main.bicep`
   - Display ingress FQDNs for all external apps
3. Hand off to `azure-prepare` / `azure-validate` / `azure-deploy` skills for production hardening.

## Reference Links

- [Azure Container Apps documentation](https://learn.microsoft.com/azure/container-apps/)
- [Migrate from Kubernetes to Azure Container Apps](https://learn.microsoft.com/azure/container-apps/migrate-from-kubernetes)
- [Container Apps ARM/Bicep reference](https://learn.microsoft.com/azure/templates/microsoft.app/containerapps)
- [ACA environment Bicep reference](https://learn.microsoft.com/azure/templates/microsoft.app/managedenvironments)
- [ACA Jobs Bicep reference](https://learn.microsoft.com/azure/templates/microsoft.app/jobs)
- [Container Apps scaling rules](https://learn.microsoft.com/azure/container-apps/scale-app)
- [Container Apps storage mounts](https://learn.microsoft.com/azure/container-apps/storage-mounts)
