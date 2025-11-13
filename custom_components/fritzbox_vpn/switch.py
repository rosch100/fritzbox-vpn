"""Switch platform for FritzBox VPN integration."""

import asyncio
import logging
from typing import Any, Dict

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DATA_COORDINATOR
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN switch entities."""
    coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    # Create a switch entity for each VPN connection
    entities = []
    if coordinator.data:
        _LOGGER.info("Found %d VPN connections, creating switch entities", len(coordinator.data))
        for connection_uid, connection_data in coordinator.data.items():
            vpn_name = connection_data.get('name', 'Unknown')
            _LOGGER.debug("Creating switch for VPN: %s (UID: %s)", vpn_name, connection_uid)
            entities.append(
                FritzBoxVPNSwitch(coordinator, entry, connection_uid, connection_data)
            )
    else:
        _LOGGER.warning("No VPN connections found in coordinator data")

    _LOGGER.info("Adding %d switch entities", len(entities))
    async_add_entities(entities, update_before_add=True)


class FritzBoxVPNSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for a FritzBox VPN connection."""

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: ConfigEntry,
        connection_uid: str,
        connection_data: Dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._connection_uid = connection_uid
        self._connection_data = connection_data
        vpn_name = connection_data.get('name', 'Unknown')
        self._attr_unique_id = f"fritzbox_vpn_{connection_uid}_switch"
        self._attr_name = None  # Use device name
        self._attr_icon = "mdi:vpn"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, connection_uid)},
            name=vpn_name,
            manufacturer="AVM",
            model="WireGuard VPN",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def is_on(self) -> bool:
        """Return True if the VPN connection is active."""
        if self.coordinator.data and self._connection_uid in self.coordinator.data:
            return self.coordinator.data[self._connection_uid].get('active', False)
        return False

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data and self._connection_uid in self.coordinator.data:
            conn = self.coordinator.data[self._connection_uid]
            active = conn.get('active', False)
            connected = conn.get('connected', False)
            
            # Determine status text based on active and connected states
            if active and connected:
                status = "connected"
            elif active and not connected:
                status = "active_not_connected"
            elif not active:
                status = "inactive"
            else:
                status = "unknown"
            
            return {
                'name': conn.get('name'),
                'uid': self._connection_uid,
                'vpn_uid': conn.get('uid'),
                'active': active,
                'connected': connected,
                'status': status,
            }
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the VPN connection."""
        vpn_name = self._attr_name or "Unknown"
        _LOGGER.info("Turning on VPN connection: %s", vpn_name)
        success = await self.coordinator.toggle_vpn(self._connection_uid, True)
        if success:
            # Force refresh to get updated status
            await self.coordinator.async_request_refresh()
            # Wait a moment for the data to be updated
            await asyncio.sleep(0.5)
            self.async_write_ha_state()
            _LOGGER.info("Successfully turned on VPN connection: %s", vpn_name)
        else:
            _LOGGER.error("Failed to activate VPN connection: %s", vpn_name)
            # Still refresh to show current state
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the VPN connection."""
        vpn_name = self._attr_name or "Unknown"
        _LOGGER.info("Turning off VPN connection: %s", vpn_name)
        success = await self.coordinator.toggle_vpn(self._connection_uid, False)
        if success:
            # Force refresh to get updated status
            await self.coordinator.async_request_refresh()
            # Wait a moment for the data to be updated
            await asyncio.sleep(0.5)
            self.async_write_ha_state()
            _LOGGER.info("Successfully turned off VPN connection: %s", vpn_name)
        else:
            _LOGGER.error("Failed to deactivate VPN connection: %s", vpn_name)
            # Still refresh to show current state
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()

