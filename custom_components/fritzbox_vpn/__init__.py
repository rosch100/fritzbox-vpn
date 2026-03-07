"""The FritzBox VPN integration."""

import logging
from typing import Any, Set

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_CONFIG_ENTRY_ID,
    DATA_COORDINATOR,
    DEFAULT_NAME_UNKNOWN,
    DOMAIN,
    ERROR_INDICATOR_AUTH,
    HOST_FALLBACK_UNKNOWN,
    MANUFACTURER_AVM,
    MODEL_FRITZBOX,
    NAME_FRITZBOX,
    SERVICE_REMOVE_UNAVAILABLE_ENTITIES,
    auth_error_notification_id,
    mask_config_for_log,
)
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.BINARY_SENSOR, Platform.SENSOR]

SERVICE_SCHEMA_REMOVE_UNAVAILABLE = vol.Schema(
    {vol.Optional(CONF_CONFIG_ENTRY_ID): str}
)


def _entry_ids_for_cleanup_service(hass: HomeAssistant, call: ServiceCall) -> list[str]:
    """Entry IDs to process for remove_unavailable_entities: one from call data or all loaded entries."""
    if call.data.get(CONF_CONFIG_ENTRY_ID):
        return [call.data[CONF_CONFIG_ENTRY_ID]]
    return [
        e.entry_id
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id in hass.data.get(DOMAIN, {})
    ]


def _apply_auto_cleanup(hass: HomeAssistant, entry_id: str, current_uids: Set[str]) -> None:
    """Clear known_uids for VPN connections no longer in current_uids. Does not remove registry entries
    so entity_id stays stable when a connection reappears (e.g. after temporary error).
    """
    from .config_flow import (
        _get_orphaned_entity_entries,
        _remove_orphaned_entities_and_clear_known_uids,
    )
    to_remove, err = _get_orphaned_entity_entries(hass, entry_id, current_uids=current_uids)
    if err or not to_remove:
        return
    _remove_orphaned_entities_and_clear_known_uids(
        hass, entry_id, to_remove, remove_from_registry=False
    )
    _LOGGER.info(
        "Cleared known_uids for %d unavailable connection(s); entity IDs kept for automation stability",
        len(to_remove),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FritzBox VPN from a config entry."""
    _LOGGER.info("Setting up FritzBox VPN integration for host: %s", entry.data.get(CONF_HOST, DEFAULT_NAME_UNKNOWN))
    _LOGGER.debug("Config entry data: %s", mask_config_for_log(entry.data))
    _LOGGER.debug("Config entry options: %s", mask_config_for_log(entry.options or {}))

    coordinator = FritzBoxVPNCoordinator(
        hass,
        entry.data,
        entry.options,
        entry.entry_id,
        on_orphaned_removed=lambda eid, cu: _apply_auto_cleanup(hass, eid, cu),
    )

    host = entry.data.get(CONF_HOST, HOST_FALLBACK_UNKNOWN)
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

    if "_service_remove_unavailable_registered" not in hass.data[DOMAIN]:
        from .config_flow import (
            _get_orphaned_entity_entries,
            _remove_orphaned_entities_and_clear_known_uids,
        )

        async def async_remove_unavailable_entities(call: ServiceCall) -> None:
            """Remove entity and device registry entries for VPN connections no longer on the Fritz!Box."""
            for entry_id in _entry_ids_for_cleanup_service(hass, call):
                to_remove, err = _get_orphaned_entity_entries(hass, entry_id)
                if err:
                    _LOGGER.warning(
                        "remove_unavailable_entities: skip entry %s (%s)",
                        entry_id,
                        err,
                    )
                    continue
                if not to_remove:
                    continue
                _remove_orphaned_entities_and_clear_known_uids(hass, entry_id, to_remove)
                await hass.config_entries.async_reload(entry_id)
                _LOGGER.info(
                    "remove_unavailable_entities: removed %d entities and reloaded entry %s",
                    len(to_remove),
                    entry_id,
                )

        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_UNAVAILABLE_ENTITIES,
            async_remove_unavailable_entities,
            schema=SERVICE_SCHEMA_REMOVE_UNAVAILABLE,
        )
        hass.data[DOMAIN]["_service_remove_unavailable_registered"] = True

    device_registry = dr.async_get(hass)
    host_for_url = entry.data.get(CONF_HOST, HOST_FALLBACK_UNKNOWN)
    parent_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=NAME_FRITZBOX,
        manufacturer=MANUFACTURER_AVM,
        model=MODEL_FRITZBOX,
        configuration_url=f"https://{host_for_url}",
    )
    _LOGGER.info("Created parent device: %s (ID: %s)", parent_device.name, parent_device.id)

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("Successfully set up all platforms")
    except Exception as err:
        _LOGGER.error("Failed to set up platforms: %s", err, exc_info=True)
        return False

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        await coordinator.fritz_session.async_close()

        host = entry.data.get(CONF_HOST, HOST_FALLBACK_UNKNOWN)
        persistent_notification.dismiss(hass, auth_error_notification_id(host))

        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading FritzBox VPN integration for host: %s", entry.data.get(CONF_HOST, DEFAULT_NAME_UNKNOWN))
    unload_ok = await async_unload_entry(hass, entry)
    if unload_ok:
        await async_setup_entry(hass, entry)
    else:
        _LOGGER.error("Failed to unload FritzBox VPN integration, cannot reload")
