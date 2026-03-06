"""The FritzBox VPN integration."""

import logging
from typing import Any

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

# Optional service parameter: limit cleanup to this config entry ID
SERVICE_SCHEMA_REMOVE_UNAVAILABLE = vol.Schema(
    {vol.Optional(CONF_CONFIG_ENTRY_ID): str}
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FritzBox VPN from a config entry."""
    _LOGGER.info("Setting up FritzBox VPN integration for host: %s", entry.data.get(CONF_HOST, DEFAULT_NAME_UNKNOWN))
    _LOGGER.debug("Config entry data: %s", mask_config_for_log(entry.data))
    _LOGGER.debug("Config entry options: %s", mask_config_for_log(entry.options or {}))
    
    coordinator = FritzBoxVPNCoordinator(hass, entry.data, entry.options, entry.entry_id)

    # Remove any existing authentication error notification (in case of reload)
    host = entry.data.get(CONF_HOST, HOST_FALLBACK_UNKNOWN)
    persistent_notification.dismiss(hass, auth_error_notification_id(host))

    # Fetch initial data so we have data when the entities are added
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

    # Register service once (same handler for all entries)
    if "_service_remove_unavailable_registered" not in hass.data[DOMAIN]:
        from .config_flow import (
            _get_orphaned_entity_entries,
            _remove_orphaned_entities_and_clear_known_uids,
        )

        async def async_remove_unavailable_entities(call: ServiceCall) -> None:
            """Remove entity registry entries for VPN connections no longer on the Fritz!Box."""
            entry_ids: list[str] = []
            if call.data.get(CONF_CONFIG_ENTRY_ID):
                entry_ids = [call.data[CONF_CONFIG_ENTRY_ID]]
            else:
                entry_ids = [
                    e.entry_id
                    for e in hass.config_entries.async_entries(DOMAIN)
                    if e.entry_id in hass.data.get(DOMAIN, {})
                ]
            for entry_id in entry_ids:
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

    # Create parent device registry entry for the FritzBox
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

    # VPN connection devices will be created automatically by the entities
    # They use via_device to link to the parent device

    # Forward the setup to the switch platform
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
        
        # Remove authentication error notification if it exists
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
