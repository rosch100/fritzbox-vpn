"""Switch platform for FritzBox VPN integration."""

import asyncio
import logging
from typing import Any, Dict, Set

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DATA_COORDINATOR,
    DATA_KNOWN_UIDS_SWITCH,
    DATA_LOCK_ADD_ENTITIES_SWITCH,
    MANUFACTURER_AVM,
    MODEL_WIREGUARD_VPN,
    DEFAULT_NAME_UNKNOWN,
    API_KEY_NAME,
    API_KEY_UID,
    API_KEY_ACTIVE,
    API_KEY_CONNECTED,
    ATTR_UID,
    ATTR_VPN_UID,
    ATTR_STATUS,
    UNIQUE_ID_PREFIX,
    UNIQUE_ID_SUFFIX_SWITCH,
)
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FritzBox VPN switch entities. Adds new entities when new VPN connections appear."""
    coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known_uids: set = hass.data[DOMAIN][entry.entry_id].setdefault(
        DATA_KNOWN_UIDS_SWITCH, set()
    )

    def _create_switch_entities(uids: Set[str]):
        """Create switch entities for UIDs present in coordinator.data."""
        if not coordinator.data:
            return []
        return [
            FritzBoxVPNSwitch(coordinator, entry, uid, coordinator.data[uid])
            for uid in uids
            if uid in coordinator.data
        ]

    if coordinator.data:
        initial_uids = set(coordinator.data.keys())
        known_uids.update(initial_uids)
        entities = _create_switch_entities(initial_uids)
        _LOGGER.info("Found %d VPN connections, creating %d switch entities", len(initial_uids), len(entities))
    else:
        entities = []
        _LOGGER.warning("No VPN connections found in coordinator data")

    async_add_entities(entities, update_before_add=True)

    async def _add_new_switch_entities() -> None:
        lock = hass.data[DOMAIN][entry.entry_id].setdefault(
            DATA_LOCK_ADD_ENTITIES_SWITCH, asyncio.Lock()
        )
        async with lock:
            current = set(coordinator.data.keys()) if coordinator.data else set()
            new_uids = current - known_uids
            if not new_uids:
                return
            new_entities = _create_switch_entities(new_uids)
            if not new_entities:
                return
            known_uids.update(new_uids)
            async_add_entities(new_entities)
            _LOGGER.info(
                "New VPN connection(s) detected, added %d switch entities: %s",
                len(new_entities),
                [coordinator.data[uid].get(API_KEY_NAME, uid) for uid in new_uids],
            )

    def _on_coordinator_update() -> None:
        hass.async_create_task(_add_new_switch_entities())

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))


class FritzBoxVPNSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for a FritzBox VPN connection."""

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: ConfigEntry,
        connection_uid: str,
        connection_data: Dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._connection_uid = connection_uid
        self._connection_data = connection_data
        vpn_name = connection_data.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
        self._attr_unique_id = f"{UNIQUE_ID_PREFIX}{connection_uid}_{UNIQUE_ID_SUFFIX_SWITCH}"
        self._attr_name = None
        self._attr_icon = "mdi:vpn"
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
        """True if coordinator has valid data and this connection is present."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return self._connection_uid in self.coordinator.data

    @property
    def is_on(self) -> bool:
        """True if the VPN connection is active."""
        if self.coordinator.data and self._connection_uid in self.coordinator.data:
            return self.coordinator.data[self._connection_uid].get(API_KEY_ACTIVE, False)
        return False

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Additional state attributes."""
        if self.coordinator.data and self._connection_uid in self.coordinator.data:
            conn = self.coordinator.data[self._connection_uid]
            active = conn.get(API_KEY_ACTIVE, False)
            connected = conn.get(API_KEY_CONNECTED, False)
            status = self.coordinator.get_vpn_status(self._connection_uid)
            return {
                API_KEY_NAME: conn.get(API_KEY_NAME),
                ATTR_UID: self._connection_uid,
                ATTR_VPN_UID: conn.get(API_KEY_UID),
                API_KEY_ACTIVE: active,
                API_KEY_CONNECTED: connected,
                ATTR_STATUS: status,
            }
        return {}

    async def _async_toggle_connection(self, enable: bool) -> None:
        """Turn VPN connection on or off; refresh coordinator afterward."""
        vpn_name = self._connection_data.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
        action = "on" if enable else "off"
        _LOGGER.info("Turning %s VPN connection: %s", action, vpn_name)
        success = await self.coordinator.toggle_vpn(self._connection_uid, enable)
        await self.coordinator.async_request_refresh()
        if success:
            _LOGGER.info("Successfully turned %s VPN connection: %s", action, vpn_name)
        else:
            _LOGGER.error(
                "Failed to %s VPN connection: %s",
                "activate" if enable else "deactivate",
                vpn_name,
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the VPN connection."""
        await self._async_toggle_connection(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the VPN connection."""
        await self._async_toggle_connection(False)
