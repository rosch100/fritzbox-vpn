"""Adapter: FritzConnection-based session for FritzBox VPN Web UI REST API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from fritzconnection import FritzConnection
    from fritzconnection.lib.fritzwireguard import FritzWireguard


class FritzConnectionVPNSession:
    """Async wrapper for FritzConnection (sync) WireGuard calls.

    The integration expects these methods:
    - async_get_vpn_connections() -> dict[connection_uid, connection_payload]
    - async_toggle_vpn(connection_uid, enable) -> bool
    - async_close()
    """

    def __init__(
        self,
        hass: Any,
        host: str,
        username: str,
        password: str,
        *,
        use_tls: bool = True,
    ) -> None:
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._use_tls = use_tls

        self._fc: FritzConnection | None = None  # type: ignore[name-defined]
        self._fwg: FritzWireguard | None = None  # type: ignore[name-defined]

    def _ensure_client(self) -> None:
        if self._fc is not None and self._fwg is not None:
            return

        # Import lazily so unit tests can run even when `fritzconnection`
        # is not installed in the fritzbox-vpn test venv.
        from fritzconnection import FritzConnection  # type: ignore
        from fritzconnection.lib.fritzwireguard import FritzWireguard  # type: ignore

        self._fc = FritzConnection(
            address=self._host,
            user=self._username or None,
            password=self._password,
            use_tls=self._use_tls,
        )
        self._fwg = FritzWireguard(fc=self._fc)

    @staticmethod
    def _is_fritz_authorization_error(err: Exception) -> bool:
        # Import lazily to avoid hard dependency at import time.
        try:
            from fritzconnection.core.exceptions import (
                FritzAuthorizationError,  # type: ignore
            )
        except Exception:
            return err.__class__.__name__ == "FritzAuthorizationError"
        return isinstance(err, FritzAuthorizationError)

    def _close_sync(self) -> None:
        if self._fc is None:
            return
        # requests.Session.close() is safe and synchronous
        self._fc.session.close()
        self._fc = None
        self._fwg = None

    def _get_vpn_connections_sync(self) -> dict[str, Any]:
        self._ensure_client()
        assert self._fwg is not None
        return self._fwg.get_vpn_connections()

    def _toggle_vpn_sync(self, connection_uid: str, enable: bool) -> bool:
        self._ensure_client()
        assert self._fwg is not None
        return self._fwg.toggle_vpn(connection_uid, enable)

    async def async_close(self) -> None:
        await self._hass.async_add_executor_job(self._close_sync)

    async def async_get_vpn_connections(self) -> dict[str, Any]:
        """Fetch latest VPN connections with HTTPS->HTTP fallback."""
        try:
            return await self._hass.async_add_executor_job(
                self._get_vpn_connections_sync
            )
        except RequestsTimeout as err:
            raise TimeoutError(str(err)) from err
        except RequestsConnectionError as err:
            if self._use_tls:
                _LOGGER.warning(
                    "HTTPS connection failed; falling back to HTTP for host %s: %s",
                    self._host,
                    err,
                )
                self._use_tls = False
                await self._hass.async_add_executor_job(self._close_sync)
                return await self._hass.async_add_executor_job(
                    self._get_vpn_connections_sync
                )
            raise ConnectionError(f"failed to get login page: {err}") from err
        except Exception as err:
            if self._is_fritz_authorization_error(err):
                # Coordinator maps auth-indicators by substring matching.
                raise ValueError(f"Invalid SID: {err}") from err
            raise

    async def async_toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle VPN on/off with HTTPS->HTTP fallback and auth propagation."""
        try:
            return await self._hass.async_add_executor_job(
                self._toggle_vpn_sync, connection_uid, enable
            )
        except RequestsTimeout as err:
            raise TimeoutError(str(err)) from err
        except RequestsConnectionError as err:
            if self._use_tls:
                _LOGGER.warning(
                    "HTTPS connection failed; falling back to HTTP for host %s: %s",
                    self._host,
                    err,
                )
                self._use_tls = False
                await self._hass.async_add_executor_job(self._close_sync)
                return await self._hass.async_add_executor_job(
                    self._toggle_vpn_sync, connection_uid, enable
                )
            raise ConnectionError(f"failed to toggle VPN: {err}") from err
        except Exception as err:
            if self._is_fritz_authorization_error(err):
                # Coordinator may schedule reauth on auth errors.
                raise ConnectionError(f"invalid sid: {err}") from err
            raise

