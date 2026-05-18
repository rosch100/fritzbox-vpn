"""Async library for AVM Fritz!Box WireGuard VPN Web API."""

from .const import API_KEY_ACTIVE, API_KEY_CONNECTED, API_KEY_NAME, API_KEY_UID
from .parsing import (
    extract_box_connections_from_data,
    normalize_box_connections,
    parse_blocktime_from_login_xml,
    parse_challenge_from_login_xml,
    parse_sid_from_login_response,
)
from .session import FritzBoxVPNSession

__all__ = [
    "API_KEY_ACTIVE",
    "API_KEY_CONNECTED",
    "API_KEY_NAME",
    "API_KEY_UID",
    "FritzBoxVPNSession",
    "extract_box_connections_from_data",
    "normalize_box_connections",
    "parse_blocktime_from_login_xml",
    "parse_challenge_from_login_xml",
    "parse_sid_from_login_response",
]
