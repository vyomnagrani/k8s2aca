// environment.bicep
@description('Name of the Log Analytics workspace (and prefix for env)')
param logAnalyticsWorkspaceName string

@description('Name of the Container Apps environment')
param managedEnvironmentName string

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Workload profile type (e.g. Consumption or one of the SKUs below)')
param workloadProfileType string

@description('Friendly name for the workload profile')
param workloadProfileName string = workloadProfileType

@description('Minimum node count for the workload profile')
param workloadProfileMinimumCount int = 1

@description('Maximum node count for the workload profile')
param workloadProfileMaximumCount int = 1

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
    workloadProfiles: [
      {
        name: workloadProfileName
        workloadProfileType: workloadProfileType
        minimumCount: workloadProfileMinimumCount
        maximumCount: workloadProfileMaximumCount
      }
    ]
  }
}

output environmentId string = managedEnvironment.id