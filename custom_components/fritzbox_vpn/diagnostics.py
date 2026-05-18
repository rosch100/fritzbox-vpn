"""Diagnostics support for Fritz!Box VPN."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_UPDATE_INTERVAL, DATA_COORDINATOR, DOMAIN, host_from_config
from .coordinator import normalize_update_interval

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "password", "pass", "user", "username"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Any
) -> dict[str, Any]:
    """Return diagnostics for a config entry (no credentials)."""
    host = host_from_config(entry.data)
    options = entry.options or {}
    update_interval = normalize_update_interval(
        options.get(CONF_UPDATE_INTERVAL) or entry.data.get(CONF_UPDATE_INTERVAL)
    )

    last_update_success: bool | None = None
    vpn_connections: list[dict[str, Any]] = []

    if DOMAIN in hass.data:
        store = hass.data[DOMAIN].get(entry.entry_id, {})
        coordinator = store.get(DATA_COORDINATOR)
        if coordinator is not None:
            last_update_success = coordinator.last_update_success
            if coordinator.data:
                for uid, conn in coordinator.data.items():
                    if not isinstance(conn, dict):
                        continue
                    vpn_connections.append(
                        {
                            "connection_uid": uid,
                            "name": conn.get("name"),
                            "active": conn.get("active"),
                            "connected": conn.get("connected"),
                        }
                    )

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "host": host,
        "update_interval_seconds": update_interval,
        "last_update_success": last_update_success,
        "vpn_connection_count": len(vpn_connections),
        "vpn_connections": vpn_connections,
    }
