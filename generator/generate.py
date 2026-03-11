#!/usr/bin/env python3
"""Main entrypoint for the homelab network config generator.

Usage:
    python generator/generate.py list
    python generator/generate.py generate <device-name|all>
    python generator/generate.py deploy <device-name>
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

import jsonschema

from loader import (
    get_device_schema,
    list_devices,
    load_device_config,
    load_inventory,
    validate,
)
from renderer import TEMPLATE_FILES, render_device

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
BUILD_DIR = REPO_ROOT / "build"
SCRIPTS_DIR = REPO_ROOT / "scripts"


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
        display = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        logger.info("  Generated: %s", display)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_list(_args: argparse.Namespace) -> None:
    """List all devices discovered from the devices/ directory."""
    devices = list_devices()
    if not devices:
        print("No devices found in devices/ directory.")
        return
    print("Available devices:")
    for device in devices:
        print(f"  {device}")


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate configs for one or all devices."""
    target = args.device
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


def cmd_deploy(args: argparse.Namespace) -> None:
    """Check that all generated config files are present, then deploy via SSH.

    Deployment is handled by ``scripts/deploy.sh``.  This command acts as a
    pre-flight gate: if any expected output file is missing the command exits
    with an error so the operator knows to run ``generate <device>`` first.
    """
    device_name = args.device

    inventory = load_inventory()
    devices = inventory.get("devices", {})
    if device_name not in devices:
        logger.error("Device '%s' not found in inventory.", device_name)
        sys.exit(1)

    device_type = devices[device_name].get("type", "")
    expected_files = [output_name for _, output_name in TEMPLATE_FILES.get(device_type, [])]

    build_device_dir = BUILD_DIR / device_name

    if not build_device_dir.exists():
        logger.error(
            "Build directory not found: %s. Run 'generate %s' first.",
            build_device_dir,
            device_name,
        )
        sys.exit(1)

    missing = [f for f in expected_files if not (build_device_dir / f).exists()]
    if missing:
        logger.error(
            "Missing generated files for '%s': %s. Run 'generate %s' first.",
            device_name,
            ", ".join(missing),
            device_name,
        )
        sys.exit(1)

    logger.info(
        "All expected config files present for '%s'. Starting deploy...", device_name
    )
    deploy_script = SCRIPTS_DIR / "deploy.sh"
    result = subprocess.run([str(deploy_script), device_name], cwd=REPO_ROOT)
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Homelab network config generator.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # list
    subparsers.add_parser(
        "list",
        help="List available devices discovered from devices/ directory",
    )

    # generate
    gen_parser = subparsers.add_parser(
        "generate",
        help="Validate and render configs for a device",
    )
    gen_parser.add_argument(
        "device",
        metavar="<device-name|all>",
        help="Device name (must be present in inventory) or 'all'",
    )

    # deploy
    dep_parser = subparsers.add_parser(
        "deploy",
        help="Deploy generated configs to a device (build files must exist)",
    )
    dep_parser.add_argument(
        "device",
        metavar="<device-name>",
        help="Device name to deploy",
    )

    return parser


def main(args: list[str]) -> None:
    """Parse CLI arguments and dispatch to the appropriate subcommand."""
    parser = build_parser()
    parsed = parser.parse_args(args)

    if parsed.command == "list":
        cmd_list(parsed)
    elif parsed.command == "generate":
        cmd_generate(parsed)
    elif parsed.command == "deploy":
        cmd_deploy(parsed)


if __name__ == "__main__":
    main(sys.argv[1:])
