"""
k8s2aca: Kubernetes to Azure Container Apps Converter
"""

# ===================== Imports =====================
import yaml
import os
import sys

# ===================== Constants =====================
# List of supported GPU SKUs for ACA
SUPPORTED_GPU_SKUS = ["A100", "T4"]

# ===================== Main Conversion Logic =====================
def convert_k8s_to_aca(input_file, output_file):
    # Main conversion function. Reads a Kubernetes manifest file, parses all relevant resources,
    # maps them to ACA equivalents, and writes both the ACA template and a migration report.
    with open(input_file, 'r') as f:
        # Load all documents from the YAML file (handles multi-document YAML files with ---)
        documents = list(yaml.safe_load_all(f))
        if len(documents) == 1:
            manifest = documents[0]
        else:
            manifest = documents

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

SUPPORTED_GPU_SKUS = ["A100", "T4"]

def prompt_choice(message, choices):
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
    resources = container.get('resources', {})
    limits = resources.get('limits', {})
    if 'nvidia.com/gpu' in limits:
        return int(limits['nvidia.com/gpu'])
    return 0

def map_gpu_to_aca(gpu_count):
    print(f"[Info] GPU resource detected: {gpu_count} x nvidia.com/gpu")
    print("ACA supports only certain GPU SKUs (A100, T4) and up to 4 GPUs per container.")
    sku = prompt_choice("Choose a supported GPU SKU:", SUPPORTED_GPU_SKUS + ["Skip GPU (run on CPU only)"])
    if sku.startswith("Skip"):
        return None, None
    return gpu_count, sku

def map_env_vars(container, configmaps, secrets):
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
    ports = []
    for port in container.get('ports', []):
        if 'containerPort' in port:
            ports.append({"port": port['containerPort']})
    return ports

def map_volumes(volumes, volume_mounts):
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


# ===================== Main Conversion Logic =====================

def convert_k8s_to_aca(input_file, output_file=None): 
    # Collect all manifests into a list
    manifests = []
    with open(input_file, 'r') as f:
        for manifest in yaml.safe_load_all(f):
            if manifest:
                manifests.append(manifest)
                print(f"Processing resource: {manifest.get('kind')}")
            else:
                print("Skipping empty manifest")

    # Separate resources
    configmaps = {}
    secrets = {}
    services = []
    ingresses = []
    unsupported = []
    pod_resources = []

    for manifest in manifests:
        kind = manifest.get('kind')
        if kind in ['Deployment', 'ReplicaSet', 'Pod']:
            pod_resources.append(manifest)
        elif kind == 'ConfigMap':
            configmaps[manifest['metadata']['name']] = manifest.get('data', {})
        elif kind == 'Secret':
            secrets[manifest['metadata']['name']] = manifest.get('data', {})
        elif kind == 'Service':
            services.append(manifest)
        elif kind == 'Ingress':
            ingresses.append(manifest)
        else:
            unsupported.append(manifest)

    if not pod_resources:
        print("[Error] No pod-spec resources (Deployment, ReplicaSet, Pod) found in manifest.")
        sys.exit(1)

    # Process each pod resource
    for pod_resource in pod_resources:
        migration_report = []

        # Extract pod spec and containers
        if pod_resource.get('kind') in ['Deployment', 'ReplicaSet']:
            pod_spec = pod_resource.get('spec', {}).get('template', {}).get('spec', {})
        else:
            pod_spec = pod_resource.get('spec', {})

        containers = pod_spec.get('containers', [])
        volumes = pod_spec.get('volumes', [])

        aca_containers = []
        dedicated_profile_needed = False

        # Containers
        for container in containers:
            resources = container.get('resources', {})
            limits = resources.get('limits', {})
            requests = resources.get('requests', {})

            cpu = 2.0
            memory = "8.0Gi"

            if 'cpu' in limits:
                try:
                    cpu = float(str(limits['cpu']).replace('m', '')) / 1000 if 'm' in str(limits['cpu']) else float(limits['cpu'])
                except Exception:
                    migration_report.append(f"[Warning] Could not parse CPU limit for container {container.get('name')}. Using default 2.0.")
            elif 'cpu' in requests:
                try:
                    cpu = float(str(requests['cpu']).replace('m', '')) / 1000 if 'm' in str(requests['cpu']) else float(requests['cpu'])
                except Exception:
                    migration_report.append(f"[Warning] Could not parse CPU request for container {container.get('name')}. Using default 2.0.")

            if 'memory' in limits:
                memory = str(limits['memory'])
            elif 'memory' in requests:
                memory = str(requests['memory'])

            if memory.endswith('Mi'):
                try:
                    mem_gi = round(float(memory.replace('Mi', '')) / 1024, 1)
                    memory = f"{mem_gi}Gi"
                except Exception:
                    migration_report.append(f"[Warning] Could not parse memory for container {container.get('name')}. Using default 8.0Gi.")
                    memory = "8.0Gi"
                    mem_gi = 8.0
            elif memory.endswith('Gi'):
                try:
                    mem_gi = float(memory.replace('Gi', ''))
                except Exception:
                    mem_gi = 8.0
            else:
                migration_report.append(f"[Warning] Memory value '{memory}' not in Mi/Gi. Using default 8.0Gi.")
                mem_gi = 8.0
                memory = "8.0Gi"

            if mem_gi > 8.0:
                dedicated_profile_needed = True
                migration_report.append(f"[Info] Container '{container.get('name')}' requests >8Gi memory. Will assign Dedicated Workload Profile in ACA.")

            aca_container = {
                "name": container.get('name'),
                "image": container.get('image'),
                "resources": {"cpu": cpu, "memory": memory},
            }

            gpu_count = detect_gpu(container)
            if gpu_count:
                count, sku = map_gpu_to_aca(gpu_count)
                if count and sku:
                    aca_container["resources"]["gpus"] = count
                    aca_container["resources"]["gpuSku"] = sku
                else:
                    migration_report.append(f"GPU mapping skipped for container {container.get('name')}. Will run on CPU only.")

            aca_container["env"] = map_env_vars(container, configmaps, secrets)
            aca_container["ports"] = map_ports(container)
            probes = map_probes(container)
            if probes:
                aca_container["probes"] = probes

            if 'volumeMounts' in container:
                aca_container["volumeMounts"] = map_volumes(volumes, container['volumeMounts'])

            aca_containers.append(aca_container)

        labels = pod_resource.get('metadata', {}).get('labels', {})
        annotations = pod_resource.get('metadata', {}).get('annotations', {})

        aca_ingress = None
        if services:
            svc = services[0]
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

        for item in unsupported:
            kind = item.get('kind', 'Unknown')
            name = item.get('metadata', {}).get('name', 'unnamed')
            migration_report.append(f"[Unsupported] {kind} '{name}' is not supported in ACA. Manual migration required.")

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

        if dedicated_profile_needed:
            aca_template["properties"]["workloadProfileName"] = "Dedicated"
            migration_report.append("[Info] 'Dedicated' workload profile assigned in ACA template for containers requiring >8GiB memory.")

        # Determine output paths
        app_name = pod_resource.get('metadata', {}).get('name', 'aca-app')
        out_file = output_file if output_file else f"{app_name}.aca.yaml"
        report_file = os.path.splitext(out_file)[0] + ".migration.txt"

        abs_out_file = os.path.abspath(out_file)
        abs_report_file = os.path.abspath(report_file)

        # Write ACA template and report
        with open(out_file, 'w') as f:
            yaml.dump(aca_template, f)
        print(f"[Success] ACA template written to {abs_out_file}")

        with open(report_file, 'w') as f:
            for line in migration_report:
                f.write(line + '\n')
        print(f"[Info] Migration report written to {abs_report_file}")


# ===================== Entry Point =====================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <input-k8s-manifest.yaml> [output-aca-template.yaml]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    convert_k8s_to_aca(input_file, output_file)
