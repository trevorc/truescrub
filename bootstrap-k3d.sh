#!/bin/sh
# Bootstrap a local k3d development cluster.
#
# Usage: ./bootstrap-k3d.sh [-n] [-d] <cluster-name>
#
# Flags:
#   -n  dry-run: print intended actions without executing
#   -d  destroy cluster and registry
#
set -eu

REPO_ROOT="$(cd "$(dirname "$0")" && pwd -P)"

usage() {
  echo "Usage: $0 [-n] [-d] <cluster-name>" >&2
  exit 1
}

DRY=
DESTROY=
while getopts "nd" opt; do
  case "$opt" in
    n) DRY=1 ;;
    d) DESTROY=1 ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))

[ $# -ne 1 ] && usage

CLUSTER_NAME=$1
CONFIG_FILE="$REPO_ROOT/k3d-config.yaml"
REGISTRY_NAME="${CLUSTER_NAME}-registry"

# In dry-run mode: print action instead of executing it.
run() {
  if [ -n "$DRY" ]; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

if [ -z "$DRY" ]; then
  command -vV kapp >/dev/null
  systemctl --user enable --now podman.socket
  DOCKER_SOCK="$(podman info -f '{{.Host.RemoteSocket.Path}}')"
  export DOCKER_SOCK
  export DOCKER_HOST="unix://${DOCKER_SOCK}"
fi

if [ -n "$DESTROY" ]; then
  echo "▸ Destroying cluster '${CLUSTER_NAME}'..."
  run k3d cluster delete "${CLUSTER_NAME}"
  run k3d registry delete "${REGISTRY_NAME}"
  exit 0
fi

# k3d does not support declarative registry management for podman:
# https://k3d.io/v5.9.0/usage/advanced/podman/#creating-local-registries
if ! k3d registry list "${REGISTRY_NAME}" >/dev/null 2>&1; then
  echo "▸ Creating registry '${REGISTRY_NAME}'..."
  run k3d registry create "${REGISTRY_NAME}" --port "127.0.0.1:random" --default-network podman
fi

if k3d cluster list "${CLUSTER_NAME}" >/dev/null 2>&1; then
  echo "▸ Starting existing cluster '${CLUSTER_NAME}'..."
  run k3d cluster start "${CLUSTER_NAME}"
else
  echo "▸ Creating cluster '${CLUSTER_NAME}'..."
  run k3d cluster create "${CLUSTER_NAME}" \
      --registry-use "${REGISTRY_NAME}" \
      --config "${CONFIG_FILE}"
fi

echo "✅ Dev cluster ready (context: k3d-${CLUSTER_NAME})"
