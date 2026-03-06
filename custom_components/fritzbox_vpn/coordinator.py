"""DataUpdateCoordinator for FritzBox VPN integration."""

import asyncio
import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from datetime import timedelta
from typing import Any, Dict, Optional
from aiohttp import ClientSession, ClientTimeout, ClientConnectorError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.components import persistent_notification
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.translation import async_get_translations

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL,
    UPDATE_INTERVAL_MIN,
    UPDATE_INTERVAL_MAX,
    DEFAULT_TIMEOUT,
    DEFAULT_PROTOCOL,
    VERIFICATION_DELAY,
    RETRY_AFTER_SECONDS,
    API_LOGIN,
    API_DATA,
    API_VPN_CONNECTION,
    API_PAGE_SHAREWIREGUARD,
    API_KEY_DATA,
    API_KEY_INIT,
    API_KEY_BOX_CONNECTIONS,
    API_KEY_UID,
    API_KEY_ACTIVE,
    API_KEY_ACTIVATED,
    API_KEY_CONNECTED,
    API_KEY_NAME,
    ERROR_MSG_INVALID_SID,
    ERROR_MSG_INVALID_SID_403,
    ERROR_MSG_INVALID_SID_HTML,
    ERROR_MSG_LOGIN_FAILED_SID,
    CONTENT_TYPE_JSON,
    PROTOCOLS_ALLOWED,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    HTTP_STATUS_OK,
    HTTP_STATUS_FORBIDDEN,
    HTTPS_FALLBACK_STATUS_CODES,
    LOGIN_TAG_CHALLENGE,
    LOGIN_TAG_SID,
    LOGIN_FORM_USERNAME,
    LOGIN_FORM_RESPONSE,
    INVALID_SID_VALUE,
    AUTH_HEADER_PREFIX,
    LOG_LABEL_ACTIVATED,
    LOG_LABEL_DEACTIVATED,
    ACTIVE_STATE_STRINGS_TRUE,
    HEADER_VALUE_APPLICATION_JSON,
    LOG_MSG_VPN_CONNECTIONS_REMOVED,
    LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT,
    STATUS_CONNECTED,
    STATUS_ENABLED,
    STATUS_DISABLED,
    STATUS_UNKNOWN,
    AUTH_INDICATORS,
    DEFAULT_NAME_UNKNOWN,
    HOST_FALLBACK_UNKNOWN,
    INTEGRATION_TITLE,
    NAME_FRITZBOX,
    NOTIFICATION_TITLE_AUTH_ERROR,
    CONFIG_URL_INTEGRATIONS,
    auth_error_notification_id,
    mask_config_for_log,
)

_LOGGER = logging.getLogger(__name__)


def _connection_active_from_api(conn: Dict[str, Any]) -> bool:
    """Derive active state from API response. Supports keys 'active' and 'activated', int/str/bool."""
    raw = conn.get(API_KEY_ACTIVE)
    if raw is None:
        raw = conn.get(API_KEY_ACTIVATED)
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw != 0
    if isinstance(raw, str):
        return raw.strip().lower() in ACTIVE_STATE_STRINGS_TRUE
    return False


def _normalize_box_connections(box: Any) -> Dict[str, Any]:
    """Convert API boxConnections (list or dict) to dict keyed by uid with normalized 'active'."""
    result: Dict[str, Any] = {}
    items = box if isinstance(box, list) else box.values() if isinstance(box, dict) else ()
    for c in items:
        if not isinstance(c, dict) or c.get(API_KEY_UID) is None:
            continue
        entry = dict(c)
        entry[API_KEY_ACTIVE] = _connection_active_from_api(c)
        result[str(entry[API_KEY_UID])] = entry
    return result


def _parse_challenge_from_login_xml(content: str) -> Optional[str]:
    """Extract challenge from login_sid.lua XML. Returns None on parse error or missing challenge."""
    if not (content and content.strip()):
        return None
    try:
        root = ET.fromstring(content)
        return root.findtext(LOGIN_TAG_CHALLENGE)
    except ET.ParseError:
        return None


def _parse_sid_from_login_response(content: str) -> Optional[str]:
    """Extract SID from login response XML. Returns None on parse error."""
    if not (content and content.strip()):
        return None
    try:
        root = ET.fromstring(content)
        return root.findtext(LOGIN_TAG_SID)
    except ET.ParseError:
        return None


def _extract_box_connections_from_data(data: Dict[str, Any]) -> Any:
    """Extract boxConnections from data.lua JSON. Returns raw list/dict or None if structure invalid."""
    if not isinstance(data, dict):
        return None
    data_inner = data.get(API_KEY_DATA)
    if not isinstance(data_inner, dict):
        return None
    init = data_inner.get(API_KEY_INIT)
    if not isinstance(init, dict):
        return None
    return init.get(API_KEY_BOX_CONNECTIONS)


def normalize_update_interval(value: Any) -> int:
    """Normalize a raw update_interval value to an int in [UPDATE_INTERVAL_MIN, UPDATE_INTERVAL_MAX]. SSOT for parsing."""
    if value is None:
        return DEFAULT_UPDATE_INTERVAL
    if isinstance(value, int):
        if UPDATE_INTERVAL_MIN <= value <= UPDATE_INTERVAL_MAX:
            return value
        _LOGGER.warning(
            "update_interval %d out of range (%d–%d), using default %s",
            value, UPDATE_INTERVAL_MIN, UPDATE_INTERVAL_MAX, DEFAULT_UPDATE_INTERVAL,
        )
        return DEFAULT_UPDATE_INTERVAL
    try:
        n = int(value)
        if UPDATE_INTERVAL_MIN <= n <= UPDATE_INTERVAL_MAX:
            return n
        _LOGGER.warning(
            "update_interval %r -> %d out of range (%d–%d), using default %s",
            value, n, UPDATE_INTERVAL_MIN, UPDATE_INTERVAL_MAX, DEFAULT_UPDATE_INTERVAL,
        )
        return DEFAULT_UPDATE_INTERVAL
    except (ValueError, TypeError):
        _LOGGER.warning(
            "Invalid update_interval value %r, using default %s",
            value,
            DEFAULT_UPDATE_INTERVAL,
        )
        return DEFAULT_UPDATE_INTERVAL


def _resolve_update_interval_seconds(
    config: Dict[str, Any],
    options: Optional[Dict[str, Any]],
) -> int:
    """Resolve update interval in seconds from options, then config, then default. Always returns a valid int."""
    options_dict = options or {}
    value = options_dict.get(CONF_UPDATE_INTERVAL) or config.get(CONF_UPDATE_INTERVAL) or DEFAULT_UPDATE_INTERVAL
    return normalize_update_interval(value)


class FritzBoxVPNSession:
    """Session manager for FritzBox Web-UI API."""

    def __init__(self, session: ClientSession, host: str, username: str, password: str, protocol: str = DEFAULT_PROTOCOL):
        """Initialize the session manager."""
        self.session = session
        self.host = host
        self.username = username
        self.password = password
        # Validate and set protocol (default to https, fallback to http if https fails)
        self.protocol = protocol if protocol in PROTOCOLS_ALLOWED else DEFAULT_PROTOCOL
        self.sid: Optional[str] = None

    async def async_get_session(self) -> tuple[ClientSession, str]:
        """Get a session ID from the FritzBox. Reuses cached SID if valid to avoid
        re-login on every poll (reduces router login notifications / email spam)."""
        if self.sid is not None:
            return self.session, self.sid

        login_url = f"{self.protocol}://{self.host}{API_LOGIN}"
        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)

        try:
            content = await self._fetch_login_page(login_url, timeout)
        except (ConnectionError, ValueError) as err:
            _LOGGER.error("Error getting session: %s", err)
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error getting session")
            raise ConnectionError(f"Unexpected error: {err}") from err

        if not content:
            raise ConnectionError(f"No response from {NAME_FRITZBOX} login page")

        challenge = _parse_challenge_from_login_xml(content)
        if not challenge:
            raise ValueError("Could not parse login response XML or find challenge")

        response_hash = hashlib.md5(
            f"{challenge}-{self.password}".encode("utf-16le")
        ).hexdigest()
        login_data = {
            LOGIN_FORM_USERNAME: self.username,
            LOGIN_FORM_RESPONSE: f"{challenge}-{response_hash}",
        }
        async with self.session.post(login_url, data=login_data, ssl=False, timeout=timeout) as response:
            if response.status != HTTP_STATUS_OK:
                raise ConnectionError(f"Login failed: {response.status}")
            content = await response.text()

        sid = _parse_sid_from_login_response(content)
        if not sid or sid == INVALID_SID_VALUE:
            raise ValueError(
                ERROR_MSG_LOGIN_FAILED_SID.format(name_fritzbox=NAME_FRITZBOX)
            )
        self.sid = sid
        return self.session, self.sid

    async def _fetch_login_page(self, login_url: str, timeout: ClientTimeout) -> Optional[str]:
        """Fetch login page (GET). Handles HTTPS→HTTP fallback. Returns page content or None."""
        try:
            async with self.session.get(login_url, ssl=False, timeout=timeout) as response:
                if response.status == HTTP_STATUS_OK:
                    return await response.text()
                if self.protocol == PROTOCOL_HTTPS and response.status in HTTPS_FALLBACK_STATUS_CODES:
                    _LOGGER.warning(
                        "HTTPS connection failed (status %d), falling back to HTTP. "
                        "Consider using HTTP if your %s doesn't support HTTPS.",
                        response.status, NAME_FRITZBOX,
                    )
                    self.protocol = PROTOCOL_HTTP
                    login_url = f"{self.protocol}://{self.host}{API_LOGIN}"
                    async with self.session.get(login_url, ssl=False, timeout=timeout) as retry_response:
                        if retry_response.status != HTTP_STATUS_OK:
                            raise ConnectionError(
                                f"Failed to get login page: {retry_response.status}"
                            )
                        return await retry_response.text()
                raise ConnectionError(f"Failed to get login page: {response.status}")
        except (ClientConnectorError, OSError) as err:
            if self.protocol != PROTOCOL_HTTPS:
                raise ConnectionError(f"Cannot connect to {self.host}: {err}") from err
            _LOGGER.warning(
                "HTTPS connection failed (%s), falling back to HTTP.",
                err,
            )
            self.protocol = PROTOCOL_HTTP
            login_url = f"{self.protocol}://{self.host}{API_LOGIN}"
            async with self.session.get(login_url, ssl=False, timeout=timeout) as response:
                if response.status != HTTP_STATUS_OK:
                    raise ConnectionError(
                        f"Failed to get login page: {response.status}"
                    ) from err
                return await response.text()

    async def _fetch_vpn_connections_once(self) -> Dict[str, Any]:
        """Perform one request to get VPN connections. Returns {} on non-auth errors."""
        session, sid = await self.async_get_session()
        data_url = f"{self.protocol}://{self.host}{API_DATA}"
        params = {
            "sid": sid,
            "xhr": "1",
            "xhrId": "all",
            "page": API_PAGE_SHAREWIREGUARD,
            "no_sidrenew": "",
        }
        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)
        async with session.post(data_url, data=params, timeout=timeout, ssl=False) as response:
            if response.status == HTTP_STATUS_FORBIDDEN:
                raise ValueError(ERROR_MSG_INVALID_SID_403)
            if response.status != HTTP_STATUS_OK:
                _LOGGER.warning("Failed to get VPN connections: HTTP %d", response.status)
                return {}

            content_type = (response.headers.get("Content-Type") or "").lower()
            if CONTENT_TYPE_JSON not in content_type:
                _LOGGER.debug(
                    "VPN data response has unexpected content type %s, treating as invalid SID",
                    content_type or "(none)",
                )
                raise ValueError(ERROR_MSG_INVALID_SID_HTML)
            try:
                body = await response.text()
                data = json.loads(body)
            except (json.JSONDecodeError, TypeError) as err:
                _LOGGER.debug(
                    "VPN data response is not valid JSON (%s), treating as invalid SID",
                    err,
                )
                raise ValueError(ERROR_MSG_INVALID_SID_HTML) from err

            box = _extract_box_connections_from_data(data)
            if box is not None:
                return _normalize_box_connections(box)
            return {}

    async def async_get_vpn_connections(self) -> Dict[str, Any]:
        """Get list of WireGuard VPN connections. Uses cached session; retries once on SID expiry."""
        try:
            return await self._fetch_vpn_connections_once()
        except ValueError as err:
            if ERROR_MSG_INVALID_SID in str(err):
                self.invalidate_session()
                return await self._fetch_vpn_connections_once()
            raise
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout getting VPN connections: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Error getting VPN connections: %s", err)
            raise

    async def async_toggle_vpn(self, connection_uid: str, enable: bool, _sid_retry: bool = True) -> bool:
        """Toggle a VPN connection on/off. Uses cached session; retries once on 403 (expired SID)."""
        # Get connection details to find the UID
        connections = await self.async_get_vpn_connections()
        if connection_uid not in connections:
            _LOGGER.error("VPN connection %s not found", connection_uid)
            return False

        conn = connections[connection_uid]
        vpn_uid = conn.get(API_KEY_UID)
        if not vpn_uid:
            _LOGGER.error("VPN connection %s has no UID", connection_uid)
            return False

        # Check current status
        current_active = conn.get(API_KEY_ACTIVE, False)
        if current_active == enable:
            vpn_name = conn.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
            label = LOG_LABEL_ACTIVATED if enable else LOG_LABEL_DEACTIVATED
            _LOGGER.info("VPN %s is already %s", vpn_name, label)
            return True

        session, sid = await self.async_get_session()
        base = f"{self.protocol}://{self.host}"
        api_url = f"{base}{API_VPN_CONNECTION.format(uid=vpn_uid)}"
        headers = {
            "Content-Type": HEADER_VALUE_APPLICATION_JSON,
            "Authorization": f"{AUTH_HEADER_PREFIX}{sid}",
            "Accept": "*/*",
            "Origin": base,
            "Referer": f"{base}/",
        }
        request_body = {API_KEY_ACTIVATED: 1 if enable else 0}

        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)
        try:
            async with session.put(
                api_url,
                json=request_body,
                headers=headers,
                timeout=timeout,
                ssl=False,
            ) as response:
                if response.status == HTTP_STATUS_FORBIDDEN and _sid_retry:
                    self.invalidate_session()
                    return await self.async_toggle_vpn(connection_uid, enable, _sid_retry=False)
                if response.status != HTTP_STATUS_OK:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Error toggling VPN: HTTP %d, %s",
                        response.status,
                        error_text[:200],
                    )
                    return False

                await asyncio.sleep(VERIFICATION_DELAY)
                new_connections = await self.async_get_vpn_connections()
                vpn_name = conn.get(API_KEY_NAME, DEFAULT_NAME_UNKNOWN)
                if connection_uid not in new_connections:
                    _LOGGER.error(
                        "Could not verify VPN status change - connection not found"
                    )
                    return False
                new_conn = new_connections[connection_uid]
                new_active = new_conn.get(API_KEY_ACTIVE, False)
                if new_active == enable:
                    label = LOG_LABEL_ACTIVATED if enable else LOG_LABEL_DEACTIVATED
                    _LOGGER.info(
                        "VPN %s successfully %s",
                        vpn_name,
                        label,
                    )
                    return True
                _LOGGER.warning(
                    "VPN status change failed. Expected: %s, Got: %s",
                    enable,
                    new_active,
                )
                return False
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout toggling VPN: %s", err)
            return False
        except Exception as err:
            _LOGGER.exception("Error toggling VPN")
            return False

    def invalidate_session(self) -> None:
        """Invalidate cached SID so next request will perform a new login."""
        self.sid = None

    async def async_close(self) -> None:
        """Close the session."""
        # Only clear SID, do not close the shared session
        self.sid = None


class FritzBoxVPNCoordinator(DataUpdateCoordinator):
    """Coordinator for FritzBox VPN data."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any], options: Optional[Dict[str, Any]] = None, entry_id: Optional[str] = None):
        """Initialize the coordinator."""
        update_interval_seconds = _resolve_update_interval_seconds(config, options)
        _LOGGER.debug(
            "Coordinator init: options=%s, config[%s]=%s, options[%s]=%s",
            mask_config_for_log(options or {}),
            CONF_UPDATE_INTERVAL,
            config.get(CONF_UPDATE_INTERVAL),
            CONF_UPDATE_INTERVAL,
            (options or {}).get(CONF_UPDATE_INTERVAL),
        )
        _LOGGER.info("Coordinator: Using update_interval=%d seconds", update_interval_seconds)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.fritz_session = FritzBoxVPNSession(
            async_get_clientsession(hass),
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
        )
        self.config = config
        self.entry_id = entry_id
        self._auth_error_notified = False

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
        """Check if an error is an authentication error."""
        return any(ind in str(error).lower() for ind in AUTH_INDICATORS)

    def _build_auth_error_fallback_message(self, host: str, error: Exception) -> str:
        """Build fallback auth error message (no translations). Single source for fallback text."""
        config_link = ""
        if self.entry_id:
            config_link = (
                f"\n\n**→ [Zur Konfiguration öffnen]({CONFIG_URL_INTEGRATIONS})**\n\n"
                f"*Gehen Sie zu Einstellungen > Geräte & Dienste und suchen Sie nach \"{INTEGRATION_TITLE}\"*"
            )
        return (
            f"Die {NAME_FRITZBOX} VPN Integration kann nicht auf die {NAME_FRITZBOX} zugreifen.\n\n"
            f"**Host:** {host}\n\n"
            f"**Fehler:** {str(error)}\n\n"
            f"**Mögliche Ursachen:**\n"
            f"- Das {NAME_FRITZBOX} Passwort wurde geändert\n"
            f"- Der Benutzername ist falsch\n"
            f"- Die {NAME_FRITZBOX} ist nicht erreichbar\n\n"
            f"Bitte überprüfen Sie die Konfiguration der Integration und aktualisieren Sie die Zugangsdaten falls nötig."
            f"{config_link}"
        )

    async def _create_auth_error_notification(self, error: Exception) -> None:
        """Create a persistent notification for authentication errors."""
        if self._auth_error_notified:
            return

        host = self.config.get(CONF_HOST, HOST_FALLBACK_UNKNOWN)
        notification_id = auth_error_notification_id(host)
        try:
            trans = await async_get_translations(
                self.hass, self.hass.config.language, "common", [DOMAIN]
            )
            title = trans.get(
                "auth_error_notification_title", NOTIFICATION_TITLE_AUTH_ERROR
            )
            config_link = ""
            if self.entry_id:
                link_tpl = trans.get("auth_error_notification_config_link", "")
                hint_tpl = trans.get(
                    "auth_error_notification_config_hint",
                    f'Go to Settings > Devices & Services and search for "{INTEGRATION_TITLE}"',
                )
                if link_tpl and hint_tpl:
                    hint = hint_tpl.format(title=INTEGRATION_TITLE)
                    config_link = "\n\n" + link_tpl.format(
                        url=CONFIG_URL_INTEGRATIONS, hint=hint
                    )
            msg_tpl = trans.get("auth_error_notification_message", "")
            if msg_tpl:
                message = msg_tpl.format(
                    host=host, error=str(error), config_link=config_link
                )
            else:
                message = self._build_auth_error_fallback_message(host, error)
        except Exception:
            title = NOTIFICATION_TITLE_AUTH_ERROR
            message = self._build_auth_error_fallback_message(host, error)

        persistent_notification.create(
            self.hass,
            message,
            title=title,
            notification_id=notification_id,
        )
        
        self._auth_error_notified = True
        _LOGGER.warning(
            "Authentication error detected. Notification created. "
            "Please check credentials in integration settings. Entry ID: %s",
            self.entry_id
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch the latest VPN data."""
        previous_uids = set(self.data.keys()) if self.data else set()
        try:
            connections = await self.fritz_session.async_get_vpn_connections()
            if previous_uids and connections is not None:
                current_uids = set(connections.keys())
                removed_uids = previous_uids - current_uids
                if removed_uids:
                    names = [
                        self.data.get(uid, {}).get(API_KEY_NAME, uid)
                        for uid in removed_uids
                    ]
                    _LOGGER.warning(
                        LOG_MSG_VPN_CONNECTIONS_REMOVED,
                        NAME_FRITZBOX,
                        names or list(removed_uids),
                    )
                    _LOGGER.info(LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT)
            # Reset notification flag on successful update
            if self._auth_error_notified:
                self._auth_error_notified = False
                persistent_notification.dismiss(
                    self.hass, auth_error_notification_id(self.config.get(CONF_HOST, HOST_FALLBACK_UNKNOWN))
                )
            return connections
        except (ConnectionError, ValueError) as err:
            if self._is_auth_error(err):
                await self._create_auth_error_notification(err)
                raise UpdateFailed(f"Error fetching VPN data: {err}") from err
            # Transient error: backoff to avoid reconnect storm (next try in RETRY_AFTER_SECONDS)
            raise UpdateFailed(
                f"Error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed(
                f"Error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err
        except Exception as err:
            if self._is_auth_error(err):
                await self._create_auth_error_notification(err)
                raise UpdateFailed(f"Unexpected error fetching VPN data: {err}") from err
            _LOGGER.exception("Unexpected error fetching VPN data")
            raise UpdateFailed(
                f"Unexpected error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err

    async def toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle a VPN connection."""
        try:
            return await self.fritz_session.async_toggle_vpn(connection_uid, enable)
        except (ConnectionError, ValueError, Exception) as err:
            if self._is_auth_error(err):
                await self._create_auth_error_notification(err)
            raise
