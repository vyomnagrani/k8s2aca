# Azure Container Apps Deployment Script
# This script deploys the k8s2aca application using Azure CLI commands instead of Bicep

param(
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",
    
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroupName = "k8s2aca-rg",
    
    [Parameter(Mandatory=$false)]
    [string]$AppName = "k8s2aca-app"
)

Write-Host "🚀 Starting Azure Container Apps deployment..." -ForegroundColor Green

# Check if user is logged in
$account = az account show --query "user.name" -o tsv 2>$null
if (-not $account) {
    Write-Host "❌ Please log in to Azure CLI first: az login" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Logged in as: $account" -ForegroundColor Green

# Create resource group
Write-Host "📦 Creating resource group..." -ForegroundColor Yellow
az group create --name $ResourceGroupName --location $Location

# Create Log Analytics workspace
Write-Host "📊 Creating Log Analytics workspace..." -ForegroundColor Yellow
$workspaceName = "la-$AppName-$((Get-Random -Maximum 99999))"
az monitor log-analytics workspace create `
    --resource-group $ResourceGroupName `
    --workspace-name $workspaceName `
    --location $Location

# Get workspace details
$workspaceId = az monitor log-analytics workspace show `
    --resource-group $ResourceGroupName `
    --workspace-name $workspaceName `
    --query "customerId" -o tsv

# Create Container Apps environment
Write-Host "🏗️ Creating Container Apps environment..." -ForegroundColor Yellow
$environmentName = "cae-$AppName-$((Get-Random -Maximum 99999))"
az containerapp env create `
    --name $environmentName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --logs-destination log-analytics `
    --logs-workspace-id $workspaceId

# Build and deploy the application
Write-Host "🔨 Building and deploying application..." -ForegroundColor Yellow
az containerapp up `
    --name $AppName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --environment $environmentName `
    --source . `
    --target-port 5000 `
    --ingress external `
    --env-vars FLASK_ENV=production

# Get the application URL
$appUrl = az containerapp show `
    --name $AppName `
    --resource-group $ResourceGroupName `
    --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host "✅ Deployment completed successfully!" -ForegroundColor Green
Write-Host "🌐 Application URL: https://$appUrl" -ForegroundColor Cyan
Write-Host "📱 You can now access your k8s2aca application!" -ForegroundColor Green
