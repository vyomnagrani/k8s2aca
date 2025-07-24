"""
k8s2aca: Kubernetes to Azure Container Apps Converter

This tool reads Kubernetes manifests (Deployments, Services, Ingress, ConfigMaps, Secrets, etc.)
and generates an Azure Container Apps (ACA) deployment template, with interactive prompts for
ambiguous or unsupported features. It also produces a migration report highlighting any manual
steps required for a successful migration.
"""

# ===================== Imports =====================
import yaml
import sys

# ===================== Constants =====================
# List of supported GPU SKUs for ACA
SUPPORTED_GPU_SKUS = ["A100", "T4"]

# ===================== Main Conversion Logic =====================
def convert_k8s_to_aca(input_file, output_file):
    # Main conversion function. Reads a Kubernetes manifest file, parses all relevant resources,
    # maps them to ACA equivalents, and writes both the ACA template and a migration report.
    with open(input_file, 'r') as f:
        manifest = yaml.safe_load(f)

    # Collect ConfigMaps, Secrets, Services, Ingress, and unsupported constructs
    configmaps = {}
    secrets = {}
    services = []
    ingresses = []
    unsupported = []
    migration_report = []

    # Parse all resources in the manifest (if list)
    if isinstance(manifest, list):
        for item in manifest:
            kind = item.get('kind')
            if kind == 'ConfigMap':
                configmaps[item['metadata']['name']] = item.get('data', {})
            elif kind == 'Secret':
                secrets[item['metadata']['name']] = item.get('data', {})
            elif kind == 'Service':
                services.append(item)
            elif kind == 'Ingress':
                ingresses.append(item)
            elif kind not in ['Deployment', 'ReplicaSet', 'Pod']:
                unsupported.append(item)
        # Find the Deployment (main workload)
        deployment = next((i for i in manifest if i.get('kind') == 'Deployment'), None)
        if not deployment:
            print("[Error] No Deployment found in manifest.")
            sys.exit(1)
        manifest = deployment

    # Extract pod spec and containers
    pod_spec = manifest.get('spec', {}).get('template', {}).get('spec', {})
    containers = pod_spec.get('containers', [])
    volumes = pod_spec.get('volumes', [])

    aca_containers = []
    for container in containers:
        aca_container = {
            "name": container.get('name'),
            "image": container.get('image'),
            "resources": {"cpu": 2.0, "memory": "8.0Gi"},
        }
        # GPU mapping (interactive if needed)
        gpu_count = detect_gpu(container)
        if gpu_count:
            count, sku = map_gpu_to_aca(gpu_count)
            if count and sku:
                aca_container["resources"]["gpus"] = count
                aca_container["resources"]["gpuSku"] = sku
            else:
                migration_report.append(f"GPU mapping skipped for container {container.get('name')}. Will run on CPU only.")
        # Environment variables (from manifest, ConfigMap, Secret)
        aca_container["env"] = map_env_vars(container, configmaps, secrets)
        # Ports
        aca_container["ports"] = map_ports(container)
        # Probes (liveness/readiness)
        probes = map_probes(container)
        if probes:
            aca_container["probes"] = probes
        # Volume mounts (interactive for unsupported types)
        if 'volumeMounts' in container:
            aca_container["volumeMounts"] = map_volumes(volumes, container['volumeMounts'])
        aca_containers.append(aca_container)

    # Labels and annotations from the Deployment
    labels = manifest.get('metadata', {}).get('labels', {})
    annotations = manifest.get('metadata', {}).get('annotations', {})

    # Map Service/Ingress to ACA ingress (basic mapping)
    aca_ingress = None
    if services:
        svc = services[0]  # Only map the first service for now
        svc_type = svc.get('spec', {}).get('type', 'ClusterIP')
        ports = svc.get('spec', {}).get('ports', [])
        if svc_type in ['LoadBalancer', 'NodePort']:
            aca_ingress = {
                "external": True,
                "targetPort": ports[0]['targetPort'] if ports else 80,
                "transport": "auto"
            }
            migration_report.append(f"Service '{svc['metadata']['name']}' mapped to ACA ingress (external).")
        elif svc_type == 'ClusterIP':
            aca_ingress = {
                "external": False,
                "targetPort": ports[0]['targetPort'] if ports else 80,
                "transport": "auto"
            }
            migration_report.append(f"Service '{svc['metadata']['name']}' mapped to ACA ingress (internal).")
        else:
            migration_report.append(f"Service type '{svc_type}' for '{svc['metadata']['name']}' not directly supported. Manual review needed.")

    if ingresses:
        ing = ingresses[0]
        rules = ing.get('spec', {}).get('rules', [])
        if aca_ingress:
            aca_ingress['customDomains'] = [r['host'] for r in rules if 'host' in r]
            migration_report.append(f"Ingress '{ing['metadata']['name']}' custom domains mapped to ACA ingress.")
        else:
            migration_report.append(f"Ingress '{ing['metadata']['name']}' found, but no Service mapped. Manual review needed.")

    # Report unsupported constructs
    for item in unsupported:
        kind = item.get('kind', 'Unknown')
        name = item.get('metadata', {}).get('name', 'unnamed')
        migration_report.append(f"[Unsupported] {kind} '{name}' is not supported in ACA. Manual migration required.")

    # Compose the ACA template
    aca_template = {
        "type": "Microsoft.App/containerApps",
        "properties": {
            "template": {
                "containers": aca_containers
            },
            "labels": labels,
            "annotations": annotations
        }
    }
    if aca_ingress:
        aca_template["properties"]["ingress"] = aca_ingress

    # Write ACA template to file
    with open(output_file, 'w') as f:
        yaml.dump(aca_template, f)
    print(f"[Success] ACA template written to {output_file}")

    # Write migration report to file
    report_file = output_file.replace('.yaml', '.migration.txt')
    with open(report_file, 'w') as f:
        for line in migration_report:
            f.write(line + '\n')
    print(f"[Info] Migration report written to {report_file}")

# ===================== Helper Functions =====================

def prompt_choice(message, choices):
    # Prompt the user to select from a list of choices. Returns the selected value.
    print(message)
    for idx, choice in enumerate(choices, 1):
        print(f"{idx}. {choice}")
    while True:
        try:
            selection = int(input(f"Enter your choice [1-{len(choices)}]: "))
            if 1 <= selection <= len(choices):
                return choices[selection - 1]
        except ValueError:
            pass
        print("Invalid input. Please try again.")

def detect_gpu(container):
    # Detects if a container requests GPU resources. Returns the GPU count (int).
    resources = container.get('resources', {})
    limits = resources.get('limits', {})
    if 'nvidia.com/gpu' in limits:
        return int(limits['nvidia.com/gpu'])
    return 0

def map_gpu_to_aca(gpu_count):
    # Interactive prompt to map GPU requests to ACA-supported SKUs.
    print(f"[Info] GPU resource detected: {gpu_count} x nvidia.com/gpu")
    print("ACA supports only certain GPU SKUs (A100, T4) and up to 4 GPUs per container.")
    sku = prompt_choice("Choose a supported GPU SKU:", SUPPORTED_GPU_SKUS + ["Skip GPU (run on CPU only)"])
    if sku.startswith("Skip"):
        return None, None
    return gpu_count, sku

def map_env_vars(container, configmaps, secrets):
    # Maps environment variables from the container spec, ConfigMaps, and Secrets.
    # Warns if referenced keys are missing and suggests Azure alternatives.
    envs = []
    for env in container.get('env', []):
        if 'value' in env:
            envs.append({"name": env['name'], "value": env['value']})
        elif 'valueFrom' in env:
            src = env['valueFrom']
            if 'configMapKeyRef' in src:
                cm_name = src['configMapKeyRef']['name']
                key = src['configMapKeyRef']['key']
                value = configmaps.get(cm_name, {}).get(key)
                if value is not None:
                    envs.append({"name": env['name'], "value": value})
                else:
                    print(f"[Warning] ConfigMap {cm_name} or key {key} not found. Consider using Azure App Configuration.")
            elif 'secretKeyRef' in src:
                sec_name = src['secretKeyRef']['name']
                key = src['secretKeyRef']['key']
                value = secrets.get(sec_name, {}).get(key)
                if value is not None:
                    envs.append({"name": env['name'], "value": value})
                else:
                    print(f"[Warning] Secret {sec_name} or key {key} not found. Consider using Azure Key Vault.")
    return envs

def map_ports(container):
    # Maps container ports to ACA format.
    ports = []
    for port in container.get('ports', []):
        if 'containerPort' in port:
            ports.append({"port": port['containerPort']})
    return ports

def map_volumes(volumes, volume_mounts):
    # Maps volume mounts to ACA-supported storage types. Prompts user for unsupported types.
    aca_volumes = []
    for mount in volume_mounts:
        vol_name = mount['name']
        vol = next((v for v in volumes if v['name'] == vol_name), None)
        if not vol:
            continue
        if 'azureFile' in vol:
            aca_volumes.append({"name": vol_name, "storageType": "AzureFile", "mountPath": mount['mountPath']})
        else:
            print(f"[Warning] Volume type for '{vol_name}' not directly supported in ACA.")
            alt = prompt_choice(f"How do you want to handle volume '{vol_name}'?", ["Skip", "Map as AzureFile", "Map as AzureBlob"])
            if alt == "Map as AzureFile":
                aca_volumes.append({"name": vol_name, "storageType": "AzureFile", "mountPath": mount['mountPath']})
            elif alt == "Map as AzureBlob":
                aca_volumes.append({"name": vol_name, "storageType": "AzureBlob", "mountPath": mount['mountPath']})
    return aca_volumes

def map_probes(container):
    # Maps liveness and readiness probes to ACA format. Warns for unsupported probe types.
    probes = {}
    for probe_type in ["livenessProbe", "readinessProbe"]:
        if probe_type in container:
            probe = container[probe_type]
            if 'httpGet' in probe:
                probes[probe_type] = {
                    "type": "http",
                    "path": probe['httpGet']['path'],
                    "port": probe['httpGet']['port']
                }
            elif 'tcpSocket' in probe:
                probes[probe_type] = {
                    "type": "tcp",
                    "port": probe['tcpSocket']['port']
                }
            else:
                print(f"[Warning] Probe type in {probe_type} not directly supported in ACA.")
    return probes

# ===================== Entry Point =====================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python main.py <input-k8s-manifest.yaml> <output-aca-template.yaml>")
        sys.exit(1)
    convert_k8s_to_aca(sys.argv[1], sys.argv[2])