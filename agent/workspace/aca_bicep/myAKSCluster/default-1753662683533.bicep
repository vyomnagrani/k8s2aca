param location string = 'eastus'
param managedEnvironmentName string = 'myAKSCluster-default-1753662683533'
param cappDedicatedName string = 'nginx'
param cappDedicatedContainerImage string = 'docker.io/nginx'
param cappDedicatedCpu string = '1'  // Adjusted from Kubernetes deployment
param cappDedicatedMemory string = '2' // Adjusted from Kubernetes deployment

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2020-10-01' = {
  name: '${managedEnvironmentName}la'
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
  name: cappDedicatedName
  location: location
  properties: {
    configuration: {
      activeRevisionsMode: 'single'
      ingress: {
        allowInsecure: false
        external: true
        targetPort: 80
      }
    }
    environmentId: managedEnvironment.id
    template: {
      containers: [
        {
          image: cappDedicatedContainerImage
          name: cappDedicatedName
          resources: {
            cpu: cappDedicatedCpu
            memory: '${cappDedicatedMemory}Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
      }
    }
  }
}
