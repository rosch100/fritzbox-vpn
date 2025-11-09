"""Binary sensor platform for FritzBox VPN integration."""

import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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
    """Set up FritzBox VPN binary sensor entities."""
    coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    # Create binary sensor entities for each VPN connection
    entities = []
    if coordinator.data:
        for connection_uid, connection_data in coordinator.data.items():
            # Connected status binary sensor (enabled by default)
            entities.append(
                FritzBoxVPNConnectedBinarySensor(coordinator, entry, connection_uid, connection_data)
            )

    async_add_entities(entities, update_before_add=True)


class FritzBoxVPNConnectedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor entity for VPN connection status."""

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: ConfigEntry,
        connection_uid: str,
        connection_data: Dict[str, Any],
    ) -> None:
        """Initialize the connected binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._connection_uid = connection_uid
        self._connection_data = connection_data
        vpn_name = connection_data.get('name', 'Unknown')
        self._attr_unique_id = f"fritzbox_vpn_{connection_uid}_connected"
        self._attr_name = "Connected"
        self._attr_icon = "mdi:connection"
        self._attr_has_entity_name = True
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, connection_uid)},
            name=vpn_name,
            manufacturer="AVM",
            model="WireGuard VPN",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def is_on(self) -> bool:
        """Return True if the VPN connection is connected."""
        if self.coordinator.data and self._connection_uid in self.coordinator.data:
            return self.coordinator.data[self._connection_uid].get('connected', False)
        return False

