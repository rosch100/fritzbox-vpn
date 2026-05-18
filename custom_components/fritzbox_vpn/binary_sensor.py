"""Binary sensor platform for FritzBox VPN integration."""

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    API_KEY_CONNECTED,
    DATA_COORDINATOR,
    DATA_KNOWN_UIDS_BINARY_SENSOR,
    DATA_LOCK_ADD_ENTITIES_BINARY_SENSOR,
    DOMAIN,
    UNIQUE_ID_SUFFIX_CONNECTED,
)
from .coordinator import FritzBoxVPNCoordinator
from .entity import FritzBoxVPNEntity, setup_vpn_platform


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN binary sensor entities."""
    coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    def _create_entities(uids: set[str]) -> list[FritzBoxVPNConnectedBinarySensor]:
        if not coordinator.data:
            return []
        return [
            FritzBoxVPNConnectedBinarySensor(coordinator, entry, uid, coordinator.data[uid])
            for uid in uids
            if uid in coordinator.data
        ]

    await setup_vpn_platform(
        hass,
        entry,
        async_add_entities,
        platform_label="binary_sensor",
        known_uids_key=DATA_KNOWN_UIDS_BINARY_SENSOR,
        lock_key=DATA_LOCK_ADD_ENTITIES_BINARY_SENSOR,
        create_entities=_create_entities,
    )


class FritzBoxVPNConnectedBinarySensor(FritzBoxVPNEntity, BinarySensorEntity):
    """Binary sensor entity for VPN connection status."""

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: ConfigEntry,
        connection_uid: str,
        connection_data: dict[str, Any],
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            connection_uid,
            connection_data,
            unique_id_suffix=UNIQUE_ID_SUFFIX_CONNECTED,
        )
        self._attr_translation_key = "connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """True if the VPN connection is connected."""
        conn = self._vpn_connection()
        if conn is None:
            return False
        return bool(conn.get(API_KEY_CONNECTED, False))
