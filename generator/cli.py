#!/usr/bin/env python3
"""Homelab CLI entry point.

Usage:
    homelab list [-l]
    homelab validate <device-name|all>
    homelab generate <device-name|all> [--dry-run] [--output-dir DIR]
    homelab status
    homelab deploy <device-name>
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

import core
from core import generate_device, validate_device
from loader import list_devices, load_inventory
from renderer import TEMPLATE_FILES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


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
            build_device_dir = core.BUILD_DIR / device
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
        build_device_dir = core.BUILD_DIR / device

        if not expected:
            print(f"{device:<{col_device}}  {'(unknown type)':<{col_file}}  -")
            continue

        for fname in expected:
            fpath = build_device_dir / fname
            status = "OK" if fpath.exists() else "MISSING"
            print(f"{device:<{col_device}}  {fname:<{col_file}}  {status}")


def cmd_deploy(args: argparse.Namespace) -> None:
    """Check that all generated config files are present, then deploy via SSH.

    Deployment is handled by ``scripts/deploy.sh``.  This command acts as a
    pre-flight gate: if any expected output file is missing the command exits
    with an error so the operator knows to run ``homelab generate <device>``
    first.
    """
    device_name = args.device

    inventory = load_inventory()
    devices = inventory.get("devices", {})
    if device_name not in devices:
        logger.error("Device '%s' not found in inventory.", device_name)
        sys.exit(1)

    device_type = devices[device_name].get("type", "")
    expected_files = [output_name for _, output_name in TEMPLATE_FILES.get(device_type, [])]

    build_device_dir = core.BUILD_DIR / device_name

    if not build_device_dir.exists():
        logger.error(
            "Build directory not found: %s. Run 'homelab generate %s' first.",
            build_device_dir,
            device_name,
        )
        sys.exit(1)

    missing = [f for f in expected_files if not (build_device_dir / f).exists()]
    if missing:
        logger.error(
            "Missing generated files for '%s': %s. Run 'homelab generate %s' first.",
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
        prog="homelab",
        description="Homelab network config generator and deployment tool.",
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
        help="Deploy generated configs to a device via SSH (build files must exist)",
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
