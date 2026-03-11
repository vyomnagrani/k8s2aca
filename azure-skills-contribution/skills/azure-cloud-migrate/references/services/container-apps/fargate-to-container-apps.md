# AWS Fargate (ECS) to Azure Container Apps Migration

Detailed guide for migrating workloads from AWS Fargate / ECS to Azure Container Apps.

## Overview — Service Mapping

| AWS Service | Azure Equivalent | Notes |
|-------------|-----------------|-------|
| ECS Cluster | ACA Environment | Isolation and networking boundary |
| ECS Service (Fargate) | Container App | Long-running workload |
| ECS Task Definition | Container App template | Container spec, resources, env vars |
| ECS Task (one-shot) | ACA Job (Manual trigger) | Run-to-completion |
| Scheduled Task (EventBridge + Fargate) | ACA Job (Schedule trigger) | Cron-based |
| ALB / NLB | ACA ingress | Built-in, auto TLS |
| Target Group | ACA ingress routing | Automatic with ingress |
| ECR | Azure Container Registry (ACR) | Image registry |
| CloudWatch Logs | Azure Monitor Log Analytics | Container logs |
| CloudWatch Alarms | Azure Monitor Alerts | Metric alerting |
| X-Ray | Application Insights | Distributed tracing |
| App Mesh | Dapr | Service mesh / microservice patterns |
| Service Connect / Cloud Map | ACA internal DNS | Service discovery |
| Secrets Manager | Azure Key Vault | Secret storage |
| Systems Manager Parameter Store | Azure App Configuration | Configuration storage |
| IAM Task Role | Managed Identity | Workload identity |
| IAM Execution Role | (ACA-managed) | ACA handles container runtime permissions |
| EFS | Azure Files | Shared file storage |
| S3 (used as storage) | Azure Blob Storage | Object storage |
| SQS | Azure Service Bus / Storage Queue | Message queue |
| SNS | Azure Event Grid | Event routing |
| EventBridge | Azure Event Grid | Event bus |
| Route 53 | Azure DNS | DNS management |
| ACM (Certificates) | ACA managed certificates | Free auto-TLS |
| VPC | Azure VNet | Network isolation |
| Security Groups | NSG on ACA subnet | Network access control |
| Auto Scaling (ECS Service) | ACA scale rules | HTTP, CPU, KEDA |

## Phase 1 — Source Discovery

### Prerequisites
The agent or user needs AWS CLI access (`aws` command) configured with appropriate permissions to read ECS resources.

### List ECS Clusters
```bash
aws ecs list-clusters --query 'clusterArns[*]' --output table
```

### List Services in a Cluster
```bash
aws ecs list-services --cluster <cluster-name> --query 'serviceArns[*]' --output table
```

### Export Task Definition
```bash
# Get the active task definition for a service
aws ecs describe-services --cluster <cluster> --services <service-name> \
  --query 'services[0].taskDefinition' --output text

# Export the full task definition
aws ecs describe-task-definition --task-definition <task-def-arn> --output json > task-def.json
```

### Export Service Configuration
```bash
aws ecs describe-services --cluster <cluster> --services <service-name> --output json > service.json
```

### Export Load Balancer Configuration
```bash
# Get target group ARN from service
aws ecs describe-services --cluster <cluster> --services <service-name> \
  --query 'services[0].loadBalancers[0].targetGroupArn' --output text

# Get ALB details
aws elbv2 describe-target-groups --target-group-arns <tg-arn> --output json > alb.json
```

### Export Auto Scaling Configuration
```bash
aws application-autoscaling describe-scalable-targets \
  --service-namespace ecs \
  --resource-ids "service/<cluster>/<service>" --output json > scaling.json
```

> **Rule**: Always export the task definition, service config, and any associated load balancers and scaling policies. These contain all the information needed for migration.

## Phase 2 — Resource Conversion Rules

### Task Definition → Container App Template

**Container mapping:**

| ECS Task Definition Field | ACA Bicep Field | Conversion |
|--------------------------|-----------------|------------|
| `containerDefinitions[].image` | `template.containers[].image` | Direct copy (after ACR import if ECR) |
| `containerDefinitions[].name` | `template.containers[].name` | Direct copy |
| `cpu` (task-level, in CPU units) | `template.containers[].resources.cpu` | Divide by 1024: `256` → `0.25`, `512` → `0.5`, `1024` → `1.0` |
| `memory` (task-level, in MiB) | `template.containers[].resources.memory` | Convert: `512` → `0.5Gi`, `1024` → `1Gi`, `2048` → `2Gi` |
| `containerDefinitions[].portMappings[].containerPort` | `configuration.ingress.targetPort` | Primary port only |
| `containerDefinitions[].environment[]` | `template.containers[].env[]` | `{ name, value }` → same format |
| `containerDefinitions[].secrets[]` | `configuration.secrets[]` + `env[].secretRef` | See secrets section |
| `containerDefinitions[].healthCheck` | `template.containers[].probes[]` | See probes section |
| `containerDefinitions[].logConfiguration` | Azure Monitor (automatic) | ACA auto-captures stdout/stderr |
| `containerDefinitions[].mountPoints[]` | `template.containers[].volumeMounts[]` | See volumes section |
| `volumes[]` | `template.volumes[]` | See volumes section |

**CPU conversion (Fargate CPU units → ACA cores):**
```
256   → 0.25
512   → 0.5
1024  → 1.0
2048  → 2.0
4096  → 4.0 (Consumption max)
8192  → 8.0 (Dedicated profile required)
16384 → 16.0 (Dedicated profile required)
```

**Memory conversion (Fargate MiB → ACA Gi):**
```
512   → 0.5Gi
1024  → 1Gi
2048  → 2Gi
4096  → 4Gi
8192  → 8Gi (Consumption max)
16384 → 16Gi (Dedicated profile required)
30720 → 30Gi (Dedicated profile required)
```

> **Rule**: Fargate allows flexible CPU/memory combinations. ACA Consumption enforces a 1:2 CPU-to-memory ratio. Adjust if the Fargate combo doesn't fit — round up CPU or reduce memory to match.

### Multi-Container Task → Multi-Container App

Fargate tasks with multiple containers (sidecar pattern) map to ACA multi-container apps. The `essential: true` container in ECS is the main container in ACA; `essential: false` containers are sidecars.

If one container has `dependsOn` referencing another, use ACA init containers for startup ordering.

### Service Networking → Ingress

| ECS Configuration | ACA Configuration |
|-------------------|-------------------|
| ALB + public listener | `external: true` ingress |
| NLB + public listener | `external: true`, `transport: 'tcp'` |
| Internal ALB | `external: false` ingress |
| No load balancer (internal only) | `external: false` or no ingress |
| Service Connect | ACA internal DNS (`<app-name>`) |
| Cloud Map (service discovery) | ACA internal DNS (`<app-name>`) |

**Service Connect / Cloud Map migration:**
Replace ECS service discovery hostnames with ACA app names in environment variables:
```
# ECS Service Connect
BACKEND_URL=http://backend.my-namespace
# ACA equivalent
BACKEND_URL=http://backend
```

### Environment Variables

**Inline values** — direct mapping:
```json
// ECS task definition
"environment": [
  { "name": "APP_ENV", "value": "production" }
]
```
→
```bicep
env: [
  { name: 'APP_ENV', value: 'production' }
]
```

**Secrets Manager / SSM Parameter Store references:**
```json
// ECS task definition
"secrets": [
  {
    "name": "DB_PASSWORD",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:123456:secret:prod/db-password"
  }
]
```
→ Migrate the secret value to Azure Key Vault, then reference in ACA:
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

> **Rule**: Never copy secret values into Bicep. Always migrate to Key Vault and use references.

### Health Checks → Probes

ECS health check (Docker HEALTHCHECK or container-level):
```json
"healthCheck": {
  "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
  "interval": 30,
  "timeout": 5,
  "retries": 3,
  "startPeriod": 60
}
```
→ ACA does not support exec/command probes. Convert to HTTP probe:
```bicep
probes: [
  {
    type: 'liveness'
    httpGet: {
      path: '/health'
      port: 8080
    }
    periodSeconds: 30
    timeoutSeconds: 5
    failureThreshold: 3
    initialDelaySeconds: 60
  }
]
```

> **Rule**: If the ECS health check uses `CMD-SHELL` with curl to an HTTP endpoint, extract the path and port for an ACA HTTP probe. If it uses a non-HTTP command, the application needs a health endpoint added.

### Auto Scaling → Scale Rules

**ECS Service Auto Scaling (target tracking):**
```json
{
  "PolicyType": "TargetTrackingScaling",
  "TargetTrackingScalingPolicyConfiguration": {
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    }
  }
}
```
→
```bicep
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
```

**ALBRequestCountPerTarget:**
```json
{
  "PredefinedMetricType": "ALBRequestCountPerTarget",
  "TargetValue": 1000.0
}
```
→ ACA HTTP scaling (concurrent requests per replica):
```bicep
scale: {
  rules: [
    {
      name: 'http-scaling'
      http: {
        metadata: {
          concurrentRequests: '100'
        }
      }
    }
  ]
}
```

> Note: ECS `ALBRequestCountPerTarget` counts total requests; ACA HTTP scaling uses concurrent requests. These are different metrics — adjust the threshold accordingly (typically much lower for concurrent).

### EFS → Azure Files

```json
// ECS task definition
"volumes": [
  {
    "name": "app-data",
    "efsVolumeConfiguration": {
      "fileSystemId": "fs-12345",
      "rootDirectory": "/app/data"
    }
  }
]
```
→ Create an Azure Storage account with a file share, link to ACA environment, and mount. See `code-migration.md` for the Bicep pattern.

### IAM Task Role → Managed Identity

| AWS | Azure |
|-----|-------|
| Task IAM Role + policy | Managed Identity + RBAC role assignment |
| `arn:aws:iam::role/my-task-role` | System-assigned or user-assigned managed identity |
| Policy: `s3:GetObject` on bucket | RBAC: `Storage Blob Data Reader` on storage account |
| Policy: `secretsmanager:GetSecretValue` | RBAC: `Key Vault Secrets User` on Key Vault |
| Policy: `sqs:SendMessage` | RBAC: `Service Bus Data Sender` on Service Bus |

> **Rule**: For each IAM policy attached to the task role, identify the equivalent Azure RBAC role and assign it to the container app's managed identity. Document the mapping in the migration report.

### Scheduled Tasks → ACA Jobs

ECS Scheduled Tasks (EventBridge rule + ECS RunTask):
```json
{
  "ScheduleExpression": "cron(0 2 * * ? *)",
  "Targets": [{
    "EcsParameters": {
      "TaskDefinitionArn": "arn:aws:ecs:...:task-definition/nightly-job:1",
      "LaunchType": "FARGATE"
    }
  }]
}
```
→ Convert EventBridge cron to standard cron and use ACA Job:
```
AWS:      cron(0 2 * * ? *)
Standard: 0 2 * * *
```
> **Rule**: AWS cron has 6 fields (with year); standard cron has 5 fields. Drop the year field and replace `?` with `*`.

## Phase 3 — Image Migration (ECR → ACR)

```bash
# Option 1: ACR import (recommended — no local Docker needed)
az acr import --name <acr-name> \
  --source <aws-account>.dkr.ecr.<region>.amazonaws.com/<image>:<tag> \
  --image <image>:<tag> \
  --username AWS \
  --password $(aws ecr get-login-password --region <region>)

# Option 2: Docker pull/push
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <aws-account>.dkr.ecr.<region>.amazonaws.com
docker pull <aws-account>.dkr.ecr.<region>.amazonaws.com/<image>:<tag>
docker tag <aws-account>.dkr.ecr.<region>.amazonaws.com/<image>:<tag> <acr-name>.azurecr.io/<image>:<tag>
az acr login --name <acr-name>
docker push <acr-name>.azurecr.io/<image>:<tag>
```

> **Rule**: Update all image references in generated Bicep to use the ACR image path after import.

## Phase 4 — Deployment

Follow the standard deployment flow from `code-migration.md`:

1. Generate all Bicep files in the output directory
2. Generate `migrate-images.sh` for ECR → ACR import
3. Ask user: "Migration files ready. Deploy to Azure now or review first?"
4. If deploying: create resource group, run image migration, deploy Bicep
5. Verify all apps running and ingress accessible

## Reference Links

- [Azure Container Apps documentation](https://learn.microsoft.com/azure/container-apps/)
- [Migrate from AWS Fargate to Azure](https://learn.microsoft.com/azure/architecture/aws-professional/compute#containers)
- [AWS to Azure services comparison](https://learn.microsoft.com/azure/architecture/aws-professional/services)
- [Container Apps ARM/Bicep reference](https://learn.microsoft.com/azure/templates/microsoft.app/containerapps)
