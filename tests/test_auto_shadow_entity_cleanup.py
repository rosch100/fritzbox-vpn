"""Auto-cleanup tests for shadow entities during setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.fritzbox_vpn import async_setup_entry
from custom_components.fritzbox_vpn.const import DOMAIN, UNIQUE_ID_PREFIX
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_VPN_CONNECTIONS


@pytest.mark.asyncio
async def test_shadow_entities_removed_on_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Shadow entities with unexpected unique_id values are removed automatically."""
    mock_config_entry.add_to_hass(hass)

    registry = er.async_get(hass)
    shadow_unique_id = f"{UNIQUE_ID_PREFIX}conn-abc"  # missing suffix on purpose

    registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        shadow_unique_id,
        config_entry=mock_config_entry,
    )

    before = er.async_entries_for_config_entry(
        registry, mock_config_entry.entry_id
    )
    assert any((e.unique_id or "") == shadow_unique_id for e in before)

    mock_coordinator = MagicMock()
    mock_coordinator.data = MOCK_VPN_CONNECTIONS
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(return_value=None)
    mock_coordinator.fritz_session = MagicMock()
    mock_coordinator.fritz_session.async_close = AsyncMock()
    mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)

    with (
        patch(
            "custom_components.fritzbox_vpn.FritzBoxVPNCoordinator",
            return_value=mock_coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert await async_setup_entry(hass, mock_config_entry)

    after = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert not any((e.unique_id or "") == shadow_unique_id for e in after)

