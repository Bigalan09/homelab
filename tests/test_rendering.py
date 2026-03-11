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
    assert "flint2" in inv["devices"]


def test_inventory_flint2_fields():
    """flint2 inventory entry has required fields."""
    inv = load_inventory()
    device = inv["devices"]["flint2"]
    assert device["type"] == "openwrt-router"
    assert device["host"] == "10.10.99.1"
    assert device["ssh_user"] == "root"


def test_load_device_config():
    """Device YAML loads correctly."""
    config = load_device_config("flint2")
    assert config["hostname"] == "mgmt-router-01"
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


def test_validate_flint2():
    """flint2 YAML is valid against the router schema."""
    config = load_device_config("flint2")
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
    config = load_device_config("flint2")
    output = render_template("network.j2", config, TEMPLATES_DIR)

    assert "config interface 'management'" in output
    assert "config interface 'wan'" in output
    assert "option proto 'static'" in output
    assert "option ipaddr '10.10.99.1'" in output
    assert "option proto 'dhcp'" in output


def test_render_wireless_template():
    """Wireless template renders expected UCI syntax."""
    config = load_device_config("flint2")
    output = render_template("wireless.j2", config, TEMPLATES_DIR)

    assert "config wifi-device 'radio0'" in output
    assert "config wifi-iface 'wifi_mgmt_2g'" in output
    assert "option ssid 'Meerkat Manor Admin'" in output
    assert "option encryption 'psk2'" in output
    assert "option mode 'ap'" in output


def test_render_dhcp_template():
    """DHCP template renders expected UCI syntax."""
    config = load_device_config("flint2")
    output = render_template("dhcp.j2", config, TEMPLATES_DIR)

    assert "config dhcp 'lan'" in output
    assert "option start '50'" in output
    assert "option limit '150'" in output
    assert "option leasetime '12h'" in output


def test_render_firewall_template():
    """Firewall template renders expected UCI syntax."""
    config = load_device_config("flint2")
    output = render_template("firewall.j2", config, TEMPLATES_DIR)

    assert "config defaults" in output
    assert "config zone" in output
    assert "config forwarding" in output
    assert "option name 'management'" in output
    assert "option name 'wan'" in output


def test_render_system_template():
    """System template renders expected UCI syntax."""
    config = load_device_config("flint2")
    output = render_template("system.j2", config, TEMPLATES_DIR)

    assert "config system" in output
    assert "option hostname 'mgmt-router-01'" in output
    assert "option timezone 'UTC'" in output


# ---------------------------------------------------------------------------
# End-to-end generation test
# ---------------------------------------------------------------------------


def test_render_device_creates_files(tmp_path):
    """render_device writes all expected output files."""
    config = load_device_config("flint2")
    results = render_device("openwrt-router", config, tmp_path)

    expected = {"network", "wireless", "dhcp", "firewall", "system"}
    assert set(results.keys()) == expected
    for name, path in results.items():
        assert path.exists(), f"Missing output file: {name}"
        assert path.stat().st_size > 0, f"Empty output file: {name}"


def test_render_device_network_content(tmp_path):
    """Generated network config contains expected UCI blocks."""
    config = load_device_config("flint2")
    render_device("openwrt-router", config, tmp_path)

    network_file = tmp_path / "network"
    content = network_file.read_text(encoding="utf-8")

    assert "config interface 'management'" in content
    assert "config interface 'wan'" in content
    assert "option ipaddr '10.10.99.1'" in content


def test_render_device_deterministic(tmp_path):
    """Config generation is deterministic across two runs."""
    config = load_device_config("flint2")

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


# ---------------------------------------------------------------------------
# Device discovery tests
# ---------------------------------------------------------------------------


def test_list_devices_returns_flint2():
    """list_devices() discovers flint2 from devices/ directory."""
    from loader import list_devices  # noqa: E402

    devices = list_devices()
    assert "flint2" in devices


def test_list_devices_sorted():
    """list_devices() returns a sorted list."""
    from loader import list_devices  # noqa: E402

    devices = list_devices()
    assert devices == sorted(devices)


def test_list_devices_uses_filename_stem():
    """Every entry in list_devices() corresponds to an existing .yaml file."""
    from loader import DEVICES_DIR, list_devices  # noqa: E402

    devices = list_devices()
    for name in devices:
        assert (DEVICES_DIR / f"{name}.yaml").exists(), (
            f"devices/{name}.yaml not found"
        )


# ---------------------------------------------------------------------------
# CLI subcommand tests
# ---------------------------------------------------------------------------


def test_cli_list(capsys):
    """'list' subcommand prints available devices."""
    from generate import main  # noqa: E402

    main(["list"])
    captured = capsys.readouterr()
    assert "flint2" in captured.out
    assert "Available devices:" in captured.out


def test_cli_generate(tmp_path, monkeypatch):
    """'generate' subcommand renders configs into the build directory."""
    import generate  # noqa: E402

    monkeypatch.setattr(generate, "BUILD_DIR", tmp_path)
    main_fn = generate.main
    main_fn(["generate", "flint2"])

    out_dir = tmp_path / "flint2"
    assert out_dir.exists()
    for fname in ("network", "wireless", "dhcp", "firewall", "system"):
        assert (out_dir / fname).exists(), f"Missing: {fname}"


def test_cli_deploy_missing_build(tmp_path, monkeypatch):
    """'deploy' subcommand exits with error when build files are absent."""
    import generate  # noqa: E402

    monkeypatch.setattr(generate, "BUILD_DIR", tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        generate.main(["deploy", "flint2"])
    assert exc_info.value.code != 0


def test_cli_deploy_preflight_passes(tmp_path, monkeypatch):
    """'deploy' pre-flight check passes when all build files are present."""
    import generate  # noqa: E402
    import subprocess  # noqa: E402

    monkeypatch.setattr(generate, "BUILD_DIR", tmp_path)

    # First generate so build files exist
    generate.main(["generate", "flint2"])

    # Patch subprocess.run to capture the deploy call without SSH
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc_info:
        generate.main(["deploy", "flint2"])

    assert exc_info.value.code == 0
    assert len(calls) == 1
    assert "deploy.sh" in calls[0][-2]
    assert calls[0][-1] == "flint2"


def test_cli_no_args(capsys):
    """Calling generate.py with no arguments prints usage and exits."""
    from generate import build_parser  # noqa: E402

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_cli_list_long(capsys):
    """'list -l' shows host, type, and build status columns."""
    from generate import main  # noqa: E402

    main(["list", "-l"])
    captured = capsys.readouterr()
    assert "flint2" in captured.out
    assert "HOST" in captured.out
    assert "TYPE" in captured.out
    assert "BUILT" in captured.out
    assert "10.10.99.1" in captured.out
    assert "openwrt-router" in captured.out


def test_cli_list_long_built(tmp_path, monkeypatch, capsys):
    """'list -l' reports BUILT=yes when all config files are present."""
    import generate  # noqa: E402

    monkeypatch.setattr(generate, "BUILD_DIR", tmp_path)
    generate.main(["generate", "flint2"])

    generate.main(["list", "-l"])
    captured = capsys.readouterr()
    assert "yes" in captured.out


def test_cli_validate_valid(capsys):
    """'validate' succeeds for a valid device config."""
    from generate import main  # noqa: E402

    main(["validate", "flint2"])
    # validate uses the logger (stderr), but the success message is emitted via logging
    # just confirm no SystemExit was raised (function returns normally)


def test_cli_validate_all(capsys):
    """'validate all' succeeds when all devices are valid."""
    from generate import main  # noqa: E402

    main(["validate", "all"])


def test_cli_validate_unknown_device(tmp_path, monkeypatch):
    """'validate' exits with non-zero for an unknown device."""
    import generate  # noqa: E402

    with pytest.raises(SystemExit) as exc_info:
        generate.main(["validate", "nonexistent_device_xyz"])
    assert exc_info.value.code != 0


def test_cli_generate_dry_run(tmp_path, monkeypatch, capsys):
    """'generate --dry-run' does not create any files."""
    import generate  # noqa: E402

    monkeypatch.setattr(generate, "BUILD_DIR", tmp_path)
    generate.main(["generate", "flint2", "--dry-run"])

    # No files should have been written
    assert not (tmp_path / "flint2").exists()


def test_cli_generate_output_dir(tmp_path):
    """'generate --output-dir' writes files to the given directory."""
    from generate import main  # noqa: E402

    main(["generate", "flint2", "--output-dir", str(tmp_path)])

    out_dir = tmp_path / "flint2"
    assert out_dir.exists()
    for fname in ("network", "wireless", "dhcp", "firewall", "system"):
        assert (out_dir / fname).exists(), f"Missing: {fname}"


def test_cli_status_missing(tmp_path, monkeypatch, capsys):
    """'status' shows MISSING when build files do not exist."""
    import generate  # noqa: E402

    monkeypatch.setattr(generate, "BUILD_DIR", tmp_path)
    generate.main(["status"])
    captured = capsys.readouterr()
    assert "MISSING" in captured.out
    assert "flint2" in captured.out


def test_cli_status_ok(tmp_path, monkeypatch, capsys):
    """'status' shows OK when all build files are present."""
    import generate  # noqa: E402

    monkeypatch.setattr(generate, "BUILD_DIR", tmp_path)
    generate.main(["generate", "flint2"])

    generate.main(["status"])
    captured = capsys.readouterr()
    assert "OK" in captured.out
    assert "flint2" in captured.out


def test_cli_verbose_flag(capsys):
    """'-v' flag enables debug-level log messages."""
    import logging  # noqa: E402

    from generate import main  # noqa: E402

    main(["-v", "list"])
    # After main(), root logger level was set to DEBUG
    assert logging.getLogger().level == logging.DEBUG


def test_cli_quiet_flag(capsys):
    """'-q' flag raises log level to ERROR only."""
    import logging  # noqa: E402

    from generate import main  # noqa: E402

    main(["-q", "list"])
    assert logging.getLogger().level == logging.ERROR
