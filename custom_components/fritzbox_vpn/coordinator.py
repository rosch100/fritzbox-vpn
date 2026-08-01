"""DataUpdateCoordinator for FritzBox VPN integration."""

import inspect
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fritzboxvpn import (
    API_KEY_ACTIVE,
    API_KEY_CONNECTED,
    API_KEY_NAME,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AUTH_INDICATORS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOG_MSG_VPN_CONNECTIONS_REMOVED,
    LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT,
    NAME_FRITZBOX,
    ORPHAN_CONFIRM_POLLS,
    RETRY_AFTER_SECONDS,
    STATUS_CONNECTED,
    STATUS_DISABLED,
    STATUS_ENABLED,
    STATUS_UNKNOWN,
    UPDATE_INTERVAL_MAX,
    UPDATE_INTERVAL_MIN,
    host_from_config,
)
from .fritzconnection_session import FritzConnectionVPNSession

_LOGGER = logging.getLogger(__name__)


def normalize_update_interval(value: Any) -> int:
    """Update interval as int in valid range. SSOT for parsing."""

    def clamp(n: int) -> int:
        if UPDATE_INTERVAL_MIN <= n <= UPDATE_INTERVAL_MAX:
            return n
        _LOGGER.warning(
            "Update interval %d out of range (%d–%d), using default %s",
            n,
            UPDATE_INTERVAL_MIN,
            UPDATE_INTERVAL_MAX,
            DEFAULT_UPDATE_INTERVAL,
        )
        return DEFAULT_UPDATE_INTERVAL

    if value is None:
        return DEFAULT_UPDATE_INTERVAL
    if isinstance(value, int):
        return clamp(value)
    try:
        return clamp(int(value))
    except (ValueError, TypeError):
        _LOGGER.warning(
            "Invalid update_interval value %r, using default %s",
            value,
            DEFAULT_UPDATE_INTERVAL,
        )
        return DEFAULT_UPDATE_INTERVAL


def _resolve_update_interval_seconds(
    config: dict[str, Any],
    options: dict[str, Any] | None,
) -> int:
    """Resolve update interval from options, then config, then default."""
    options_dict = options or {}
    value = (
        options_dict.get(CONF_UPDATE_INTERVAL)
        or config.get(CONF_UPDATE_INTERVAL)
        or DEFAULT_UPDATE_INTERVAL
    )
    return normalize_update_interval(value)


class FritzBoxVPNCoordinator(DataUpdateCoordinator):
    """Coordinator for FritzBox VPN data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        options: dict[str, Any] | None = None,
        entry_id: str | None = None,
        on_orphaned_removed: Callable[[str, set[str]], None] | None = None,
    ):
        update_interval_seconds = _resolve_update_interval_seconds(config, options)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.fritz_session = FritzConnectionVPNSession(
            hass,
            host_from_config(config),
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            use_tls=True,
        )
        self.config = config
        self.entry_id = entry_id
        self._reauth_scheduled = False
        self._on_orphaned_removed = on_orphaned_removed
        self._seen_uids: set[str] = set()
        self._missing_uid_counts: dict[str, int] = {}
        self._confirmed_orphan_uids: set[str] = set()
        self._uid_names: dict[str, str] = {}

    def get_vpn_status(self, connection_uid: str) -> str:
        """Get the textual status of a VPN connection."""
        if not self.data or connection_uid not in self.data:
            return STATUS_UNKNOWN
        conn = self.data[connection_uid]
        active = conn.get(API_KEY_ACTIVE, False)
        connected = conn.get(API_KEY_CONNECTED, False)
        if not active:
            return STATUS_DISABLED
        return STATUS_CONNECTED if connected else STATUS_ENABLED

    def _is_auth_error(self, error: Exception) -> bool:
        """True if error message indicates credential/authentication failure."""
        return any(ind in str(error).lower() for ind in AUTH_INDICATORS)

    def _prepare_session_for_retry(self, error: Exception) -> None:
        """Drop cached SID/protocol after transient failures so the next poll recovers."""
        if self._is_auth_error(error):
            return
        self.fritz_session.invalidate_session()

    def _schedule_reauth(self) -> None:
        """Start re-authentication flow once per auth failure cycle."""
        if self._reauth_scheduled or not self.entry_id:
            return
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None or entry.state != ConfigEntryState.LOADED:
            return
        self._reauth_scheduled = True
        _LOGGER.warning(
            "Authentication failed; starting reauth flow for entry %s", self.entry_id
        )
        self.hass.async_create_task(self._async_start_reauth(entry))

    async def _async_start_reauth(self, entry: Any) -> None:
        """Start re-authentication flow for an entry."""
        result = entry.async_start_reauth(self.hass)
        if inspect.isawaitable(result):
            await result

    def _remember_connection_names(self, connections: dict[str, Any]) -> None:
        """Cache display names so orphan warnings stay useful after partial polls."""
        for uid, payload in connections.items():
            if not isinstance(payload, dict):
                continue
            name = payload.get(API_KEY_NAME)
            if name:
                self._uid_names[uid] = str(name)

    def _reset_orphan_miss_streaks(self) -> None:
        """Clear in-progress miss counts so confirmations require consecutive successes."""
        self._missing_uid_counts.clear()

    def _track_missing_uids(self, current_uids: set[str]) -> set[str]:
        """Return UIDs newly confirmed missing after ORPHAN_CONFIRM_POLLS polls."""
        if self.data:
            self._seen_uids |= set(self.data.keys())
            self._remember_connection_names(self.data)
        self._seen_uids |= current_uids
        for uid in current_uids:
            self._missing_uid_counts.pop(uid, None)
            self._confirmed_orphan_uids.discard(uid)

        newly_confirmed: set[str] = set()
        for uid in self._seen_uids - current_uids:
            count = self._missing_uid_counts.get(uid, 0) + 1
            self._missing_uid_counts[uid] = count
            if count >= ORPHAN_CONFIRM_POLLS and uid not in self._confirmed_orphan_uids:
                self._confirmed_orphan_uids.add(uid)
                newly_confirmed.add(uid)
        return newly_confirmed

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest VPN data from Fritz!Box."""
        try:
            connections = await self.fritz_session.async_get_vpn_connections()
            current_uids = set(connections.keys())
            self._remember_connection_names(connections)
            newly_confirmed = self._track_missing_uids(current_uids)
            if newly_confirmed:
                names = [self._uid_names.get(uid, uid) for uid in newly_confirmed]
                _LOGGER.warning(
                    LOG_MSG_VPN_CONNECTIONS_REMOVED,
                    NAME_FRITZBOX,
                    names or list(newly_confirmed),
                )
                _LOGGER.info(LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT)
                if self._on_orphaned_removed and self.entry_id:
                    self._on_orphaned_removed(self.entry_id, current_uids)
            self._reauth_scheduled = False
            return connections
        except (ConnectionError, ValueError) as err:
            self._reset_orphan_miss_streaks()
            self._prepare_session_for_retry(err)
            if self._is_auth_error(err):
                self._schedule_reauth()
                raise UpdateFailed(f"Error fetching VPN data: {err}") from err
            raise UpdateFailed(
                f"Error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err
        except TimeoutError as err:
            self._reset_orphan_miss_streaks()
            self._prepare_session_for_retry(err)
            raise UpdateFailed(
                f"Error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err
        except Exception as err:
            self._reset_orphan_miss_streaks()
            self._prepare_session_for_retry(err)
            if self._is_auth_error(err):
                self._schedule_reauth()
                raise UpdateFailed(
                    f"Unexpected error fetching VPN data: {err}"
                ) from err
            _LOGGER.exception("Unexpected error fetching VPN data")
            raise UpdateFailed(
                f"Unexpected error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err

    async def toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle VPN on/off; schedule reauth on authentication errors."""
        try:
            return await self.fritz_session.async_toggle_vpn(connection_uid, enable)
        except Exception as err:
            if self._is_auth_error(err):
                self._schedule_reauth()
            raise
