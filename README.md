# k8s2aca

This repository provides two different Azure Container Apps (ACA) migration tools:

1. **convert-app**  
   A command-line utility that reads Kubernetes YAML manifests and generates corresponding Bicep templates for Azure Container Apps.  
   See the detailed instructions in [convert-app/README.md](convert-app/README.md).

2. **agent**  
   An interactive AI-powered migration agent that walks you through the migration process step-by-step using Goose AI.  
   See the setup and usage guide in [agent/README.md](agent/README.md).

---

## Getting Started

Choose the tool that best fits your workflow:

- If you prefer a simple CLI converter, jump into `convert-app`.
- If you want an AI assistant to guide you end-to-end, use the `agent` tool.

Each directory contains its own README with detailed setup and usage instructions.
