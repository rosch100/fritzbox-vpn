"""DataUpdateCoordinator for FritzBox VPN integration."""

from __future__ import annotations

import inspect
import logging
import time
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
    LOG_MSG_EMPTY_DURING_RECOVERY,
    LOG_MSG_RECOVERY_ARMED,
    LOG_MSG_RECOVERY_CLEARED,
    LOG_MSG_RECOVERY_EMPTY_ACCEPTED,
    LOG_MSG_UID_DELTA,
    LOG_MSG_UID_REMAP,
    LOG_MSG_UID_REMAP_REFUSED,
    LOG_MSG_VPN_CONNECTIONS_REMOVED,
    LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT,
    NAME_FRITZBOX,
    ORPHAN_CONFIRM_POLLS,
    RECOVERY_MAX_WINDOW_FACTOR,
    RECOVERY_MIN_INTERVAL_FACTOR,
    RECOVERY_STABLE_POLLS,
    RETRY_AFTER_SECONDS,
    STATUS_CONNECTED,
    STATUS_DISABLED,
    STATUS_ENABLED,
    STATUS_UNKNOWN,
    UPDATE_INTERVAL_MAX,
    UPDATE_INTERVAL_MIN,
    host_from_config,
)
from .entity_registry import remap_connection_uids
from .fritzconnection_session import FritzConnectionVPNSession
from .uid_identity import name_bijection_uid_remap

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


def recovery_window_seconds(update_interval_seconds: int) -> int:
    """Minimum recovery window after connectivity outage."""
    return max(
        RECOVERY_MIN_INTERVAL_FACTOR * update_interval_seconds,
        RECOVERY_MIN_INTERVAL_FACTOR * RETRY_AFTER_SECONDS,
    )


def recovery_max_seconds(update_interval_seconds: int) -> int:
    """Hard cap so recovery cannot stick forever on a permanently empty list."""
    return RECOVERY_MAX_WINDOW_FACTOR * recovery_window_seconds(update_interval_seconds)


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
        self._update_interval_seconds = update_interval_seconds

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
        self._uid_remap: dict[str, str] = {}
        self._recovering_until: float | None = None
        self._recovery_started_at: float | None = None
        self._recovery_stable_polls: int = 0

    def resolve_connection_uid(self, connection_uid: str) -> str:
        """Map a pre-remap entity UID to the current coordinator data key."""
        uid = connection_uid
        seen: set[str] = set()
        while uid in self._uid_remap and uid not in seen:
            seen.add(uid)
            uid = self._uid_remap[uid]
        return uid

    def get_vpn_status(self, connection_uid: str) -> str:
        """Get the textual status of a VPN connection."""
        resolved = self.resolve_connection_uid(connection_uid)
        if not self.data or resolved not in self.data:
            return STATUS_UNKNOWN
        conn = self.data[resolved]
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

    def _in_recovery(self) -> bool:
        """True while post-outage recovery window is active."""
        return self._recovering_until is not None

    def _arm_recovery(self) -> None:
        """Start or extend the post-outage recovery window."""
        if self.data:
            self._seen_uids |= set(self.data.keys())
            self._remember_connection_names(self.data)
        duration = recovery_window_seconds(self._update_interval_seconds)
        until = time.monotonic() + duration
        was_recovering = self._recovering_until is not None
        if self._recovery_started_at is None:
            self._recovery_started_at = time.monotonic()
        if self._recovering_until is None or until > self._recovering_until:
            self._recovering_until = until
        self._recovery_stable_polls = 0
        self._reset_orphan_miss_streaks()
        if not was_recovering:
            _LOGGER.warning(
                LOG_MSG_RECOVERY_ARMED,
                host_from_config(self.config),
                duration,
                len(self._seen_uids),
            )

    def _clear_recovery(self) -> None:
        """Exit recovery window and reset related counters."""
        self._recovering_until = None
        self._recovery_started_at = None
        self._recovery_stable_polls = 0

    def _recovery_max_elapsed(self) -> bool:
        """True when recovery has exceeded the hard empty-list cap."""
        if self._recovery_started_at is None:
            return False
        return time.monotonic() >= (
            self._recovery_started_at
            + recovery_max_seconds(self._update_interval_seconds)
        )

    def _note_successful_poll(self, connections: dict[str, Any]) -> None:
        """Advance or clear recovery based on non-empty successful polls."""
        if self._recovering_until is None:
            return
        if not connections:
            self._recovery_stable_polls = 0
            return
        # Only count stable polls after the minimum recovery window elapses.
        if time.monotonic() < self._recovering_until:
            self._recovery_stable_polls = 0
            return
        self._recovery_stable_polls += 1
        if self._recovery_stable_polls >= RECOVERY_STABLE_POLLS:
            self._clear_recovery()
            _LOGGER.info(
                LOG_MSG_RECOVERY_CLEARED,
                host_from_config(self.config),
                RECOVERY_STABLE_POLLS,
            )

    def _log_uid_delta(self, current_uids: set[str]) -> None:
        """Log added/removed UIDs with cached names when the set changes."""
        if not self._seen_uids:
            return
        added = sorted(current_uids - self._seen_uids)
        removed = sorted(self._seen_uids - current_uids)
        if not added and not removed:
            return

        def _labeled(uids: list[str]) -> list[str]:
            return [f"{self._uid_names.get(uid, uid)} ({uid})" for uid in uids]

        _LOGGER.info(
            LOG_MSG_UID_DELTA,
            host_from_config(self.config),
            _labeled(added),
            _labeled(removed),
        )

    def _apply_uid_remap_if_needed(self, connections: dict[str, Any]) -> None:
        """During recovery, remap registry UIDs when names form a 1:1 bijection."""
        if not self._in_recovery() or not self.entry_id or not connections:
            return
        current_uids = set(connections.keys())
        removed = self._seen_uids - current_uids
        added = current_uids - self._seen_uids
        if not removed or not added:
            return

        mapping, reason = name_bijection_uid_remap(
            removed, added, self._uid_names, connections
        )
        host = host_from_config(self.config)
        if mapping is None:
            _LOGGER.error(
                LOG_MSG_UID_REMAP_REFUSED,
                host,
                reason or "unknown",
                sorted(added),
                sorted(removed),
            )
            return

        applied = remap_connection_uids(self.hass, self.entry_id, mapping)
        skipped = set(mapping) - set(applied)
        if skipped:
            _LOGGER.error(
                "UID remap partially skipped for %s; refused=%s applied=%s",
                host,
                sorted(skipped),
                sorted(applied),
            )
        for old_uid, new_uid in applied.items():
            self._uid_remap[old_uid] = new_uid
            self._seen_uids.discard(old_uid)
            self._seen_uids.add(new_uid)
            name = self._uid_names.pop(old_uid, None)
            if name is not None:
                self._uid_names[new_uid] = name
            else:
                payload = connections.get(new_uid)
                if isinstance(payload, dict) and payload.get(API_KEY_NAME):
                    self._uid_names[new_uid] = str(payload[API_KEY_NAME])
            self._missing_uid_counts.pop(old_uid, None)
            self._confirmed_orphan_uids.discard(old_uid)
            _LOGGER.warning(
                LOG_MSG_UID_REMAP,
                host,
                old_uid,
                new_uid,
                self._uid_names.get(new_uid, new_uid),
            )
        if applied:
            _LOGGER.info(
                "Remapped %d connection UID(s) after outage recovery for entry %s",
                len(applied),
                self.entry_id,
            )

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
            had_connections = bool(self._seen_uids) or bool(self.data)
            if not connections and self._in_recovery() and had_connections:
                seen_count = len(self._seen_uids) or len(self.data or {})
                if self._recovery_max_elapsed():
                    max_seconds = recovery_max_seconds(self._update_interval_seconds)
                    _LOGGER.warning(
                        LOG_MSG_RECOVERY_EMPTY_ACCEPTED,
                        host_from_config(self.config),
                        max_seconds,
                        seen_count,
                    )
                    self._clear_recovery()
                else:
                    _LOGGER.warning(
                        LOG_MSG_EMPTY_DURING_RECOVERY,
                        host_from_config(self.config),
                        seen_count,
                    )
                    self._reset_orphan_miss_streaks()
                    self._recovery_stable_polls = 0
                    raise UpdateFailed(
                        "VPN list empty while recovering after connectivity outage",
                        retry_after=RETRY_AFTER_SECONDS,
                    )

            current_uids = set(connections.keys())
            self._remember_connection_names(connections)
            self._log_uid_delta(current_uids)
            self._apply_uid_remap_if_needed(connections)

            if self._in_recovery():
                self._reset_orphan_miss_streaks()
                if self.data:
                    self._seen_uids |= set(self.data.keys())
                self._seen_uids |= current_uids
                newly_confirmed: set[str] = set()
            else:
                newly_confirmed = self._track_missing_uids(current_uids)

            if newly_confirmed:
                names = [self._uid_names.get(uid, uid) for uid in newly_confirmed]
                _LOGGER.warning(
                    LOG_MSG_VPN_CONNECTIONS_REMOVED,
                    NAME_FRITZBOX,
                    names or list(newly_confirmed),
                    sorted(newly_confirmed),
                )
                _LOGGER.info(LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT)
                if self._on_orphaned_removed and self.entry_id:
                    self._on_orphaned_removed(self.entry_id, current_uids)

            self._note_successful_poll(connections)
            self._reauth_scheduled = False
            return connections
        except UpdateFailed:
            raise
        except (ConnectionError, ValueError) as err:
            self._prepare_session_for_retry(err)
            if self._is_auth_error(err):
                self._schedule_reauth()
                raise UpdateFailed(f"Error fetching VPN data: {err}") from err
            self._arm_recovery()
            raise UpdateFailed(
                f"Error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err
        except TimeoutError as err:
            self._arm_recovery()
            self._prepare_session_for_retry(err)
            raise UpdateFailed(
                f"Error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err
        except Exception as err:
            self._prepare_session_for_retry(err)
            if self._is_auth_error(err):
                self._schedule_reauth()
                raise UpdateFailed(
                    f"Unexpected error fetching VPN data: {err}"
                ) from err
            self._arm_recovery()
            _LOGGER.exception("Unexpected error fetching VPN data")
            raise UpdateFailed(
                f"Unexpected error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err

    async def toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle VPN on/off; schedule reauth on authentication errors."""
        resolved = self.resolve_connection_uid(connection_uid)
        try:
            return await self.fritz_session.async_toggle_vpn(resolved, enable)
        except Exception as err:
            if self._is_auth_error(err):
                self._schedule_reauth()
            raise
