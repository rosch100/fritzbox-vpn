"""Tests for SSDP unique_id helpers."""

from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from custom_components.fritzbox_vpn.ssdp_unique_id import (
    host_from_ssdp,
    parse_device_uuid,
    unique_id_for_discovery,
    uuid_from_discovery,
    uuid_from_ssdp_usn,
    uuid_from_upnp_udn,
)

MOCK_DEVICE_UUID = "2f402f80-da79-4e15-8e7b-4b6b6b6b6b6b"
MOCK_UDN = f"uuid:{MOCK_DEVICE_UUID}"
MOCK_USN = f"uuid:{MOCK_DEVICE_UUID}::upnp:rootdevice"
MOCK_HOST = "192.168.178.1"
MOCK_OTHER_UUID = "8c3e9f12-4a5b-6c7d-8e9f-0a1b2c3d4e5f"


def test_parse_device_uuid_accepts_valid_uuid() -> None:
    assert parse_device_uuid(MOCK_DEVICE_UUID) == MOCK_DEVICE_UUID


def test_parse_device_uuid_rejects_invalid() -> None:
    assert parse_device_uuid("not-a-uuid") is None
    assert parse_device_uuid("") is None


def test_uuid_from_upnp_udn() -> None:
    assert uuid_from_upnp_udn(MOCK_UDN) == MOCK_DEVICE_UUID


def test_uuid_from_ssdp_usn() -> None:
    assert uuid_from_ssdp_usn(MOCK_USN) == MOCK_DEVICE_UUID


def test_uuid_from_ssdp_usn_ignores_non_uuid_prefix() -> None:
    assert uuid_from_ssdp_usn("mock_usn") is None


def test_uuid_from_discovery_prefers_udn() -> None:
    discovery = SsdpServiceInfo(
        ssdp_usn=MOCK_USN,
        ssdp_st="mock_st",
        ssdp_location=f"https://{MOCK_HOST}:12345/",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name", ATTR_UPNP_UDN: MOCK_UDN},
    )
    assert uuid_from_discovery(discovery) == MOCK_DEVICE_UUID


def test_uuid_from_discovery_falls_back_to_usn() -> None:
    discovery = SsdpServiceInfo(
        ssdp_usn=MOCK_USN,
        ssdp_st="mock_st",
        ssdp_location=f"https://{MOCK_HOST}:12345/",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert uuid_from_discovery(discovery) == MOCK_DEVICE_UUID


def test_unique_id_for_discovery_uses_host_without_uuid() -> None:
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location=f"https://{MOCK_HOST}:12345/",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert unique_id_for_discovery(discovery, MOCK_HOST) == MOCK_HOST


def test_host_from_ssdp_location() -> None:
    discovery = SsdpServiceInfo(
        ssdp_usn=MOCK_USN,
        ssdp_st="mock_st",
        ssdp_location=f"https://{MOCK_HOST}:12345/",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert host_from_ssdp(discovery) == MOCK_HOST


def test_host_from_ssdp_fritz_box_from_usn() -> None:
    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:device-1::upnp:rootdevice://fritz.box",
        ssdp_st="mock_st",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert host_from_ssdp(discovery) == "fritz.box"


def test_host_from_ssdp_skips_non_string_header_location() -> None:
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_headers={"location": 12345},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "name"},
    )
    assert host_from_ssdp(discovery) is None
