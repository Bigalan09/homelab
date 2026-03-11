#!/usr/bin/env python3
"""Main entrypoint for the homelab network config generator.

Usage:
    python generator/generate.py router1
    python generator/generate.py all
"""

import logging
import sys
from pathlib import Path
from typing import NoReturn

import jsonschema

from loader import get_device_schema, load_device_config, load_inventory, validate
from renderer import render_device

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
BUILD_DIR = REPO_ROOT / "build"


def generate_device(device_name: str, inventory: dict) -> None:
    """Generate configs for a single device."""
    devices = inventory.get("devices", {})
    if device_name not in devices:
        logger.error("Device '%s' not found in inventory.", device_name)
        sys.exit(1)

    device_meta = devices[device_name]
    device_type = device_meta.get("type", "")

    logger.info("Loading config for device '%s' (type=%s)", device_name, device_type)
    config = load_device_config(device_name)

    schema_name = get_device_schema(device_type)
    logger.info("Validating config against schema '%s'", schema_name)
    try:
        validate(config, schema_name)
    except jsonschema.ValidationError as exc:
        logger.error("Schema validation failed for '%s': %s", device_name, exc.message)
        sys.exit(1)

    output_dir = BUILD_DIR / device_name
    logger.info("Rendering configs to %s", output_dir)
    results = render_device(device_type, config, output_dir)

    for name, path in sorted(results.items()):
        logger.info("  Generated: %s", path.relative_to(REPO_ROOT))


def main(args: list[str]) -> None:
    """Parse CLI arguments and run generation."""
    if len(args) != 1:
        print(f"Usage: python {Path(__file__).name} <device-name|all>", file=sys.stderr)
        sys.exit(1)

    target = args[0]

    inventory = load_inventory()

    if target == "all":
        devices = inventory.get("devices", {})
        if not devices:
            logger.warning("No devices found in inventory.")
            return
        for device_name in sorted(devices):
            generate_device(device_name, inventory)
    else:
        generate_device(target, inventory)


if __name__ == "__main__":
    main(sys.argv[1:])
