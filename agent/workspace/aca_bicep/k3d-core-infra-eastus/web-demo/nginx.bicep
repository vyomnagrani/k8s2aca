param managedEnvironmentName string = 'k3d-core-infra-eastus'
param location string = 'eastus'
param cappConsumptionName string = 'nginx'
param cappConsumptionContainerImage string = 'nginx:latest'

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2020-10-01' = {
  name: '${managedEnvironmentName}-la'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2022-11-01-preview' = {
  name: managedEnvironmentName
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

resource containerApp 'Microsoft.App/containerApps@2022-11-01-preview' = {
  name: cappConsumptionName
  location: location
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        allowInsecure: true
      }
    }
    template: {
      containers: [
        {
          name: cappConsumptionName
          image: cappConsumptionContainerImage
          resources: {
            cpu: '1.0'
            memory: '2Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
}
