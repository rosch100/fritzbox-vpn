"""Sensor platform for FritzBox VPN integration."""

import logging
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DATA_COORDINATOR, STATUS_UNKNOWN
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN sensor entities."""
    coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    # Create sensor entities for each VPN connection
    entities = []
    if coordinator.data:
        _LOGGER.info("Found %d VPN connections, creating sensor entities", len(coordinator.data))
        for connection_uid, connection_data in coordinator.data.items():
            # Status sensor (enabled by default) - shows combined status as text
            entities.append(
                FritzBoxVPNStatusSensor(coordinator, entry, connection_uid, connection_data)
            )
            # UID sensor (disabled by default)
            entities.append(
                FritzBoxVPNUIDSensor(coordinator, entry, connection_uid, connection_data)
            )
            # VPN UID sensor (disabled by default)
            entities.append(
                FritzBoxVPNVPNUIDSensor(coordinator, entry, connection_uid, connection_data)
            )
    else:
        _LOGGER.warning("No VPN connections found in coordinator data")

    _LOGGER.info("Adding %d sensor entities", len(entities))
    async_add_entities(entities, update_before_add=True)


class FritzBoxVPNStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for VPN connection status (textual)."""

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: ConfigEntry,
        connection_uid: str,
        connection_data: Dict[str, Any],
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._connection_uid = connection_uid
        self._connection_data = connection_data
        vpn_name = connection_data.get('name', 'Unknown')
        self._attr_unique_id = f"fritzbox_vpn_{connection_uid}_status"
        self._attr_name = "Status"
        self._attr_icon = "mdi:information"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, connection_uid)},
            name=vpn_name,
            manufacturer="AVM",
            model="WireGuard VPN",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def native_value(self) -> str:
        """Return the status as text."""
        if hasattr(self.coordinator, "get_vpn_status"):
            return self.coordinator.get_vpn_status(self._connection_uid)
        return STATUS_UNKNOWN

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return None


class FritzBoxVPNUIDSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for VPN connection UID."""

    _attr_entity_registry_enabled_default = False  # Disabled by default

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: ConfigEntry,
        connection_uid: str,
        connection_data: Dict[str, Any],
    ) -> None:
        """Initialize the UID sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._connection_uid = connection_uid
        self._connection_data = connection_data
        vpn_name = connection_data.get('name', 'Unknown')
        self._attr_unique_id = f"fritzbox_vpn_{connection_uid}_uid"
        self._attr_name = "UID"
        self._attr_icon = "mdi:identifier"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, connection_uid)},
            name=vpn_name,
            manufacturer="AVM",
            model="WireGuard VPN",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def native_value(self) -> str:
        """Return the connection UID."""
        return self._connection_uid

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return None


class FritzBoxVPNVPNUIDSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for VPN internal UID."""

    _attr_entity_registry_enabled_default = False  # Disabled by default

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: ConfigEntry,
        connection_uid: str,
        connection_data: Dict[str, Any],
    ) -> None:
        """Initialize the VPN UID sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._connection_uid = connection_uid
        self._connection_data = connection_data
        vpn_name = connection_data.get('name', 'Unknown')
        self._attr_unique_id = f"fritzbox_vpn_{connection_uid}_vpn_uid"
        self._attr_name = "VPN UID"
        self._attr_icon = "mdi:identifier"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, connection_uid)},
            name=vpn_name,
            manufacturer="AVM",
            model="WireGuard VPN",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def native_value(self) -> str:
        """Return the VPN UID."""
        if self.coordinator.data and self._connection_uid in self.coordinator.data:
            return self.coordinator.data[self._connection_uid].get('uid', '')
        return ''

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return None
