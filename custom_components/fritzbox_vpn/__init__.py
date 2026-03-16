"""The FritzBox VPN integration."""

import logging
from typing import Set

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .config_flow import (
    _get_orphaned_entity_entries,
    _remove_orphaned_entities_and_clear_known_uids,
    repair_entity_id_suffixes,
)
from .const import (
    CONF_CONFIG_ENTRY_ID,
    DATA_COORDINATOR,
    DOMAIN,
    ERROR_INDICATOR_AUTH,
    host_from_config,
    MANUFACTURER_AVM,
    MODEL_FRITZBOX,
    NAME_FRITZBOX,
    SERVICE_REMOVE_UNAVAILABLE_ENTITIES,
    SERVICE_REPAIR_ENTITY_ID_SUFFIXES,
    auth_error_notification_id,
)
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.BINARY_SENSOR, Platform.SENSOR]

SERVICE_SCHEMA_OPTIONAL_ENTRY_ID = vol.Schema(
    {vol.Optional(CONF_CONFIG_ENTRY_ID): str}
)


def _entry_host(entry: ConfigEntry) -> str:
    """Host from config entry."""
    return host_from_config(entry.data)


def _entry_ids_for_cleanup_service(hass: HomeAssistant, call: ServiceCall) -> list[str]:
    """Entry IDs to process: one from call data or all loaded config entries for this domain."""
    if call.data.get(CONF_CONFIG_ENTRY_ID):
        return [call.data[CONF_CONFIG_ENTRY_ID]]
    return [e.entry_id for e in hass.config_entries.async_loaded_entries(DOMAIN)]


async def _async_remove_unavailable_entities(hass: HomeAssistant, call: ServiceCall) -> None:
    """Remove entity and device registry entries for VPN connections no longer on the Fritz!Box."""
    for entry_id in _entry_ids_for_cleanup_service(hass, call):
        to_remove, err = _get_orphaned_entity_entries(hass, entry_id)
        if err:
            _LOGGER.warning("remove_unavailable_entities: skip entry %s (%s)", entry_id, err)
            continue
        if not to_remove:
            continue
        _remove_orphaned_entities_and_clear_known_uids(hass, entry_id, to_remove)
        await hass.config_entries.async_reload(entry_id)
        _LOGGER.info("remove_unavailable_entities: removed %d entities and reloaded entry %s", len(to_remove), entry_id)


async def _async_repair_entity_id_suffixes(hass: HomeAssistant, call: ServiceCall) -> None:
    """Repair entity IDs with _2, _3, … suffix: remove stale base entry and rename to base ID."""
    for entry_id in _entry_ids_for_cleanup_service(hass, call):
        count, _ = repair_entity_id_suffixes(hass, entry_id)
        if count:
            await hass.config_entries.async_reload(entry_id)
            _LOGGER.info("repair_entity_id_suffixes: repaired %d entities for entry %s", count, entry_id)


def _apply_auto_cleanup(hass: HomeAssistant, entry_id: str, current_uids: Set[str]) -> None:
    """Clear known_uids for UIDs no longer present; do not remove from registry so entity_id stays stable."""
    to_remove, err = _get_orphaned_entity_entries(hass, entry_id, current_uids=current_uids)
    if err or not to_remove:
        return
    _remove_orphaned_entities_and_clear_known_uids(
        hass, entry_id, to_remove, remove_from_registry=False
    )
    _LOGGER.info(
        "Cleared known_uids for %d unavailable connection(s); entity IDs kept",
        len(to_remove),
    )


def _register_services_if_needed(hass: HomeAssistant) -> None:
    """Register integration services once per HA instance."""
    if "_service_remove_unavailable_registered" in hass.data.get(DOMAIN, {}):
        return
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["_service_remove_unavailable_registered"] = True

    async def _handle_remove_unavailable(call: ServiceCall) -> None:
        await _async_remove_unavailable_entities(hass, call)

    async def _handle_repair_suffixes(call: ServiceCall) -> None:
        await _async_repair_entity_id_suffixes(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_UNAVAILABLE_ENTITIES,
        _handle_remove_unavailable,
        schema=SERVICE_SCHEMA_OPTIONAL_ENTRY_ID,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REPAIR_ENTITY_ID_SUFFIXES,
        _handle_repair_suffixes,
        schema=SERVICE_SCHEMA_OPTIONAL_ENTRY_ID,
    )


def _cleanup_empty_connection_devices(hass: HomeAssistant, entry_id: str) -> int:
    """Remove empty child devices of this config entry (parent device is kept)."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    removed = 0

    for device in dr.async_entries_for_config_entry(device_registry, entry_id):
        is_connection_device = any(
            identifier[0] == DOMAIN and identifier[1] == entry_id and len(identifier) == 3
            for identifier in device.identifiers
        )
        if not is_connection_device:
            continue
        if entity_registry.async_entries_for_device(device.id):
            continue
        device_registry.async_remove_device(device.id)
        removed += 1
        _LOGGER.info(
            "Removed empty connection device at startup: %s (device_id: %s)",
            device.name_by_user or device.name,
            device.id,
        )
    return removed


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FritzBox VPN from a config entry."""
    host = _entry_host(entry)
    _LOGGER.info("Setting up FritzBox VPN integration for host: %s", host)

    coordinator = FritzBoxVPNCoordinator(
        hass,
        entry.data,
        entry.options,
        entry.entry_id,
        on_orphaned_removed=lambda eid, cu: _apply_auto_cleanup(hass, eid, cu),
    )

    persistent_notification.dismiss(hass, auth_error_notification_id(host))

    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial data refresh successful. Found %d VPN connections", len(coordinator.data) if coordinator.data else 0)
    except Exception as err:
        err_lower = str(err).lower()
        if any(ind in err_lower for ind in ERROR_INDICATOR_AUTH):
            _LOGGER.error("Failed to fetch initial VPN data due to authentication error: %s", err)
            return False

        _LOGGER.warning("Failed to fetch initial VPN data, retrying later: %s", err)
        raise ConfigEntryNotReady(f"Timeout/Error connecting to {NAME_FRITZBOX}: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    _register_services_if_needed(hass)

    device_registry = dr.async_get(hass)
    parent_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=NAME_FRITZBOX,
        manufacturer=MANUFACTURER_AVM,
        model=MODEL_FRITZBOX,
        configuration_url=f"https://{host}",
    )
    _LOGGER.info("Created parent device: %s (ID: %s)", parent_device.name, parent_device.id)

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("Successfully set up all platforms")
    except Exception as err:
        _LOGGER.error("Failed to set up platforms: %s", err, exc_info=True)
        return False

    removed_empty_devices = _cleanup_empty_connection_devices(hass, entry.entry_id)
    if removed_empty_devices:
        _LOGGER.info(
            "Cleaned up %d empty connection device(s) after setup",
            removed_empty_devices,
        )

    count, _ = repair_entity_id_suffixes(hass, entry.entry_id)
    if count:
        _LOGGER.info(
            "Repaired %d entity ID suffix(es) at setup; reloading to apply",
            count,
        )
        await hass.config_entries.async_reload(entry.entry_id)
        return True

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        await coordinator.fritz_session.async_close()

        persistent_notification.dismiss(hass, auth_error_notification_id(_entry_host(entry)))

        hass.data[DOMAIN].pop(entry.entry_id)

        other_loaded = [
            e for e in hass.config_entries.async_loaded_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not other_loaded and hass.data[DOMAIN].pop("_service_remove_unavailable_registered", None):
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_UNAVAILABLE_ENTITIES)
            hass.services.async_remove(DOMAIN, SERVICE_REPAIR_ENTITY_ID_SUFFIXES)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading FritzBox VPN integration for host: %s", _entry_host(entry))
    unload_ok = await async_unload_entry(hass, entry)
    if unload_ok:
        await async_setup_entry(hass, entry)
    else:
        _LOGGER.error("Failed to unload FritzBox VPN integration, cannot reload")
