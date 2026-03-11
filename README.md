# homelab-gitops-network

A **GitOps-style homelab network configuration system** for OpenWrt routers, combining both network operations tooling and network design documentation in a single repository.

Network config lives in YAML, gets validated, rendered into OpenWrt UCI config files, and deployed safely via SSH with automatic backup and rollback support.
Network design documentation is generated from the YAML data files under `data/network/` and the Jinja2 templates under `templates/network/`.

---

## Architecture

```
Git Repository
      │
      ├─── Network Design Data (data/network/*.yaml)
      │         │
      │         ▼
      │    Doc generator (scripts/generate-docs.py)
      │         │  • loads all YAML data files
      │         │  • renders Jinja2 doc templates
      │         ▼
      │    Generated docs (docs/network/*.md)
      │
      └─── OpenWrt Device Configs (devices/<device>.yaml)
                │
                ▼
         Python generator (generator/generate.py)
                │  • loads inventory
                │  • validates YAML against JSON Schema
                │  • renders Jinja2 templates
                ▼
         Rendered OpenWrt configs (build/<device>/network, wireless, dhcp, ...)
                │
                ▼
         SSH deploy script (scripts/deploy.sh)
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
├── data/
│   └── network/            ← network design data (single source of truth)
│       ├── devices.yaml    ← infrastructure devices and external zones
│       ├── dns.yaml        ← DNS zones and records
│       ├── ports.yaml      ← service port assignments
│       ├── services.yaml   ← homelab services
│       ├── site.yaml       ← site-level metadata
│       ├── tailnet.yaml    ← Tailscale / tailnet configuration
│       ├── wireless.yaml   ← wireless SSIDs and radio config
│       └── zones.yaml      ← VLAN zones
│
├── docs/
│   └── network/            ← generated documentation (do not edit directly)
│       ├── README.md
│       ├── architecture.md
│       ├── dns-and-tailnet.md
│       ├── operations.md
│       ├── physical-topology.md
│       └── policy-and-exposure.md
│
├── inventory/
│   └── devices.yaml        ← device inventory (hosts, types, SSH users)
│
├── devices/
│   └── flint2.yaml         ← per-device OpenWrt YAML configuration
│
├── schemas/
│   └── router.schema.json  ← JSON Schema for router YAML validation
│
├── templates/
│   ├── network/            ← Jinja2 templates for documentation
│   │   ├── README.md.j2
│   │   ├── architecture.md.j2
│   │   ├── dns-and-tailnet.md.j2
│   │   ├── operations.md.j2
│   │   ├── physical-topology.md.j2
│   │   └── policy-and-exposure.md.j2
│   └── openwrt/            ← Jinja2 templates for OpenWrt UCI configs
│       ├── network.j2      ← /etc/config/network
│       ├── wireless.j2     ← /etc/config/wireless
│       ├── dhcp.j2         ← /etc/config/dhcp
│       ├── firewall.j2     ← /etc/config/firewall
│       └── system.j2       ← /etc/config/system
│
├── generator/
│   ├── generate.py         ← CLI entrypoint (list / generate / deploy)
│   ├── loader.py           ← YAML loading + schema validation + device discovery
│   └── renderer.py         ← Jinja2 template rendering
│
├── scripts/
│   ├── deploy.sh           ← generate + backup + deploy + reload
│   ├── backup.sh           ← download /etc/config locally
│   ├── rollback.sh         ← restore last router backup
│   ├── generate-docs.py    ← regenerate docs/network/ from data/network/
│   └── generate-readme.py  ← compile docs/ into a single README
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

All device configuration lives in `devices/<device-name>.yaml`.  The device
name is taken directly from the filename stem — no additional registration is
needed to discover it.  Example (`devices/flint2.yaml`):

```yaml
hostname: flint2

system:
  hostname: flint2
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

## CLI Reference

The generator exposes three subcommands:

```bash
# List all devices discovered from the devices/ directory
python generator/generate.py list

# Generate (validate + render) configs for one device
python generator/generate.py generate <device-name>

# Generate configs for every device in inventory
python generator/generate.py generate all

# Deploy configs to a device (build files must already exist)
python generator/generate.py deploy <device-name>
```

The `deploy` subcommand performs a **pre-flight check**: it verifies that all
expected config files are present in `build/<device-name>/` before attempting
any SSH operations.  If files are missing it exits with an error and tells you
to run `generate <device-name>` first.

---

## GitOps Workflow

### Network design changes
1. **Edit** `data/network/*.yaml` to update your network design.
2. **Regenerate docs**: `make docs`
3. **Commit everything** (`data/`, `docs/network/`) together — data and docs stay in sync.

### OpenWrt device config changes
1. **Edit** `devices/<device-name>.yaml` to change your router configuration.
2. **Commit and push** to the repository.
3. **CI** automatically validates the YAML and renders configs.
4. **Deploy** manually (or automate via CD):
   ```bash
   make generate DEVICE=flint2
   make deploy DEVICE=flint2
   ```

---

## Developer Setup

Requires Python 3.11+ and `make`.

```bash
# Create virtualenv and install dependencies
make setup

# List all devices discovered in devices/
make list

# Generate configs for flint2
make generate DEVICE=flint2

# Generate configs for all devices
make generate-all

# Regenerate docs/network/ from data/network/ and templates/network/
make docs

# Run the test suite
make test

# Remove generated build output
make clean
```

---

## Deploying to a Router

> Prerequisites: SSH key-based auth to your OpenWrt router.

```bash
# 1. Generate fresh configs
make generate DEVICE=flint2

# 2. Deploy to the router (pre-flight check runs automatically)
make deploy DEVICE=flint2

# or using the scripts directly
./scripts/deploy.sh flint2
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
./scripts/rollback.sh flint2
```

This SSHes to the router, finds the most recent `/etc/config-backup-*` directory, copies it back over `/etc/config`, and reloads services.

---

## Local Backup

Download a copy of the router's live `/etc/config` directory:

```bash
./scripts/backup.sh flint2
# Saved to: backups/flint2/<timestamp>.tar.gz
```

---

## Adding New Devices

### New router

1. Create `devices/<device-name>.yaml` following the same structure as `flint2.yaml`.
2. Add an entry to `inventory/devices.yaml`:
   ```yaml
   devices:
     my-router:
       type: openwrt-router
       host: 192.168.1.2
       ssh_user: root
   ```
3. Generate and deploy:
   ```bash
   make generate DEVICE=my-router
   make deploy DEVICE=my-router
   ```

The device name is derived automatically from the YAML filename — you can
verify it is detected with `make list`.

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
3. Validate YAML and generate configs (`python generator/generate.py generate flint2`)
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
