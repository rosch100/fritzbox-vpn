"""Regression tests for non-destructive numeric entity_id repair (#37)."""

from __future__ import annotations

import pytest
from custom_components.fritzbox_vpn import _repair_entity_ids_before_platform_setup
from custom_components.fritzbox_vpn.const import DOMAIN, UNIQUE_ID_PREFIX
from custom_components.fritzbox_vpn.entity_registry import (
    get_entity_id_suffix_repairs,
    repair_entity_id_suffixes,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.asyncio
async def test_auto_repair_does_not_replace_existing_base(hass: HomeAssistant) -> None:
    """When base entity_id exists, setup repair must not delete/rename over it."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    base = registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn1_connected",
        suggested_object_id="office_vpn_connected",
        config_entry=entry,
    )
    suffixed = registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn1b_connected",
        suggested_object_id="office_vpn_connected_2",
        config_entry=entry,
    )
    assert base.entity_id == "binary_sensor.office_vpn_connected"
    assert suffixed.entity_id == "binary_sensor.office_vpn_connected_2"

    repairs = get_entity_id_suffix_repairs(
        registry, entry.entry_id, allow_replace_base=False
    )
    assert repairs == []

    repaired = _repair_entity_ids_before_platform_setup(hass, entry.entry_id)
    assert repaired == 0
    assert registry.async_get(base.entity_id) is not None
    assert registry.async_get(suffixed.entity_id) is not None
    assert registry.async_get(base.entity_id).unique_id == (
        f"{UNIQUE_ID_PREFIX}vpn1_connected"
    )


@pytest.mark.asyncio
async def test_repair_renames_when_base_is_free(hass: HomeAssistant) -> None:
    """Numeric suffix may be renamed to base when the base entity_id is unused."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    suffixed = registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn1_switch",
        suggested_object_id="office_vpn_2",
        config_entry=entry,
    )
    assert suffixed.entity_id.endswith("_2")

    count, messages = repair_entity_id_suffixes(hass, entry.entry_id)
    assert count == 1
    assert messages
    assert registry.async_get("switch.office_vpn") is not None
    assert registry.async_get(suffixed.entity_id) is None


@pytest.mark.asyncio
async def test_repair_allow_replace_base_removes_base_then_renames(
    hass: HomeAssistant,
) -> None:
    """Opt-in allow_replace_base=True reassigns base ID to the suffixed entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
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
    suffixed_unique_id = suffixed.unique_id

    count, _messages = repair_entity_id_suffixes(
        hass, entry.entry_id, allow_replace_base=True
    )
    assert count == 1
    assert registry.async_get("switch.office_vpn_2") is None
    replaced = registry.async_get("switch.office_vpn")
    assert replaced is not None
    assert replaced.unique_id == suffixed_unique_id
