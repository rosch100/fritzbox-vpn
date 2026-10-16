"""UID renumber without a transport outage must not create another entity set."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.fritzbox_vpn.const import (
    DOMAIN,
    UNIQUE_ID_SUFFIX_SWITCH,
)
from custom_components.fritzbox_vpn.coordinator import FritzBoxVPNCoordinator
from custom_components.fritzbox_vpn.entity import setup_vpn_platform, vpn_unique_id
from custom_components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry


def _payload(uid: str, name: str) -> dict:
    return {"uid": uid, "name": name, "active": True, "connected": False}


def _register_connection(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    uid: str,
    name: str,
) -> None:
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        vpn_unique_id(uid, UNIQUE_ID_SUFFIX_SWITCH),
        config_entry=entry,
    )
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id, uid)},
        name=name,
    )


@pytest.mark.asyncio
async def test_same_name_uid_change_without_outage_keeps_one_entity(
    hass: HomeAssistant,
) -> None:
    """A new box UID with the same name remaps the existing entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.178.1", "username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = FritzBoxVPNCoordinator(hass, entry.data, None, entry.entry_id)
    entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)

    old_uid = "vpnconnection7117"
    new_uid = "vpnconnection7200"
    name = "Galaxy"
    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={old_uid: _payload(old_uid, name)}
    )
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    _register_connection(hass, entry, old_uid, name)

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
        entry,
        _async_add_entities,
        platform="switch",
        create_entities=_create_entities,
    )

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={new_uid: _payload(new_uid, name)}
    )
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert unique_ids == {vpn_unique_id(new_uid, UNIQUE_ID_SUFFIX_SWITCH)}
    assert len(add_calls) == 1
    assert coordinator.resolve_connection_uid(old_uid) == new_uid


@pytest.mark.asyncio
async def test_existing_same_name_generations_collapse_on_poll(
    hass: HomeAssistant,
) -> None:
    """Registry generations of one name collapse to the UID in the current poll."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.178.1", "username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = FritzBoxVPNCoordinator(hass, entry.data, None, entry.entry_id)
    entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)

    name = "Galaxy"
    live_uid = "vpnconnection7300"
    for uid in ("vpnconnection7117", "vpnconnection7200", live_uid):
        _register_connection(hass, entry, uid, name)

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={live_uid: _payload(live_uid, name)}
    )
    await coordinator._async_update_data()

    registry = er.async_get(hass)
    unique_ids = {
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert unique_ids == {vpn_unique_id(live_uid, UNIQUE_ID_SUFFIX_SWITCH)}


@pytest.mark.asyncio
async def test_first_poll_remaps_one_uid_when_another_connection_stays(
    hass: HomeAssistant,
) -> None:
    """One renumbered UID remaps while an unchanged connection stays put."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.178.1", "username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = FritzBoxVPNCoordinator(hass, entry.data, None, entry.entry_id)
    entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)

    _register_connection(hass, entry, "vpnconnection7117", "Galaxy")
    _register_connection(hass, entry, "vpnconnection7118", "Tablet")

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={
            "vpnconnection7200": _payload("vpnconnection7200", "Galaxy"),
            "vpnconnection7118": _payload("vpnconnection7118", "Tablet"),
        }
    )
    await coordinator._async_update_data()

    registry = er.async_get(hass)
    unique_ids = {
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert unique_ids == {
        vpn_unique_id("vpnconnection7200", UNIQUE_ID_SUFFIX_SWITCH),
        vpn_unique_id("vpnconnection7118", UNIQUE_ID_SUFFIX_SWITCH),
    }
    assert (
        coordinator.resolve_connection_uid("vpnconnection7117") == "vpnconnection7200"
    )


@pytest.mark.asyncio
async def test_second_uid_change_still_keeps_one_entity(
    hass: HomeAssistant,
) -> None:
    """A later renumber must not treat the previous UID as a second old name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.178.1", "username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = FritzBoxVPNCoordinator(hass, entry.data, None, entry.entry_id)
    entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)

    async def _poll(uid: str) -> None:
        coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
            return_value={uid: _payload(uid, "Galaxy")}
        )
        coordinator.async_set_updated_data(await coordinator._async_update_data())

    await _poll("vpnconnection7117")
    _register_connection(hass, entry, "vpnconnection7117", "Galaxy")
    await _poll("vpnconnection7200")
    await _poll("vpnconnection7300")

    registry = er.async_get(hass)
    unique_ids = {
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert unique_ids == {vpn_unique_id("vpnconnection7300", UNIQUE_ID_SUFFIX_SWITCH)}
    assert (
        coordinator.resolve_connection_uid("vpnconnection7117") == "vpnconnection7300"
    )


@pytest.mark.asyncio
async def test_same_name_on_two_live_uids_is_not_collapsed(
    hass: HomeAssistant,
) -> None:
    """Two live UIDs that share a device name stay; the match is ambiguous."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.178.1", "username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = FritzBoxVPNCoordinator(hass, entry.data, None, entry.entry_id)
    entry.runtime_data = FritzboxVpnRuntimeData(coordinator=coordinator)
    _register_connection(hass, entry, "vpnconnection7117", "Galaxy")
    _register_connection(hass, entry, "vpnconnection7118", "Galaxy")

    coordinator.fritz_session.async_get_vpn_connections = AsyncMock(
        return_value={
            "vpnconnection7117": _payload("vpnconnection7117", "Galaxy"),
            "vpnconnection7118": _payload("vpnconnection7118", "Galaxy"),
        }
    )
    await coordinator._async_update_data()

    registry = er.async_get(hass)
    unique_ids = {
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert unique_ids == {
        vpn_unique_id("vpnconnection7117", UNIQUE_ID_SUFFIX_SWITCH),
        vpn_unique_id("vpnconnection7118", UNIQUE_ID_SUFFIX_SWITCH),
    }
