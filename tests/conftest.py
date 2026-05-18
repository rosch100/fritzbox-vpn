"""Pytest fixtures for FritzBox VPN tests."""

from pathlib import Path

import pytest
from custom_components.fritzbox_vpn.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytest_plugins = "pytest_homeassistant_custom_component"

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def hass_config_dir() -> str:
    """Use repository root so custom_components/ is discoverable."""
    return str(REPO_ROOT)


@pytest.fixture(autouse=True)
def enable_custom_integrations_fixture(enable_custom_integrations) -> None:
    """Rescan custom_components from hass_config_dir."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Configured FritzBox VPN entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.178.1",
            "username": "user",
            "password": "pass",
        },
        title="FritzBox VPN",
    )
