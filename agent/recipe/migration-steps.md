# Migration Recipe: Self-hosted Kubernetes to Azure Container Apps

## Overview
This recipe includes the steps performed to migrate a self-hosted Kubernetes `nginx` service to Azure Container Apps (ACA). Each step is detailed, along with the commands used during execution, to facilitate reuse or reference.

---

## Steps

### 1. Establish SSH Connection
- **Command Executed**:
  ```bash
  ssh -i ~/.ssh/id_rsa.pub azureuser@130.131.250.34
  ```
- SSH was used to interact with the self-hosted Kubernetes cluster.
  
---

### 2. Switch Kubernetes Context
- **Command Executed**:
  ```bash
  kubectl config use-context k3d-data-pipeline-west
  ```
- Switched to the data-pipeline cluster context: `k3d-data-pipeline-west`.

---

### 3. List Services Across all Namespaces
- **Command Executed**:
  ```bash
  kubectl get services --all-namespaces
  ```
- Outcome:
  Identified the `nginx` service in the `web-demo` namespace for migration.

---

### 4. Export the `nginx` Service YAML
- **Command Executed**:
  ```bash
  kubectl get service nginx -n web-demo -o yaml > k8s_exports/k3d-data-pipeline-west/web-demo/nginx_export.yaml
  ```
- Saved YAML export to: `k8s_exports/k3d-data-pipeline-west/web-demo/nginx_export.yaml`.

---

### 5. Translate YAML to ACA Bicep
- Used the `managed-env-workload-profiles.bicep` template to generate an ACA configuration.
- Key configuration changes:
  - **Container Resources**:
    - CPU: `1`
    - Memory: `2 GiB`
  - **Ingress**:
    - Exposed on port `80` with external access.

- **Bicep File**: Saved as `aca_bicep/k3d-data-pipeline-west/nginx.bicep`.

---

### 6. Deploy to Azure
- Created a resource group:
  ```bash
  az group create --name k3d-data-pipeline-west-web-demo --location eastus
  ```

- Deployed the generated Bicep:
  ```bash
  az deployment group create --resource-group k3d-data-pipeline-west-web-demo --template-file /home/simon/code/k8s2aca/goose-agent/aca_bicep/k3d-data-pipeline-west/nginx.bicep
  ```

---

### 7. Ingress URL
- **Command Executed**:
  ```bash
  az containerapp show --name nginx-ayv6w7rlesyoy --resource-group k3d-data-pipeline-west-web-demo --query "properties.configuration.ingress.fqdn" -o tsv
  ```
- **Ingress URL**:
  [nginx-ayv6w7rlesyoy.victoriousmushroom-45aef9d1.eastus.azurecontainerapps.io](https://nginx-ayv6w7rlesyoy.victoriousmushroom-45aef9d1.eastus.azurecontainerapps.io)

---

### 8. Save Recipe to Disk
- Saved this recipe file as `migration-steps.md` for future reference.

---

## File Locations
- Bicep File: `/home/simon/code/k8s2aca/goose-agent/aca_bicep/k3d-data-pipeline-west/nginx.bicep`
- Recipe Markdown: `/home/simon/code/k8s2aca/goose-agent/recipe/migration-steps.md`

---
