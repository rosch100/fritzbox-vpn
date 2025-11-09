"""The FritzBox VPN integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, DATA_COORDINATOR
from .coordinator import FritzBoxVPNCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FritzBox VPN from a config entry."""
    coordinator = FritzBoxVPNCoordinator(hass, entry.data)

    # Fetch initial data so we have data when the entities are added
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    # Create device registry entry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"FritzBox VPN ({entry.data.get('host', 'Unknown')})",
        manufacturer="AVM",
        model="FritzBox",
        configuration_url=f"http://{entry.data.get('host', '')}",
    )

    # Forward the setup to the switch platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: FritzBoxVPNCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        await coordinator.fritz_session.async_close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

