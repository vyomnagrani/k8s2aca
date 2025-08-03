#!/bin/bash

# === Configuration ===
# store outputs in the workspace directory
ROOT_DIR="../workspace"

# === Inputs ===
CLUSTER_NAME="$1"
LOCATION="$2"

if [[ -z "$CLUSTER_NAME" || -z "$LOCATION" ]]; then
  echo "Usage: $0 <cluster-name> <location>"
  exit 1
fi

# === Ensuring the output directory exists ===
output_dir="$ROOT_DIR/aks_namespace_exports"
mkdir -p "$output_dir"

# === Get the resource group for the specified cluster ===
echo "🔍 Looking up resource group for cluster '$CLUSTER_NAME' in '$LOCATION'..."
rg=$(az aks list --query "[?name=='$CLUSTER_NAME' && location=='$LOCATION'].resourceGroup" -o tsv)

if [[ -z "$rg" ]]; then
  echo "❌ Cluster '$CLUSTER_NAME' not found in region '$LOCATION'."
  exit 1
fi

# === Connect to the cluster ===
echo "🔗 Connecting to cluster: $CLUSTER_NAME (RG: $rg)"
az aks get-credentials --name "$CLUSTER_NAME" --resource-group "$rg" --overwrite-existing

# === List namespaces ===
echo "📦 Namespaces in $CLUSTER_NAME:"
namespaces=$(kubectl get ns -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')
echo "$namespaces"

# === Create directory for this cluster ===
cluster_dir="$output_dir/$CLUSTER_NAME"
mkdir -p "$cluster_dir"

# === Dump Deployments & Services for each namespace ===
for ns in $namespaces; do
  echo "📄 Dumping YAML for namespace: $ns"
  ns_dir="$cluster_dir/$ns"
  mkdir -p "$ns_dir"
  kubectl get deploy,svc -n "$ns" -o yaml > "$ns_dir/${CLUSTER_NAME}_${ns}_export.yaml"
done

echo "✅ Export complete. All files saved to $output_dir."

