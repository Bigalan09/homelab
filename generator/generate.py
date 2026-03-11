#!/usr/bin/env python3
"""Main entrypoint for the homelab network config generator.

Usage:
    python generator/generate.py list
    python generator/generate.py validate <device-name|all>
    python generator/generate.py generate <device-name|all> [--dry-run] [--output-dir DIR]
    python generator/generate.py deploy <device-name>
    python generator/generate.py status
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


def generate_device(
    device_name: str,
    inventory: dict,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> None:
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

    if dry_run:
        logger.info(
            "[dry-run] Would render configs for '%s' to %s",
            device_name,
            (output_dir or BUILD_DIR) / device_name,
        )
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
    """Validate the config for a single device.  Returns True on success."""
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


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> None:
    """List all devices discovered from the devices/ directory."""
    devices = list_devices()
    if not devices:
        print("No devices found in devices/ directory.")
        return

    inventory = load_inventory()
    inv_devices = inventory.get("devices", {})

    if args.long:
        # Build row data in a single pass, then determine column widths
        rows = []
        for device in devices:
            meta = inv_devices.get(device, {})
            host = meta.get("host", "-")
            dtype = meta.get("type", "-")
            expected = [n for _, n in TEMPLATE_FILES.get(dtype, [])]
            build_device_dir = BUILD_DIR / device
            if expected and build_device_dir.exists() and all(
                (build_device_dir / f).exists() for f in expected
            ):
                built = "yes"
            else:
                built = "no"
            rows.append((device, host, dtype, built))

        col_device = max(len("DEVICE"), *(len(r[0]) for r in rows))
        col_host = max(len("HOST"), *(len(r[1]) for r in rows))
        col_type = max(len("TYPE"), *(len(r[2]) for r in rows))

        header = f"{'DEVICE':<{col_device}}  {'HOST':<{col_host}}  {'TYPE':<{col_type}}  BUILT"
        print(header)
        print("-" * len(header))
        for device, host, dtype, built in rows:
            print(f"{device:<{col_device}}  {host:<{col_host}}  {dtype:<{col_type}}  {built}")
    else:
        print("Available devices:")
        for device in devices:
            print(f"  {device}")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate device config(s) against their schemas without generating files."""
    target = args.device
    inventory = load_inventory()

    if target == "all":
        devices = inventory.get("devices", {})
        if not devices:
            logger.warning("No devices found in inventory.")
            return
        failed = []
        for device_name in sorted(devices):
            if not validate_device(device_name, inventory):
                failed.append(device_name)
        if failed:
            logger.error("Validation failed for: %s", ", ".join(failed))
            sys.exit(1)
    else:
        if not validate_device(target, inventory):
            sys.exit(1)


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate configs for one or all devices."""
    target = args.device
    inventory = load_inventory()
    output_dir = Path(args.output_dir) if args.output_dir else None
    dry_run = args.dry_run

    if target == "all":
        devices = inventory.get("devices", {})
        if not devices:
            logger.warning("No devices found in inventory.")
            return
        for device_name in sorted(devices):
            generate_device(device_name, inventory, output_dir=output_dir, dry_run=dry_run)
    else:
        generate_device(target, inventory, output_dir=output_dir, dry_run=dry_run)


def cmd_status(_args: argparse.Namespace) -> None:
    """Show the build status of generated configs for all devices."""
    devices = list_devices()
    if not devices:
        print("No devices found in devices/ directory.")
        return

    inventory = load_inventory()
    inv_devices = inventory.get("devices", {})

    col_device = max(len("DEVICE"), *(len(d) for d in devices))
    col_file = max(len("FILE"), 10)

    header = f"{'DEVICE':<{col_device}}  {'FILE':<{col_file}}  STATUS"
    print(header)
    print("-" * len(header))

    for device in devices:
        meta = inv_devices.get(device, {})
        device_type = meta.get("type", "")
        expected = [n for _, n in TEMPLATE_FILES.get(device_type, [])]
        build_device_dir = BUILD_DIR / device

        if not expected:
            print(f"{device:<{col_device}}  {'(unknown type)':<{col_file}}  -")
            continue

        for fname in expected:
            fpath = build_device_dir / fname
            if fpath.exists():
                status = "OK"
            else:
                status = "MISSING"
            print(f"{device:<{col_device}}  {fname:<{col_file}}  {status}")


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
        epilog=(
            "Examples:\n"
            "  %(prog)s list -l                       # list devices with details\n"
            "  %(prog)s validate flint2               # validate a device config\n"
            "  %(prog)s validate all                  # validate all device configs\n"
            "  %(prog)s generate flint2               # render configs for flint2\n"
            "  %(prog)s generate all --dry-run        # preview what would be generated\n"
            "  %(prog)s generate flint2 --output-dir /tmp/out\n"
            "  %(prog)s status                        # show build status\n"
            "  %(prog)s deploy flint2                 # deploy to device"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global verbosity flags
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    verbosity.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Show only error messages",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # list
    list_parser = subparsers.add_parser(
        "list",
        help="List available devices discovered from devices/ directory",
    )
    list_parser.add_argument(
        "-l", "--long",
        action="store_true",
        help="Show host, type, and build status for each device",
    )

    # validate
    val_parser = subparsers.add_parser(
        "validate",
        help="Validate device config(s) against their schemas without generating files",
    )
    val_parser.add_argument(
        "device",
        metavar="<device-name|all>",
        help="Device name (must be present in inventory) or 'all'",
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
    gen_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show what would be generated without writing any files",
    )
    gen_parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Write generated files to DIR/<device> instead of the default build/ directory",
    )

    # status
    subparsers.add_parser(
        "status",
        help="Show per-device build status (which config files have been generated)",
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

    # Apply global verbosity flags
    root_logger = logging.getLogger()
    if parsed.verbose:
        root_logger.setLevel(logging.DEBUG)
    elif parsed.quiet:
        root_logger.setLevel(logging.ERROR)

    if parsed.command == "list":
        cmd_list(parsed)
    elif parsed.command == "validate":
        cmd_validate(parsed)
    elif parsed.command == "generate":
        cmd_generate(parsed)
    elif parsed.command == "status":
        cmd_status(parsed)
    elif parsed.command == "deploy":
        cmd_deploy(parsed)


if __name__ == "__main__":
    main(sys.argv[1:])
