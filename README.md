# homelab-gitops-network

A **GitOps-style homelab network configuration system** for OpenWrt routers.

Network config lives in YAML, gets validated, rendered into OpenWrt UCI config files, and deployed safely via SSH with automatic backup and rollback support.

---

## Architecture

```
Git Repository
      │
      ▼
YAML network definition   (devices/router1.yaml)
      │
      ▼
Python generator          (generator/generate.py)
      │  • loads inventory
      │  • validates YAML against JSON Schema
      │  • renders Jinja2 templates
      ▼
Rendered OpenWrt configs  (build/router1/network, wireless, dhcp, ...)
      │
      ▼
SSH deploy script         (scripts/deploy.sh)
      │  • backs up /etc/config
      │  • installs new configs
      │  • reloads services
      ▼
OpenWrt Router
```

---

## Repository Structure

```
homelab-gitops-network/
│
├── README.md               ← this file
├── pyproject.toml          ← Python project metadata
├── requirements.txt        ← Python dependencies
├── Makefile                ← developer workflow shortcuts
│
├── inventory/
│   └── devices.yaml        ← device inventory (hosts, types, SSH users)
│
├── devices/
│   └── router1.yaml        ← per-device YAML configuration (single source of truth)
│
├── schemas/
│   └── router.schema.json  ← JSON Schema for router YAML validation
│
├── templates/
│   └── openwrt/
│       ├── network.j2      ← /etc/config/network
│       ├── wireless.j2     ← /etc/config/wireless
│       ├── dhcp.j2         ← /etc/config/dhcp
│       ├── firewall.j2     ← /etc/config/firewall
│       └── system.j2       ← /etc/config/system
│
├── generator/
│   ├── generate.py         ← CLI entrypoint
│   ├── loader.py           ← YAML loading + schema validation
│   └── renderer.py         ← Jinja2 template rendering
│
├── scripts/
│   ├── deploy.sh           ← generate + backup + deploy + reload
│   ├── backup.sh           ← download /etc/config locally
│   └── rollback.sh         ← restore last router backup
│
├── build/                  ← generated configs (git-ignored)
├── backups/                ← local backups (git-ignored)
│
├── tests/
│   └── test_rendering.py   ← pytest test suite
│
└── .github/
    └── workflows/
        └── ci.yml          ← GitHub Actions CI pipeline
```

---

## YAML Design

All device configuration lives in `devices/<device-name>.yaml`. Example:

```yaml
hostname: router1

system:
  hostname: router1
  timezone: UTC

network:
  lan:
    type: interface
    device: br-lan
    proto: static
    ipaddr: 192.168.10.1
    netmask: 255.255.255.0
  wan:
    type: interface
    device: eth0
    proto: dhcp

wireless:
  radios:
    radio0:
      type: mac80211
      channel: 11
      country: GB
  interfaces:
    wifi0:
      device: radio0
      mode: ap
      ssid: HomelabWiFi
      encryption: psk2
      key: changeme123

dhcp:
  lan:
    start: 100
    limit: 150
    leasetime: 12h
```

Each network interface **must** include a `proto` field. Wireless interfaces **must** include `ssid`. These constraints are enforced by the JSON Schema validator.

---

## GitOps Workflow

1. **Edit** `devices/router1.yaml` to change your network configuration.
2. **Commit and push** to the repository.
3. **CI** automatically validates the YAML and renders configs.
4. **Deploy** manually (or automate via CD):
   ```bash
   make deploy DEVICE=router1
   ```

---

## Developer Setup

Requires Python 3.11+ and `make`.

```bash
# Create virtualenv and install dependencies
make setup

# Generate configs for router1
make generate DEVICE=router1

# Generate configs for all devices
make generate-all

# Run the test suite
make test

# Remove generated build output
make clean
```

---

## Deploying to a Router

> Prerequisites: SSH key-based auth to your OpenWrt router.

```bash
# Deploy configs to router1
./scripts/deploy.sh router1
# or via make
make deploy DEVICE=router1
```

The deploy script will:
1. Generate fresh configs from YAML
2. Read the target host from `inventory/devices.yaml`
3. Copy generated files to `/tmp/gitops-config` on the router
4. Backup existing `/etc/config` to `/etc/config-backup-YYYYMMDD-HHMMSS`
5. Replace the configs
6. Reload `network`, `wifi`, and `dnsmasq` services

---

## Rollback Procedure

If something goes wrong after a deploy, roll back to the last backup:

```bash
./scripts/rollback.sh router1
```

This SSHes to the router, finds the most recent `/etc/config-backup-*` directory, copies it back over `/etc/config`, and reloads services.

---

## Local Backup

Download a copy of the router's live `/etc/config` directory:

```bash
./scripts/backup.sh router1
# Saved to: backups/router1/<timestamp>.tar.gz
```

---

## Adding New Devices

### New router

1. Add an entry to `inventory/devices.yaml`:
   ```yaml
   devices:
     router2:
       type: openwrt-router
       host: 192.168.1.2
       ssh_user: root
       config_file: router2.yaml
   ```
2. Create `devices/router2.yaml` following the same structure as `router1.yaml`.
3. Generate and deploy:
   ```bash
   make generate DEVICE=router2
   make deploy DEVICE=router2
   ```

### Future device types (access points, managed switches)

The architecture is structured to support additional device types:

- Add a new device YAML in `devices/` (e.g. `ap1.yaml`, `switch1.yaml`)
- Add a corresponding schema in `schemas/` (e.g. `ap.schema.json`)
- Add a template directory (e.g. `templates/openwrt-ap/`, `templates/switch/`)
- Register the new type in `generator/loader.py` (`get_device_schema`) and `generator/renderer.py` (`TEMPLATE_DIRS`, `TEMPLATE_FILES`)
- Add the device to `inventory/devices.yaml`

---

## CI Pipeline

GitHub Actions automatically runs on every push and pull request:

1. Install Python 3.11
2. Install dependencies (`pip install -r requirements.txt`)
3. Validate YAML and generate configs (`python generator/generate.py router1`)
4. Run tests (`pytest tests/ -v`)

See `.github/workflows/ci.yml`.

---

## Topology

Current implementation supports a single router. The architecture is ready for:

```
Internet
   │
OpenWrt Router   ← implemented
   │
Managed Switch   ← future
   │
Access Point     ← future
   │
Clients
```