"""Core business logic for the homelab network config generator.

This module contains the device-level generate and validate operations used by
the CLI.  Keeping them here keeps the CLI entry point thin and makes the logic
easy to import and test directly.
"""

import logging
import sys
from pathlib import Path

import jsonschema

from loader import (
    get_device_schema,
    load_device_config,
    validate,
)
from renderer import TEMPLATE_FILES, render_device

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
BUILD_DIR = REPO_ROOT / "build"


def generate_device(
    device_name: str,
    inventory: dict,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> None:
    """Validate and render configs for a single device.

    Writes rendered files to ``output_dir/<device_name>`` (defaults to
    ``build/<device_name>`` when *output_dir* is ``None``).  When *dry_run* is
    ``True`` the files are not written; only logging output is produced.
    """
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

    if dry_run:
        dest = (output_dir or BUILD_DIR) / device_name
        logger.info("[dry-run] Would render configs for '%s' to %s", device_name, dest)
        for _, output_name in TEMPLATE_FILES.get(device_type, []):
            logger.info("[dry-run]   %s", output_name)
        return

    dest = (output_dir or BUILD_DIR) / device_name
    logger.info("Rendering configs to %s", dest)
    results = render_device(device_type, config, dest)

    for name, path in sorted(results.items()):
        display = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        logger.info("  Generated: %s", display)


def validate_device(device_name: str, inventory: dict) -> bool:
    """Validate the config for a single device against its schema.

    Returns ``True`` on success, ``False`` on any failure (the error is logged
    but no exception is raised so callers can collect results across multiple
    devices).
    """
    devices = inventory.get("devices", {})
    if device_name not in devices:
        logger.error("Device '%s' not found in inventory.", device_name)
        return False

    device_meta = devices[device_name]
    device_type = device_meta.get("type", "")

    try:
        config = load_device_config(device_name)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return False

    try:
        schema_name = get_device_schema(device_type)
    except ValueError as exc:
        logger.error("%s", exc)
        return False

    try:
        validate(config, schema_name)
    except jsonschema.ValidationError as exc:
        logger.error("Schema validation failed for '%s': %s", device_name, exc.message)
        return False

    logger.info("Config for '%s' is valid.", device_name)
    return True
