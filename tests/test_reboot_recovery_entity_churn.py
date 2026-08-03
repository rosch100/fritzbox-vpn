"""Regression tests for #37 reboot empty-list / UID-churn / orphan-base+_2 heal."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.fritzbox_vpn import _repair_entity_ids_before_platform_setup
from custom_components.fritzbox_vpn.const import (
    DOMAIN,
    ORPHAN_CONFIRM_POLLS,
    RECOVERY_STABLE_POLLS,
    UNIQUE_ID_PREFIX,
    UNIQUE_ID_SUFFIX_SWITCH,
)
from custom_components.fritzbox_vpn.coordinator import FritzBoxVPNCoordinator
from custom_components.fritzbox_vpn.entity import (
    connection_available,
    setup_vpn_platform,
    vpn_unique_id,
)
from custom_components.fritzbox_vpn.entity_registry import (
    count_repairable_entity_issues,
    get_orphan_base_suffix_merges,
    remap_connection_uids,
    repair_orphan_base_suffix_merges,
)
from custom_components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from custom_components.fritzbox_vpn.uid_identity import name_bijection_uid_remap
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_HOST, MOCK_VPN_CONNECTIONS


def _coordinator(hass: HomeAssistant, entry: MockConfigEntry) -> FritzBoxVPNCoordinator:
    coordinator = FritzBoxVPNCoordinator(
        hass, entry.data, None, entry.entry_id, on_orphaned_removed=MagicMock()
    )
    coordinator.fritz_session = MagicMock()
    coordinator.fritz_session.invalidate_session = MagicMock()
    return coordinator


@pytest.mark.asyncio
async def test_empty_list_during_recovery_is_outage_not_orphan(
    hass: HomeAssistant,
) -> None:
    """Empty {} after connect failure must not confirm orphans or replace data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    coordinator = _coordinator(hass, entry)
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    coordinator._seen_uids = set(MOCK_VPN_CONNECTIONS)
    coordinator._remember_connection_names(MOCK_VPN_CONNECTIONS)

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ConnectionError("refused")
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator._in_recovery()

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(return_value={})
    for _ in range(ORPHAN_CONFIRM_POLLS + 1):
        with pytest.raises(UpdateFailed, match="empty while recovering"):
            await coordinator._async_update_data()

    coordinator._on_orphaned_removed.assert_not_called()
    assert coordinator.data == MOCK_VPN_CONNECTIONS


@pytest.mark.asyncio
async def test_partial_during_recovery_does_not_confirm_orphan(
    hass: HomeAssistant,
) -> None:
    """Partial lists during recovery must not fire orphan confirmation."""
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
        side_effect=ConnectionError("refused")
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={"conn-abc": MOCK_VPN_CONNECTIONS["conn-abc"]}
    )
    for _ in range(ORPHAN_CONFIRM_POLLS + 2):
        await coordinator._async_update_data()
    callback.assert_not_called()


def test_name_bijection_uid_remap_success_and_refuse() -> None:
    """Bijection requires unique matching names; duplicates refuse remap."""
    mapping, reason = name_bijection_uid_remap(
        {"old-a", "old-b"},
        {"new-a", "new-b"},
        {"old-a": "Office VPN", "old-b": "Guest VPN"},
        {
            "new-a": {"name": "Office VPN"},
            "new-b": {"name": "Guest VPN"},
        },
    )
    assert reason is None
    assert mapping == {"old-a": "new-a", "old-b": "new-b"}

    mapping, reason = name_bijection_uid_remap(
        {"old-a", "old-b"},
        {"new-a", "new-b"},
        {"old-a": "Same", "old-b": "Same"},
        {
            "new-a": {"name": "Same"},
            "new-b": {"name": "Other"},
        },
    )
    assert mapping is None
    assert reason == "duplicate_old_name"


@pytest.mark.asyncio
async def test_recovery_uid_remap_updates_registry_and_alias(
    hass: HomeAssistant,
) -> None:
    """Name-stable UID churn remaps registry and keeps old entity UID available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    coordinator = _coordinator(hass, entry)
    old = {
        "old-abc": {
            "uid": "old-abc",
            "name": "Office VPN",
            "active": True,
            "connected": False,
        },
        "old-def": {
            "uid": "old-def",
            "name": "Guest VPN",
            "active": False,
            "connected": False,
        },
    }
    coordinator.async_set_updated_data(old)
    coordinator._seen_uids = set(old)
    coordinator._remember_connection_names(old)
    entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)
    entry.runtime_data.known_uids_switch = set(old)

    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    for uid, payload in old.items():
        registry.async_get_or_create(
            "switch",
            DOMAIN,
            vpn_unique_id(uid, UNIQUE_ID_SUFFIX_SWITCH),
            config_entry=entry,
        )
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id, uid)},
            name=payload["name"],
        )

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ConnectionError("refused")
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    new = {
        "new-abc": {
            "uid": "new-abc",
            "name": "Office VPN",
            "active": True,
            "connected": False,
        },
        "new-def": {
            "uid": "new-def",
            "name": "Guest VPN",
            "active": False,
            "connected": False,
        },
    }
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(return_value=new)
    result = await coordinator._async_update_data()
    assert set(result) == {"new-abc", "new-def"}
    assert coordinator.resolve_connection_uid("old-abc") == "new-abc"
    assert entry.runtime_data.known_uids_switch == {"new-abc", "new-def"}

    assert registry.async_get_entity_id(
        "switch", DOMAIN, vpn_unique_id("new-abc", UNIQUE_ID_SUFFIX_SWITCH)
    )
    assert (
        registry.async_get_entity_id(
            "switch", DOMAIN, vpn_unique_id("old-abc", UNIQUE_ID_SUFFIX_SWITCH)
        )
        is None
    )
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id, "new-abc")}
    )
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id, "old-abc")}
        )
        is None
    )

    coordinator.async_set_updated_data(new)
    coordinator.last_update_success = True
    assert connection_available(coordinator, "old-abc") is True


@pytest.mark.asyncio
async def test_uid_remap_prevents_platform_readd(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """After remapping known_uids, platforms must not async_add remapped UIDs."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = FritzBoxVPNCoordinator(
        hass, mock_config_entry.data, None, mock_config_entry.entry_id
    )
    old = {
        "old-abc": {**MOCK_VPN_CONNECTIONS["conn-abc"], "uid": "old-abc", "name": "Office VPN"},
    }
    coordinator.async_set_updated_data(old)
    coordinator.last_update_success = True
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)

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

    remap_connection_uids(hass, mock_config_entry.entry_id, {"old-abc": "new-abc"})
    assert mock_config_entry.runtime_data.known_uids_switch == {"new-abc"}

    coordinator.async_set_updated_data(
        {
            "new-abc": {
                "uid": "new-abc",
                "name": "Office VPN",
                "active": True,
                "connected": False,
            }
        }
    )
    await hass.async_block_till_done()
    assert len(add_calls) == 1


@pytest.mark.asyncio
async def test_orphan_base_suffix_merge_and_setup_heal(hass: HomeAssistant) -> None:
    """Orphan base + live _2 merges; live+live base+_2 stays untouched."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": MOCK_HOST})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = FritzBoxVPNCoordinator(
        hass,
        {"host": MOCK_HOST, "username": "u", "password": "p"},
        None,
        entry.entry_id,
    )
    coordinator.async_set_updated_data(
        {
            "vpn_new": {
                "uid": "vpn_new",
                "name": "Office VPN",
                "active": True,
                "connected": False,
            }
        }
    )
    entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)

    registry = er.async_get(hass)
    base = registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn_old_switch",
        suggested_object_id="office_vpn",
        config_entry=entry,
    )
    suffixed = registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn_new_switch",
        suggested_object_id="office_vpn_2",
        config_entry=entry,
    )
    assert base.entity_id == "switch.office_vpn"
    assert suffixed.entity_id == "switch.office_vpn_2"

    merges = get_orphan_base_suffix_merges(hass, entry.entry_id)
    assert len(merges) == 1
    assert count_repairable_entity_issues(hass, entry.entry_id) >= 1

    count, messages = repair_orphan_base_suffix_merges(hass, entry.entry_id)
    assert count == 1
    assert messages
    assert registry.async_get("switch.office_vpn_2") is None
    healed = registry.async_get("switch.office_vpn")
    assert healed is not None
    assert healed.unique_id == f"{UNIQUE_ID_PREFIX}vpn_new_switch"

    # Live base + live _2 (same current UID set containing both) must not merge.
    entry2 = MockConfigEntry(domain=DOMAIN, data={"host": MOCK_HOST})
    entry2.add_to_hass(hass)
    entry2.mock_state(hass, ConfigEntryState.LOADED)
    coordinator2 = FritzBoxVPNCoordinator(
        hass,
        {"host": MOCK_HOST, "username": "u", "password": "p"},
        None,
        entry2.entry_id,
    )
    coordinator2.async_set_updated_data(
        {
            "vpn1": {"uid": "vpn1", "name": "A", "active": True, "connected": False},
            "vpn1b": {"uid": "vpn1b", "name": "B", "active": True, "connected": False},
        }
    )
    entry2.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator2)
    registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn1_connected",
        suggested_object_id="office_vpn_connected",
        config_entry=entry2,
    )
    registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn1b_connected",
        suggested_object_id="office_vpn_connected_2",
        config_entry=entry2,
    )
    assert get_orphan_base_suffix_merges(hass, entry2.entry_id) == []
    assert _repair_entity_ids_before_platform_setup(hass, entry2.entry_id) == 0


@pytest.mark.asyncio
async def test_empty_recovery_then_same_uids_available_no_readd(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Outage → empty → same UIDs: no orphan callback and no entity re-add."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    callback = MagicMock()
    coordinator = FritzBoxVPNCoordinator(
        hass,
        mock_config_entry.data,
        None,
        mock_config_entry.entry_id,
        on_orphaned_removed=callback,
    )
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    coordinator.last_update_success = True
    coordinator.fritz_session = MagicMock()
    coordinator.fritz_session.invalidate_session = MagicMock()
    coordinator.fritz_session.async_close = AsyncMock()
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)

    add_calls: list[list] = []

    def _async_add_entities(entities, **kwargs):
        add_calls.append(list(entities))

    def _create_entities(coord, uids):
        return [
            MagicMock(
                unique_id=vpn_unique_id(uid, UNIQUE_ID_SUFFIX_SWITCH),
                _connection_uid=uid,
            )
            for uid in uids
        ]

    await setup_vpn_platform(
        mock_config_entry,
        _async_add_entities,
        platform="switch",
        create_entities=_create_entities,
    )
    assert len(add_calls) == 1

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ConnectionError("refused")
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(return_value={})
    with pytest.raises(UpdateFailed, match="empty while recovering"):
        await coordinator._async_update_data()

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value=dict(MOCK_VPN_CONNECTIONS)
    )
    data = await coordinator._async_update_data()
    assert set(data) == set(MOCK_VPN_CONNECTIONS)
    callback.assert_not_called()

    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    coordinator.last_update_success = True
    await hass.async_block_till_done()
    assert len(add_calls) == 1
    assert connection_available(coordinator, "conn-abc") is True


@pytest.mark.asyncio
async def test_recovery_clears_after_window_and_stable_polls(
    hass: HomeAssistant,
) -> None:
    """Recovery exits only after min window elapsed and stable non-empty polls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "username": "u", "password": "p"},
    )
    coordinator = _coordinator(hass, entry)
    coordinator.async_set_updated_data(dict(MOCK_VPN_CONNECTIONS))
    coordinator._seen_uids = set(MOCK_VPN_CONNECTIONS)
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        side_effect=ConnectionError("refused")
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator._in_recovery()

    # Time not elapsed yet: stable polls alone must not clear recovery.
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value=dict(MOCK_VPN_CONNECTIONS)
    )
    for _ in range(RECOVERY_STABLE_POLLS + 1):
        await coordinator._async_update_data()
    assert coordinator._in_recovery()

    coordinator._recovering_until = 0  # window.monotonic() always >= 0
    coordinator._recovery_stable_polls = 0
    for _ in range(RECOVERY_STABLE_POLLS):
        await coordinator._async_update_data()
    assert not coordinator._in_recovery()
