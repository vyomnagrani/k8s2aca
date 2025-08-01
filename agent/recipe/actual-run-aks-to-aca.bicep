@description('The location where the resources will be created.')
param location string = 'eastus'

@description('Name of the Container Apps environment.')
param containerAppEnvironmentName string = 'k3d-data-pipeline-west-env'

@description('The name of the log analytics workspace to connect.')
param logAnalyticsWorkspaceName string = '${containerAppEnvironmentName}-logs'

var uniqueNameSuffix = uniqueString(resourceGroup().id)

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2020-08-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    retentionInDays: 30
    sku: {
        name: 'PerGB2018'
    }
  }
}

resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2022-03-01' = {
  name: containerAppEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource nginxContainerApp 'Microsoft.App/containerApps@2022-03-01' = {
  name: 'nginx-${uniqueNameSuffix}'
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
      }
    }
    template: {
      containers: [
        {
          name: 'nginx'
          image: 'nginx:latest'
          resources: {
            cpu: 1
            memory: '2.0Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
      }
    }
  }
}
