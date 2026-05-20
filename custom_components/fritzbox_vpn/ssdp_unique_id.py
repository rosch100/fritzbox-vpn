"""SSDP helpers; keep host/UUID parsing in sync with homeassistant.components.fritz.ssdp_discovery."""

import ipaddress
from urllib.parse import urlparse
from uuid import UUID

from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo

from .const import FRITZBOX_SSDP_INDICATORS, REPEATER_INDICATORS

FRITZ_BOX_HOST = "fritz.box"


def parse_device_uuid(value: str) -> str | None:
    """Return a normalized UUID string, or None if the value is not a UUID."""
    value = value.strip()
    if not value:
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


def uuid_from_upnp_udn(raw_udn: str) -> str | None:
    """Parse UPnP UDN (``uuid:<uuid>``)."""
    return parse_device_uuid(raw_udn.removeprefix("uuid:"))


def uuid_from_ssdp_usn(usn: str) -> str | None:
    """Parse device UUID from SSDP USN (``uuid:<uuid>::...``)."""
    if not usn.startswith("uuid:"):
        return None
    return uuid_from_upnp_udn(usn.split("::", 1)[0])


def hostname_from_url(url: str) -> str | None:
    """Return hostname from a URL, or None if parsing fails."""
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


def uuid_from_discovery(discovery_info: SsdpServiceInfo) -> str | None:
    """Device UUID from UPnP UDN or SSDP USN."""
    if raw_udn := discovery_info.upnp.get(ATTR_UPNP_UDN):
        if device_uuid := uuid_from_upnp_udn(raw_udn):
            return device_uuid
    if discovery_info.ssdp_usn:
        if device_uuid := uuid_from_ssdp_usn(discovery_info.ssdp_usn):
            return device_uuid
    return None


def unique_id_for_discovery(discovery_info: SsdpServiceInfo, host: str) -> str:
    """Config-flow unique_id: device UUID if present, else host."""
    return uuid_from_discovery(discovery_info) or host


def is_link_local_host(host: str) -> bool:
    """Return True if host is a link-local IP address."""
    try:
        return ipaddress.ip_address(host).is_link_local
    except ValueError:
        return False


def host_from_ssdp_usn(usn: str) -> str | None:
    """Return fritz.box when embedded in a non-standard USN URL segment."""
    search_start = 0
    while (scheme_pos := usn.find("://", search_start)) != -1:
        fragment_start = scheme_pos + 1
        fragment_end = fragment_start
        while fragment_end < len(usn) and usn[fragment_end] not in " \t\r\n":
            if (
                fragment_end > fragment_start
                and usn[fragment_end : fragment_end + 2] == "::"
            ):
                break
            fragment_end += 1
        fragment = usn[fragment_start:fragment_end]
        if hostname := hostname_from_url(f"http:{fragment}"):
            if hostname.lower() == FRITZ_BOX_HOST:
                return FRITZ_BOX_HOST
        search_start = scheme_pos + 3
    return None


def host_from_ssdp(discovery_info: SsdpServiceInfo) -> str | None:
    """Host from SSDP location, headers, or USN."""
    if discovery_info.ssdp_location:
        if hostname := hostname_from_url(discovery_info.ssdp_location):
            return hostname
    if discovery_info.ssdp_headers:
        location_header = discovery_info.ssdp_headers.get("location")
        if isinstance(location_header, str):
            if hostname := hostname_from_url(location_header):
                return hostname
    if discovery_info.ssdp_usn:
        return host_from_ssdp_usn(discovery_info.ssdp_usn)
    return None


def is_fritzbox_router_discovery(discovery_info: SsdpServiceInfo) -> bool:
    """Return True if SSDP data looks like a FRITZ!Box router (not a repeater)."""
    st = discovery_info.ssdp_st or ""
    usn = discovery_info.ssdp_usn or ""
    server = discovery_info.ssdp_server or ""
    location = discovery_info.ssdp_location or ""

    combined = f"{st} {usn} {server} {location}".lower()
    if discovery_info.ssdp_headers:
        combined += (
            " "
            + " ".join(
                str(value) for value in discovery_info.ssdp_headers.values()
            ).lower()
        )

    if not any(indicator in combined for indicator in FRITZBOX_SSDP_INDICATORS):
        return False

    if any(indicator in combined for indicator in REPEATER_INDICATORS):
        return False

    has_igd = "internetgatewaydevice" in combined or "igd" in combined
    if not has_igd:
        return "fritz!box" in combined
    return True
