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

from .const import DEFAULT_UPDATE_INTERVAL, DEFAULT_TIMEOUT, API_LOGIN, API_DATA, API_VPN_CONNECTION

_LOGGER = logging.getLogger(__name__)


class FritzBoxVPNSession:
    """Session manager for FritzBox Web-UI API."""

    def __init__(self, host: str, username: str, password: str):
        """Initialize the session manager."""
        self.host = host
        self.username = username
        self.password = password
        self.session: Optional[ClientSession] = None
        self.sid: Optional[str] = None

    async def async_get_session(self) -> tuple[ClientSession, str]:
        """Get a session ID from the FritzBox."""
        if self.session is None:
            self.session = ClientSession()

        # Get challenge
        login_url = f"http://{self.host}{API_LOGIN}"
        try:
            async with self.session.get(login_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get login page: {response.status}")

                content = await response.text()
                challenge_match = re.search(r'<Challenge>(.*?)</Challenge>', content)
                if not challenge_match:
                    raise Exception("Could not find challenge in login response")

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
            async with self.session.post(login_url, data=login_data) as response:
                if response.status != 200:
                    raise Exception(f"Login failed: {response.status}")

                content = await response.text()
                sid_match = re.search(r'<SID>(.*?)</SID>', content)
                if not sid_match or sid_match.group(1) == '0000000000000000':
                    raise Exception("Login failed: Invalid SID")

                self.sid = sid_match.group(1)

            return self.session, self.sid
        except Exception as err:
            _LOGGER.error(f"Error getting session: {err}")
            raise

    async def async_get_vpn_connections(self) -> Dict[str, Any]:
        """Get list of WireGuard VPN connections."""
        session, sid = await self.async_get_session()

        data_url = f"http://{self.host}{API_DATA}"
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
            async with session.post(data_url, data=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data and 'init' in data['data'] and 'boxConnections' in data['data']['init']:
                        return data['data']['init']['boxConnections']
        except Exception as err:
            _LOGGER.error(f"Error getting VPN connections: {err}")
            raise

        return {}

    async def async_toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle a VPN connection on/off."""
        session, sid = await self.async_get_session()

        api_url = f"http://{self.host}{API_VPN_CONNECTION.format(uid=connection_uid)}"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'AVM-SID {sid}',
            'Accept': '*/*',
            'Origin': f'http://{self.host}',
            'Referer': f'http://{self.host}/'
        }
        request_body = {'activated': '1' if enable else '0'}

        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)
        try:
            async with session.put(
                api_url,
                json=request_body,
                headers=headers,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    # Wait a bit for the change to take effect
                    await asyncio.sleep(1.5)
                    return True
                else:
                    error_text = await response.text()
                    _LOGGER.error(
                        f"Error toggling VPN: HTTP {response.status}, {error_text[:200]}"
                    )
                    return False
        except Exception as err:
            _LOGGER.error(f"Error toggling VPN: {err}")
            return False

    async def async_close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
            self.session = None
            self.sid = None


class FritzBoxVPNCoordinator(DataUpdateCoordinator):
    """Coordinator for FritzBox VPN data."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="fritzbox_vpn",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.fritz_session = FritzBoxVPNSession(
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD]
        )
        self.config = config

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch the latest VPN data."""
        try:
            connections = await self.fritz_session.async_get_vpn_connections()
            return connections
        except Exception as err:
            raise UpdateFailed(f"Error fetching VPN data: {err}")

    async def toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle a VPN connection."""
        return await self.fritz_session.async_toggle_vpn(connection_uid, enable)

