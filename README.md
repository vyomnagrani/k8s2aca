k8s2aca is a tool that converts Kubernetes deployment manifests into an Azure Container Apps deployment template.

## Overview
This project helps you migrate your Kubernetes workloads to Azure Container Apps by transforming your existing Kubernetes YAML manifests into the format required for Azure Container Apps deployments.

## Features

## Usage
1. Provide your Kubernetes deployment manifest.
2. Run the tool to generate the Azure Container Apps template.
3. Deploy the generated template to Azure.

## License
MIT

# k8s2aca

k8s2aca is a Python tool that converts Kubernetes deployment manifests into an Azure Container Apps (ACA) deployment template, with interactive guidance for unsupported or ambiguous features.

## Overview
This project helps you migrate your Kubernetes workloads to Azure Container Apps by transforming your existing Kubernetes YAML manifests into the format required for ACA deployments. It provides:
- Automated manifest parsing and conversion
- Interactive prompts for special cases
- A migration report highlighting any manual steps required

## Features
- Parses Kubernetes deployment manifests (Deployments, Services, Ingress, ConfigMaps, Secrets, etc.)
- Generates Azure Container Apps deployment templates
- Interactive mode for ambiguous or unsupported features
- Migration report listing all manual actions needed
- Maps environment variables, ports, volumes, probes, and GPU requests
- Warns and guides for unsupported features (e.g., unsupported volume types, network policies)

## Packaging & Installation

1. **Clone the repository:**
   ```sh
   git clone https://github.com/vyomnagrani/k8s2aca.git
   cd k8s2aca
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **(Optional) Package as a CLI tool:**
   You can use [pipx](https://pypa.github.io/pipx/) for isolated CLI installs:
   ```sh
   pipx install .
   ```
   Or, create a simple shell wrapper script to call `python main.py` from anywhere.


## Usage


### Quick Start Demos

**Simple Example:**
A sample Kubernetes manifest is included in this repo as `starter-k8s-hello-world.yaml` (a simple web app and service). You can try the tool immediately:

```sh
python main.py starter-k8s-hello-world.yaml hello-world-aca.yaml
```

**Microservices Example:**
For a more robust, microservices-style demo, use `starter-k8s-microservices.yaml` (frontend, backend, and Redis):

```sh
python main.py starter-k8s-microservices.yaml microservices-aca.yaml
```

This will:
- Parse the included Kubernetes manifest
- Generate an ACA deployment template (e.g., `microservices-aca.yaml`)
- Generate a migration report (e.g., `microservices-aca.migration.txt`)

### General Usage

```sh
python main.py <input-k8s-manifest.yaml> <output-aca-template.yaml>
```

This will:
- Parse your Kubernetes manifest(s)
- Generate an ACA deployment template (`output-aca-template.yaml`)
- Generate a migration report (`output-aca-template.migration.txt`)


### Deploying the ACA Template

Once you have generated your ACA YAML template, you can deploy it to Azure Container Apps using the Azure CLI:

1. **Login to Azure (if not already):**
   ```sh
   az login
   ```

2. **Create a resource group (if needed):**
   ```sh
   az group create --name my-aca-rg --location <azure-region>
   ```

3. **Deploy the ACA template:**
   ```sh
   az containerapp create --resource-group my-aca-rg --name my-aca-app --environment <aca-env-name> --yaml <output-aca-template.yaml>
   ```
   - Replace `<aca-env-name>` with your ACA environment name (create one if you don't have it: [docs](https://learn.microsoft.com/en-us/azure/container-apps/environment))
   - Replace `<output-aca-template.yaml>` with your generated file

4. **Check deployment status:**
   ```sh
   az containerapp show --resource-group my-aca-rg --name my-aca-app
   ```

For more details, see the [Azure Container Apps documentation](https://learn.microsoft.com/en-us/azure/container-apps/).

---

### Interactive Mode

The tool is interactive by default. When it encounters features that do not map directly to ACA (e.g., unsupported volume types, GPU SKUs, missing ConfigMap/Secret keys), it will prompt you for alternatives or guidance. Example prompts include:

- "Volume type for 'my-volume' not directly supported in ACA. How do you want to handle it? [Skip/Map as AzureFile/Map as AzureBlob]"
- "GPU resource detected: 2 x nvidia.com/gpu. Choose a supported GPU SKU: [A100/T4/Skip]"
- "ConfigMap 'my-config' or key 'foo' not found. Consider using Azure App Configuration."

You can run the tool non-interactively by providing only supported features in your manifests.

### Handling Unsupported Features

If the tool encounters Kubernetes features that are not supported in ACA (e.g., NetworkPolicy, certain volume types, custom CRDs), it will:
- Warn you in the console
- List the unsupported features in the migration report
- Suggest Azure-native alternatives where possible (e.g., Azure App Configuration, Azure Key Vault)
- Allow you to skip, map, or manually handle these features

**Migration Report:**
After each run, a `.migration.txt` file is generated alongside your output template. This report summarizes:
- What was mapped automatically
- What was skipped or needs manual migration
- Any special instructions or Azure alternatives

## Example

```sh
python main.py my-k8s-deployment.yaml my-aca-template.yaml
```

You will be prompted for any ambiguous or unsupported features. After completion, check `my-aca-template.yaml` and `my-aca-template.migration.txt` for results and next steps.

## Contributing
Contributions are welcome! Please open issues or pull requests for improvements, new feature mappings, or bug fixes.

## License
MIT
