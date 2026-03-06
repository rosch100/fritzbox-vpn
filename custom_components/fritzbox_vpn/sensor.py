"""Sensor platform for FritzBox VPN integration."""

import asyncio
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DATA_COORDINATOR,
    DATA_KNOWN_UIDS_SENSOR,
    DATA_LOCK_ADD_ENTITIES_SENSOR,
    STATUS_UNKNOWN,
    MANUFACTURER_AVM,
    MODEL_WIREGUARD_VPN,
    DEFAULT_NAME_UNKNOWN,
    API_KEY_NAME,
    API_KEY_UID,
    UNIQUE_ID_PREFIX,
    UNIQUE_ID_SUFFIX_STATUS,
    UNIQUE_ID_SUFFIX_UID,
    UNIQUE_ID_SUFFIX_VPN_UID,
)
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN sensor entities. Adds new entities when new VPN connections appear."""
    coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known_uids: set = hass.data[DOMAIN][entry.entry_id].setdefault(
        DATA_KNOWN_UIDS_SENSOR, set()
    )

    def _create_sensor_entities(uids: set):
        """Create status/uid/vpn_uid sensor entities for the given UIDs."""
        if not coordinator.data:
            return []
        entities = []
        for uid in uids:
            if uid not in coordinator.data:
                continue
            conn = coordinator.data[uid]
            entities.append(FritzBoxVPNStatusSensor(coordinator, entry, uid, conn))
            entities.append(FritzBoxVPNUIDSensor(coordinator, entry, uid, conn))
            entities.append(FritzBoxVPNVPNUIDSensor(coordinator, entry, uid, conn))
        return entities

    if coordinator.data:
        initial_uids = set(coordinator.data.keys())
        known_uids.update(initial_uids)
        entities = _create_sensor_entities(initial_uids)
        _LOGGER.info("Found %d VPN connections, creating %d sensor entities", len(initial_uids), len(entities))
    else:
        entities = []
        _LOGGER.warning("No VPN connections found in coordinator data")

    async_add_entities(entities, update_before_add=True)

    async def _add_new_sensor_entities() -> None:
        lock = hass.data[DOMAIN][entry.entry_id].setdefault(
            DATA_LOCK_ADD_ENTITIES_SENSOR, asyncio.Lock()
        )
        async with lock:
            current = set(coordinator.data.keys()) if coordinator.data else set()
            new_uids = current - known_uids
            if not new_uids:
                return
            new_entities = _create_sensor_entities(new_uids)
            if not new_entities:
                return
            known_uids.update(new_uids)
            async_add_entities(new_entities)
            _LOGGER.info(
                "New VPN connection(s) detected, added %d sensor entity(ies)",
                len(new_entities),
            )

    def _on_coordinator_update() -> None:
        hass.async_create_task(_add_new_sensor_entities())

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))


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
        vpn_name = connection_data.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
        self._attr_unique_id = f"{UNIQUE_ID_PREFIX}{connection_uid}_{UNIQUE_ID_SUFFIX_STATUS}"
        self._attr_name = "Status"
        self._attr_icon = "mdi:information"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, connection_uid)},
            name=vpn_name,
            manufacturer=MANUFACTURER_AVM,
            model=MODEL_WIREGUARD_VPN,
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def available(self) -> bool:
        """Return True if the coordinator has valid data and this connection is still present."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return self._connection_uid in self.coordinator.data

    @property
    def native_value(self) -> str:
        """Return the status as text."""
        return self.coordinator.get_vpn_status(self._connection_uid)

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement (none for status text)."""
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
        vpn_name = connection_data.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
        self._attr_unique_id = f"{UNIQUE_ID_PREFIX}{connection_uid}_{UNIQUE_ID_SUFFIX_UID}"
        self._attr_name = "UID"
        self._attr_icon = "mdi:identifier"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, connection_uid)},
            name=vpn_name,
            manufacturer=MANUFACTURER_AVM,
            model=MODEL_WIREGUARD_VPN,
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def available(self) -> bool:
        """Return True if the coordinator has valid data and this connection is still present."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return self._connection_uid in self.coordinator.data

    @property
    def native_value(self) -> str:
        """Return the connection UID."""
        return self._connection_uid

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement (none for identifier)."""
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
        vpn_name = connection_data.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
        self._attr_unique_id = f"{UNIQUE_ID_PREFIX}{connection_uid}_{UNIQUE_ID_SUFFIX_VPN_UID}"
        self._attr_name = "VPN UID"
        self._attr_icon = "mdi:identifier"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, connection_uid)},
            name=vpn_name,
            manufacturer=MANUFACTURER_AVM,
            model=MODEL_WIREGUARD_VPN,
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def available(self) -> bool:
        """Return True if the coordinator has valid data and this connection is still present."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return self._connection_uid in self.coordinator.data

    @property
    def native_value(self) -> str:
        """Return the VPN UID."""
        if self.coordinator.data and self._connection_uid in self.coordinator.data:
            return self.coordinator.data[self._connection_uid].get(API_KEY_UID, '')
        return ''

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement (none for VPN UID)."""
        return None
