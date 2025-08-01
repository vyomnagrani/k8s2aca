// =================================================================
// TEMPLATE FOR K8S TO AZURE CONTAINER APPS MIGRATION
// =================================================================
// This template is designed to help convert Kubernetes resources to Azure Container Apps
// An LLM can use this as a reference to generate ACA infrastructure from K8s manifests


// ----------------------- LOGGING CONFIGURATION -----------------------
// [OPTIONAL] Name for the Log Analytics workspace that will store logs from Container Apps
// Name is derived from the managed environment name plus 4 random characters for uniqueness
param logAnalyticsWorkspaceName string = '${managedEnvironmentName}${uniqueString(resourceGroup().id)[0:3]}la'


// ----------------------- ENVIRONMENT CONFIGURATION -----------------------
// [REQUIRED] Name for the Container Apps managed environment (similar to a K8s cluster)
// FROM K8S: Use the same name as your Kubernetes cluster for easy tracking
param managedEnvironmentName string  // [INPUT]: Set to your K8s cluster name

// [OPTIONAL] Region for deploying resources
// FROM K8S: Use the same region as your AKS cluster if possible
param location string = resourceGroup().location


// ----------------------- WORKLOAD PROFILE CONFIGURATION -----------------------
// Workload profiles determine the compute resources and scaling behavior
// CHOICE: 'Consumption' (serverless) or 'Dedicated' (reserved infrastructure)
// Run 'az containerapp env workload-profile list-supported -l <location>' to see available options

// [REQUIRED] Type of workload profile to use
// FROM K8S: Choose based on node pool type or resource requirements
// EXAMPLE VALUES: 'Consumption', 'D4', 'D8', 'D16', 'E4', 'E8', 'E16'
param workloadProfileType string

// [REQUIRED] Name for the workload profile (can match type or be descriptive)
// FROM K8S: Could be named after node pool or deployment purpose
param workloadProfileName string = 

// [OPTIONAL] Minimum number of nodes for the workload profile
// FROM K8S: Could be derived from deployment minReplicas or node count
param workloadProfileMinimumCount int = 3

// [OPTIONAL] Maximum number of nodes for the workload profile
// FROM K8S: Could be derived from deployment maxReplicas or autoscaling settings
param workloadProfileMaximumCount int = 5


// ----------------------- DEDICATED APP CONFIGURATION -----------------------
// For workloads that need predictable performance and reserved resources
// FROM K8S: Map from Deployments with specific resource requirements

// [REQUIRED] Name of the container app using dedicated workload profile
// FROM K8S: Use the deployment name
param cappDedicatedName string

// [REQUIRED] Container image for the dedicated app
// FROM K8S: Use the container image from deployment spec
param cappDedicatedContainerImage string

// [REQUIRED] CPU cores for the dedicated app (e.g., '0.5', '1', '2')
// FROM K8S: Map from container resources.requests.cpu
param cappDedicatedCpu string

// [REQUIRED] Memory in GB for the dedicated app (without 'Gi' suffix)
// FROM K8S: Map from container resources.requests.memory (convert to GB)
param cappDedicatedMemory string


// ----------------------- CONSUMPTION APP CONFIGURATION -----------------------
// For workloads that can scale to zero and have variable load
// FROM K8S: Map from Deployments without strict resource requirements

// [REQUIRED] Name of the container app using consumption workload profile
// FROM K8S: Use the deployment name
param cappConsumptionName string

// [OPTIONAL] Container image for the consumption app
// FROM K8S: Use the container image from deployment spec
param cappConsumptionContainerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// [OPTIONAL] CPU cores for the consumption app (e.g., '0.25', '0.5', '1')
// FROM K8S: Map from container resources.requests.cpu
param cappConsumptionCpu string = '0.5'

// [OPTIONAL] Memory in GB for the consumption app (without 'Gi' suffix)
// FROM K8S: Map from container resources.requests.memory (convert to GB)
param cappConsumptionMemory string = '1'


// ----------------------- LOG ANALYTICS WORKSPACE -----------------------
// Creates a Log Analytics workspace for monitoring Container Apps
// FROM K8S: No direct equivalent - this is ACA-specific for logging and monitoring
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2020-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'  // Standard pay-as-you-go pricing tier
    }
  }
}


// ----------------------- MANAGED ENVIRONMENT -----------------------
// Creates a Container Apps environment, equivalent to a K8s cluster
// FROM K8S: Similar to a namespace or cluster
resource managedEnvironment 'Microsoft.App/managedEnvironments@2022-11-01-preview' = {
  name: managedEnvironmentName
  location: location
  properties: {
    // Configure logging to Log Analytics
    // FROM K8S: Map from cluster-level logging configurations
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    // Configure workload profiles (similar to K8s node pools)
    // FROM K8S: Map from node pools or node selectors
    workloadProfiles: [
      {
        maximumCount: workloadProfileMaximumCount  // Max number of infrastructure nodes
        minimumCount: workloadProfileMinimumCount  // Min number of infrastructure nodes
        name: workloadProfileName                  // Profile name (used as a reference)
        workloadProfileType: workloadProfileType   // Profile type (D4, D8, E4, E8, etc.)
      },
      // Always include the Consumption profile for serverless workloads
      // This allows deploying both dedicated and serverless apps in the same environment
      {
        name: 'Consumption'                        // Built-in consumption profile
        workloadProfileType: 'Consumption'         // Serverless, scales to zero
      }
    ]
  }
}

// ----------------------- CONTAINER APP -----------------------
// Add more than one app if needed.
// Creates a Container App using a dedicated workload profile
// FROM K8S: Map from a Deployment with resource requirements
resource containerApp 'Microsoft.App/containerApps@2022-11-01-preview' = {
  name: cappName
  location: location
  properties: {
    configuration: {
      // Revision mode defines how updates are applied
      // FROM K8S: Similar to Deployment strategy
      activeRevisionsMode: 'single'  // Only one revision is active at a time
      
      // Ingress configuration
      // FROM K8S: Map from Service and Ingress resources
      ingress: {
        allowInsecure: false         // Require HTTPS (set to true if HTTP is needed)
        external: true               // Expose externally (false for internal only)
        targetPort: 80               // Container port to expose (from containerPort)
      }
    }
    // Link to the managed environment
    environmentId: managedEnvironment.id
    
    // Container configuration
    // FROM K8S: Map from container spec in Deployment
    template: {
      containers: [
        {
          image: cappImage  // Container image
          name: cappName             // Container name
          
          // Resource allocation
          // FROM K8S: Map from container resources
          resources: {
            cpu: json('${cappCpu}')           // CPU cores
            memory: '${cappMemory}Gi'         // Memory with Gi suffix
          }
          
          // OPTIONAL: Add environment variables, volume mounts, etc.
          env: [
            // Standard environment variable (from ConfigMap)
            {
              name: 'LOG_LEVEL'
              value: 'info'
            }
            // Database connection (from Secret)
            {
              name: 'DB_CONNECTION_STRING'
              secretRef: 'db-connection-string'  // Reference to a secret
            }
            // API endpoint (from ConfigMap)
            {
              name: 'API_ENDPOINT'
              value: 'https://api.example.com/v1'
            }
          ]
          // FROM K8S: Map from container env and volumeMounts
        }
      ]
      
      // Scaling configuration
      // FROM K8S: Map from HPA or Deployment replicas
      scale: {
        minReplicas: 1  // Minimum number of replicas
        // OPTIONAL: Add maxReplicas, rules for scaling
      }
    }
    
    // Specify the workload profile to use
    // Either 'Consumption' for serverless or dedicated-d4, dedicated-e16, ... (match from environment)
    workloadProfileName: workloadProfileName
  }
}




// ----------------------- OUTPUTS -----------------------
// OPTIONAL: Add outputs for the Container App URLs, etc.
// Example:
// output containerAppUrl string = 'https://${containerAppUrl.properties.configuration.ingress.fqdn}'
