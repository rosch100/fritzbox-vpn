"""The FritzBox VPN integration."""

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, DATA_COORDINATOR
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FritzBox VPN from a config entry."""
    _LOGGER.info("Setting up FritzBox VPN integration for host: %s", entry.data.get('host', 'Unknown'))
    
    coordinator = FritzBoxVPNCoordinator(hass, entry.data)

    # Fetch initial data so we have data when the entities are added
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial data refresh successful. Found %d VPN connections", len(coordinator.data) if coordinator.data else 0)
    except Exception as err:
        _LOGGER.error("Failed to fetch initial VPN data: %s", err, exc_info=True)
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    # Create parent device registry entry for the FritzBox
    device_registry = dr.async_get(hass)
    host = entry.data.get('host', 'Unknown')
    parent_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="FritzBox",
        manufacturer="AVM",
        model="FritzBox",
        configuration_url=f"http://{host}",
    )
    _LOGGER.info("Created parent device: %s (ID: %s)", parent_device.name, parent_device.id)

    # VPN connection devices will be created automatically by the entities
    # They use via_device to link to the parent device

    # Don't create entities immediately to avoid showing the "Geräte erstellt" dialog
    # Instead, create them on the first coordinator update (after 30 seconds)
    # This prevents the dialog from appearing after auto-setup
    _platforms_setup = False
    
    def _setup_platforms_on_update():
        """Set up platforms on first coordinator update to avoid showing dialog."""
        nonlocal _platforms_setup
        if not _platforms_setup:
            _platforms_setup = True
            # Remove this listener to avoid setting up multiple times
            coordinator.async_remove_listener(_setup_platforms_on_update)
            async def _setup():
                try:
                    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
                    _LOGGER.info("Successfully set up all platforms (on first update)")
                except Exception as err:
                    _LOGGER.error("Failed to set up platforms: %s", err, exc_info=True)
            hass.async_create_task(_setup())
    
    # Register listener to set up platforms on first coordinator update
    coordinator.async_add_listener(_setup_platforms_on_update)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        await coordinator.fritz_session.async_close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

