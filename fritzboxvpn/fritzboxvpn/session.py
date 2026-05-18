"""Fritz!Box Web UI session for WireGuard VPN API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any
from urllib.parse import urlsplit

from aiohttp import ClientConnectorError, ClientSession, ClientTimeout

from .const import (
    API_DATA,
    API_KEY_ACTIVATED,
    API_KEY_ACTIVE,
    API_KEY_NAME,
    API_KEY_UID,
    API_LOGIN,
    API_PAGE_SHAREWIREGUARD,
    API_VPN_CONNECTION,
    AUTH_HEADER_PREFIX,
    CONTENT_TYPE_JSON,
    DEFAULT_NAME_UNKNOWN,
    DEFAULT_PROTOCOL,
    DEFAULT_TIMEOUT,
    ERROR_MSG_INVALID_SID,
    ERROR_MSG_INVALID_SID_403,
    ERROR_MSG_INVALID_SID_HTML,
    ERROR_MSG_LOGIN_FAILED_SID,
    HEADER_VALUE_APPLICATION_JSON,
    HTTP_STATUS_FORBIDDEN,
    HTTP_STATUS_OK,
    HTTPS_FALLBACK_STATUS_CODES,
    INVALID_SID_VALUE,
    LOG_LABEL_ACTIVATED,
    LOG_LABEL_DEACTIVATED,
    LOGIN_FORM_RESPONSE,
    LOGIN_FORM_USERNAME,
    NAME_FRITZBOX,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    PROTOCOLS_ALLOWED,
    VERIFICATION_DELAY,
)
from .parsing import (
    extract_box_connections_from_data,
    normalize_box_connections,
    parse_blocktime_from_login_xml,
    parse_challenge_from_login_xml,
    parse_sid_from_login_response,
)

_LOGGER = logging.getLogger(__name__)


class FritzBoxVPNSession:
    """Session manager for Fritz!Box Web-UI API."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        username: str,
        password: str,
        protocol: str = DEFAULT_PROTOCOL,
    ) -> None:
        self.session = session
        self.host = host
        self.username = username
        self.password = password
        self.protocol = protocol if protocol in PROTOCOLS_ALLOWED else DEFAULT_PROTOCOL
        self.sid: str | None = None

    async def async_get_session(self) -> tuple[ClientSession, str]:
        """Return session and SID; reuse cached SID if valid."""
        if self.sid is not None:
            return self.session, self.sid

        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)

        sid = None
        try:
            sid = await self._try_get_session_via_pbkdf2(timeout)
        except (ConnectionError, ValueError):
            _LOGGER.debug("PBKDF2 login not usable; falling back to MD5.")

        if sid:
            _LOGGER.debug("Using PBKDF2 login flow for session generation.")
            self.sid = sid
            return self.session, self.sid
        if sid is None:
            _LOGGER.debug(
                "PBKDF2 not supported by this Fritz!OS (or challenge format mismatch); "
                "falling back to MD5."
            )

        login_url = f"{self.protocol}://{self.host}{API_LOGIN}"
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

        challenge = parse_challenge_from_login_xml(content)
        if not challenge:
            raise ValueError("Could not parse login response XML or find challenge")

        _LOGGER.debug("Using legacy MD5 login flow for session generation.")

        md5_input = f"{challenge}-{self.password}".encode("utf-16le")
        # codeql[py/weak-sensitive-data-hashing]: FRITZ!Box legacy login protocol requires MD5 challenge-response.
        response_hash = hashlib.md5(md5_input).hexdigest()
        login_data = {
            LOGIN_FORM_USERNAME: self.username,
            LOGIN_FORM_RESPONSE: f"{challenge}-{response_hash}",
        }
        async with self.session.post(
            login_url, data=login_data, ssl=False, timeout=timeout
        ) as response:
            if response.status != HTTP_STATUS_OK:
                raise ConnectionError(f"Login failed: {response.status}")
            content = await response.text()

        sid = parse_sid_from_login_response(content)
        if not sid or sid == INVALID_SID_VALUE:
            raise ValueError(
                ERROR_MSG_LOGIN_FAILED_SID.format(name_fritzbox=NAME_FRITZBOX)
            )
        self.sid = sid
        return self.session, self.sid

    async def _try_get_session_via_pbkdf2(self, timeout: ClientTimeout) -> str | None:
        """Return valid SID via pbkdf2 challenge-response, or None if unsupported."""
        _LOGGER.debug("Trying PBKDF2 login flow (login_sid.lua?version=2).")
        login_url_get = f"{self.protocol}://{self.host}{API_LOGIN}?version=2"
        content = await self._fetch_login_page(login_url_get, timeout)
        if not content:
            return None

        challenge = parse_challenge_from_login_xml(content)
        if not challenge or not challenge.startswith("2$"):
            _LOGGER.debug(
                "PBKDF2 not supported (challenge format mismatch); falling back."
            )
            return None

        blocktime = parse_blocktime_from_login_xml(content)
        if blocktime and blocktime > 0:
            _LOGGER.debug("PBKDF2 BlockTime=%d; waiting before login.", blocktime)
            await asyncio.sleep(blocktime)

        response = self._calculate_pbkdf2_response(challenge, self.password)
        login_data = {
            LOGIN_FORM_USERNAME: self.username,
            LOGIN_FORM_RESPONSE: response,
        }

        login_url_post = f"{self.protocol}://{self.host}{API_LOGIN}?version=2"
        async with self.session.post(
            login_url_post, data=login_data, ssl=False, timeout=timeout
        ) as response_http:
            if response_http.status != HTTP_STATUS_OK:
                return None
            resp_content = await response_http.text()

        sid = parse_sid_from_login_response(resp_content)
        if not sid or sid == INVALID_SID_VALUE:
            return None
        _LOGGER.debug("PBKDF2 login flow succeeded for session generation.")
        return sid

    @staticmethod
    def _calculate_pbkdf2_response(challenge: str, password: str) -> str:
        """Calculate PBKDF2-based Fritz!Box web login response."""
        parts = challenge.split("$")
        if len(parts) < 5 or parts[0] != "2":
            raise ValueError("Unexpected PBKDF2 challenge format")

        iter1 = int(parts[1])
        salt1_hex = parts[2]
        iter2 = int(parts[3])
        salt2_hex = parts[4]

        salt1 = bytes.fromhex(salt1_hex)
        salt2 = bytes.fromhex(salt2_hex)

        hash1 = hashlib.pbkdf2_hmac("sha256", password.encode(), salt1, iter1)
        hash2 = hashlib.pbkdf2_hmac("sha256", hash1, salt2, iter2)

        return f"{salt2_hex}${hash2.hex()}"

    async def _fetch_login_page(self, login_url: str, timeout: ClientTimeout) -> str | None:
        """GET login page; HTTPS→HTTP fallback. Returns content or None."""
        parsed = urlsplit(login_url)
        api_path = parsed.path
        query = parsed.query
        try:
            async with self.session.get(
                login_url, ssl=False, timeout=timeout
            ) as response:
                if response.status == HTTP_STATUS_OK:
                    return await response.text()
                if (
                    self.protocol == PROTOCOL_HTTPS
                    and response.status in HTTPS_FALLBACK_STATUS_CODES
                ):
                    _LOGGER.warning(
                        "HTTPS connection failed (status %d), falling back to HTTP. "
                        "Consider using HTTP if your %s doesn't support HTTPS.",
                        response.status,
                        NAME_FRITZBOX,
                    )
                    self.protocol = PROTOCOL_HTTP
                    login_url = (
                        f"{self.protocol}://{self.host}{api_path}"
                        f"{'?' + query if query else ''}"
                    )
                    async with self.session.get(
                        login_url, ssl=False, timeout=timeout
                    ) as retry_response:
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
            login_url = (
                f"{self.protocol}://{self.host}{api_path}"
                f"{'?' + query if query else ''}"
            )
            async with self.session.get(
                login_url, ssl=False, timeout=timeout
            ) as response:
                if response.status != HTTP_STATUS_OK:
                    raise ConnectionError(
                        f"Failed to get login page: {response.status}"
                    ) from err
                return await response.text()

    async def _fetch_vpn_connections_once(self) -> dict[str, Any]:
        """Single VPN connections request; {} on non-auth errors."""
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
        async with session.post(
            data_url, data=params, timeout=timeout, ssl=False
        ) as response:
            if response.status == HTTP_STATUS_FORBIDDEN:
                raise ValueError(ERROR_MSG_INVALID_SID_403)
            if response.status != HTTP_STATUS_OK:
                _LOGGER.warning("Failed to get VPN connections: HTTP %d", response.status)
                return {}

            content_type = (response.headers.get("Content-Type") or "").lower()
            if CONTENT_TYPE_JSON not in content_type:
                raise ValueError(ERROR_MSG_INVALID_SID_HTML)
            try:
                body = await response.text()
                data = json.loads(body)
            except (json.JSONDecodeError, TypeError) as err:
                raise ValueError(ERROR_MSG_INVALID_SID_HTML) from err

            box = extract_box_connections_from_data(data, API_PAGE_SHAREWIREGUARD)
            if box is not None:
                return normalize_box_connections(box)
            return {}

    async def async_get_vpn_connections(self) -> dict[str, Any]:
        """WireGuard VPN connections; cached session, retry once on SID expiry."""
        try:
            return await self._fetch_vpn_connections_once()
        except ValueError as err:
            if ERROR_MSG_INVALID_SID in str(err):
                self.invalidate_session()
                return await self._fetch_vpn_connections_once()
            raise
        except TimeoutError as err:
            _LOGGER.error("Timeout getting VPN connections: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Error getting VPN connections: %s", err)
            raise

    async def async_toggle_vpn(
        self, connection_uid: str, enable: bool, _sid_retry: bool = True
    ) -> bool:
        """Toggle VPN on/off; retry once on 403 (expired SID)."""
        connections = await self.async_get_vpn_connections()
        if connection_uid not in connections:
            _LOGGER.error("VPN connection %s not found", connection_uid)
            return False

        conn = connections[connection_uid]
        vpn_uid = conn.get(API_KEY_UID)
        if not vpn_uid:
            _LOGGER.error("VPN connection %s has no UID", connection_uid)
            return False

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
                    return await self.async_toggle_vpn(
                        connection_uid, enable, _sid_retry=False
                    )
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
        except TimeoutError as err:
            _LOGGER.error("Timeout toggling VPN: %s", err)
            return False
        except Exception:
            _LOGGER.exception("Error toggling VPN")
            return False

    def invalidate_session(self) -> None:
        """Invalidate cached SID so next request performs new login."""
        self.sid = None

    async def async_close(self) -> None:
        """Clear cached SID."""
        self.sid = None
