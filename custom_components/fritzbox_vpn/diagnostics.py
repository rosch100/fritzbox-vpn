"""Diagnostics support for Fritz!Box VPN."""

from typing import Any

from fritzboxvpn import API_KEY_ACTIVE, API_KEY_CONNECTED, API_KEY_NAME
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .availability import resolve_availability_mode
from .const import CONF_UPDATE_INTERVAL, host_from_config
from .coordinator import normalize_update_interval
from .models import FritzboxVpnConfigEntry, runtime_from_entry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "password", "pass", "user", "username"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FritzboxVpnConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (no credentials)."""
    host = host_from_config(entry.data)
    options = entry.options or {}
    update_interval = normalize_update_interval(
        options.get(CONF_UPDATE_INTERVAL) or entry.data.get(CONF_UPDATE_INTERVAL)
    )
    availability_mode = resolve_availability_mode(entry.data, options)

    last_update_success: bool | None = None
    entities_trusted: bool | None = None
    consecutive_poll_failures: int | None = None
    vpn_connections: list[dict[str, Any]] = []

    runtime = runtime_from_entry(entry)
    if runtime is not None:
        coordinator = runtime.coordinator
        last_update_success = coordinator.last_update_success
        entities_trusted = coordinator.entities_trusted()
        consecutive_poll_failures = coordinator.consecutive_poll_failures
        if coordinator.data:
            for uid, conn in coordinator.data.items():
                if not isinstance(conn, dict):
                    continue
                vpn_connections.append(
                    {
                        "connection_uid": uid,
                        API_KEY_NAME: conn.get(API_KEY_NAME),
                        API_KEY_ACTIVE: conn.get(API_KEY_ACTIVE),
                        API_KEY_CONNECTED: conn.get(API_KEY_CONNECTED),
                    }
                )

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "host": host,
        "update_interval_seconds": update_interval,
        "availability_mode": availability_mode,
        "last_update_success": last_update_success,
        "entities_trusted": entities_trusted,
        "consecutive_poll_failures": consecutive_poll_failures,
        "vpn_connection_count": len(vpn_connections),
        "vpn_connections": vpn_connections,
    }
