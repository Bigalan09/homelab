"""Tests for the homelab network config generator and renderer."""

import sys
from pathlib import Path

import pytest

# Make the generator package importable
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "generator"))

from loader import (  # noqa: E402
    get_device_schema,
    load_device_config,
    load_inventory,
    validate,
)
from renderer import render_device, render_template  # noqa: E402


TEMPLATES_DIR = REPO_ROOT / "templates" / "openwrt"


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------


def test_load_inventory():
    """Inventory loads and contains expected keys."""
    inv = load_inventory()
    assert "devices" in inv
    assert "router1" in inv["devices"]


def test_inventory_router1_fields():
    """router1 inventory entry has required fields."""
    inv = load_inventory()
    device = inv["devices"]["router1"]
    assert device["type"] == "openwrt-router"
    assert "host" in device
    assert "ssh_user" in device


def test_load_device_config():
    """Device YAML loads correctly."""
    config = load_device_config("router1")
    assert config["hostname"] == "router1"
    assert "network" in config
    assert "wireless" in config
    assert "dhcp" in config


def test_load_device_config_missing():
    """Loading a non-existent device raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_device_config("nonexistent_device_xyz")


def test_schema_mapping():
    """Known device type returns correct schema filename."""
    assert get_device_schema("openwrt-router") == "router.schema.json"


def test_schema_mapping_unknown():
    """Unknown device type raises ValueError."""
    with pytest.raises(ValueError):
        get_device_schema("unknown-device-type")


def test_validate_router1():
    """router1 YAML is valid against the router schema."""
    config = load_device_config("router1")
    # Should not raise
    validate(config, "router.schema.json")


def test_validate_missing_required():
    """Config missing required fields fails validation."""
    import jsonschema

    with pytest.raises(jsonschema.ValidationError):
        validate({"hostname": "test"}, "router.schema.json")


# ---------------------------------------------------------------------------
# Template rendering tests
# ---------------------------------------------------------------------------


def test_render_network_template():
    """Network template renders expected UCI syntax."""
    config = load_device_config("router1")
    output = render_template("network.j2", config, TEMPLATES_DIR)

    assert "config interface 'lan'" in output
    assert "config interface 'wan'" in output
    assert "option proto 'static'" in output
    assert "option ipaddr '192.168.10.1'" in output
    assert "option proto 'dhcp'" in output


def test_render_wireless_template():
    """Wireless template renders expected UCI syntax."""
    config = load_device_config("router1")
    output = render_template("wireless.j2", config, TEMPLATES_DIR)

    assert "config wifi-device 'radio0'" in output
    assert "config wifi-iface 'wifi0'" in output
    assert "option ssid 'HomelabWiFi'" in output
    assert "option encryption 'psk2'" in output
    assert "option mode 'ap'" in output


def test_render_dhcp_template():
    """DHCP template renders expected UCI syntax."""
    config = load_device_config("router1")
    output = render_template("dhcp.j2", config, TEMPLATES_DIR)

    assert "config dhcp 'lan'" in output
    assert "option start '100'" in output
    assert "option limit '150'" in output
    assert "option leasetime '12h'" in output


def test_render_firewall_template():
    """Firewall template renders expected UCI syntax."""
    config = load_device_config("router1")
    output = render_template("firewall.j2", config, TEMPLATES_DIR)

    assert "config defaults" in output
    assert "config zone" in output
    assert "config forwarding" in output
    assert "option name 'lan'" in output
    assert "option name 'wan'" in output


def test_render_system_template():
    """System template renders expected UCI syntax."""
    config = load_device_config("router1")
    output = render_template("system.j2", config, TEMPLATES_DIR)

    assert "config system" in output
    assert "option hostname 'router1'" in output
    assert "option timezone 'UTC'" in output


# ---------------------------------------------------------------------------
# End-to-end generation test
# ---------------------------------------------------------------------------


def test_render_device_creates_files(tmp_path):
    """render_device writes all expected output files."""
    config = load_device_config("router1")
    results = render_device("openwrt-router", config, tmp_path)

    expected = {"network", "wireless", "dhcp", "firewall", "system"}
    assert set(results.keys()) == expected
    for name, path in results.items():
        assert path.exists(), f"Missing output file: {name}"
        assert path.stat().st_size > 0, f"Empty output file: {name}"


def test_render_device_network_content(tmp_path):
    """Generated network config contains expected UCI blocks."""
    config = load_device_config("router1")
    render_device("openwrt-router", config, tmp_path)

    network_file = tmp_path / "network"
    content = network_file.read_text(encoding="utf-8")

    assert "config interface 'lan'" in content
    assert "config interface 'wan'" in content
    assert "option ipaddr '192.168.10.1'" in content


def test_render_device_deterministic(tmp_path):
    """Config generation is deterministic across two runs."""
    config = load_device_config("router1")

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    render_device("openwrt-router", config, out1)
    render_device("openwrt-router", config, out2)

    for name in ["network", "wireless", "dhcp", "system"]:
        assert (out1 / name).read_text() == (out2 / name).read_text(), (
            f"Non-deterministic output for {name}"
        )


def test_render_device_unknown_type(tmp_path):
    """render_device raises ValueError for unknown device types."""
    with pytest.raises(ValueError):
        render_device("unknown-device-type", {}, tmp_path)
