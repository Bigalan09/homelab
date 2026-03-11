#!/usr/bin/env bash
# rollback.sh - Restore the last config backup on an OpenWrt router
#
# Usage: ./scripts/rollback.sh <device-name>
#
# Steps:
#   1. SSH to router
#   2. Find latest /etc/config-backup-*
#   3. Restore files
#   4. Reload services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
    echo "Usage: $0 <device-name>" >&2
    exit 1
}

[[ $# -eq 1 ]] || usage
DEVICE="$1"

INVENTORY="${REPO_ROOT}/docs/inventory/devices.yaml"
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
echo "[rollback] Target: ${SSH_TARGET}"

# ---------------------------------------------------------------------------
# 1-2. Find latest backup directory on router
# ---------------------------------------------------------------------------
echo "[rollback] Looking for latest backup..."
LATEST_BACKUP=$(ssh "${SSH_TARGET}" "ls -1d /etc/config-backup-* 2>/dev/null | sort | tail -1")

if [[ -z "${LATEST_BACKUP}" ]]; then
    echo "[rollback] ERROR: No backup directories found on router." >&2
    exit 1
fi

echo "[rollback] Restoring from: ${LATEST_BACKUP}"

# ---------------------------------------------------------------------------
# 3. Restore files
# ---------------------------------------------------------------------------
ssh "${SSH_TARGET}" "cp ${LATEST_BACKUP}/* /etc/config/"

# ---------------------------------------------------------------------------
# 4. Reload services
# ---------------------------------------------------------------------------
echo "[rollback] Reloading services..."
ssh "${SSH_TARGET}" "/etc/init.d/network reload"
ssh "${SSH_TARGET}" "wifi reload"
ssh "${SSH_TARGET}" "/etc/init.d/dnsmasq restart"

echo "[rollback] Rollback complete. Restored from ${LATEST_BACKUP}."
