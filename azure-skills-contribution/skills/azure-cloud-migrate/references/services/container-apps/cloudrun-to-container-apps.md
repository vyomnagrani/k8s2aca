# GCP Cloud Run to Azure Container Apps Migration

Detailed guide for migrating workloads from Google Cloud Run to Azure Container Apps.

## Overview — Service Mapping

| GCP Service | Azure Equivalent | Notes |
|-------------|-----------------|-------|
| Cloud Run Service | Container App | Long-running HTTP workload |
| Cloud Run Job | ACA Job | Batch/scheduled/event-driven |
| Artifact Registry / GCR | Azure Container Registry (ACR) | Image registry |
| Cloud Logging | Azure Monitor Log Analytics | Container logs |
| Cloud Monitoring | Azure Monitor | Metrics and alerting |
| Cloud Trace | Application Insights | Distributed tracing |
| Secret Manager | Azure Key Vault | Secret storage |
| Cloud SQL | Azure SQL / Azure Database for PostgreSQL / MySQL | Managed database |
| Cloud Storage (GCS) | Azure Blob Storage | Object storage |
| Pub/Sub | Azure Service Bus / Event Grid | Messaging |
| Cloud Scheduler | ACA Job (Schedule trigger) | Cron-based triggers |
| Cloud Tasks | Azure Service Bus + ACA scale rule | Task queue processing |
| Eventarc | Azure Event Grid | Event routing |
| IAM Service Account | Managed Identity | Workload identity |
| Cloud CDN | Azure Front Door / CDN | Content delivery |
| Cloud DNS | Azure DNS | DNS management |
| VPC Connector (Serverless VPC Access) | ACA VNet integration | Private networking |
| Cloud Armor | Azure WAF (via Front Door) | Web app firewall |
| Identity Platform / Firebase Auth | Entra ID / ACA Easy Auth | Authentication |

## Why Cloud Run → ACA Is the Easiest Migration

Cloud Run and Azure Container Apps share almost identical architectural models:
- Both are serverless container platforms
- Both scale to zero by default
- Both provide automatic HTTPS with managed TLS
- Both support revision-based traffic splitting
- Both use per-container resource allocation (not VM-based)
- Both support custom domains with managed certificates

The primary work is service mapping (GCP services → Azure services) and infrastructure setup (Bicep). Application code rarely needs changes.

## Phase 1 — Source Discovery

### Prerequisites
The agent or user needs `gcloud` CLI access configured with appropriate permissions.

### List Cloud Run Services
```bash
# List all services in a project
gcloud run services list --project <project-id> --format="table(name, region, status.url)"

# List services in a specific region
gcloud run services list --region <region> --project <project-id>
```

### Export Service Configuration
```bash
# Export full service YAML
gcloud run services describe <service-name> \
  --region <region> \
  --project <project-id> \
  --format yaml > service.yaml

# Export as JSON for structured parsing
gcloud run services describe <service-name> \
  --region <region> \
  --project <project-id> \
  --format json > service.json
```

### List Cloud Run Jobs
```bash
gcloud run jobs list --project <project-id> --format="table(name, region)"

# Export job config
gcloud run jobs describe <job-name> \
  --region <region> \
  --project <project-id> \
  --format yaml > job.yaml
```

### Export Environment Variables and Secrets
```bash
# Env vars are included in the service YAML export above
# For Secret Manager references, list secrets:
gcloud secrets list --project <project-id>

# Get secret versions
gcloud secrets versions access latest --secret <secret-name> --project <project-id>
```

> **Rule**: Always export the full service YAML. It contains the complete container spec, env vars, scaling config, traffic splits, and networking config in one file.

## Phase 2 — Resource Conversion Rules

### Cloud Run Service → Container App

**Field mapping:**

| Cloud Run Field | ACA Bicep Field | Conversion |
|----------------|-----------------|------------|
| `spec.template.spec.containers[].image` | `template.containers[].image` | Direct copy (after GCR/AR → ACR import) |
| `spec.template.spec.containers[].name` | `template.containers[].name` | Direct copy |
| `spec.template.spec.containers[].resources.limits.cpu` | `template.containers[].resources.cpu` | Direct: `1` → `1.0`, `2` → `2.0` |
| `spec.template.spec.containers[].resources.limits.memory` | `template.containers[].resources.memory` | Direct: `512Mi` → `0.5Gi`, `1Gi` → `1Gi` |
| `spec.template.spec.containerConcurrency` | `configuration.ingress.maxConcurrentRequests` (or scale rule) | See scaling section |
| `spec.template.spec.containers[].ports[].containerPort` | `configuration.ingress.targetPort` | Direct map |
| `spec.template.spec.containers[].env[]` | `template.containers[].env[]` | See env var section |
| `spec.template.spec.containers[].startupProbe` | `template.containers[].probes[]` | Direct map, set `type: 'startup'` |
| `spec.template.spec.containers[].livenessProbe` | `template.containers[].probes[]` | Direct map, set `type: 'liveness'` |
| `spec.template.metadata.annotations['autoscaling.knative.dev/minScale']` | `template.scale.minReplicas` | Direct: `"0"` → `0` |
| `spec.template.metadata.annotations['autoscaling.knative.dev/maxScale']` | `template.scale.maxReplicas` | Direct: `"100"` → `100` |
| `spec.traffic[]` | `configuration.ingress.traffic[]` | Traffic split map |

**CPU conversion (Cloud Run → ACA):**
Cloud Run uses whole or fractional CPUs (same as ACA):
```
Cloud Run    → ACA
1 CPU        → 1.0
2 CPU        → 2.0
4 CPU        → 4.0 (Consumption max)
8 CPU        → 8.0 (Dedicated profile required)
```

**Memory conversion:**
Cloud Run supports up to 32 Gi per instance. Map directly, use Dedicated profile if >8 Gi:
```
128Mi → 0.5Gi (ACA min for 0.25 CPU)
256Mi → 0.5Gi
512Mi → 0.5Gi
1Gi   → 1Gi
2Gi   → 2Gi
4Gi   → 4Gi
8Gi   → 8Gi (Consumption max)
16Gi  → 16Gi (Dedicated required)
32Gi  → 32Gi (Dedicated required)
```

### Networking and Ingress

| Cloud Run Config | ACA Equivalent |
|-----------------|----------------|
| `ingress: all` (public) | `external: true` |
| `ingress: internal` | `external: false` with VNet |
| `ingress: internal-and-cloud-load-balancing` | `external: true` with VNet + NSG restrictions |
| Custom domain | ACA custom domain with managed certificate |
| Cloud Run URL (`*.run.app`) | ACA FQDN (`*.azurecontainerapps.io`) |

**Custom domains:**
```bash
# Cloud Run
gcloud run domain-mappings list --region <region>
```
→
```bicep
configuration: {
  ingress: {
    external: true
    targetPort: 8080
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

### Traffic Splitting / Revisions

Cloud Run's revision-based traffic splitting maps to ACA's revision traffic:

```yaml
# Cloud Run
spec:
  traffic:
  - revisionName: my-service-v2
    percent: 80
  - revisionName: my-service-v1
    percent: 20
```
→
```bicep
configuration: {
  activeRevisionsMode: 'Multiple'
  ingress: {
    traffic: [
      { revisionName: 'v2', weight: 80 }
      { revisionName: 'v1', weight: 20 }
    ]
  }
}
```

> This is nearly 1:1. ACA and Cloud Run both use a revision-based deployment model with percentage-based traffic splitting.

### Environment Variables

**Inline values** — direct mapping:
```yaml
# Cloud Run
env:
- name: APP_ENV
  value: production
```
→
```bicep
env: [
  { name: 'APP_ENV', value: 'production' }
]
```

**Secret Manager references:**
```yaml
# Cloud Run
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: db-password    # GCP Secret Manager secret
      key: latest
```
→ Migrate secret to Azure Key Vault:
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
env: [
  { name: 'DB_PASSWORD', secretRef: 'db-password' }
]
```

> **Rule**: For each GCP Secret Manager reference, create a corresponding Azure Key Vault secret and update the reference.

### Scaling Configuration

**Container concurrency:**
Cloud Run `containerConcurrency` controls max concurrent requests per instance. ACA equivalent is HTTP scale rule:

```yaml
# Cloud Run: max 80 concurrent requests per instance
spec:
  template:
    spec:
      containerConcurrency: 80
```
→
```bicep
scale: {
  minReplicas: 0
  maxReplicas: 100
  rules: [
    {
      name: 'http-scaling'
      http: {
        metadata: {
          concurrentRequests: '80'
        }
      }
    }
  ]
}
```

**Min/max instances:**
```yaml
# Cloud Run annotations
metadata:
  annotations:
    autoscaling.knative.dev/minScale: "1"
    autoscaling.knative.dev/maxScale: "50"
```
→
```bicep
scale: {
  minReplicas: 1
  maxReplicas: 50
}
```

### Cloud Run Job → ACA Job

```yaml
# Cloud Run Job
apiVersion: run.googleapis.com/v1
kind: Job
metadata:
  name: data-processor
spec:
  template:
    spec:
      template:
        spec:
          containers:
          - image: gcr.io/my-project/processor:latest
            resources:
              limits:
                cpu: "2"
                memory: 4Gi
```
→ Use ACA Job Bicep template from `code-migration.md` with appropriate trigger type.

**Cloud Scheduler + Cloud Run Job → ACA Job (Schedule):**
```bash
# Cloud Scheduler cron
gcloud scheduler jobs list --project <project-id>
```
Extract the cron expression and use it directly in the ACA Job `cronExpression`.

### Service Account → Managed Identity

| GCP | Azure |
|-----|-------|
| Cloud Run service account | ACA system-assigned managed identity |
| IAM binding: `roles/storage.objectViewer` | RBAC: `Storage Blob Data Reader` |
| IAM binding: `roles/secretmanager.secretAccessor` | RBAC: `Key Vault Secrets User` |
| IAM binding: `roles/cloudsql.client` | Connection string / firewall rule (Azure SQL) |
| IAM binding: `roles/pubsub.publisher` | RBAC: `Service Bus Data Sender` (or Event Grid) |

> **Rule**: Map each GCP IAM role to the closest Azure RBAC role and assign to the managed identity.

### VPC Connector → VNet Integration

Cloud Run with Serverless VPC Access:
```yaml
metadata:
  annotations:
    run.googleapis.com/vpc-access-connector: projects/my-project/locations/us-central1/connectors/my-connector
    run.googleapis.com/vpc-access-egress: private-ranges-only
```
→ Deploy ACA environment into a VNet subnet:
```bicep
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: subnetId
      internal: false  // or true for fully internal
    }
  }
}
```

## Phase 3 — Image Migration (GCR/Artifact Registry → ACR)

```bash
# Option 1: ACR import (recommended)
# For GCR:
az acr import --name <acr-name> \
  --source gcr.io/<project>/<image>:<tag> \
  --image <image>:<tag>

# For Artifact Registry:
az acr import --name <acr-name> \
  --source <region>-docker.pkg.dev/<project>/<repo>/<image>:<tag> \
  --image <image>:<tag>

# Note: For private images, you may need to configure credentials:
# gcloud auth configure-docker
# Then pull/tag/push via local Docker
```

> **Rule**: GCR public images can be imported directly. For private Artifact Registry images, use `gcloud auth print-access-token` as password with `az acr import --username oauth2accesstoken`.

## Phase 4 — GCP-Specific Service Migration Notes

### Cloud SQL → Azure Database

Cloud Run often connects to Cloud SQL via Unix socket or Cloud SQL Auth Proxy. ACA doesn't have an equivalent proxy — use direct connection strings:

```
# Cloud Run (Cloud SQL socket)
/cloudsql/<project>:<region>:<instance>

# ACA (direct connection)
Server=<server>.database.windows.net;Database=<db>;Authentication=Active Directory Managed Identity
```

> **Rule**: Replace Cloud SQL socket connections with standard TCP connection strings for Azure databases. Use managed identity authentication.

### Pub/Sub → Service Bus / Event Grid

Cloud Run Pub/Sub push subscription → ACA with Service Bus KEDA scaler:
```bicep
scale: {
  rules: [
    {
      name: 'servicebus-scaling'
      custom: {
        type: 'azure-servicebus'
        metadata: {
          queueName: 'my-queue'
          namespace: serviceBusNamespace
          messageCount: '5'
        }
        auth: [
          { secretRef: 'sb-connection', triggerParameter: 'connection' }
        ]
      }
    }
  ]
}
```

### Cloud Storage → Azure Blob Storage
Replace GCS client libraries with Azure Blob Storage SDK. Update env vars:
```
# Cloud Run
BUCKET_NAME=my-gcs-bucket

# ACA
STORAGE_ACCOUNT_URL=https://<account>.blob.core.windows.net
CONTAINER_NAME=my-container
```

## Phase 5 — Deployment

Follow the standard deployment flow from `code-migration.md`:

1. Generate all Bicep files
2. Generate `migrate-images.sh` for GCR/AR → ACR import
3. Ask user: "Migration files ready. Deploy to Azure now or review first?"
4. Deploy infrastructure and apps
5. Update DNS records for custom domains
6. Verify all apps running

## Reference Links

- [Azure Container Apps documentation](https://learn.microsoft.com/azure/container-apps/)
- [GCP to Azure services comparison](https://learn.microsoft.com/azure/architecture/gcp-professional/services)
- [Migrate from Google Cloud to Azure](https://learn.microsoft.com/azure/architecture/gcp-professional/)
- [Container Apps ARM/Bicep reference](https://learn.microsoft.com/azure/templates/microsoft.app/containerapps)
