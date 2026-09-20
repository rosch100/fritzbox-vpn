"""Tests for shared entity helpers."""

from unittest.mock import MagicMock

import pytest
from custom_components.fritzbox_vpn.const import DOMAIN, UNIQUE_ID_SUFFIX_SWITCH
from custom_components.fritzbox_vpn.entity import (
    connection_available,
    connection_data,
    device_info_supports_via_device_id,
    vpn_device_info,
    vpn_switch_attributes,
    vpn_unique_id,
)
from homeassistant.exceptions import HomeAssistantError

from tests.fixtures import MOCK_VPN_CONNECTIONS


def test_vpn_unique_id() -> None:
    """Unique ID combines prefix, connection UID, and suffix."""
    assert vpn_unique_id("abc", UNIQUE_ID_SUFFIX_SWITCH) == "fritzbox_vpn_abc_switch"


def test_connection_available_and_data() -> None:
    """Availability follows coordinator trust and UID membership."""
    coordinator = MagicMock()
    coordinator.entities_trusted = MagicMock(return_value=True)
    coordinator.data = MOCK_VPN_CONNECTIONS
    coordinator.resolve_connection_uid = lambda uid: uid
    assert connection_available(coordinator, "conn-abc") is True
    assert connection_data(coordinator, "missing") is None


def test_connection_available_respects_entities_trusted() -> None:
    """Entities stay available in graceful mode while coordinator data is trusted."""
    coordinator = MagicMock()
    coordinator.entities_trusted = MagicMock(return_value=False)
    coordinator.data = MOCK_VPN_CONNECTIONS
    coordinator.resolve_connection_uid = lambda uid: uid
    assert connection_available(coordinator, "conn-abc") is False


def test_vpn_switch_attributes() -> None:
    """Switch attributes include status from coordinator."""
    coordinator = MagicMock()
    coordinator.data = MOCK_VPN_CONNECTIONS
    coordinator.get_vpn_status = MagicMock(return_value="enabled")
    coordinator.resolve_connection_uid = lambda uid: uid
    attrs = vpn_switch_attributes(coordinator, "conn-abc")
    assert attrs["name"] == "Office VPN"
    assert attrs["status"] == "enabled"


def test_vpn_device_info_uses_via_device_id() -> None:
    """HA 2026.8+ DeviceInfo links the parent by registry id, not via_device."""
    if not device_info_supports_via_device_id():
        pytest.skip("Installed Home Assistant has no DeviceInfo.via_device_id")
    entry = MagicMock()
    entry.entry_id = "entry-1"
    info = vpn_device_info(
        entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"], "parent-device"
    )
    assert info["name"] == "Office VPN"
    assert info["via_device_id"] == "parent-device"
    assert "via_device" not in info


def test_vpn_device_info_legacy_via_device(monkeypatch: pytest.MonkeyPatch) -> None:
    """HA without via_device_id keeps the identifier tuple parent link."""
    monkeypatch.setattr(
        "custom_components.fritzbox_vpn.entity.device_info_supports_via_device_id",
        lambda: False,
    )
    entry = MagicMock()
    entry.entry_id = "entry-1"
    info = vpn_device_info(
        entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"], "parent-device"
    )
    assert info["via_device"] == (DOMAIN, "entry-1")
    assert "via_device_id" not in info


def test_vpn_device_info_requires_parent_id_for_via_device_id() -> None:
    """via_device_id must not be invented; missing parent is an error."""
    if not device_info_supports_via_device_id():
        pytest.skip("Installed Home Assistant has no DeviceInfo.via_device_id")
    entry = MagicMock()
    entry.entry_id = "entry-1"
    with pytest.raises(HomeAssistantError, match="parent device"):
        vpn_device_info(entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"], None)
