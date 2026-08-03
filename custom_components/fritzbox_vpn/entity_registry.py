"""Entity and device registry helpers for VPN connection lifecycle."""

from __future__ import annotations

import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    LOG_MSG_ORPHAN_BASE_MERGE,
    UNIQUE_ID_PREFIX,
    UNIQUE_ID_SUFFIX_SWITCH,
    UNIQUE_ID_SUFFIXES,
)
from .models import runtime_from_hass

_LOGGER = logging.getLogger(__name__)

_ENTITY_ID_OBJECT_ID_SUFFIX_RE = re.compile(r"^(.+)_(\d+)$")


def _entity_unique_id(connection_uid: str, suffix: str) -> str:
    """Build entity unique_id (SSOT format; avoids importing entity.py)."""
    return f"{UNIQUE_ID_PREFIX}{connection_uid}_{suffix}"


def unique_id_suffix_from_entity_unique_id(unique_id: str) -> str | None:
    """Platform suffix token from entity unique_id; None if not our format."""
    if not unique_id or not unique_id.startswith(UNIQUE_ID_PREFIX):
        return None
    rest = unique_id[len(UNIQUE_ID_PREFIX) :]
    for suffix in UNIQUE_ID_SUFFIXES:
        if rest.endswith("_" + suffix):
            return suffix
    return None


def connection_uid_from_entity_unique_id(unique_id: str) -> str | None:
    """Connection UID from entity unique_id; None if not our format."""
    suffix = unique_id_suffix_from_entity_unique_id(unique_id)
    if suffix is None:
        return None
    rest = unique_id[len(UNIQUE_ID_PREFIX) :]
    return rest[: -len(suffix) - 1]


def expected_object_id_for_device_suffix(
    device_name: str, unique_id_suffix: str
) -> str:
    """Stable object_id slug for a VPN device name and platform suffix."""
    if unique_id_suffix == UNIQUE_ID_SUFFIX_SWITCH:
        return slugify(device_name)
    return slugify(f"{device_name} {unique_id_suffix}")


def expected_entity_id_for_registry_entry(
    device_registry: dr.DeviceRegistry,
    entry: er.RegistryEntry,
) -> str | None:
    """Expected entity_id for a registry entry based on device name and unique_id."""
    unique_id_suffix = unique_id_suffix_from_entity_unique_id(entry.unique_id or "")
    if unique_id_suffix is None or not entry.device_id:
        return None
    device = device_registry.async_get(entry.device_id)
    if device is None:
        return None
    device_name = device.name_by_user or device.name
    if not device_name:
        return None
    object_id = expected_object_id_for_device_suffix(device_name, unique_id_suffix)
    return f"{entry.domain}.{object_id}"


def resolve_current_uids(
    hass: HomeAssistant, entry_id: str
) -> tuple[set[str] | None, str | None]:
    """Current VPN UIDs from coordinator.data."""
    runtime = runtime_from_hass(hass, entry_id)
    if runtime is None:
        return (None, "integration_not_loaded")
    coordinator = runtime.coordinator
    if not coordinator or not hasattr(coordinator, "data") or coordinator.data is None:
        return (None, "coordinator_not_ready")
    current_uids = set(coordinator.data.keys()) if coordinator.data else set()
    return (current_uids, None)


def get_orphaned_entity_entries(
    hass: HomeAssistant,
    entry_id: str,
    current_uids: set[str] | None = None,
) -> tuple[list[er.RegistryEntry] | None, str | None]:
    """Entity entries whose VPN connection no longer exists on the Fritz!Box."""
    if current_uids is None:
        current_uids, error_key = resolve_current_uids(hass, entry_id)
        if error_key is not None:
            return (None, error_key)
    registry = er.async_get(hass)
    to_remove = []
    for entry in er.async_entries_for_config_entry(registry, entry_id):
        uid = connection_uid_from_entity_unique_id(entry.unique_id or "")
        if uid is not None and uid not in current_uids:
            to_remove.append(entry)
    return (to_remove, None)


def remove_unexpected_entity_entries(
    hass: HomeAssistant,
    entry_id: str,
    *,
    current_uids: set[str] | None = None,
) -> int:
    """Remove shadow entities with broken unique_id formats.

    Only removes registry entries whose unique_id starts with our prefix but is
    not a valid ``fritzbox_vpn_{uid}_{suffix}`` value. Valid-format entities for
    UIDs missing from the current poll are kept (temporary reboot / partial
    lists must not destroy registry rows; see issue #37 residual).

    ``current_uids`` is ignored (kept optional for older call sites).
    """
    _ = current_uids

    entity_registry = er.async_get(hass)
    to_remove: list[er.RegistryEntry] = []
    for entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        unique_id = entry.unique_id or ""
        if not unique_id.startswith(UNIQUE_ID_PREFIX):
            continue
        if connection_uid_from_entity_unique_id(unique_id) is not None:
            continue
        to_remove.append(entry)

    remove_orphaned_entities(hass, entry_id, to_remove)
    return len(to_remove)


def uids_from_entity_entries(entries: list[er.RegistryEntry]) -> set[str]:
    """Connection UIDs from entity registry entries."""
    uids: set[str] = set()
    for entry in entries:
        uid = connection_uid_from_entity_unique_id(entry.unique_id or "")
        if uid is not None:
            uids.add(uid)
    return uids


def entity_id_base(entity_id: str) -> str | None:
    """Base entity_id when object_id has numeric suffix (_2, _3, …)."""
    if not entity_id or "." not in entity_id:
        return None
    domain, object_id = entity_id.split(".", 1)
    match = _ENTITY_ID_OBJECT_ID_SUFFIX_RE.match(object_id)
    if not match:
        return None
    return f"{domain}.{match.group(1)}"


def entity_id_suffix_number(entity_id: str) -> int | None:
    """Numeric suffix from entity_id object_id (_2, _3, ...)."""
    if not entity_id or "." not in entity_id:
        return None
    _, object_id = entity_id.split(".", 1)
    match = _ENTITY_ID_OBJECT_ID_SUFFIX_RE.match(object_id)
    if not match:
        return None
    try:
        return int(match.group(2))
    except (TypeError, ValueError):
        return None


def get_legacy_entity_object_id_repairs(
    hass: HomeAssistant, entry_id: str
) -> list[tuple[er.RegistryEntry, str]]:
    """Rename operations for legacy entity IDs missing suffix tokens.

    Uses the current device name to compute target entity IDs. Intended for the
    one-time v1→v2 config-entry migration and explicit user-initiated repair,
    not for automatic repair on every setup/reload.
    """
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    repairs: list[tuple[er.RegistryEntry, str]] = []

    for entry in er.async_entries_for_config_entry(registry, entry_id):
        target_entity_id = expected_entity_id_for_registry_entry(device_registry, entry)
        if target_entity_id is None or entry.entity_id == target_entity_id:
            continue
        if registry.async_get(target_entity_id) is not None:
            continue
        repairs.append((entry, target_entity_id))

    return repairs


def repair_legacy_entity_object_ids(
    hass: HomeAssistant, entry_id: str
) -> tuple[int, list[str]]:
    """Rename legacy entity IDs to current suffix-based object_id scheme."""
    registry = er.async_get(hass)
    repairs = get_legacy_entity_object_id_repairs(hass, entry_id)
    messages: list[str] = []
    for entry, target_entity_id in repairs:
        try:
            registry.async_update_entity(
                entry.entity_id, new_entity_id=target_entity_id
            )
            messages.append(f"{entry.entity_id} → {target_entity_id}")
            _LOGGER.info(
                "Repaired legacy entity ID: %s → %s",
                entry.entity_id,
                target_entity_id,
            )
        except Exception as err:
            _LOGGER.warning(
                "Failed to repair legacy entity ID %s → %s: %s",
                entry.entity_id,
                target_entity_id,
                err,
            )
    return (len(messages), messages)


def get_entity_id_suffix_repairs(
    registry: er.EntityRegistry,
    entry_id: str,
    *,
    allow_replace_base: bool = False,
) -> list[tuple[er.RegistryEntry, str, bool]]:
    """Repair operations as (suffixed entry, base_entity_id, remove_base_first).

    By default only renames when the base entity_id is free. Replacing an
    existing base (delete base, rename ``_2``) causes recorder history
    migration warnings and can orphan correct entities on every reload.
    """
    all_entries = er.async_entries_for_config_entry(registry, entry_id)
    by_entity_id = {e.entity_id: e for e in all_entries}
    suffixed_by_base: dict[str, list[er.RegistryEntry]] = {}

    for entry in all_entries:
        base = entity_id_base(entry.entity_id)
        if not base:
            continue
        suffixed_by_base.setdefault(base, []).append(entry)

    result: list[tuple[er.RegistryEntry, str, bool]] = []
    for base_entity_id, suffixed_entries in suffixed_by_base.items():
        preferred = sorted(
            suffixed_entries,
            key=lambda e: (entity_id_suffix_number(e.entity_id) or 10_000, e.entity_id),
        )[0]
        base_entry = by_entity_id.get(base_entity_id)
        if base_entry and base_entry.id == preferred.id:
            continue

        if not base_entry and registry.async_get(base_entity_id) is None:
            result.append((preferred, base_entity_id, False))
            continue

        if allow_replace_base and base_entry and base_entry.config_entry_id == entry_id:
            result.append((preferred, base_entity_id, True))

    return result


def repair_entity_id_suffixes(
    hass: HomeAssistant,
    entry_id: str,
    *,
    allow_replace_base: bool = False,
) -> tuple[int, list[str]]:
    """Repair suffixed entity IDs (_2, _3, ...) toward base IDs.

    Default (``allow_replace_base=False``): only rename when the base
    entity_id is free. Opt-in ``allow_replace_base=True`` is destructive:
    a same-entry base entity may be removed so a ``_2``/``_3`` entry can
    take the base ID (manual repair / service only — not used on setup).
    """
    registry = er.async_get(hass)
    repairs = get_entity_id_suffix_repairs(
        registry, entry_id, allow_replace_base=allow_replace_base
    )
    messages: list[str] = []
    for suffixed_entry, base_entity_id, remove_base_first in repairs:
        try:
            if remove_base_first:
                registry.async_remove(base_entity_id)
            registry.async_update_entity(
                suffixed_entry.entity_id, new_entity_id=base_entity_id
            )
            messages.append(f"{suffixed_entry.entity_id} → {base_entity_id}")
            _LOGGER.info(
                "Repaired entity ID: %s → %s",
                suffixed_entry.entity_id,
                base_entity_id,
            )
        except Exception as err:
            _LOGGER.warning(
                "Failed to repair %s → %s: %s",
                suffixed_entry.entity_id,
                base_entity_id,
                err,
            )
    return (len(messages), messages)


def repair_entity_ids(hass: HomeAssistant, entry_id: str) -> tuple[int, list[str]]:
    """Repair legacy IDs, orphan-base+_2 merges, and free-base numeric suffixes."""
    legacy_count, legacy_messages = repair_legacy_entity_object_ids(hass, entry_id)
    merge_count, merge_messages = repair_orphan_base_suffix_merges(hass, entry_id)
    suffix_count, suffix_messages = repair_entity_id_suffixes(hass, entry_id)
    return (
        legacy_count + merge_count + suffix_count,
        legacy_messages + merge_messages + suffix_messages,
    )


def remap_connection_uids(
    hass: HomeAssistant,
    entry_id: str,
    old_to_new: dict[str, str],
) -> int:
    """Remap entity unique_ids and device identifiers; update runtime known_uids."""
    if not old_to_new:
        return 0

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    remapped_entities = 0

    for entry in list(er.async_entries_for_config_entry(entity_registry, entry_id)):
        unique_id = entry.unique_id or ""
        old_uid = connection_uid_from_entity_unique_id(unique_id)
        suffix = unique_id_suffix_from_entity_unique_id(unique_id)
        if old_uid is None or suffix is None or old_uid not in old_to_new:
            continue
        new_uid = old_to_new[old_uid]
        new_unique_id = _entity_unique_id(new_uid, suffix)
        if entity_registry.async_get_entity_id(entry.domain, DOMAIN, new_unique_id):
            _LOGGER.error(
                "Cannot remap unique_id %s → %s; target already exists",
                unique_id,
                new_unique_id,
            )
            continue
        entity_registry.async_update_entity(entry.entity_id, new_unique_id=new_unique_id)
        remapped_entities += 1

    for old_uid, new_uid in old_to_new.items():
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry_id, old_uid)}
        )
        if device is None:
            continue
        existing_new = device_registry.async_get_device(
            identifiers={(DOMAIN, entry_id, new_uid)}
        )
        if existing_new is not None and existing_new.id != device.id:
            _LOGGER.error(
                "Cannot remap device UID %s → %s; target device already exists",
                old_uid,
                new_uid,
            )
            continue
        new_identifiers = set(device.identifiers)
        new_identifiers.discard((DOMAIN, entry_id, old_uid))
        new_identifiers.add((DOMAIN, entry_id, new_uid))
        device_registry.async_update_device(device.id, new_identifiers=new_identifiers)

    runtime = runtime_from_hass(hass, entry_id)
    if runtime is not None:
        runtime.remap_known_uids(old_to_new)

    return remapped_entities


def get_orphan_base_suffix_merges(
    hass: HomeAssistant,
    entry_id: str,
    current_uids: set[str] | None = None,
) -> list[tuple[er.RegistryEntry, er.RegistryEntry, str]]:
    """Orphan base + live ``_2`` pairs eligible for merge.

    Base unique_id UID must be absent from ``current_uids``; suffixed entry UID
    must be present. Narrower than ``allow_replace_base=True``.
    """
    if current_uids is None:
        current_uids, error_key = resolve_current_uids(hass, entry_id)
        if error_key is not None or current_uids is None:
            return []

    registry = er.async_get(hass)
    all_entries = er.async_entries_for_config_entry(registry, entry_id)
    by_entity_id = {e.entity_id: e for e in all_entries}
    result: list[tuple[er.RegistryEntry, er.RegistryEntry, str]] = []

    for entry in all_entries:
        base_entity_id = entity_id_base(entry.entity_id)
        if not base_entity_id:
            continue
        base_entry = by_entity_id.get(base_entity_id)
        if base_entry is None or base_entry.config_entry_id != entry_id:
            continue
        base_uid = connection_uid_from_entity_unique_id(base_entry.unique_id or "")
        live_uid = connection_uid_from_entity_unique_id(entry.unique_id or "")
        if base_uid is None or live_uid is None:
            continue
        if base_uid in current_uids:
            continue
        if live_uid not in current_uids:
            continue
        if base_uid == live_uid:
            continue
        result.append((base_entry, entry, base_entity_id))

    # Prefer lowest numeric suffix per base when multiple exist.
    preferred: dict[str, tuple[er.RegistryEntry, er.RegistryEntry, str]] = {}
    for base_entry, suffixed_entry, base_entity_id in result:
        existing = preferred.get(base_entity_id)
        if existing is None:
            preferred[base_entity_id] = (base_entry, suffixed_entry, base_entity_id)
            continue
        _, prev_suffixed, _ = existing
        prev_n = entity_id_suffix_number(prev_suffixed.entity_id) or 10_000
        cur_n = entity_id_suffix_number(suffixed_entry.entity_id) or 10_000
        if cur_n < prev_n:
            preferred[base_entity_id] = (base_entry, suffixed_entry, base_entity_id)
    return list(preferred.values())


def repair_orphan_base_suffix_merges(
    hass: HomeAssistant,
    entry_id: str,
    current_uids: set[str] | None = None,
) -> tuple[int, list[str]]:
    """Remove orphan base registry rows and rename live ``_2`` entities to base IDs."""
    merges = get_orphan_base_suffix_merges(hass, entry_id, current_uids)
    if not merges:
        return (0, [])

    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    messages: list[str] = []
    orphan_uids: set[str] = set()
    for base_entry, suffixed_entry, base_entity_id in merges:
        try:
            orphan_unique_id = base_entry.unique_id
            orphan_uid = connection_uid_from_entity_unique_id(orphan_unique_id or "")
            if orphan_uid is not None:
                orphan_uids.add(orphan_uid)
            registry.async_remove(base_entry.entity_id)
            registry.async_update_entity(
                suffixed_entry.entity_id, new_entity_id=base_entity_id
            )
            messages.append(f"{suffixed_entry.entity_id} → {base_entity_id}")
            _LOGGER.warning(
                LOG_MSG_ORPHAN_BASE_MERGE,
                suffixed_entry.entity_id,
                base_entity_id,
                orphan_unique_id,
            )
        except Exception as err:
            _LOGGER.warning(
                "Failed orphan-base merge %s → %s: %s",
                suffixed_entry.entity_id,
                base_entity_id,
                err,
            )

    for uid in orphan_uids:
        device = device_registry.async_get_device(identifiers={(DOMAIN, entry_id, uid)})
        if device is None:
            continue
        if er.async_entries_for_device(registry, device.id):
            continue
        device_registry.async_remove_device(device.id)
        _LOGGER.info("Removed empty device after orphan-base merge for UID %s", uid)

    return (len(messages), messages)


def count_repairable_entity_issues(hass: HomeAssistant, entry_id: str) -> int:
    """Pending legacy, orphan-base merge, and free-base suffix repairs."""
    registry = er.async_get(hass)
    legacy = get_legacy_entity_object_id_repairs(hass, entry_id)
    merges = get_orphan_base_suffix_merges(hass, entry_id)
    suffixes = get_entity_id_suffix_repairs(registry, entry_id)
    return len(legacy) + len(merges) + len(suffixes)


def remove_orphaned_entities(
    hass: HomeAssistant,
    entry_id: str,
    entries: list[er.RegistryEntry],
    *,
    remove_from_registry: bool = True,
) -> None:
    """Optionally remove registry entries; clear known_uids only when removed."""
    if not entries:
        return

    uids_removed = uids_from_entity_entries(entries)

    if not remove_from_registry:
        # Keep known_uids so platforms do not re-add existing unique_ids when a
        # connection reappears after a temporary absence (issue #37 residual).
        return

    entity_registry = er.async_get(hass)
    device_ids_affected = set()
    for entry in entries:
        if entry.device_id:
            device_ids_affected.add(entry.device_id)
        entity_registry.async_remove(entry.entity_id)
        _LOGGER.info(
            "Removed unavailable entity: %s (%s)",
            entry.entity_id,
            entry.unique_id,
        )

    device_registry = dr.async_get(hass)
    for uid in uids_removed:
        device = device_registry.async_get_device(identifiers={(DOMAIN, entry_id, uid)})
        if device:
            device_registry.async_remove_device(device.id)
            _LOGGER.info(
                "Removed unavailable device for connection UID: %s (device_id: %s)",
                uid,
                device.id,
            )
            device_ids_affected.discard(device.id)

    for dev_id in device_ids_affected:
        device = device_registry.async_get(dev_id)
        if not device:
            continue
        if not er.async_entries_for_device(entity_registry, dev_id):
            device_registry.async_remove_device(dev_id)
            _LOGGER.info(
                "Removed empty device (no entities left): %s (device_id: %s)",
                device.name_by_user or device.name,
                dev_id,
            )

    runtime = runtime_from_hass(hass, entry_id)
    if not uids_removed or runtime is None:
        return
    runtime.clear_known_uids(uids_removed)
