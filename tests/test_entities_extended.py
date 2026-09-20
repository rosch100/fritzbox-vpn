"""Extended entity behavior tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.fritzbox_vpn.binary_sensor import (
    FritzBoxVPNConnectedBinarySensor,
)
from custom_components.fritzbox_vpn.const import STATUS_CONNECTED
from custom_components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from custom_components.fritzbox_vpn.sensor import FritzBoxVPNStatusSensor
from custom_components.fritzbox_vpn.switch import FritzBoxVPNSwitch
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_VPN_CONNECTIONS


def _coordinator(entry: MockConfigEntry, **overrides):
    coordinator = MagicMock()
    coordinator.data = overrides.get("data", MOCK_VPN_CONNECTIONS)
    coordinator.last_update_success = overrides.get("last_update_success", True)
    coordinator.get_vpn_status = MagicMock(
        return_value=overrides.get("status", STATUS_CONNECTED)
    )
    coordinator.toggle_vpn = AsyncMock(return_value=overrides.get("toggle_ok", True))
    coordinator.async_request_refresh = AsyncMock()
    coordinator.resolve_connection_uid = lambda uid: uid
    coordinator.entities_trusted = MagicMock(return_value=True)
    entry.runtime_data = FritzboxVpnRuntimeData(
        coordinator=coordinator, parent_device_id="parent-device"
    )
    return coordinator


@pytest.mark.asyncio
async def test_switch_turn_off_and_toggle_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Turn off and coordinator exceptions propagate as HomeAssistantError."""
    coordinator = _coordinator(mock_config_entry)
    entity = FritzBoxVPNSwitch(
        coordinator, mock_config_entry, "conn-def", MOCK_VPN_CONNECTIONS["conn-def"]
    )
    await entity.async_turn_off()
    coordinator.toggle_vpn.assert_awaited_with("conn-def", False)

    coordinator.toggle_vpn = AsyncMock(side_effect=RuntimeError("network"))
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()


def test_switch_extra_attributes(mock_config_entry: MockConfigEntry) -> None:
    """Switch exposes VPN attributes when data is present."""
    coordinator = _coordinator(mock_config_entry)
    switch = FritzBoxVPNSwitch(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    attrs = switch.extra_state_attributes
    assert attrs["name"] == "Office VPN"
    assert attrs["uid"] == "conn-abc"


def test_binary_sensor_connected_on(mock_config_entry: MockConfigEntry) -> None:
    """Binary sensor reflects connected flag from coordinator data."""
    data = {**MOCK_VPN_CONNECTIONS["conn-abc"], "connected": True}
    coordinator = _coordinator(mock_config_entry, data={"conn-abc": data})
    entity = FritzBoxVPNConnectedBinarySensor(
        coordinator, mock_config_entry, "conn-abc", data
    )
    assert entity.is_on is True


def test_graceful_keeps_available_when_poll_failed(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Coordinator last_update_success must not hide trusted VPN state (#65)."""
    coordinator = _coordinator(mock_config_entry, last_update_success=False)
    coordinator.entities_trusted = MagicMock(return_value=True)
    switch = FritzBoxVPNSwitch(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    connected = FritzBoxVPNConnectedBinarySensor(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    status = FritzBoxVPNStatusSensor(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert switch.available is True
    assert switch._attr_available is True
    assert connected.available is True
    assert connected._attr_available is True
    assert status.available is True
    assert status._attr_available is True


def test_attr_available_tracks_untrusted_coordinator(
    mock_config_entry: MockConfigEntry,
) -> None:
    """_attr_available must follow connection_available, not Entity defaults (#65)."""
    coordinator = _coordinator(mock_config_entry, last_update_success=False)
    coordinator.entities_trusted = MagicMock(return_value=False)
    switch = FritzBoxVPNSwitch(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert switch.available is False
    assert switch._attr_available is False


def test_handle_coordinator_update_syncs_attr_available(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Coordinator listener must refresh _attr_available after the first poll (#65)."""
    coordinator = _coordinator(mock_config_entry)
    switch = FritzBoxVPNSwitch(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert switch._attr_available is True
    coordinator.entities_trusted = MagicMock(return_value=False)
    with patch.object(switch, "async_write_ha_state"):
        switch._handle_coordinator_update()
    assert switch.available is False
    assert switch._attr_available is False


def test_entities_unavailable_without_data(mock_config_entry: MockConfigEntry) -> None:
    """Entities are unavailable when coordinator data is missing."""
    coordinator = _coordinator(mock_config_entry, data={}, last_update_success=False)
    coordinator.entities_trusted = MagicMock(return_value=False)
    switch = FritzBoxVPNSwitch(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert switch.available is False
    assert switch._attr_available is False
    assert switch.is_on is False

    connected = FritzBoxVPNConnectedBinarySensor(
        coordinator,
        mock_config_entry,
        "conn-abc",
        {**MOCK_VPN_CONNECTIONS["conn-abc"], "connected": True},
    )
    assert connected.available is False

    status = FritzBoxVPNStatusSensor(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert status.native_value == STATUS_CONNECTED
