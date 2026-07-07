"""Setup-time repair for legacy entity IDs missing suffix tokens."""

from __future__ import annotations

import pytest
from custom_components.fritzbox_vpn import _repair_entity_ids_before_platform_setup
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


@pytest.mark.asyncio
async def test_setup_repairs_legacy_entity_ids_before_platforms(
    hass, mock_config_entry
) -> None:
    """Upgrade path renames legacy entity IDs before platform setup runs."""
    mock_config_entry.add_to_hass(hass)
    connection_uid = next(iter(MOCK_VPN_CONNECTIONS))
    vpn_name = MOCK_VPN_CONNECTIONS[connection_uid]["name"]

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id, connection_uid)},
        name=vpn_name,
    )
    slug = vpn_name.lower().replace(" ", "_")

    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_CONNECTED),
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id=slug,
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_VPN_UID),
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id=slug,
    )
    entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        vpn_unique_id(connection_uid, UNIQUE_ID_SUFFIX_SWITCH),
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id=f"{slug}_vpn",
    )

    repaired = _repair_entity_ids_before_platform_setup(hass, mock_config_entry.entry_id)
    assert repaired == 3

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
