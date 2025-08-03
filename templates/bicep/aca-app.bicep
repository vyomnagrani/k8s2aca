// application.bicep
@description('Resource ID of the Container Apps environment')
param environmentId string

@description('Name of the Container App')
param appName string

@description('Container image (e.g. myregistry.azurecr.io/myimage:tag)')
param containerImage string

@description('CPU per container (e.g. "0.5", "1")')
param containerCpu string

@description('Memory per container, in Gi (e.g. "1", "2")')
param containerMemory string

@description('Which workload profile to deploy into (must match one defined in environment)')
param workloadProfileName string

@description('Azure region for the app (should match environment)')
param location string = resourceGroup().location

resource containerApp 'Microsoft.App/containerApps@2022-11-01-preview' = {
  name: appName
  location: location
  properties: {
    environmentId: environmentId
    configuration: {
      activeRevisionsMode: 'single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 80
      }
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: json(containerCpu)
            memory: '${containerMemory}Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
      }
    }
  }
  workloadProfileName: workloadProfileName
}