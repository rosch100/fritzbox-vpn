"""Parse Fritz!Box login and data.lua responses."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from .const import (
    ACCESS_TYPE_WIREGUARD,
    ACTIVE_STATE_STRINGS_TRUE,
    API_KEY_ACCESS_TYPE,
    API_KEY_ACTIVATED,
    API_KEY_ACTIVE,
    API_KEY_BOX_CONNECTIONS,
    API_KEY_CONNECTED,
    API_KEY_CONNECTED_SINCE,
    API_KEY_CONNECTION,
    API_KEY_DATA,
    API_KEY_INIT,
    API_KEY_NAME,
    API_KEY_STATE,
    API_KEY_UID,
    API_KEY_UID_REST,
    LOGIN_TAG_BLOCKTIME,
    LOGIN_TAG_CHALLENGE,
    LOGIN_TAG_SID,
    WIREGUARD_STATE_READY,
)

_LOGGER = logging.getLogger(__name__)


def connection_active_from_api(conn: dict[str, Any]) -> bool:
    """Active state from API (active/activated, int/str/bool)."""
    raw = conn.get(API_KEY_ACTIVE)
    if raw is None:
        raw = conn.get(API_KEY_ACTIVATED)
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw != 0
    if isinstance(raw, str):
        return raw.strip().lower() in ACTIVE_STATE_STRINGS_TRUE
    return False


def normalize_connection_uid(raw_uid: Any) -> str | None:
    """Normalize a connection uid to a stable canonical string."""
    if raw_uid is None:
        return None
    uid = str(raw_uid).strip()
    if not uid:
        return None
    return uid


def normalize_box_connections(box: Any) -> dict[str, Any]:
    """API boxConnections (list or dict) → dict keyed by uid with normalized active."""
    result: dict[str, Any] = {}
    if isinstance(box, dict):
        items_with_keys = box.items()
    elif isinstance(box, list):
        items_with_keys = ((None, c) for c in box)
    else:
        items_with_keys = ()
    for dict_key, c in items_with_keys:
        if not isinstance(c, dict):
            continue
        raw_uid = c.get(API_KEY_UID)
        if isinstance(dict_key, str) and (
            raw_uid is None or (isinstance(raw_uid, str) and not raw_uid.strip())
        ):
            raw_uid = dict_key
        uid = normalize_connection_uid(raw_uid)
        if uid is None:
            continue
        entry = dict(c)
        entry[API_KEY_UID] = uid
        entry[API_KEY_ACTIVE] = connection_active_from_api(c)
        if uid in result:
            _LOGGER.warning(
                "Duplicate VPN uid detected after normalization: %r. Latest payload wins.",
                uid,
            )
        elif isinstance(raw_uid, str) and raw_uid != uid:
            _LOGGER.debug(
                "Normalized VPN uid from %r to %r",
                raw_uid,
                uid,
            )
        result[uid] = entry
    return result


def parse_challenge_from_login_xml(content: str) -> str | None:
    """Challenge from login_sid.lua XML; None if missing or parse error."""
    if not (content and content.strip()):
        return None
    try:
        root = ET.fromstring(content)
        return root.findtext(LOGIN_TAG_CHALLENGE)
    except ET.ParseError:
        return None


def parse_sid_from_login_response(content: str) -> str | None:
    """SID from login response XML; None on parse error."""
    if not (content and content.strip()):
        return None
    try:
        root = ET.fromstring(content)
        return root.findtext(LOGIN_TAG_SID)
    except ET.ParseError:
        return None


def parse_blocktime_from_login_xml(content: str) -> int | None:
    """BlockTime from login_sid.lua XML; None if missing or parse error."""
    if not (content and content.strip()):
        return None
    try:
        root = ET.fromstring(content)
        raw = root.findtext(LOGIN_TAG_BLOCKTIME)
        if raw is None:
            return None
        return int(raw)
    except (ET.ParseError, ValueError):
        return None


def describe_json_value(value: Any, *, max_keys: int = 20) -> dict[str, Any]:
    """Return a small summary for debug logs (no full payload)."""
    if isinstance(value, dict):
        keys = list(value.keys())
        return {
            "type": "dict",
            "len": len(value),
            "keys": keys[:max_keys],
        }
    if isinstance(value, list):
        return {"type": "list", "len": len(value)}
    return {"type": type(value).__name__}


def extract_box_connections_from_data(data: dict[str, Any], page: str) -> Any:
    """Extract boxConnections from data.lua JSON (WireGuard page)."""
    if not isinstance(data, dict):
        return None

    data_inner = data.get(API_KEY_DATA)
    if not isinstance(data_inner, dict):
        return None

    init = data_inner.get(API_KEY_INIT)
    if isinstance(init, dict):
        box_connections = init.get(API_KEY_BOX_CONNECTIONS)
        if box_connections is not None:
            return box_connections

        page_payload = init.get(page)
        if isinstance(page_payload, dict):
            box_connections = page_payload.get(API_KEY_BOX_CONNECTIONS)
            if box_connections is not None:
                return box_connections

    box_connections = data_inner.get(API_KEY_BOX_CONNECTIONS)
    if box_connections is not None:
        return box_connections

    page_payload = data_inner.get(page)
    if isinstance(page_payload, dict):
        box_connections = page_payload.get(API_KEY_BOX_CONNECTIONS)
        if box_connections is not None:
            return box_connections

    _LOGGER.debug(
        "Could not extract boxConnections from data.lua JSON. data.lua structure summary=%s",
        {
            "data_keys": list(data.keys())[:50],
            "data_inner": describe_json_value(data_inner),
            "init": describe_json_value(init),
            "init_page_payload": describe_json_value(
                init.get(page) if isinstance(init, dict) else None
            ),
            "data_inner_page_payload": describe_json_value(
                data_inner.get(page) if isinstance(data_inner, dict) else None
            ),
            "data_inner_boxConnections": describe_json_value(
                data_inner.get(API_KEY_BOX_CONNECTIONS)
                if isinstance(data_inner, dict)
                else None
            ),
            "requested_page": page,
        },
    )
    return None


def _connection_connected_from_rest(conn: dict[str, Any]) -> bool:
    """Connected flag from FRITZ!OS 8.40 REST connection fields."""
    state = conn.get(API_KEY_STATE)
    if isinstance(state, str) and state.strip() == WIREGUARD_STATE_READY:
        return True
    raw_since = conn.get(API_KEY_CONNECTED_SINCE)
    if raw_since is None:
        return False
    try:
        return int(raw_since) != 0
    except (TypeError, ValueError):
        return False


def _rest_wireguard_entry(conn: dict[str, Any]) -> dict[str, Any] | None:
    """Map one REST connection to the shared boxConnections entry shape."""
    access_type = conn.get(API_KEY_ACCESS_TYPE)
    if str(access_type).strip() != ACCESS_TYPE_WIREGUARD:
        return None
    uid = conn.get(API_KEY_UID)
    if uid is None:
        uid = conn.get(API_KEY_UID_REST)
    activated = conn.get(API_KEY_ACTIVATED)
    return {
        API_KEY_UID: uid,
        API_KEY_NAME: conn.get(API_KEY_NAME),
        API_KEY_ACTIVATED: activated,
        API_KEY_ACTIVE: conn.get(API_KEY_ACTIVE, activated),
        API_KEY_CONNECTED: _connection_connected_from_rest(conn),
    }


def extract_wireguard_connections_from_rest(
    data: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """Extract WireGuard connections from GET /api/v0/generic/vpn JSON.

    Returns None when the REST listing contract is absent. An empty list means
    the endpoint answered with zero WireGuard connections.
    """
    if not isinstance(data, dict):
        return None
    raw_connections = data.get(API_KEY_CONNECTION)
    if raw_connections is None:
        _LOGGER.debug(
            "Could not extract connection list from REST VPN JSON. structure summary=%s",
            {
                "data_keys": list(data.keys())[:50],
                "connection": describe_json_value(data.get(API_KEY_CONNECTION)),
            },
        )
        return None
    if not isinstance(raw_connections, list):
        return None

    result: list[dict[str, Any]] = []
    for conn in raw_connections:
        if not isinstance(conn, dict):
            continue
        entry = _rest_wireguard_entry(conn)
        if entry is not None:
            result.append(entry)
    return result
