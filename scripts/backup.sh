#!/usr/bin/env bash
# backup.sh - Download router /etc/config locally
#
# Usage: ./scripts/backup.sh <device-name>
#
# Saves backup to: backups/<device-name>/<timestamp>.tar.gz

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
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="${REPO_ROOT}/backups/${DEVICE}"
BACKUP_FILE="${BACKUP_DIR}/${TIMESTAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"

echo "[backup] Creating remote archive of /etc/config on ${SSH_TARGET}..."
ssh "${SSH_TARGET}" "tar czf /tmp/config-backup.tar.gz -C /etc config"

echo "[backup] Downloading backup to ${BACKUP_FILE}..."
scp "${SSH_TARGET}:/tmp/config-backup.tar.gz" "${BACKUP_FILE}"

ssh "${SSH_TARGET}" "rm -f /tmp/config-backup.tar.gz"

echo "[backup] Backup saved to ${BACKUP_FILE}."
