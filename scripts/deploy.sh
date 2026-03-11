#!/usr/bin/env bash
# deploy.sh - Deploy generated configs to an OpenWrt router
#
# Usage: ./scripts/deploy.sh <device-name>
#
# Steps:
#   1. Generate configs
#   2. Read host/user from inventory
#   3. Copy files to router /tmp/gitops-config
#   4. Backup router /etc/config
#   5. Replace router configs
#   6. Reload services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
    echo "Usage: $0 <device-name>" >&2
    exit 1
}

[[ $# -eq 1 ]] || usage
DEVICE="$1"

# ---------------------------------------------------------------------------
# 1. Generate configs
# ---------------------------------------------------------------------------
echo "[deploy] Generating configs for ${DEVICE}..."
cd "${REPO_ROOT}"
PYTHONPATH=generator python generator/generate.py generate "${DEVICE}"

BUILD_DIR="${REPO_ROOT}/build/${DEVICE}"
if [[ ! -d "${BUILD_DIR}" ]]; then
    echo "[deploy] ERROR: Build directory not found: ${BUILD_DIR}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Read host/user from inventory
# ---------------------------------------------------------------------------
INVENTORY="${REPO_ROOT}/inventory/devices.yaml"
HOST=$(python3 -c "
import yaml, sys
with open('${INVENTORY}') as f:
    inv = yaml.safe_load(f)
dev = inv['devices'].get('${DEVICE}')
if not dev:
    print('ERROR: device not found', file=sys.stderr)
    sys.exit(1)
print(dev['host'])
")
SSH_USER=$(python3 -c "
import yaml, sys
with open('${INVENTORY}') as f:
    inv = yaml.safe_load(f)
dev = inv['devices']['${DEVICE}']
print(dev.get('ssh_user', 'root'))
")

SSH_TARGET="${SSH_USER}@${HOST}"
echo "[deploy] Target: ${SSH_TARGET}"

# ---------------------------------------------------------------------------
# 3. Copy files to router /tmp/gitops-config
# ---------------------------------------------------------------------------
echo "[deploy] Copying configs to router..."
ssh "${SSH_TARGET}" "rm -rf /tmp/gitops-config && mkdir -p /tmp/gitops-config"
scp "${BUILD_DIR}"/* "${SSH_TARGET}:/tmp/gitops-config/"

# ---------------------------------------------------------------------------
# 4. Backup router /etc/config
# ---------------------------------------------------------------------------
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/etc/config-backup-${TIMESTAMP}"
echo "[deploy] Backing up router configs to ${BACKUP_DIR}..."
ssh "${SSH_TARGET}" "mkdir -p ${BACKUP_DIR} && cp /etc/config/* ${BACKUP_DIR}/"

# ---------------------------------------------------------------------------
# 5. Replace router configs
# ---------------------------------------------------------------------------
echo "[deploy] Installing new configs..."
for f in "${BUILD_DIR}"/*; do
    config_name="$(basename "${f}")"
    ssh "${SSH_TARGET}" "
        mv /etc/config/${config_name} /etc/config/${config_name}.old 2>/dev/null || true
        mv /tmp/gitops-config/${config_name} /etc/config/${config_name}
    "
done

# ---------------------------------------------------------------------------
# 6. Reload services
# ---------------------------------------------------------------------------
echo "[deploy] Reloading services..."
ssh "${SSH_TARGET}" "/etc/init.d/network reload"
ssh "${SSH_TARGET}" "wifi reload"
ssh "${SSH_TARGET}" "/etc/init.d/dnsmasq restart"

echo "[deploy] Deployment complete for ${DEVICE}."
