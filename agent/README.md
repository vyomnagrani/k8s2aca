# Azure Container Apps Migration Agent

This repository contains a POC AI agent to automate migrations to Azure Container Apps. It utlizes [Goose AI Agent](https://github.com/gooseai/gooseai).

## Setup & Install

- **Install Goose Agent**: [Installation options and instructions](https://block.github.io/goose/docs/getting-started/installation/)
- **AI API Endpoint**: Ensure you have access to a [supported LLM API endpoint](https://block.github.io/goose/docs/getting-started/providers). The current `config.yaml` is pre-configured for Azure OpenAI. All you need to populate is `<YOUR_DEPLOYMENT_NAME>` and `<YOUR_API_KEY>` (assuming you have a gpt-4o model available). Ensure you have sufficient capacity as the agent can consume a lot of tokens.
- **Configuration File**: Copy and edit the provided `config.yaml` into your Goose config directory. Which is `%APPDATA%\Block\goose\config\config.yaml` on Windows and `~/.config/goose/config.yaml` macOS and Linux.


## Usage

The agent makes heavy use of azure cli. Ensure you have it installed, it's in your `$PATH` and you are logged into your subscription. Then run the agent with the instruction file and from the `./agent` directory. (**this is important**).

```bash
goose run --instructions azure-container-apps-migration-agent.md
```

This will start the agent in interactive mode and you can start the migration now.


## Notes & Todos

- This is only a POC implementation and not for production use.
- Only single container applications with publicly available images have been tested.
- There are many gaps with the YAML to Bicep translation process.
- Only K8s and AKS have been implemented as migration sources.
