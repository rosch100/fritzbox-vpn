"""Constants for FritzBox VPN integration."""

from typing import Any, Mapping, Optional

from homeassistant.const import CONF_HOST, CONF_PASSWORD

DOMAIN = "fritzbox_vpn"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_HOST = "192.168.178.1"
HOST_FALLBACK_UNKNOWN = "unknown"
DEFAULT_UPDATE_INTERVAL = 30
UPDATE_INTERVAL_MIN = 5
UPDATE_INTERVAL_MAX = 3600
RETRY_AFTER_SECONDS = 300
DEFAULT_TIMEOUT = 10
DEFAULT_PROTOCOL = "https"
VERIFICATION_DELAY = 1.5

API_LOGIN = "/login_sid.lua"
API_DATA = "/data.lua"
API_VPN_CONNECTION = "/api/v0/generic/vpn/connection/{uid}"

# API request/response keys (Fritz!Box data.lua / boxConnections)
API_PAGE_SHAREWIREGUARD = "shareWireguard"
API_KEY_DATA = "data"
API_KEY_INIT = "init"
API_KEY_BOX_CONNECTIONS = "boxConnections"
API_KEY_UID = "uid"
API_KEY_ACTIVE = "active"
API_KEY_ACTIVATED = "activated"
API_KEY_CONNECTED = "connected"
API_KEY_NAME = "name"

ATTR_UID = "uid"
ATTR_VPN_UID = "vpn_uid"
ATTR_STATUS = "status"
UNIQUE_ID_PREFIX = f"{DOMAIN}_"
UNIQUE_ID_SUFFIX_SWITCH = "switch"
UNIQUE_ID_SUFFIX_STATUS = "status"
UNIQUE_ID_SUFFIX_UID = "uid"
UNIQUE_ID_SUFFIX_VPN_UID = "vpn_uid"
UNIQUE_ID_SUFFIX_CONNECTED = "connected"
UNIQUE_ID_SUFFIXES = (
    UNIQUE_ID_SUFFIX_VPN_UID,
    UNIQUE_ID_SUFFIX_CONNECTED,
    UNIQUE_ID_SUFFIX_STATUS,
    UNIQUE_ID_SUFFIX_SWITCH,
    UNIQUE_ID_SUFFIX_UID,
)
ERROR_MSG_INVALID_SID = "Invalid SID"
ERROR_MSG_INVALID_SID_403 = "Invalid SID (HTTP 403)"
ERROR_MSG_INVALID_SID_HTML = "Invalid SID (HTML response)"
ERROR_MSG_LOGIN_FAILED_SID = (
    "Login failed: Invalid SID. This can be caused by: "
    "(1) Incorrect username or password, or "
    "(2) TR-064 not being enabled. "
    "Please check your credentials first, then verify that TR-064 (Permit access for apps) "
    "is enabled in the {name_fritzbox} under "
    "Home Network > Network > Network settings > Access Settings in the Home Network. "
    "Note: UPnP is only needed for automatic discovery via SSDP, not for API access."
)
PROTOCOL_HTTP = "http"
PROTOCOL_HTTPS = "https"
PROTOCOLS_ALLOWED = (PROTOCOL_HTTP, PROTOCOL_HTTPS)
CONTENT_TYPE_JSON = "json"

HTTP_STATUS_OK = 200
HTTP_STATUS_FORBIDDEN = 403
HTTPS_FALLBACK_STATUS_CODES = (400, 404, 502, 503)

LOGIN_TAG_CHALLENGE = "Challenge"
LOGIN_TAG_SID = "SID"
LOGIN_FORM_USERNAME = "username"
LOGIN_FORM_RESPONSE = "response"
INVALID_SID_VALUE = "0000000000000000"

LOG_LABEL_ACTIVATED = "activated"
LOG_LABEL_DEACTIVATED = "deactivated"
ACTIVE_STATE_STRINGS_TRUE = ("1", "true", "yes", "on")
HEADER_VALUE_APPLICATION_JSON = "application/json"
AUTH_HEADER_PREFIX = "AVM-SID "

DATA_COORDINATOR = "coordinator"
DATA_FRITZ_SESSION = "fritz_session"
DATA_KNOWN_UIDS_SWITCH = "known_uids_switch"
DATA_KNOWN_UIDS_SENSOR = "known_uids_sensor"
DATA_KNOWN_UIDS_BINARY_SENSOR = "known_uids_binary_sensor"
DATA_KNOWN_UIDS_KEYS = (
    DATA_KNOWN_UIDS_SWITCH,
    DATA_KNOWN_UIDS_SENSOR,
    DATA_KNOWN_UIDS_BINARY_SENSOR,
)
DATA_LOCK_ADD_ENTITIES_SWITCH = "lock_add_entities_switch"
DATA_LOCK_ADD_ENTITIES_SENSOR = "lock_add_entities_sensor"
DATA_LOCK_ADD_ENTITIES_BINARY_SENSOR = "lock_add_entities_binary_sensor"

OPTIONS_ACTION_CONFIGURE = "configure"
OPTIONS_ACTION_CLEANUP = "cleanup"
OPTIONS_ACTION_REPAIR_ENTITY_IDS = "repair_entity_ids"
SERVICE_REMOVE_UNAVAILABLE_ENTITIES = "remove_unavailable_entities"
SERVICE_REPAIR_ENTITY_ID_SUFFIXES = "repair_entity_id_suffixes"
CONF_CONFIG_ENTRY_ID = "config_entry_id"

LOG_MSG_VPN_CONNECTIONS_REMOVED = (
    "VPN connection(s) no longer available on the %s; related entities will show as unavailable: %s"
)
LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT = (
    "You can remove obsolete entities under Settings > Devices & Services > Entities (filter by Fritz!Box VPN)."
)

MANUFACTURER_AVM = "AVM"
NAME_FRITZBOX = "Fritz!Box"
MODEL_FRITZBOX = "Fritz!Box"
MODEL_WIREGUARD_VPN = "WireGuard VPN"
DEFAULT_NAME_UNKNOWN = "Unknown"
INTEGRATION_TITLE = "Fritz!Box VPN"
NOTIFICATION_TITLE_AUTH_ERROR = "Fritz!Box VPN: Authentifizierungsfehler"

ERROR_KEY_UNKNOWN = "unknown"
ERROR_KEY_CANNOT_CONNECT = "cannot_connect"
ERROR_KEY_INVALID_AUTH = "invalid_auth"
ERROR_KEY_INVALID_HOST = "invalid_host"
ERROR_KEY_CONFIG_ENTRY_NOT_FOUND = "config_entry_not_found"

CONFIG_URL_INTEGRATIONS = "/config/integrations"


def auth_error_notification_id(host: str) -> str:
    """Return the persistent notification ID for auth errors."""
    return f"{DOMAIN}_auth_error_{host or HOST_FALLBACK_UNKNOWN}"


def host_from_config(config: Mapping[str, Any]) -> str:
    """Host from config/entry data; HOST_FALLBACK_UNKNOWN if missing."""
    return config.get(CONF_HOST, HOST_FALLBACK_UNKNOWN)


def mask_config_for_log(data: dict) -> dict:
    """Return a copy of the config dict with sensitive keys masked."""
    return {k: "***" if k in SENSITIVE_CONFIG_KEYS else v for k, v in data.items()}


def password_from_source(source: Optional[Mapping[str, Any]]) -> str:
    """Return password from one dict (CONF_PASSWORD, 'password', or 'pass'), or empty string."""
    if not source:
        return ""
    return str(source.get(CONF_PASSWORD) or source.get("password") or source.get("pass") or "")


def password_from_sources(*sources: Optional[Mapping[str, Any]]) -> str:
    """Return first non-empty password from any of the given dicts."""
    for src in sources:
        p = password_from_source(src)
        if p:
            return p
    return ""


STATUS_CONNECTED = "connected"
STATUS_ENABLED = "enabled"
STATUS_DISABLED = "disabled"
STATUS_UNKNOWN = "unknown"

FRITZBOX_SSDP_INDICATORS = (
    "fritz.box",
    "fritzbox",
    "fritz!box",
    "avm",
    "fritz",
)

FRITZ_INTEGRATION_DOMAINS = ("fritz", "fritzbox_tools", "fritzbox", "fritzbox_tools_plus")
SENSITIVE_CONFIG_KEYS = ("password", "pass", "username", "user")

REPEATER_INDICATORS = (
    "repeater",
    "wlan repeater",
    "fritz!wlan repeater",
    "fritz!wlanrepeater",
)

ERROR_INDICATOR_AUTH = ("login failed", "invalid sid")
ERROR_INDICATOR_CONNECT = ("failed to get login page", "connection")
AUTH_INDICATORS = (
    "login failed",
    "invalid sid",
    "authentication failed",
    "invalid credentials",
    "unauthorized",
    "access denied",
)
