"""Fritz!Box Web UI session for WireGuard VPN API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, NoReturn
from urllib.parse import urlsplit

from aiohttp import (
    ClientConnectorError,
    ClientResponse,
    ClientSession,
    ClientTimeout,
    hdrs,
)

from .const import (
    API_DATA,
    API_KEY_ACTIVATED,
    API_KEY_ACTIVE,
    API_KEY_NAME,
    API_KEY_UID,
    API_LOGIN,
    API_PAGE_SHAREWIREGUARD,
    API_VPN_CONNECTION,
    API_VPN_ROOT,
    AUTH_HEADER_PREFIX,
    CONTENT_TYPE_JSON,
    DEFAULT_NAME_UNKNOWN,
    DEFAULT_PROTOCOL,
    DEFAULT_TIMEOUT,
    ERROR_MSG_INVALID_SID,
    ERROR_MSG_INVALID_SID_403,
    ERROR_MSG_INVALID_SID_HTML,
    ERROR_MSG_LOGIN_FAILED_SID,
    ERROR_MSG_VPN_PAYLOAD_MISSING,
    HEADER_CLIENT_NAME,
    HEADER_VALUE_APPLICATION_JSON,
    HEADER_VALUE_CLIENT_NAME,
    HTTP_STATUS_FORBIDDEN,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
    HTTPS_FALLBACK_STATUS_CODES,
    INVALID_SID_VALUE,
    LISTING_MODE_DATA_LUA,
    LISTING_MODE_REST,
    LISTING_PROBE_ORDER,
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
    extract_wireguard_connections_from_rest,
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
        self._listing_mode: str | None = None

    def _base_url(self) -> str:
        """Protocol + host origin for REST URLs and browser-like headers."""
        return f"{self.protocol}://{self.host}"

    def _login_url(self, *, version2: bool = False) -> str:
        """login_sid.lua URL; optionally FRITZ!OS version=2 (PBKDF2)."""
        url = f"{self._base_url()}{API_LOGIN}"
        if version2:
            return f"{url}?version=2"
        return url

    def _rest_headers(self, sid: str, *, mutation: bool = False) -> dict[str, str]:
        """Headers required by FRITZ!OS REST helpers (AVM-SID + WebGUI client)."""
        headers = {
            hdrs.AUTHORIZATION: f"{AUTH_HEADER_PREFIX}{sid}",
            hdrs.CONTENT_TYPE: HEADER_VALUE_APPLICATION_JSON,
            hdrs.ACCEPT: HEADER_VALUE_APPLICATION_JSON,
            HEADER_CLIENT_NAME: HEADER_VALUE_CLIENT_NAME,
        }
        if mutation:
            base = self._base_url()
            headers[hdrs.ACCEPT] = "*/*"
            headers[hdrs.ORIGIN] = base
            headers[hdrs.REFERER] = f"{base}/"
        return headers

    @staticmethod
    async def _response_json_dict(
        response: ClientResponse, *, require_json: bool = False
    ) -> dict[str, Any] | None:
        """Parse response body as a JSON object; None when contract is absent."""
        content_type = (response.headers.get(hdrs.CONTENT_TYPE) or "").lower()
        if CONTENT_TYPE_JSON not in content_type:
            if require_json:
                raise ValueError(ERROR_MSG_INVALID_SID_HTML)
            return None
        try:
            data = json.loads(await response.text())
        except (json.JSONDecodeError, TypeError) as err:
            if require_json:
                raise ValueError(ERROR_MSG_INVALID_SID_HTML) from err
            return None
        if isinstance(data, dict):
            return data
        return None

    def _validate_vpn_listing_status(
        self,
        response: ClientResponse,
        *,
        source: str,
    ) -> None:
        """Validate a successful listing response or raise its explicit error."""
        if response.status == HTTP_STATUS_FORBIDDEN:
            raise ValueError(ERROR_MSG_INVALID_SID_403)
        if response.status != HTTP_STATUS_OK:
            self.invalidate_session()
            raise ConnectionError(
                f"Failed to get VPN connections{source}: HTTP {response.status}"
            )

    async def async_get_session(self) -> tuple[ClientSession, str]:
        """Return session and SID; reuse cached SID if valid."""
        if self.sid is not None:
            return self.session, self.sid

        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)

        sid = None
        try:
            sid = await self._try_get_session_via_pbkdf2(timeout)
        except ValueError:
            # Challenge/format mismatch only — transport failures must propagate
            # so reboot outages are not masked as "try MD5 next".
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

        login_url = self._login_url()
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
        # Rebuild after possible HTTPS→HTTP fallback in _fetch_login_page.
        login_url = self._login_url()
        try:
            async with self.session.post(
                login_url, data=login_data, ssl=False, timeout=timeout
            ) as response:
                if response.status != HTTP_STATUS_OK:
                    raise ConnectionError(f"Login failed: {response.status}")
                content = await response.text()
        except ConnectionError:
            raise
        except (ClientConnectorError, OSError) as err:
            self._raise_transport_error(err)

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
        content = await self._fetch_login_page(self._login_url(version2=True), timeout)
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

        try:
            async with self.session.post(
                self._login_url(version2=True),
                data=login_data,
                ssl=False,
                timeout=timeout,
            ) as response_http:
                if response_http.status != HTTP_STATUS_OK:
                    return None
                resp_content = await response_http.text()
        except ConnectionError:
            raise
        except (ClientConnectorError, OSError) as err:
            self._raise_transport_error(err)

        sid = parse_sid_from_login_response(resp_content)
        if not sid or sid == INVALID_SID_VALUE:
            return None
        _LOGGER.debug("PBKDF2 login flow succeeded for session generation.")
        return sid

    def _raise_transport_error(self, err: BaseException) -> NoReturn:
        """Clear SID/protocol and raise ConnectionError for transport failures."""
        self.invalidate_session()
        raise ConnectionError(f"Cannot connect to {self.host}: {err}") from err

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

    async def _get_login_page_http(
        self, api_path: str, query: str, timeout: ClientTimeout
    ) -> str:
        """GET login page over HTTP and switch protocol only after success."""
        login_url = (
            f"{PROTOCOL_HTTP}://{self.host}{api_path}{'?' + query if query else ''}"
        )
        try:
            async with self.session.get(
                login_url, ssl=False, timeout=timeout
            ) as response:
                if response.status != HTTP_STATUS_OK:
                    raise ConnectionError(
                        f"Failed to get login page: {response.status}"
                    )
                content = await response.text()
        except ConnectionError:
            raise
        except (ClientConnectorError, OSError) as err:
            raise ConnectionError(f"Cannot connect to {self.host}: {err}") from err
        self.protocol = PROTOCOL_HTTP
        return content

    async def _fetch_login_page(
        self, login_url: str, timeout: ClientTimeout
    ) -> str | None:
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
                    return await self._get_login_page_http(api_path, query, timeout)
                raise ConnectionError(f"Failed to get login page: {response.status}")
        except (ClientConnectorError, OSError) as err:
            if self.protocol != PROTOCOL_HTTPS:
                raise ConnectionError(f"Cannot connect to {self.host}: {err}") from err
            _LOGGER.warning(
                "HTTPS connection failed (%s), falling back to HTTP.",
                err,
            )
            return await self._get_login_page_http(api_path, query, timeout)

    async def _fetch_listing_by_mode(
        self, mode: str, session: ClientSession, sid: str
    ) -> dict[str, Any] | None:
        """Dispatch to the listing implementation for a cached/probed mode."""
        if mode == LISTING_MODE_REST:
            return await self._fetch_vpn_connections_via_rest(session, sid)
        if mode == LISTING_MODE_DATA_LUA:
            return await self._fetch_vpn_connections_via_data_lua(session, sid)
        raise ValueError(f"Unknown VPN listing mode: {mode}")

    async def _fetch_vpn_connections_via_rest(
        self, session: ClientSession, sid: str
    ) -> dict[str, Any] | None:
        """GET /api/v0/generic/vpn; None when the REST listing contract is absent."""
        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)
        try:
            async with session.get(
                f"{self._base_url()}{API_VPN_ROOT}",
                headers=self._rest_headers(sid),
                timeout=timeout,
                ssl=False,
            ) as response:
                if response.status == HTTP_STATUS_NOT_FOUND:
                    return None
                self._validate_vpn_listing_status(response, source=" via REST")
                data = await self._response_json_dict(response)
                if data is None:
                    return None
                box = extract_wireguard_connections_from_rest(data)
                if box is None:
                    return None
                return normalize_box_connections(box)
        except (ClientConnectorError, OSError) as err:
            self._raise_transport_error(err)

    async def _fetch_vpn_connections_via_data_lua(
        self, session: ClientSession, sid: str
    ) -> dict[str, Any] | None:
        """POST /data.lua shareWireguard; None when boxConnections is absent."""
        params = {
            "sid": sid,
            "xhr": "1",
            "xhrId": "all",
            "page": API_PAGE_SHAREWIREGUARD,
            "no_sidrenew": "",
        }
        timeout = ClientTimeout(total=DEFAULT_TIMEOUT)
        try:
            async with session.post(
                f"{self._base_url()}{API_DATA}",
                data=params,
                timeout=timeout,
                ssl=False,
            ) as response:
                self._validate_vpn_listing_status(response, source="")
                data = await self._response_json_dict(response, require_json=True)
                if data is None:
                    return None
                box = extract_box_connections_from_data(data, API_PAGE_SHAREWIREGUARD)
                if box is None:
                    return None
                return normalize_box_connections(box)
        except (ClientConnectorError, OSError) as err:
            # Reboot / port-down: clear cached SID+protocol so the next poll recovers.
            self._raise_transport_error(err)

    async def _fetch_vpn_connections_once(self) -> dict[str, Any]:
        """Single VPN connections request; raises on outage/missing payload."""
        session, sid = await self.async_get_session()
        preferred = self._listing_mode

        if preferred is not None:
            result = await self._fetch_listing_by_mode(preferred, session, sid)
            if result is not None:
                return result
            self._listing_mode = None

        for mode in LISTING_PROBE_ORDER:
            if mode == preferred:
                continue
            result = await self._fetch_listing_by_mode(mode, session, sid)
            if result is not None:
                self._listing_mode = mode
                return result

        # Missing payloads are typical while the box is rebooting or the
        # cached SID/protocol is stale — do not soft-succeed with {}.
        self.invalidate_session()
        raise ConnectionError(ERROR_MSG_VPN_PAYLOAD_MISSING)

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
        except ConnectionError as err:
            _LOGGER.error("Error getting VPN connections: %s", err)
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
        api_url = f"{self._base_url()}{API_VPN_CONNECTION.format(uid=vpn_uid)}"
        headers = self._rest_headers(sid, mutation=True)
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
        """Invalidate cached SID and reset protocol so the next request re-logins.

        Protocol is reset to HTTPS because a temporary reboot outage can flip
        HTTPS→HTTP permanently for the lifetime of this session object.
        Listing mode is cleared so a firmware/API change is rediscovered.
        """
        self.sid = None
        self.protocol = DEFAULT_PROTOCOL
        self._listing_mode = None

    async def async_close(self) -> None:
        """Clear cached SID and reset protocol."""
        self.invalidate_session()
