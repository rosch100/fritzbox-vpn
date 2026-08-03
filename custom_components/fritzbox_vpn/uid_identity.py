"""Stable VPN connection UID identity helpers (name bijection remap)."""

from __future__ import annotations

from typing import Any

from fritzboxvpn import API_KEY_NAME


def name_bijection_uid_remap(
    old_uids: set[str],
    new_uids: set[str],
    old_names: dict[str, str],
    new_payloads: dict[str, Any],
) -> tuple[dict[str, str] | None, str | None]:
    """Map old→new UIDs when names form a 1:1 bijection.

    Returns ``(mapping, None)`` on success, or ``(None, reason)`` when remap
    must be refused (no silent guessing).
    """
    if not old_uids or not new_uids or old_uids & new_uids:
        return (None, "sets_overlap_or_empty")

    old_by_name: dict[str, str] = {}
    for uid in old_uids:
        name = old_names.get(uid)
        if name is None or not str(name).strip():
            return (None, "missing_old_name")
        name = str(name).strip()
        if name in old_by_name:
            return (None, "duplicate_old_name")
        old_by_name[name] = uid

    new_by_name: dict[str, str] = {}
    for uid in new_uids:
        payload = new_payloads.get(uid)
        if not isinstance(payload, dict):
            return (None, "missing_new_name")
        name = payload.get(API_KEY_NAME)
        if name is None or not str(name).strip():
            return (None, "missing_new_name")
        name = str(name).strip()
        if name in new_by_name:
            return (None, "duplicate_new_name")
        new_by_name[name] = uid

    if set(old_by_name) != set(new_by_name):
        return (None, "name_sets_differ")

    return ({old_by_name[name]: new_by_name[name] for name in old_by_name}, None)
