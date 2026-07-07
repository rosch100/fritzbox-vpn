"""Shared VPN connection entity helpers and dynamic platform setup."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fritzboxvpn import API_KEY_ACTIVE, API_KEY_CONNECTED, API_KEY_NAME, API_KEY_UID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_STATUS,
    ATTR_UID,
    ATTR_VPN_UID,
    DEFAULT_NAME_UNKNOWN,
    DOMAIN,
    MANUFACTURER_AVM,
    MODEL_WIREGUARD_VPN,
    UNIQUE_ID_PREFIX,
)
from .coordinator import FritzBoxVPNCoordinator
from .models import FritzboxVpnConfigEntry, RuntimePlatform, runtime_from_entry

_LOGGER = logging.getLogger(__name__)

EntityFactory = Callable[[FritzBoxVPNCoordinator, set[str]], list]
VpnEntityFactory = Callable[
    [FritzBoxVPNCoordinator, FritzboxVpnConfigEntry, str, dict[str, Any]], Any
]
VpnConnectionEntitiesFactory = Callable[
    [FritzBoxVPNCoordinator, FritzboxVpnConfigEntry, str, dict[str, Any]], list[Any]
]


def vpn_entities_for_connections(
    coordinator: FritzBoxVPNCoordinator,
    entry: FritzboxVpnConfigEntry,
    uids: set[str],
    create_entities: VpnConnectionEntitiesFactory,
) -> list[Any]:
    """Create entities for each VPN UID (factory may return multiple per connection)."""
    if not coordinator.data:
        return []
    entities: list[Any] = []
    for uid in uids:
        if uid in coordinator.data:
            entities.extend(
                create_entities(coordinator, entry, uid, coordinator.data[uid])
            )
    return entities


def vpn_entities_for_uids(
    coordinator: FritzBoxVPNCoordinator,
    entry: FritzboxVpnConfigEntry,
    uids: set[str],
    create_entity: VpnEntityFactory,
) -> list[Any]:
    """Create one entity per VPN UID that exists in coordinator data."""

    def _create_one(
        coord: FritzBoxVPNCoordinator,
        ent: FritzboxVpnConfigEntry,
        uid: str,
        conn: dict[str, Any],
    ) -> list[Any]:
        return [create_entity(coord, ent, uid, conn)]

    return vpn_entities_for_connections(coordinator, entry, uids, _create_one)


def vpn_unique_id(connection_uid: str, suffix: str) -> str:
    """Entity unique_id for a VPN connection and platform suffix."""
    return f"{UNIQUE_ID_PREFIX}{connection_uid}_{suffix}"


def vpn_device_info(
    entry: FritzboxVpnConfigEntry,
    connection_uid: str,
    connection_payload: dict[str, Any],
) -> DeviceInfo:
    """Device registry entry for one WireGuard VPN connection."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id, connection_uid)},
        name=connection_payload.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN),
        manufacturer=MANUFACTURER_AVM,
        model=MODEL_WIREGUARD_VPN,
        via_device=(DOMAIN, entry.entry_id),
    )


def connection_available(
    coordinator: FritzBoxVPNCoordinator, connection_uid: str
) -> bool:
    """True when the coordinator has data for this VPN connection."""
    if not coordinator.last_update_success or not coordinator.data:
        return False
    return connection_uid in coordinator.data


def connection_data(
    coordinator: FritzBoxVPNCoordinator, connection_uid: str
) -> dict[str, Any] | None:
    """VPN connection payload from coordinator data, if present."""
    if not coordinator.data or connection_uid not in coordinator.data:
        return None
    return coordinator.data[connection_uid]


def vpn_switch_attributes(
    coordinator: FritzBoxVPNCoordinator, connection_uid: str
) -> dict[str, Any]:
    """State attributes for the VPN switch entity."""
    conn = connection_data(coordinator, connection_uid)
    if conn is None:
        return {}
    return {
        API_KEY_NAME: conn.get(API_KEY_NAME),
        ATTR_UID: connection_uid,
        ATTR_VPN_UID: conn.get(API_KEY_UID),
        API_KEY_ACTIVE: conn.get(API_KEY_ACTIVE, False),
        API_KEY_CONNECTED: conn.get(API_KEY_CONNECTED, False),
        ATTR_STATUS: coordinator.get_vpn_status(connection_uid),
    }


def raise_toggle_failed(vpn_name: str, error: str = "") -> None:
    """Raise translated HomeAssistantError for failed VPN toggle."""
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="toggle_failed",
        translation_placeholders={"name": vpn_name, "error": error},
    )


class FritzBoxVPNEntity(CoordinatorEntity):
    """Base entity bound to one VPN connection on the coordinator."""

    _attr_has_entity_name = True
    _attr_translation_domain = DOMAIN
    # Keep entity_id (object_id) stable across languages by using fixed tokens.
    _attr_object_id_suffix: str | None = None

    def __init__(
        self,
        coordinator: FritzBoxVPNCoordinator,
        entry: FritzboxVpnConfigEntry,
        connection_uid: str,
        connection_payload: dict[str, Any],
        *,
        unique_id_suffix: str,
        translation_key: str | None = None,
        object_id_suffix: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._connection_uid = connection_uid
        self._connection_data = connection_payload
        self._attr_unique_id = vpn_unique_id(connection_uid, unique_id_suffix)
        self._attr_device_info = vpn_device_info(
            entry, connection_uid, connection_payload
        )
        if translation_key is not None:
            self._attr_translation_key = translation_key
            self._attr_object_id_suffix = (
                object_id_suffix if object_id_suffix is not None else unique_id_suffix
            )
        elif object_id_suffix is not None:
            self._attr_object_id_suffix = object_id_suffix

    @property
    def available(self) -> bool:
        """True if coordinator has valid data and this connection is present."""
        return connection_available(self.coordinator, self._connection_uid)

    def _vpn_connection(self) -> dict[str, Any] | None:
        """Current connection dict from coordinator, if available."""
        return connection_data(self.coordinator, self._connection_uid)

    @property
    def suggested_object_id(self) -> str | None:
        """Return a stable object_id suffix for entity_id generation.

        With ``has_entity_name=True``, Home Assistant prepends the device name
        via ``async_calculate_suggested_object_id``; return only the fixed
        suffix token here to avoid duplicated name parts and language drift.
        """
        if self._attr_object_id_suffix:
            return self._attr_object_id_suffix
        return super().suggested_object_id


async def setup_vpn_platform(
    entry: FritzboxVpnConfigEntry,
    async_add_entities: AddEntitiesCallback,
    *,
    platform: RuntimePlatform,
    create_entities: EntityFactory,
) -> None:
    """Register entities and add new ones when coordinator data gains VPN UIDs."""
    runtime = runtime_from_entry(entry)
    if runtime is None:
        _LOGGER.error("Runtime data missing during %s platform setup", platform)
        return

    coordinator = runtime.coordinator
    known_uids, lock = runtime.platform_tracking(platform)

    if coordinator.data:
        initial_uids = set(coordinator.data.keys())
        known_uids.update(initial_uids)
        entities = create_entities(coordinator, initial_uids)
        _LOGGER.info(
            "Found %d VPN connections, creating %d %s entities",
            len(initial_uids),
            len(entities),
            platform,
        )
    else:
        entities = []
        _LOGGER.warning("No VPN connections found in coordinator data")

    async_add_entities(entities, update_before_add=True)

    async def _add_new_entities() -> None:
        async with lock:
            current = set(coordinator.data.keys()) if coordinator.data else set()
            new_uids = current - known_uids
            if not new_uids:
                return
            new_entities = create_entities(coordinator, new_uids)
            if not new_entities:
                return
            known_uids.update(new_uids)
            async_add_entities(new_entities)
            _LOGGER.info(
                "New VPN connection(s) detected, added %d %s entities",
                len(new_entities),
                platform,
            )

    def _on_coordinator_update() -> None:
        coordinator.hass.async_create_task(_add_new_entities())

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))
