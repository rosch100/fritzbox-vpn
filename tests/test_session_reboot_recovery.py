"""Regression tests for Fritz!Box reboot / session recovery (#42)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectorError
from custom_components.fritzbox_vpn.const import RETRY_AFTER_SECONDS
from custom_components.fritzbox_vpn.coordinator import FritzBoxVPNCoordinator
from fritzboxvpn import FritzBoxVPNSession
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.aiohttp_mock import MockAiohttpResponse, QueuedAiohttpSession, json_response
from tests.fixtures import (
    LOGIN_XML_CHALLENGE,
    LOGIN_XML_SID,
    MOCK_DATA_LUA_JSON,
    MOCK_HOST,
    MOCK_PASSWORD,
    MOCK_USERNAME,
)


def _connector_error(host: str = MOCK_HOST, port: int = 443) -> ClientConnectorError:
    """Build an aiohttp ClientConnectorError like a refused Fritz!Box port."""
    conn_key = MagicMock()
    conn_key.host = host
    conn_key.port = port
    conn_key.ssl = False
    return ClientConnectorError(
        conn_key, OSError(111, f"Connect call failed ('{host}', {port})")
    )


def _login_sequence() -> list[MockAiohttpResponse]:
    return [
        MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
        MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
        MockAiohttpResponse(200, text=LOGIN_XML_SID),
    ]


@pytest.mark.asyncio
async def test_non_ok_vpn_fetch_invalidates_session_and_raises() -> None:
    """HTTP 502 on data.lua must not soft-succeed with {} and keep a stale SID."""
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            MockAiohttpResponse(502, text="bad gateway"),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ConnectionError, match="502"):
        await fb.async_get_vpn_connections()
    assert fb.sid is None
    assert fb.protocol == "https"


@pytest.mark.asyncio
async def test_invalidate_session_resets_protocol_to_https() -> None:
    """Sticky HTTP fallback must be cleared so reboot recovery retries HTTPS."""
    fb = FritzBoxVPNSession(
        QueuedAiohttpSession([]), MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD
    )
    fb.sid = "stale"
    fb.protocol = "http"
    fb.invalidate_session()
    assert fb.sid is None
    assert fb.protocol == "https"


@pytest.mark.asyncio
async def test_reboot_outage_then_recover_without_reload() -> None:
    """After 502 outage, next poll can re-login and return VPN data again."""
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            MockAiohttpResponse(502, text="bad gateway"),
            *_login_sequence(),
            json_response(MOCK_DATA_LUA_JSON),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ConnectionError):
        await fb.async_get_vpn_connections()
    connections = await fb.async_get_vpn_connections()
    assert "conn-abc" in connections


@pytest.mark.asyncio
async def test_coordinator_sid_expiry_does_not_schedule_reauth(
    hass,
) -> None:
    """Session-expiry 'Invalid SID' is not a credential failure."""
    coordinator = FritzBoxVPNCoordinator(
        hass,
        {"host": MOCK_HOST, "username": "u", "password": "p"},
        None,
        "entry-1",
    )
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ValueError("Invalid SID (HTTP 403)")
    )
    with (
        patch.object(coordinator, "_schedule_reauth") as schedule_reauth,
        pytest.raises(UpdateFailed) as exc_info,
    ):
        await coordinator._async_update_data()
    schedule_reauth.assert_not_called()
    assert exc_info.value.retry_after is not None


@pytest.mark.asyncio
async def test_coordinator_login_failed_still_schedules_reauth(hass) -> None:
    """Real credential failures still start reauth."""
    coordinator = FritzBoxVPNCoordinator(
        hass,
        {"host": MOCK_HOST, "username": "u", "password": "p"},
        None,
        "entry-1",
    )
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ValueError("Login failed: Invalid SID")
    )
    mock_entry = MagicMock()
    mock_entry.async_start_reauth = AsyncMock()
    from homeassistant.config_entries import ConfigEntryState

    mock_entry.state = ConfigEntryState.LOADED
    hass.async_create_task = MagicMock()
    with (
        patch.object(hass.config_entries, "async_get_entry", return_value=mock_entry),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()
    hass.async_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_missing_box_connections_invalidates_and_raises() -> None:
    """JSON without boxConnections/REST listing is treated as outage, not empty success."""
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            json_response({"data": {"init": {"other": True}}}),
            MockAiohttpResponse(404, text="not found"),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ConnectionError, match="payload missing"):
        await fb.async_get_vpn_connections()
    assert fb.sid is None


@pytest.mark.asyncio
async def test_connect_refused_on_data_lua_invalidates_and_raises_connection_error() -> (
    None
):
    """Reboot ConnectionRefused on data.lua must clear SID and raise ConnectionError.

    Reporter log (#42): ClientConnectorError during session.post must not leave a
    cached SID and must not surface as an unhandled aiohttp exception.
    """
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            _connector_error(),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ConnectionError, match="Cannot connect"):
        await fb.async_get_vpn_connections()
    assert fb.sid is None
    assert fb.protocol == "https"


@pytest.mark.asyncio
async def test_connect_refused_then_recovers_on_next_poll() -> None:
    """After connect-refused outage, the next poll re-logins and returns data."""
    http = QueuedAiohttpSession(
        [
            *_login_sequence(),
            _connector_error(),
            *_login_sequence(),
            json_response(MOCK_DATA_LUA_JSON),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ConnectionError):
        await fb.async_get_vpn_connections()
    connections = await fb.async_get_vpn_connections()
    assert "conn-abc" in connections


@pytest.mark.asyncio
async def test_https_and_http_connect_refused_does_not_stick_protocol_to_http() -> None:
    """Failed HTTPS→HTTP fallback must not leave protocol permanently on HTTP."""
    http = QueuedAiohttpSession(
        [
            _connector_error(port=443),  # HTTPS login
            _connector_error(port=80),  # HTTP fallback
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ConnectionError, match="Cannot connect"):
        await fb.async_get_session()
    assert fb.protocol == "https"
    assert fb.sid is None


@pytest.mark.asyncio
async def test_coordinator_client_connector_error_uses_short_retry(
    hass,
) -> None:
    """Transport failures use UpdateFailed.retry_after suited for reboot recovery."""
    coordinator = FritzBoxVPNCoordinator(
        hass,
        {"host": MOCK_HOST, "username": "u", "password": "p"},
        None,
        "entry-1",
    )
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ConnectionError("Cannot connect to host")
    )
    coordinator.fritz_session.invalidate_session = MagicMock()
    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.retry_after == RETRY_AFTER_SECONDS
    assert RETRY_AFTER_SECONDS <= 60
    coordinator.fritz_session.invalidate_session.assert_called_once()


@pytest.mark.asyncio
async def test_md5_login_post_uses_http_after_https_get_fallback() -> None:
    """After HTTPS GET fails and HTTP login-page succeeds, MD5 POST must use HTTP."""
    http = QueuedAiohttpSession(
        [
            # PBKDF2 probe: HTTPS OK with legacy challenge → fall through to MD5
            MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
            # MD5 GET: HTTPS refused → HTTP challenge OK → MD5 POST on HTTP
            _connector_error(port=443),
            MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
            MockAiohttpResponse(200, text=LOGIN_XML_SID),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    session, sid = await fb.async_get_session()
    assert session is http
    assert sid == "deadbeef"
    assert fb.protocol == "http"
    post_urls = [url for method, url, _ in http.requests if method == "POST"]
    assert post_urls
    assert all(url.startswith("http://") for url in post_urls)
    assert not any(url.startswith("https://") for url in post_urls)


@pytest.mark.asyncio
async def test_md5_login_post_connector_error_raises_connection_error() -> None:
    """MD5 auth POST connect refused maps to ConnectionError and clears session."""
    http = QueuedAiohttpSession(
        [
            MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
            MockAiohttpResponse(200, text=LOGIN_XML_CHALLENGE),
            _connector_error(port=443),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ConnectionError, match="Cannot connect"):
        await fb.async_get_session()
    assert fb.sid is None
    assert fb.protocol == "https"


@pytest.mark.asyncio
async def test_pbkdf2_login_post_connector_error_raises_connection_error() -> None:
    """PBKDF2 version=2 auth POST connect refused maps to ConnectionError."""
    challenge = (
        "2$5$0123456789abcdef0123456789abcdef$5$fedcba9876543210fedcba9876543210"
    )
    pbkdf2_challenge_xml = (
        f'<?xml version="1.0"?><SessionInfo><Challenge>{challenge}</Challenge>'
        f"</SessionInfo>"
    )
    http = QueuedAiohttpSession(
        [
            MockAiohttpResponse(200, text=pbkdf2_challenge_xml),
            _connector_error(port=443),
        ]
    )
    fb = FritzBoxVPNSession(http, MOCK_HOST, MOCK_USERNAME, MOCK_PASSWORD)
    with pytest.raises(ConnectionError, match="Cannot connect"):
        await fb.async_get_session()
    assert fb.sid is None
    assert fb.protocol == "https"
