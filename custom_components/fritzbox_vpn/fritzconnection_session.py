"""Adapter: FritzConnection-based session for FritzBox VPN HTTP API endpoints."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from fritzboxvpn.const import DEFAULT_TIMEOUT
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

from .const import LOG_MSG_SESSION_MODE_FALLBACK

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from fritzconnection import FritzConnection
    from fritzconnection.lib.fritzwireguard import FritzWireguard

T = TypeVar("T")


class FritzConnectionVPNSession:
    """Async wrapper for FritzConnection (sync) WireGuard calls.

    The integration expects these methods:
    - async_get_vpn_connections() -> dict[connection_uid, connection_payload]
    - async_toggle_vpn(connection_uid, enable) -> bool
    - invalidate_session()
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

        self._mode: str | None = None
        self._fallback_mode_logged = False

        self._fc: FritzConnection | None = None  # type: ignore[name-defined]
        self._fwg: FritzWireguard | None = None  # type: ignore[name-defined]
        self._fallback_session: Any | None = None

    def _ensure_client(self) -> None:
        if (
            self._mode == "fritzconnection"
            and self._fc is not None
            and self._fwg is not None
        ):
            return
        if self._mode == "fritzboxvpn" and self._fallback_session is not None:
            return

        # Import lazily so unit tests can run even when `fritzconnection`
        # is not installed in the fritzbox-vpn test venv.
        try:
            from fritzconnection import FritzConnection  # type: ignore
            from fritzconnection.lib.fritzwireguard import (
                FritzWireguard,  # type: ignore
            )
        except ModuleNotFoundError:
            # Some fritzconnection builds ship without the WireGuard module.
            # In that case fall back to the integration's fritzboxvpn library.
            from fritzboxvpn import FritzBoxVPNSession
            from homeassistant.helpers.aiohttp_client import (
                async_get_clientsession,
            )

            protocol = "https" if self._use_tls else "http"
            self._fallback_session = FritzBoxVPNSession(
                async_get_clientsession(self._hass),
                self._host,
                self._username,
                self._password,
                protocol=protocol,
            )
            self._mode = "fritzboxvpn"
            if not self._fallback_mode_logged:
                self._fallback_mode_logged = True
                _LOGGER.warning(LOG_MSG_SESSION_MODE_FALLBACK, self._host)
            return

        # Router API discovery happens here — callers must invoke this from a
        # path that maps Timeout/Connection/auth errors (see async_* methods).
        self._fc = FritzConnection(
            address=self._host,
            user=self._username or None,
            password=self._password,
            timeout=float(DEFAULT_TIMEOUT),
            use_tls=self._use_tls,
        )
        self._fwg = FritzWireguard(fc=self._fc)
        self._mode = "fritzconnection"

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

    def invalidate_session(self) -> None:
        """Drop cached client/session so the next request reconnects.

        Also resets TLS preference to HTTPS. A temporary reboot outage can
        flip HTTPS→HTTP for the lifetime of this adapter otherwise.
        """
        if self._fallback_session is not None:
            self._fallback_session.invalidate_session()
        if self._fc is not None:
            try:
                self._fc.session.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                _LOGGER.debug("Error closing FritzConnection session", exc_info=True)
        self._fc = None
        self._fwg = None
        self._use_tls = True
        # Keep mode/fallback; only the active transport cache is cleared.

    def _get_vpn_connections_sync(self) -> dict[str, Any]:
        self._ensure_client()
        if self._mode != "fritzconnection":
            raise RuntimeError("Unexpected mode for sync VPN fetch")
        assert self._fwg is not None
        return self._fwg.get_vpn_connections()

    def _toggle_vpn_sync(self, connection_uid: str, enable: bool) -> bool:
        self._ensure_client()
        if self._mode != "fritzconnection":
            raise RuntimeError("Unexpected mode for sync VPN toggle")
        assert self._fwg is not None
        return self._fwg.toggle_vpn(connection_uid, enable)

    async def async_close(self) -> None:
        """Close only already-initialized transport; never bootstrap a client."""
        if self._fallback_session is not None:
            await self._fallback_session.async_close()
            return
        if self._fc is not None:
            await self._hass.async_add_executor_job(self._close_sync)

    def _raise_auth_error(self, err: Exception, *, as_value_error: bool) -> None:
        """Raise auth failure with the caller-specific exception type."""
        message = f"Login failed: {err}"
        if as_value_error:
            raise ValueError(message) from err
        raise ConnectionError(message) from err

    async def _async_with_https_http_fallback(
        self,
        *,
        fallback_primary: Callable[[], Awaitable[T]],
        sync_call: Callable[[], T],
        fail_message: str,
        auth_as_value_error: bool,
    ) -> T:
        """Run call; on HTTPS connect error retry once over HTTP."""
        try:
            await self._hass.async_add_executor_job(self._ensure_client)
            if self._mode == "fritzboxvpn":
                return await fallback_primary()
            return await self._hass.async_add_executor_job(sync_call)
        except RequestsTimeout as err:
            self.invalidate_session()
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
                try:
                    return await self._hass.async_add_executor_job(sync_call)
                except RequestsTimeout as retry_err:
                    self.invalidate_session()
                    raise TimeoutError(str(retry_err)) from retry_err
                except RequestsConnectionError as retry_err:
                    self.invalidate_session()
                    raise ConnectionError(f"{fail_message}: {retry_err}") from retry_err
                except Exception as retry_err:
                    if self._is_fritz_authorization_error(retry_err):
                        self._raise_auth_error(
                            retry_err, as_value_error=auth_as_value_error
                        )
                    raise
            self.invalidate_session()
            raise ConnectionError(f"{fail_message}: {err}") from err
        except Exception as err:
            if self._is_fritz_authorization_error(err):
                self._raise_auth_error(err, as_value_error=auth_as_value_error)
            raise

    async def async_get_vpn_connections(self) -> dict[str, Any]:
        """Fetch latest VPN connections with HTTPS->HTTP fallback."""

        async def _fallback_primary() -> dict[str, Any]:
            assert self._fallback_session is not None
            return await self._fallback_session.async_get_vpn_connections()

        return await self._async_with_https_http_fallback(
            fallback_primary=_fallback_primary,
            sync_call=self._get_vpn_connections_sync,
            fail_message="failed to get login page",
            auth_as_value_error=True,
        )

    async def async_toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle VPN on/off with HTTPS->HTTP fallback and auth propagation."""

        async def _fallback_primary() -> bool:
            assert self._fallback_session is not None
            return await self._fallback_session.async_toggle_vpn(connection_uid, enable)

        return await self._async_with_https_http_fallback(
            fallback_primary=_fallback_primary,
            sync_call=lambda: self._toggle_vpn_sync(connection_uid, enable),
            fail_message="failed to toggle VPN",
            auth_as_value_error=False,
        )
