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

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FritzBox VPN from a config entry."""
    coordinator = FritzBoxVPNCoordinator(hass, entry.data)

    # Fetch initial data so we have data when the entities are added
    await coordinator.async_config_entry_first_refresh()

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
        sw_version=host,  # Store IP address as software version for reference
        configuration_url=f"http://{host}",
    )

    # Create VPN connection devices as child devices
    # These will only appear under the FritzBox device, not in the main device list
    if coordinator.data:
        for connection_uid, connection_data in coordinator.data.items():
            vpn_name = connection_data.get('name', 'Unknown')
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, entry.entry_id, connection_uid)},
                name=vpn_name,
                manufacturer="AVM",
                model="WireGuard VPN",
                via_device_id=parent_device.id,
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

