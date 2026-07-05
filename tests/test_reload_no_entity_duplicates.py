"""Regression tests for avoiding entity duplication on reload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.fritzbox_vpn.const import (
    STATUS_CONNECTED,
    STATUS_DISABLED,
    STATUS_ENABLED,
    UNIQUE_ID_SUFFIX_CONNECTED,
    UNIQUE_ID_SUFFIX_STATUS,
    UNIQUE_ID_SUFFIX_SWITCH,
    UNIQUE_ID_SUFFIX_UID,
    UNIQUE_ID_SUFFIX_VPN_UID,
)
from custom_components.fritzbox_vpn.entity import vpn_unique_id
from homeassistant.helpers import entity_registry as er

from tests.fixtures import MOCK_VPN_CONNECTIONS


def _fake_get_vpn_status(connection_data: dict) -> str:
    """Return coordinator status consistent with coordinator.get_vpn_status()."""
    active = connection_data.get("active", False)
    if not active:
        return STATUS_DISABLED
    return STATUS_CONNECTED if connection_data.get("connected", False) else STATUS_ENABLED


def _make_fake_coordinator(hass) -> MagicMock:
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = dict(MOCK_VPN_CONNECTIONS)
    coordinator.last_update_success = True

    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)

    coordinator.get_vpn_status = MagicMock(
        side_effect=lambda uid: _fake_get_vpn_status(coordinator.data[uid])
    )
    coordinator.toggle_vpn = AsyncMock(return_value=True)

    coordinator.fritz_session = MagicMock()
    coordinator.fritz_session.async_close = AsyncMock()

    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=lambda: None
    )

    return coordinator


@pytest.mark.asyncio
async def test_reload_does_not_duplicate_entity_registry_entries(
    hass, mock_config_entry
) -> None:
    """Reload must not create a new set of entities (no endless _2/_3 suffixes)."""
    mock_config_entry.add_to_hass(hass)

    expected_unique_ids = set()
    for connection_uid in MOCK_VPN_CONNECTIONS:
        expected_unique_ids |= {
            vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_SWITCH),
            vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_CONNECTED),
            vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_STATUS),
            vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_UID),
            vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_VPN_UID),
        }

    def _assert_registry_entries(entries) -> None:
        unique_id_to_entity_id = {e.unique_id: e.entity_id for e in entries}
        assert {e.unique_id for e in entries} == expected_unique_ids
        assert len(entries) == len(expected_unique_ids)

        for connection_uid in MOCK_VPN_CONNECTIONS:
            assert unique_id_to_entity_id[
                vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_CONNECTED)
            ].endswith("_connected")
            assert unique_id_to_entity_id[
                vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_STATUS)
            ].endswith("_status")

            uid_entity_id = unique_id_to_entity_id[
                vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_UID)
            ]
            assert uid_entity_id.endswith("_uid") or uid_entity_id.endswith(
                "_connection_uid"
            )

            assert unique_id_to_entity_id[
                vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_VPN_UID)
            ].endswith("_vpn_uid")

    def _factory(*_args, **_kwargs):
        return _make_fake_coordinator(hass)

    with patch(
        "custom_components.fritzbox_vpn.FritzBoxVPNCoordinator",
        side_effect=_factory,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        _assert_registry_entries(entries)

        await hass.config_entries.async_reload(mock_config_entry.entry_id)

        entries_after_reload = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        _assert_registry_entries(entries_after_reload)

        await hass.config_entries.async_reload(mock_config_entry.entry_id)

        entries_after_second_reload = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        _assert_registry_entries(entries_after_second_reload)

