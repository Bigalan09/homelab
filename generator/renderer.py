"""Jinja2 template renderer for OpenWrt UCI config files."""

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_BASE = REPO_ROOT / "templates"

# Mapping from device type to template directory
TEMPLATE_DIRS: dict[str, str] = {
    "openwrt-router": "openwrt",
}

# Templates to render per device type, and the output filename
TEMPLATE_FILES: dict[str, list[tuple[str, str]]] = {
    "openwrt-router": [
        ("network.j2", "network"),
        ("wireless.j2", "wireless"),
        ("dhcp.j2", "dhcp"),
        ("firewall.j2", "firewall"),
        ("system.j2", "system"),
    ],
}


def _build_env(template_dir: Path) -> Environment:
    """Create a Jinja2 environment for the given template directory."""
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(
    template_name: str,
    context: dict[str, Any],
    template_dir: Path,
) -> str:
    """Render a single Jinja2 template with the given context."""
    env = _build_env(template_dir)
    template = env.get_template(template_name)
    return template.render(**context)


def render_device(
    device_type: str,
    config: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Render all templates for a device and write output files.

    Returns a mapping of config name → output path.
    """
    if device_type not in TEMPLATE_DIRS:
        raise ValueError(f"No templates registered for device type '{device_type}'")

    template_dir = TEMPLATES_BASE / TEMPLATE_DIRS[device_type]
    template_files = TEMPLATE_FILES[device_type]

    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Path] = {}
    for template_name, output_name in template_files:
        logger.info("Rendering template %s → %s", template_name, output_name)
        rendered = render_template(template_name, config, template_dir)
        output_path = output_dir / output_name
        output_path.write_text(rendered, encoding="utf-8")
        logger.info("Written %s", output_path)
        results[output_name] = output_path

    return results
