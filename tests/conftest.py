"""Pytest fixtures for FritzBox VPN tests."""

from pathlib import Path

import pytest
from custom_components.fritzbox_vpn.const import (
    DATA_COORDINATOR,
    DATA_KNOWN_UIDS_BINARY_SENSOR,
    DATA_KNOWN_UIDS_SENSOR,
    DATA_KNOWN_UIDS_SWITCH,
    DOMAIN,
)
from custom_components.fritzbox_vpn.coordinator import FritzBoxVPNCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_VPN_CONNECTIONS

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


@pytest.fixture
async def coordinator_with_data(
    hass, mock_config_entry: MockConfigEntry
) -> FritzBoxVPNCoordinator:
    """Coordinator registered in hass.data with VPN sample data."""
    mock_config_entry.add_to_hass(hass)
    coordinator = FritzBoxVPNCoordinator(
        hass,
        mock_config_entry.data,
        mock_config_entry.options,
        mock_config_entry.entry_id,
    )
    coordinator.async_set_updated_data(MOCK_VPN_CONNECTIONS)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_KNOWN_UIDS_SWITCH: set(),
        DATA_KNOWN_UIDS_SENSOR: set(),
        DATA_KNOWN_UIDS_BINARY_SENSOR: set(),
    }
    return coordinator
