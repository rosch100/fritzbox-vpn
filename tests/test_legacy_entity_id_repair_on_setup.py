"""One-time legacy entity ID migration (config entry v1→v2)."""

from __future__ import annotations

import pytest
from custom_components.fritzbox_vpn import (
    _repair_entity_ids_before_platform_setup,
    async_migrate_entry,
)
from custom_components.fritzbox_vpn.const import (
    DOMAIN,
    UNIQUE_ID_SUFFIX_CONNECTED,
    UNIQUE_ID_SUFFIX_SWITCH,
    UNIQUE_ID_SUFFIX_VPN_UID,
)
from custom_components.fritzbox_vpn.entity import vpn_unique_id
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from tests.fixtures import MOCK_VPN_CONNECTIONS


def _seed_legacy_entities(
    hass,
    config_entry,
    *,
    connection_uid: str,
    vpn_name: str,
) -> tuple[str, er.EntityRegistry]:
    """Register legacy entity IDs for one VPN connection device."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id, connection_uid)},
        name=vpn_name,
    )
    slug = vpn_name.lower().replace(" ", "_")

    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_CONNECTED),
        config_entry=config_entry,
        device_id=device.id,
        suggested_object_id=slug,
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_VPN_UID),
        config_entry=config_entry,
        device_id=device.id,
        suggested_object_id=slug,
    )
    entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_SWITCH),
        config_entry=config_entry,
        device_id=device.id,
        suggested_object_id=f"{slug}_vpn",
    )
    return slug, entity_registry


@pytest.mark.asyncio
async def test_migrate_entry_v1_repairs_legacy_entity_ids(
    hass, mock_config_entry
) -> None:
    """Config entry v1→v2 migration renames legacy entity IDs once."""
    mock_config_entry.add_to_hass(hass)
    connection_uid = next(iter(MOCK_VPN_CONNECTIONS))
    vpn_name = MOCK_VPN_CONNECTIONS[connection_uid]["name"]
    slug, entity_registry = _seed_legacy_entities(
        hass,
        mock_config_entry,
        connection_uid=connection_uid,
        vpn_name=vpn_name,
    )

    assert mock_config_entry.version == 1
    assert await async_migrate_entry(hass, mock_config_entry)
    assert mock_config_entry.version == 2

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    unique_id_to_entity_id = {entry.unique_id: entry.entity_id for entry in entries}

    assert unique_id_to_entity_id[
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_CONNECTED)
    ].endswith("_connected")
    assert unique_id_to_entity_id[
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_VPN_UID)
    ].endswith("_vpn_uid")
    assert unique_id_to_entity_id[
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_SWITCH)
    ] == f"switch.{slug}"


@pytest.mark.asyncio
async def test_migrate_entry_v2_skips_legacy_repair(hass, mock_config_entry) -> None:
    """Already-migrated config entries do not run legacy repair again."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, version=2)
    connection_uid = next(iter(MOCK_VPN_CONNECTIONS))
    vpn_name = MOCK_VPN_CONNECTIONS[connection_uid]["name"]
    slug, entity_registry = _seed_legacy_entities(
        hass,
        mock_config_entry,
        connection_uid=connection_uid,
        vpn_name=vpn_name,
    )

    assert await async_migrate_entry(hass, mock_config_entry)

    unique_id_to_entity_id = {
        entry.unique_id: entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert unique_id_to_entity_id[
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_CONNECTED)
    ] == f"binary_sensor.{slug}"
    assert unique_id_to_entity_id[
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_SWITCH)
    ] == f"switch.{slug}_vpn"


@pytest.mark.asyncio
async def test_setup_does_not_rename_entities_after_device_rename(
    hass, mock_config_entry
) -> None:
    """Setup-time repair must not follow later device renames."""
    mock_config_entry.add_to_hass(hass)
    connection_uid = next(iter(MOCK_VPN_CONNECTIONS))
    vpn_name = MOCK_VPN_CONNECTIONS[connection_uid]["name"]
    slug, entity_registry = _seed_legacy_entities(
        hass,
        mock_config_entry,
        connection_uid=connection_uid,
        vpn_name=vpn_name,
    )

    assert await async_migrate_entry(hass, mock_config_entry)
    assert mock_config_entry.version == 2

    entries_after_migration = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    unique_id_to_entity_id = {
        entry.unique_id: entry.entity_id for entry in entries_after_migration
    }
    connected_entity_id = unique_id_to_entity_id[
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_CONNECTED)
    ]
    switch_entity_id = unique_id_to_entity_id[
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_SWITCH)
    ]

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id, connection_uid)}
    )
    assert device is not None
    device_registry.async_update_device(device.id, name_by_user="Renamed VPN")

    repaired = _repair_entity_ids_before_platform_setup(hass, mock_config_entry.entry_id)
    assert repaired == 0

    assert entity_registry.async_get(connected_entity_id) is not None
    assert entity_registry.async_get(switch_entity_id) is not None
    assert connected_entity_id == f"binary_sensor.{slug}_connected"
    assert switch_entity_id == f"switch.{slug}"
