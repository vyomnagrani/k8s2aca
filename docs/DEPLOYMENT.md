# k8s2aca Azure Container Apps Deployment Guide

## Prerequisites

✅ **Azure CLI** - Installed (version check needed)  
✅ **Azure Developer CLI (azd)** - Installed (v1.17.2, can be updated)  
⚠️ **Docker** - Installed but not running  

## Quick Start

1. **Make sure you're logged into Azure:**
   ```powershell
   az login
   ```

2. **Deploy immediately** (creates all infrastructure automatically):
   ```powershell
   az containerapp up --name k8s2aca-app --resource-group k8s2aca-rg --location eastus --source . --target-port 5000 --ingress external --env-vars FLASK_ENV=production
   ```

3. **Access your application:**
   - Your app will be deployed and accessible via HTTPS
   - The deployment command will show your app URL
   - Example: `https://k8s2aca-app.calmsand-4cb90aab.eastus.azurecontainerapps.io/`

## Detailed Deployment Steps

### 1. Start Docker
- Start Docker Desktop application
- Wait for it to be fully running

### 2. Deploy with AZD (No Setup Required!)
```powershell
# Deploy infrastructure and application
azd up
```

**That's it!** The app will automatically:
- ✅ Generate secure session keys
- ✅ Run in production mode by default
- ✅ Configure all Azure resources
- ✅ Set up monitoring and logging

## Architecture Overview

The deployment creates:

- **Resource Group**: Contains all resources
- **Container Registry**: Stores your application container images
- **Container Apps Environment**: Managed environment for running containers
- **Container App**: Your Flask web application
- **Log Analytics Workspace**: Centralized logging
- **Application Insights**: Application monitoring and telemetry
- **Managed Identity**: Secure access to Azure Container Registry

## Application Features

- 🎨 **Azure-branded UI** with official Container Apps logo
- 📁 **Drag-and-drop file upload** for Kubernetes YAML files
- 🔄 **Real-time conversion** from K8s to Azure Container Apps
- 📋 **Copy-to-clipboard** functionality
- 📥 **Download options** for templates and reports
- 🛡️ **Security validation** and file type checking
- 📱 **Responsive design**

## Security Features

- ✅ **Managed Identity** for secure registry access
- ✅ **No hardcoded credentials**
- ✅ **HTTPS-only** communication
- ✅ **CORS policy** configured
- ✅ **File upload validation**
- ✅ **Secure secret management**

## Monitoring

- **Application Insights**: Real-time performance monitoring
- **Log Analytics**: Centralized log aggregation
- **Health checks**: Built-in container health monitoring

## Scaling

- **Automatic scaling**: 1-10 replicas based on HTTP requests
- **Resource limits**: 0.5 CPU, 1GB memory per container
- **Load balancing**: Automatic across replicas

## Troubleshooting

1. **Container Registry SKU issues**: Use `az containerapp up` instead of Bicep files - it automatically selects compatible registry settings
2. **Permission issues**: Ensure you're logged into Azure CLI with `az login`
3. **Region limitations**: Try different Azure regions like `eastus`, `westus2`, or `canadacentral`
4. **Build failures**: Check Dockerfile and requirements.txt

## Useful Commands

```powershell
# Check deployment status
azd show

# View application logs
azd logs

# Open application in browser
azd show --output json | ConvertFrom-Json | Select-Object -ExpandProperty services | Select-Object -ExpandProperty k8s2aca-web | Select-Object -ExpandProperty uri

# Update application
azd deploy

# Clean up resources
azd down
```

## Production Considerations

- Update the secret key to a strong, random value
- Configure custom domain if needed
- Set up monitoring alerts
- Implement backup strategies
- Review security settings
