"""YAML loader with JSON Schema validation for homelab network configs."""

import json
import logging
from pathlib import Path
from typing import Any

import jsonschema
import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
INVENTORY_FILE = REPO_ROOT / "inventory" / "devices.yaml"
DEVICES_DIR = REPO_ROOT / "devices"


def load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file."""
    logger.debug("Loading YAML from %s", path)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    return data


def load_schema(schema_name: str) -> dict[str, Any]:
    """Load a JSON Schema by name."""
    schema_path = SCHEMAS_DIR / schema_name
    logger.debug("Loading schema from %s", schema_path)
    with open(schema_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate(data: dict[str, Any], schema_name: str) -> None:
    """Validate data dict against a named JSON Schema.

    Raises jsonschema.ValidationError on failure.
    """
    schema = load_schema(schema_name)
    jsonschema.validate(instance=data, schema=schema)
    logger.debug("Validation passed for schema %s", schema_name)


def load_inventory() -> dict[str, Any]:
    """Load the device inventory."""
    return load_yaml(INVENTORY_FILE)


def load_device_config(device_name: str) -> dict[str, Any]:
    """Load the YAML config for a named device."""
    config_path = DEVICES_DIR / f"{device_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Device config not found: {config_path}")
    return load_yaml(config_path)


def get_device_schema(device_type: str) -> str:
    """Map a device type string to a schema filename."""
    schema_map: dict[str, str] = {
        "openwrt-router": "router.schema.json",
    }
    if device_type not in schema_map:
        raise ValueError(f"Unknown device type '{device_type}'. No schema available.")
    return schema_map[device_type]


def list_devices() -> list[str]:
    """Return device names discovered from YAML files in the devices directory.

    The device name is the stem of each ``*.yaml`` file found, so a file named
    ``devices/flint2.yaml`` yields the device name ``flint2``.  This means no
    explicit registration in inventory is required to discover a device.
    """
    return sorted(p.stem for p in DEVICES_DIR.glob("*.yaml"))
