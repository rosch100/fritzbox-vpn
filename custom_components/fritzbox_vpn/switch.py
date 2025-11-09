"""Switch platform for FritzBox VPN integration."""

import logging
from typing import Any, Dict

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
                FritzBoxVPNSwitch(coordinator, connection_uid, connection_data)
            )

    async_add_entities(entities, update_before_add=True)


class FritzBoxVPNSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for a FritzBox VPN connection."""

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        connection_uid: str,
        connection_data: Dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._connection_uid = connection_uid
        self._connection_data = connection_data
        self._attr_unique_id = f"fritzbox_vpn_{connection_uid}"
        self._attr_name = f"FritzBox VPN {connection_data.get('name', 'Unknown')}"
        self._attr_icon = "mdi:vpn"
        self._attr_has_entity_name = True

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
            return {
                'name': conn.get('name'),
                'uid': self._connection_uid,
                'active': conn.get('active', False),
            }
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the VPN connection."""
        success = await self.coordinator.toggle_vpn(self._connection_uid, True)
        if success:
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
        else:
            _LOGGER.error(
                f"Failed to activate VPN connection {self._attr_name}"
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the VPN connection."""
        success = await self.coordinator.toggle_vpn(self._connection_uid, False)
        if success:
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
        else:
            _LOGGER.error(
                f"Failed to deactivate VPN connection {self._attr_name}"
            )

