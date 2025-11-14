"""DataUpdateCoordinator for FritzBox VPN integration."""

import asyncio
import hashlib
import re
import logging
from datetime import timedelta
from typing import Any, Dict, Optional
from aiohttp import ClientSession, ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.components import persistent_notification

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_PROTOCOL,
    VERIFICATION_DELAY,
    API_LOGIN,
    API_DATA,
    API_VPN_CONNECTION,
)

_LOGGER = logging.getLogger(__name__)


class FritzBoxVPNSession:
    """Session manager for FritzBox Web-UI API."""

    def __init__(self, host: str, username: str, password: str, protocol: str = DEFAULT_PROTOCOL):
        """Initialize the session manager."""
        self.host = host
        self.username = username
        self.password = password
        # Validate and set protocol (default to https, fallback to http if https fails)
        self.protocol = protocol if protocol in ("http", "https") else DEFAULT_PROTOCOL
        self.session: Optional[ClientSession] = None
        self.sid: Optional[str] = None

    async def async_get_session(self) -> tuple[ClientSession, str]:
        """Get a session ID from the FritzBox."""
        # Create new session if needed or if closed
        if self.session is None or self.session.closed:
            if self.session and not self.session.closed:
                await self.session.close()
            self.session = ClientSession()

        # Get challenge
        login_url = f"{self.protocol}://{self.host}{API_LOGIN}"
        try:
            async with self.session.get(login_url, ssl=False) as response:
                if response.status != 200:
                    # If HTTPS fails, try HTTP as fallback (for older FritzBox models)
                    if self.protocol == "https" and response.status in (400, 404, 502, 503):
                        _LOGGER.warning(
                            "HTTPS connection failed (status %d), falling back to HTTP. "
                            "Consider using HTTP if your FritzBox doesn't support HTTPS.",
                            response.status
                        )
                        self.protocol = "http"
                        login_url = f"{self.protocol}://{self.host}{API_LOGIN}"
                        async with self.session.get(login_url, ssl=False) as retry_response:
                            if retry_response.status != 200:
                                raise ConnectionError(
                                    f"Failed to get login page: {retry_response.status}"
                                )
                            content = await retry_response.text()
                    else:
                        raise ConnectionError(f"Failed to get login page: {response.status}")
                else:
                    content = await response.text()

                challenge_match = re.search(r'<Challenge>(.*?)</Challenge>', content)
                if not challenge_match:
                    raise ValueError("Could not find challenge in login response")

                challenge = challenge_match.group(1)

            # Calculate response
            response_hash = hashlib.md5(
                f"{challenge}-{self.password}".encode('utf-16le')
            ).hexdigest()
            login_response = f"{challenge}-{response_hash}"

            # Login
            login_data = {
                'username': self.username,
                'response': login_response
            }
            async with self.session.post(login_url, data=login_data, ssl=False) as response:
                if response.status != 200:
                    raise ConnectionError(f"Login failed: {response.status}")

                content = await response.text()
                sid_match = re.search(r'<SID>(.*?)</SID>', content)
                if not sid_match or sid_match.group(1) == '0000000000000000':
                    raise ValueError("Login failed: Invalid SID")

                self.sid = sid_match.group(1)

            return self.session, self.sid
        except (ConnectionError, ValueError) as err:
            _LOGGER.error("Error getting session: %s", err)
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error getting session")
            raise ConnectionError(f"Unexpected error: {err}") from err

    async def async_get_vpn_connections(self) -> Dict[str, Any]:
        """Get list of WireGuard VPN connections."""
        session, sid = await self.async_get_session()

        data_url = f"{self.protocol}://{self.host}{API_DATA}"
        params = {
            'sid': sid,
            'xhr': '1',
            'xhrId': 'all',
            'lang': 'de',
            'page': 'shareWireguard',
            'no_sidrenew': ''
        }

        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)
        try:
            async with session.post(data_url, data=params, timeout=timeout, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data and 'init' in data['data'] and 'boxConnections' in data['data']['init']:
                        return data['data']['init']['boxConnections']
                else:
                    _LOGGER.warning(
                        "Failed to get VPN connections: HTTP %d", response.status
                    )
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout getting VPN connections: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Error getting VPN connections: %s", err)
            raise

        return {}

    async def async_toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle a VPN connection on/off."""
        # Get connection details to find the UID
        connections = await self.async_get_vpn_connections()
        if connection_uid not in connections:
            _LOGGER.error("VPN connection %s not found", connection_uid)
            return False
        
        conn = connections[connection_uid]
        vpn_uid = conn.get('uid')
        if not vpn_uid:
            _LOGGER.error("VPN connection %s has no UID", connection_uid)
            return False
        
        # Check current status
        current_status = conn.get('active', False)
        if current_status == enable:
            vpn_name = conn.get('name', 'Unknown')
            _LOGGER.info(
                "VPN %s is already %s",
                vpn_name,
                "activated" if enable else "deactivated"
            )
            return True
        
        session, sid = await self.async_get_session()

        api_url = f"{self.protocol}://{self.host}{API_VPN_CONNECTION.format(uid=vpn_uid)}"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'AVM-SID {sid}',
            'Accept': '*/*',
            'Origin': f'{self.protocol}://{self.host}',
            'Referer': f'{self.protocol}://{self.host}/'
        }
        request_body = {'activated': '1' if enable else '0'}

        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)
        try:
            async with session.put(
                api_url,
                json=request_body,
                headers=headers,
                timeout=timeout,
                ssl=False
            ) as response:
                if response.status == 200:
                    # Wait a bit for the change to take effect
                    await asyncio.sleep(VERIFICATION_DELAY)
                    
                    # Verify the status was actually changed
                    new_connections = await self.async_get_vpn_connections()
                    if connection_uid in new_connections:
                        new_conn = new_connections[connection_uid]
                        new_status = new_conn.get('active', False)
                        vpn_name = conn.get('name', 'Unknown')
                        if new_status == enable:
                            _LOGGER.info(
                                "VPN %s successfully %s",
                                vpn_name,
                                "activated" if enable else "deactivated"
                            )
                            return True
                        else:
                            _LOGGER.warning(
                                "VPN status change failed. Expected: %s, Got: %s",
                                enable,
                                new_status
                            )
                            return False
                    else:
                        _LOGGER.error(
                            "Could not verify VPN status change - connection not found"
                        )
                        return False
                else:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Error toggling VPN: HTTP %d, %s",
                        response.status,
                        error_text[:200]
                    )
                    return False
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout toggling VPN: %s", err)
            return False
        except Exception as err:
            _LOGGER.exception("Error toggling VPN")
            return False

    async def async_close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
            self.session = None
            self.sid = None


class FritzBoxVPNCoordinator(DataUpdateCoordinator):
    """Coordinator for FritzBox VPN data."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any], options: Optional[Dict[str, Any]] = None, entry_id: Optional[str] = None):
        """Initialize the coordinator."""
        # Get update interval from options or config, fallback to default
        options_dict = options or {}
        config_value = config.get(CONF_UPDATE_INTERVAL)
        options_value = options_dict.get(CONF_UPDATE_INTERVAL)
        
        _LOGGER.debug("Coordinator init: options=%s, config[%s]=%s, options[%s]=%s", 
                     options_dict, CONF_UPDATE_INTERVAL, config_value, CONF_UPDATE_INTERVAL, options_value)
        
        update_interval_seconds = (
            options_value
            or config_value
            or DEFAULT_UPDATE_INTERVAL
        )
        
        # Ensure it's an integer
        if not isinstance(update_interval_seconds, int):
            try:
                update_interval_seconds = int(update_interval_seconds)
            except (ValueError, TypeError):
                _LOGGER.warning("Coordinator: Invalid update_interval value '%s', using default", 
                               update_interval_seconds)
                update_interval_seconds = DEFAULT_UPDATE_INTERVAL
        
        _LOGGER.info("Coordinator: Using update_interval=%d seconds", update_interval_seconds)
        
        super().__init__(
            hass,
            _LOGGER,
            name="fritzbox_vpn",
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.fritz_session = FritzBoxVPNSession(
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD]
        )
        self.config = config
        self.entry_id = entry_id
        self._auth_error_notified = False  # Flag to prevent duplicate notifications

    def _is_auth_error(self, error: Exception) -> bool:
        """Check if an error is an authentication error."""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Check for authentication-related error messages
        auth_indicators = [
            "login failed",
            "invalid sid",
            "authentication failed",
            "invalid credentials",
            "unauthorized",
            "access denied",
        ]
        
        # Check if error message contains authentication indicators
        if any(indicator in error_str for indicator in auth_indicators):
            return True
        
        # Check for ValueError with "Invalid SID" (from async_get_session)
        if isinstance(error, ValueError) and "invalid sid" in error_str:
            return True
        
        # Check for ConnectionError with "Login failed" (from async_get_session)
        if isinstance(error, ConnectionError) and "login failed" in error_str:
            return True
        
        return False

    def _create_auth_error_notification(self, error: Exception) -> None:
        """Create a persistent notification for authentication errors."""
        if self._auth_error_notified:
            # Already notified, don't create duplicate
            return
        
        host = self.config.get(CONF_HOST, "Unknown")
        notification_id = f"{DOMAIN}_auth_error_{self.config.get(CONF_HOST, 'unknown')}"
        
        title = "Fritz!Box VPN: Authentifizierungsfehler"
        
        # Create link to configuration page if entry_id is available
        config_link = ""
        if self.entry_id:
            config_url = f"/config/integrations/integration/{self.entry_id}"
            config_link = f"\n\n[**→ Zur Konfiguration öffnen**]({config_url})"
        
        message = (
            f"Die Fritz!Box VPN Integration kann nicht auf die Fritz!Box zugreifen.\n\n"
            f"**Host:** {host}\n\n"
            f"**Fehler:** {str(error)}\n\n"
            f"**Mögliche Ursachen:**\n"
            f"- Das Fritz!Box Passwort wurde geändert\n"
            f"- Der Benutzername ist falsch\n"
            f"- Die Fritz!Box ist nicht erreichbar\n\n"
            f"Bitte überprüfen Sie die Konfiguration der Integration und aktualisieren Sie die Zugangsdaten falls nötig."
            f"{config_link}"
        )
        
        persistent_notification.create(
            self.hass,
            message,
            title=title,
            notification_id=notification_id,
        )
        
        self._auth_error_notified = True
        _LOGGER.warning(
            "Authentifizierungsfehler erkannt. Benachrichtigung wurde erstellt. "
            "Bitte überprüfen Sie die Zugangsdaten in den Integrationseinstellungen."
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch the latest VPN data."""
        try:
            connections = await self.fritz_session.async_get_vpn_connections()
            # Reset notification flag on successful update
            if self._auth_error_notified:
                self._auth_error_notified = False
                # Remove the notification if it exists
                notification_id = f"{DOMAIN}_auth_error_{self.config.get(CONF_HOST, 'unknown')}"
                persistent_notification.dismiss(self.hass, notification_id)
            return connections
        except (ConnectionError, ValueError) as err:
            # Check if this is an authentication error
            if self._is_auth_error(err):
                self._create_auth_error_notification(err)
            raise UpdateFailed(f"Error fetching VPN data: {err}") from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Error fetching VPN data: {err}") from err
        except Exception as err:
            # Check if this is an authentication error (might be wrapped)
            if self._is_auth_error(err):
                self._create_auth_error_notification(err)
            _LOGGER.exception("Unexpected error fetching VPN data")
            raise UpdateFailed(f"Unexpected error fetching VPN data: {err}") from err

    async def toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle a VPN connection."""
        try:
            return await self.fritz_session.async_toggle_vpn(connection_uid, enable)
        except (ConnectionError, ValueError) as err:
            # Check if this is an authentication error
            if self._is_auth_error(err):
                self._create_auth_error_notification(err)
            raise
        except Exception as err:
            # Check if this is an authentication error (might be wrapped)
            if self._is_auth_error(err):
                self._create_auth_error_notification(err)
            raise

