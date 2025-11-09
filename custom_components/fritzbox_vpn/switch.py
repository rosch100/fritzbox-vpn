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
        for connection_uid, connection_data in coordinator.data.items():
            entities.append(
                FritzBoxVPNSwitch(coordinator, entry, connection_uid, connection_data)
            )

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
        self._attr_unique_id = f"fritzbox_vpn_{connection_uid}_switch"
        self._attr_name = connection_data.get('name', 'Unknown')
        self._attr_icon = "mdi:vpn"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"FritzBox VPN ({entry.data.get('host', 'Unknown')})",
            manufacturer="AVM",
            model="FritzBox",
            configuration_url=f"http://{entry.data.get('host', '')}",
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
        _LOGGER.info(f"Turning on VPN connection: {self._attr_name}")
        success = await self.coordinator.toggle_vpn(self._connection_uid, True)
        if success:
            # Force refresh to get updated status
            await self.coordinator.async_request_refresh()
            # Wait a moment for the data to be updated
            await asyncio.sleep(0.5)
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully turned on VPN connection: {self._attr_name}")
        else:
            _LOGGER.error(
                f"Failed to activate VPN connection {self._attr_name}"
            )
            # Still refresh to show current state
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the VPN connection."""
        _LOGGER.info(f"Turning off VPN connection: {self._attr_name}")
        success = await self.coordinator.toggle_vpn(self._connection_uid, False)
        if success:
            # Force refresh to get updated status
            await self.coordinator.async_request_refresh()
            # Wait a moment for the data to be updated
            await asyncio.sleep(0.5)
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully turned off VPN connection: {self._attr_name}")
        else:
            _LOGGER.error(
                f"Failed to deactivate VPN connection {self._attr_name}"
            )
            # Still refresh to show current state
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()

