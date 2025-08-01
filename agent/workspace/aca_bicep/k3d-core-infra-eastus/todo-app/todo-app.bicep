param location string = resourceGroup().location
param environmentName string = 'todo-app-env'
param todoAppName string = 'todo-app'
param redisAppName string = 'redis-app'

resource managedEnvironment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: environmentName
  location: location
  properties: {}
}

resource todoAppContainerApp 'Microsoft.App/containerApps@2025-07-01' = {
  name: todoAppName
  location: location
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
      }
      registries: []
    }
    template: {
      containers: [
        {
          name: todoAppName
          image: 'simon.azurecr.io/todo-app:latest'
          resources: {
            cpu: 1
            memory: '2Gi'
          }
        }
      ]
    }
  }
}

resource redisContainerApp 'Microsoft.App/containerApps@2025-07-01' = {
  name: redisAppName
  location: location
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      registries: []
    }
    template: {
      containers: [
        {
          name: redisAppName
          image: 'docker.io/redis:latest'
          resources: {
            cpu: 1
            memory: '2Gi'
          }
        }
      ]
    }
  }
}
