# Azure Container Apps — Code Migration Patterns

Shared output format and Bicep patterns for all migrations targeting Azure Container Apps.
Applies after assessment is complete. Produces deployment-ready Bicep and a migration report.

## Output Directory Structure

All output goes to `<source-folder>-azure/` at workspace root:

```
<source-folder>-azure/
├── assessment.md                    # From assessment phase
├── code-migration.md                # Migration summary and decisions
├── migration-status.md              # Progress tracker
├── infra/
│   ├── main.bicep                   # Top-level orchestrator
│   ├── main.parameters.json         # Deployment parameters
│   ├── environment.bicep            # ACA environment module
│   └── apps/
│       ├── <app-name-1>.bicep       # One module per container app
│       ├── <app-name-2>.bicep       # One module per container app
│       └── ...
└── scripts/
    ├── deploy.sh                    # Deployment script
    └── migrate-images.sh            # Image migration script (if ACR push needed)
```

> **Rule**: Never modify the source directory. All generated files go in the output directory.

## Bicep Template — ACA Environment

```bicep
param environmentName string
param location string = resourceGroup().location
param logAnalyticsName string = '${environmentName}-logs'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

output environmentId string = environment.id
output defaultDomain string = environment.properties.defaultDomain
```

## Bicep Template — Container App

Use this as the base template for each migrated workload. Customize per workload.

```bicep
param appName string
param location string = resourceGroup().location
param environmentId string
param containerImage string
param containerPort int = 80
param isExternalIngress bool = true
param cpu string = '0.5'
param memory string = '1Gi'
param minReplicas int = 0
param maxReplicas int = 10
param envVars array = []
param secrets array = []

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: isExternalIngress
        targetPort: containerPort
        transport: 'auto'
      }
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: envVars
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output appId string = containerApp.id
```

## Bicep Template — ACA Job

For CronJob, scheduled tasks, or batch workloads:

```bicep
param jobName string
param location string = resourceGroup().location
param environmentId string
param containerImage string
param cpu string = '0.5'
param memory string = '1Gi'
param cronExpression string = ''
param triggerType string = 'Schedule' // 'Schedule' | 'Manual' | 'Event'
param envVars array = []

resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: jobName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      replicaTimeout: 1800
      replicaRetryLimit: 1
      triggerType: triggerType
      scheduleTriggerConfig: triggerType == 'Schedule' ? {
        cronExpression: cronExpression
        parallelism: 1
        replicaCompletionCount: 1
      } : null
      manualTriggerConfig: triggerType == 'Manual' ? {
        parallelism: 1
        replicaCompletionCount: 1
      } : null
    }
    template: {
      containers: [
        {
          name: jobName
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: envVars
        }
      ]
    }
  }
}
```

## Bicep Template — main.bicep Orchestrator

```bicep
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param environmentName string

// Deploy ACA environment
module env 'environment.bicep' = {
  name: 'aca-environment'
  params: {
    environmentName: environmentName
    location: location
  }
}

// Deploy each app — add one module block per migrated workload
// module app1 'apps/<app-name>.bicep' = {
//   name: '<app-name>'
//   params: {
//     appName: '<app-name>'
//     location: location
//     environmentId: env.outputs.environmentId
//     containerImage: '<image>'
//   }
// }
```

## Environment Variable Migration

### Inline values
Source env var with a literal value → ACA `env` array entry:
```bicep
env: [
  { name: 'APP_ENV', value: 'production' }
]
```

### Secret references
Sensitive values → ACA secret + `secretRef`:
```bicep
// In configuration.secrets:
secrets: [
  { name: 'db-password', value: dbPassword } // from Bicep parameter
]
// In container env:
env: [
  { name: 'DB_PASSWORD', secretRef: 'db-password' }
]
```

### Key Vault references
For production, prefer Key Vault references over inline secrets:
```bicep
secrets: [
  {
    name: 'db-password'
    keyVaultUrl: 'https://<vault-name>.vault.azure.net/secrets/<secret-name>'
    identity: 'system'
  }
]
```

## Service-to-Service Communication

Replace all source platform service discovery with ACA internal DNS:

| Source Pattern | ACA Pattern |
|---------------|-------------|
| `<svc>.<ns>.svc.cluster.local` (K8s) | `<app-name>` (same environment) |
| `<svc>.internal` (Fargate Service Connect) | `<app-name>` |
| Auto-injected env `<SVC>_SERVICE_HOST` (K8s) | Environment variable pointing to `<app-name>` |
| Cloud Map / Cloud Run service URL | `<app-name>` or FQDN if cross-environment |

> **Rule**: When migrating env vars that contain service URLs, update them to use the ACA app name. Set as env var: `{ name: 'BACKEND_URL', value: 'http://<backend-app-name>' }`.

## Image Migration

If source images are in a private registry (ECR, GCR, private Docker Hub), migrate to Azure Container Registry:

```bash
# Login to source registry
# docker login <source-registry>

# Pull, tag, push to ACR
docker pull <source-image>:<tag>
docker tag <source-image>:<tag> <acr-name>.azurecr.io/<image-name>:<tag>
az acr login --name <acr-name>
docker push <acr-name>.azurecr.io/<image-name>:<tag>
```

Or use ACR import (no local Docker needed):
```bash
az acr import --name <acr-name> \
  --source <source-registry>/<image>:<tag> \
  --image <image>:<tag>
```

> **Rule**: If source uses a public image (Docker Hub public), it can be used directly — no ACR import needed. For private images, generate the `migrate-images.sh` script.

## Deployment Script

Generate `scripts/deploy.sh`:

```bash
#!/bin/bash
set -e

RESOURCE_GROUP="${RESOURCE_GROUP:-<default-rg-name>}"
LOCATION="${LOCATION:-eastus}"

# Create resource group
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# Deploy infrastructure + apps
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json \
  --parameters location="$LOCATION"

echo "Deployment complete."
echo "Run 'az containerapp list -g $RESOURCE_GROUP -o table' to see your apps."
```

## Validation Checklist

After migration, verify:

- [ ] All container apps are in `Running` state
- [ ] Ingress FQDNs return expected responses
- [ ] Internal service-to-service communication works
- [ ] Environment variables are correctly set
- [ ] Secrets are properly referenced (not plaintext in logs)
- [ ] Scaling rules trigger as expected
- [ ] Logs appear in Log Analytics workspace
- [ ] Managed identity has required RBAC roles
