# Quick Deploy with Azure Container Apps
# This is the simplest way to deploy without any infrastructure files

# Make sure you're logged in
az login

# Deploy directly from source code (creates everything automatically)
az containerapp up `
  --name k8s2aca-app `
  --resource-group k8s2aca-rg `
  --location eastus `
  --source . `
  --target-port 5000 `
  --ingress external `
  --env-vars FLASK_ENV=production

# That's it! The command will:
# ✅ Create the resource group
# ✅ Create a Container Apps environment 
# ✅ Create a container registry (with working SKU)
# ✅ Build your Docker image
# ✅ Deploy the container app
# ✅ Set up ingress and networking
