"""Tests for FritzConnectionVPNSession adapter hardening."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.fritzbox_vpn.fritzconnection_session import (
    FritzConnectionVPNSession,
)
from fritzboxvpn.const import DEFAULT_TIMEOUT
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout


@pytest.mark.asyncio
async def test_async_close_does_not_bootstrap_client() -> None:
    """Unload must not create a FritzConnection against an unavailable router."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: fn(*a))
    session = FritzConnectionVPNSession(hass, "1.2.3.4", "u", "p")

    with patch.object(session, "_ensure_client") as ensure:
        await session.async_close()
    ensure.assert_not_called()
    hass.async_add_executor_job.assert_not_called()


@pytest.mark.asyncio
async def test_async_close_closes_existing_fritzconnection_only() -> None:
    """Initialized FritzConnection sessions are closed via executor."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: fn(*a))
    session = FritzConnectionVPNSession(hass, "1.2.3.4", "u", "p")
    session._mode = "fritzconnection"
    fc = MagicMock()
    session._fc = fc
    session._fwg = MagicMock()

    await session.async_close()
    fc.session.close.assert_called_once()
    assert session._fc is None


def test_ensure_client_passes_timeout_to_fritzconnection() -> None:
    """FritzConnection bootstrap must set a constructor timeout."""
    hass = MagicMock()
    session = FritzConnectionVPNSession(hass, "1.2.3.4", "user", "pass", use_tls=True)

    fake_fc_cls = MagicMock(return_value=MagicMock())
    fake_fwg_cls = MagicMock(return_value=MagicMock())
    fake_mod = types.ModuleType("fritzconnection.lib.fritzwireguard")
    fake_mod.FritzWireguard = fake_fwg_cls

    with (
        patch.dict(sys.modules, {"fritzconnection.lib.fritzwireguard": fake_mod}),
        patch("fritzconnection.FritzConnection", fake_fc_cls),
    ):
        session._ensure_client()

    fake_fc_cls.assert_called_once_with(
        address="1.2.3.4",
        user="user",
        password="pass",
        timeout=float(DEFAULT_TIMEOUT),
        use_tls=True,
    )
    assert session._mode == "fritzconnection"


@pytest.mark.asyncio
async def test_get_vpn_connections_maps_bootstrap_timeout() -> None:
    """Discovery timeouts during ensure_client become TimeoutError."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=RequestsTimeout("slow"))
    session = FritzConnectionVPNSession(hass, "1.2.3.4", "u", "p")

    with pytest.raises(TimeoutError, match="slow"):
        await session.async_get_vpn_connections()


@pytest.mark.asyncio
async def test_get_vpn_connections_https_fallback_on_bootstrap_connection_error() -> (
    None
):
    """Connection errors during bootstrap trigger HTTPS→HTTP retry."""
    hass = MagicMock()
    session = FritzConnectionVPNSession(hass, "1.2.3.4", "u", "p", use_tls=True)
    calls = {"ensure": 0}

    def ensure() -> None:
        calls["ensure"] += 1
        if calls["ensure"] == 1:
            raise RequestsConnectionError("https down")
        session._mode = "fritzconnection"
        session._fwg = MagicMock()
        session._fwg.get_vpn_connections.return_value = {"a": {"uid": "a"}}

    session._ensure_client = ensure  # type: ignore[method-assign]
    session._close_sync = MagicMock()  # type: ignore[method-assign]

    async def run_job(fn, *args):
        return fn(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=run_job)

    data = await session.async_get_vpn_connections()
    assert data == {"a": {"uid": "a"}}
    assert session._use_tls is False
    assert calls["ensure"] >= 2
