@description('Name of the Azure Container App')
param appName string = 'migrate-target'

@description('Region for deploying resources')
param location string = 'eastus'

@description('Log Analytics workspace name for monitoring logs')
param logAnalyticsWorkspaceName string = '${appName}la'

@description('CPU and memory allocation for the app')
param cappCpu string = '1'
param cappMemory string = '2'

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2020-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2022-11-01-preview' = {
  name: '${appName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }, { name: 'mig-dedicated', workloadProfileType: 'D4', minimumCount: 1, maximumCount: 3 }]
  }
}

resource containerApp 'Microsoft.App/containerApps@2022-11-01-preview' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      ingress: {
        external: false
        targetPort: 5000
      }
      activeRevisionsMode: 'single'
    }
    template: {
      containers: [
        {
          name: appName
          image: 'simon.azurecr.io/migrate-app:latest'
          resources: {
            cpu: json(cappCpu)
            memory: '${cappMemory}Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
      }
    }
  }
}
