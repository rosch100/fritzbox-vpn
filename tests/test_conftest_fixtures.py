"""Tests for the shared fixtures defined in tests/conftest.py."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.components.ssdp.scanner import Scanner
from homeassistant.components.ssdp.server import Server


def test_ssdp_scanner_async_start_is_mocked() -> None:
    """The autouse mock_ssdp_network fixture replaces Scanner.async_start."""
    assert isinstance(Scanner.async_start, AsyncMock)


def test_ssdp_server_async_start_is_mocked() -> None:
    """The autouse mock_ssdp_network fixture replaces Server.async_start."""
    assert isinstance(Server.async_start, AsyncMock)


@pytest.mark.asyncio
async def test_ssdp_scanner_async_start_is_a_safe_no_op() -> None:
    """Calling the mocked Scanner.async_start does not touch the network."""
    result = await Scanner.async_start(object())

    assert result is None
    assert Scanner.async_start.called


@pytest.mark.asyncio
async def test_ssdp_server_async_start_is_a_safe_no_op() -> None:
    """Calling the mocked Server.async_start does not touch the network."""
    result = await Server.async_start(object())

    assert result is None
    assert Server.async_start.called


def test_ssdp_mocks_are_reset_between_tests() -> None:
    """Each test gets a fresh AsyncMock, so call counts do not leak across tests."""
    # Neither of the previous tests' explicit calls should be visible here because
    # the autouse fixture is function-scoped and re-patches for every test.
    assert not Scanner.async_start.called
    assert not Server.async_start.called