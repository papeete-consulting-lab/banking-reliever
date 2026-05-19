#!/usr/bin/env bash

set -euo pipefail

IMAGE="structurizr:yo-latest"
CONTAINER_NAME="structurizr-local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_WORKSPACE_DIR="${HOST_WORKSPACE_DIR:-${SCRIPT_DIR}/model}"
CONTAINER_WORKSPACE_DIR="/usr/local/structurizr"
PORT="8081"

if [[ -f "${SCRIPT_DIR}/.env" ]]; then
	set -a
	source "${SCRIPT_DIR}/.env"
	set +a
fi

if [[ -z "${STRUCTURIZR_LICENSE:-}" ]]; then
	echo "Error: STRUCTURIZR_LICENSE is not set." >&2
	echo "Create/update ${SCRIPT_DIR}/.env with STRUCTURIZR_LICENSE=<your-license-key>." >&2
	exit 1
fi

if [[ ! -d "${HOST_WORKSPACE_DIR}" ]]; then
	echo "Error: host directory does not exist: ${HOST_WORKSPACE_DIR}" >&2
	exit 1
fi

echo "Starting Structurizr locally..."
echo "Image: ${IMAGE}"
echo "Host workspace: ${HOST_WORKSPACE_DIR}"
echo "Container workspace: ${CONTAINER_WORKSPACE_DIR}"
echo "URL: http://localhost:${PORT}"

# Remove previous container if it exists.
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
	docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

docker run --name "${CONTAINER_NAME}" \
	--user 0:0 \
	--env "STRUCTURIZR_LICENSE=${STRUCTURIZR_LICENSE}" \
	--publish "${PORT}:8080" \
	--volume "${HOST_WORKSPACE_DIR}:${CONTAINER_WORKSPACE_DIR}" \
	--detach \
	"${IMAGE}" server

echo "Structurizr container '${CONTAINER_NAME}' is running."