"""Regression tests for #37 residual: entity lifecycle across temporary UID loss."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.fritzbox_vpn.const import (
    DOMAIN,
    ORPHAN_CONFIRM_POLLS,
    UNIQUE_ID_PREFIX,
    UNIQUE_ID_SUFFIX_SWITCH,
)
from custom_components.fritzbox_vpn.coordinator import FritzBoxVPNCoordinator
from custom_components.fritzbox_vpn.entity import setup_vpn_platform, vpn_unique_id
from custom_components.fritzbox_vpn.entity_registry import (
    remove_orphaned_entities,
    remove_unexpected_entity_entries,
)
from custom_components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_HOST, MOCK_VPN_CONNECTIONS


@pytest.mark.asyncio
async def test_remove_orphaned_keeps_known_uids_when_not_removing_registry(
    hass: HomeAssistant,
) -> None:
    """Temporary orphan cleanup must not clear known_uids (issue #37 residual)."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    runtime = FritzboxVpnRuntimeData(coordinator=type("C", (), {"data": {}})())
    runtime.known_uids_switch = {"gone", "keep"}
    entry.runtime_data = runtime
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}gone_switch",
        config_entry=entry,
    )

    remove_orphaned_entities(hass, entry.entry_id, [entity], remove_from_registry=False)

    assert entry.runtime_data.known_uids_switch == {"gone", "keep"}
    assert entity_registry.async_get(entity.entity_id) is not None


@pytest.mark.asyncio
async def test_remove_orphaned_clears_known_uids_when_removing_registry(
    hass: HomeAssistant,
) -> None:
    """Manual/registry removal still clears known_uids for removed connections."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    runtime = FritzboxVpnRuntimeData(coordinator=type("C", (), {"data": {}})())
    runtime.known_uids_switch = {"gone", "keep"}
    entry.runtime_data = runtime
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}gone_switch",
        config_entry=entry,
    )

    remove_orphaned_entities(hass, entry.entry_id, [entity], remove_from_registry=True)

    assert entry.runtime_data.known_uids_switch == {"keep"}
    assert entity_registry.async_get(entity.entity_id) is None


@pytest.mark.asyncio
async def test_shadow_cleanup_keeps_valid_uids_missing_from_current_poll(
    hass: HomeAssistant,
) -> None:
    """Setup shadow cleanup must not delete valid entities for temporarily missing UIDs."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    valid_missing = registry.async_get_or_create(
        "switch",
        DOMAIN,
        vpn_unique_id("conn-def", UNIQUE_ID_SUFFIX_SWITCH),
        config_entry=entry,
    )
    invalid_shadow = registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}conn-abc",  # missing platform suffix
        config_entry=entry,
    )

    removed = remove_unexpected_entity_entries(hass, entry.entry_id)

    assert removed == 1
    assert registry.async_get(valid_missing.entity_id) is not None
    assert registry.async_get(invalid_shadow.entity_id) is None


@pytest.mark.asyncio
async def test_uid_loss_and_return_does_not_readd_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Full → partial → full poll must keep known_uids and not re-add entities."""
    mock_config_entry.add_to_hass(hass)
    coordinator = FritzBoxVPNCoordinator(
        hass, mock_config_entry.data, None, mock_config_entry.entry_id
    )
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    coordinator.last_update_success = True
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    add_calls: list[list] = []

    def _async_add_entities(entities, **kwargs):
        add_calls.append(list(entities))

    def _create_entities(coord, uids):
        entities = []
        for uid in uids:
            entity = MagicMock()
            entity.unique_id = vpn_unique_id(uid, UNIQUE_ID_SUFFIX_SWITCH)
            entity._connection_uid = uid
            entities.append(entity)
        return entities

    await setup_vpn_platform(
        mock_config_entry,
        _async_add_entities,
        platform="switch",
        create_entities=_create_entities,
    )
    assert len(add_calls) == 1
    assert len(add_calls[0]) == len(MOCK_VPN_CONNECTIONS)
    known = mock_config_entry.runtime_data.known_uids_switch
    assert known == set(MOCK_VPN_CONNECTIONS.keys())

    # Simulate temporary loss of one connection (reboot partial poll).
    partial = {"conn-abc": MOCK_VPN_CONNECTIONS["conn-abc"]}
    coordinator.async_set_updated_data(partial)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.known_uids_switch == set(
        MOCK_VPN_CONNECTIONS.keys()
    )
    assert len(add_calls) == 1

    # Connection returns — must not create a second entity batch.
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.known_uids_switch == set(
        MOCK_VPN_CONNECTIONS.keys()
    )
    assert len(add_calls) == 1


@pytest.mark.asyncio
async def test_partial_setup_adds_entities_when_missing_uid_returns(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """After setup with a partial poll, returning UIDs must be added (HA restores IDs)."""
    mock_config_entry.add_to_hass(hass)
    coordinator = FritzBoxVPNCoordinator(
        hass, mock_config_entry.data, None, mock_config_entry.entry_id
    )
    # Simulate reload/setup during reboot: only one connection visible.
    partial = {"conn-abc": MOCK_VPN_CONNECTIONS["conn-abc"]}
    coordinator.async_set_updated_data(partial)
    coordinator.last_update_success = True
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    # Registry still has the temporarily missing connection from before reboot.
    registry = er.async_get(hass)
    for uid in MOCK_VPN_CONNECTIONS:
        registry.async_get_or_create(
            "switch",
            DOMAIN,
            vpn_unique_id(uid, UNIQUE_ID_SUFFIX_SWITCH),
            config_entry=mock_config_entry,
        )

    add_calls: list[list] = []

    def _async_add_entities(entities, **kwargs):
        add_calls.append(list(entities))

    def _create_entities(coord, uids):
        entities = []
        for uid in uids:
            if coord.data and uid not in coord.data:
                continue
            entity = MagicMock()
            entity.unique_id = vpn_unique_id(uid, UNIQUE_ID_SUFFIX_SWITCH)
            entity._connection_uid = uid
            entities.append(entity)
        return entities

    await setup_vpn_platform(
        mock_config_entry,
        _async_add_entities,
        platform="switch",
        create_entities=_create_entities,
    )
    assert len(add_calls) == 1
    assert len(add_calls[0]) == 1
    assert mock_config_entry.runtime_data.known_uids_switch == {"conn-abc"}

    # Full set returns — must add the missing UID (registry presence must not block).
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.known_uids_switch == set(
        MOCK_VPN_CONNECTIONS.keys()
    )
    assert len(add_calls) == 2
    assert {e.unique_id for e in add_calls[1]} == {
        vpn_unique_id("conn-def", UNIQUE_ID_SUFFIX_SWITCH)
    }


@pytest.mark.asyncio
async def test_coordinator_orphan_warning_debounced(hass: HomeAssistant) -> None:
    """Orphan callback/warning only after ORPHAN_CONFIRM_POLLS consecutive misses."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "username": "u", "password": "p"},
    )
    callback = MagicMock()
    coordinator = FritzBoxVPNCoordinator(
        hass, entry.data, None, entry.entry_id, on_orphaned_removed=callback
    )
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    coordinator.fritz_session = AsyncMock()
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={"conn-abc": MOCK_VPN_CONNECTIONS["conn-abc"]}
    )

    for _ in range(ORPHAN_CONFIRM_POLLS - 1):
        await coordinator._async_update_data()
    callback.assert_not_called()

    await coordinator._async_update_data()
    callback.assert_called_once()
    assert callback.call_args.args[1] == {"conn-abc"}
    assert coordinator._uid_names.get("conn-def") == "Guest VPN"

    # Further misses for the same UID must not re-fire the callback.
    await coordinator._async_update_data()
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_update_failed_resets_orphan_miss_streak(
    hass: HomeAssistant,
) -> None:
    """Transport failures must reset miss streaks (consecutive successful polls)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "username": "u", "password": "p"},
    )
    callback = MagicMock()
    coordinator = FritzBoxVPNCoordinator(
        hass, entry.data, None, entry.entry_id, on_orphaned_removed=callback
    )
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    coordinator.fritz_session = MagicMock()
    coordinator.fritz_session.invalidate_session = MagicMock()
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={"conn-abc": MOCK_VPN_CONNECTIONS["conn-abc"]}
    )

    for _ in range(ORPHAN_CONFIRM_POLLS - 1):
        await coordinator._async_update_data()
    assert coordinator._missing_uid_counts.get("conn-def") == ORPHAN_CONFIRM_POLLS - 1

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ConnectionError("connect refused")
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator._missing_uid_counts == {}
    assert coordinator._in_recovery()

    # After outage, orphan confirmation stays paused until recovery clears.
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={"conn-abc": MOCK_VPN_CONNECTIONS["conn-abc"]}
    )
    for _ in range(ORPHAN_CONFIRM_POLLS):
        await coordinator._async_update_data()
    callback.assert_not_called()

    coordinator._recovering_until = None
    coordinator._recovery_stable_polls = 0
    for _ in range(ORPHAN_CONFIRM_POLLS - 1):
        await coordinator._async_update_data()
    callback.assert_not_called()

    await coordinator._async_update_data()
    callback.assert_called_once()
