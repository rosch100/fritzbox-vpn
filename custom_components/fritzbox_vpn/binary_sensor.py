"""Binary sensor platform for FritzBox VPN integration."""

import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DATA_COORDINATOR,
    DATA_KNOWN_UIDS_BINARY_SENSOR,
    MANUFACTURER_AVM,
    MODEL_WIREGUARD_VPN,
    DEFAULT_NAME_UNKNOWN,
    API_KEY_NAME,
    API_KEY_CONNECTED,
)
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN binary sensor entities. Adds new entities when new VPN connections appear."""
    coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known_uids: set = hass.data[DOMAIN][entry.entry_id].setdefault(
        DATA_KNOWN_UIDS_BINARY_SENSOR, set()
    )

    def _create_binary_sensor_entities(uids: set):
        """Create connected binary sensor entities for the given UIDs."""
        if not coordinator.data:
            return []
        return [
            FritzBoxVPNConnectedBinarySensor(coordinator, entry, uid, coordinator.data[uid])
            for uid in uids
            if uid in coordinator.data
        ]

    if coordinator.data:
        initial_uids = set(coordinator.data.keys())
        known_uids.update(initial_uids)
        entities = _create_binary_sensor_entities(initial_uids)
        _LOGGER.info("Found %d VPN connections, creating %d binary sensor entities", len(initial_uids), len(entities))
    else:
        entities = []
        _LOGGER.warning("No VPN connections found in coordinator data")

    async_add_entities(entities, update_before_add=True)

    async def _add_new_binary_sensor_entities() -> None:
        current = set(coordinator.data.keys()) if coordinator.data else set()
        new_uids = current - known_uids
        if not new_uids:
            return
        new_entities = _create_binary_sensor_entities(new_uids)
        if new_entities:
            async_add_entities(new_entities)
            known_uids.update(new_uids)
            _LOGGER.info(
                "New VPN connection(s) detected, added %d binary sensor entity(ies)",
                len(new_entities),
            )

    def _on_coordinator_update() -> None:
        hass.async_create_task(_add_new_binary_sensor_entities())

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))


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
        vpn_name = connection_data.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
        self._attr_unique_id = f"fritzbox_vpn_{connection_uid}_connected"
        self._attr_name = "Connected"
        self._attr_icon = "mdi:connection"
        self._attr_has_entity_name = True
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
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
    def is_on(self) -> bool:
        """Return True if the VPN connection is connected."""
        if self.coordinator.data and self._connection_uid in self.coordinator.data:
            return self.coordinator.data[self._connection_uid].get(API_KEY_CONNECTED, False)
        return False

