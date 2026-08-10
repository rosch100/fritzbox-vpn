"""Constants for Fritz!Box VPN Web API."""

API_LOGIN = "/login_sid.lua"
API_DATA = "/data.lua"
API_VPN_ROOT = "/api/v0/generic/vpn"
API_VPN_CONNECTION = f"{API_VPN_ROOT}/connection/{{uid}}"

API_PAGE_SHAREWIREGUARD = "shareWireguard"
API_KEY_DATA = "data"
API_KEY_INIT = "init"
API_KEY_BOX_CONNECTIONS = "boxConnections"
API_KEY_CONNECTION = "connection"
API_KEY_UID = "uid"
API_KEY_UID_REST = "UID"
API_KEY_ACTIVE = "active"
API_KEY_ACTIVATED = "activated"
API_KEY_CONNECTED = "connected"
API_KEY_CONNECTED_SINCE = "connected_since"
API_KEY_STATE = "state"
API_KEY_NAME = "name"
API_KEY_ACCESS_TYPE = "access_type"
ACCESS_TYPE_WIREGUARD = "4"
WIREGUARD_STATE_READY = "ready"
HEADER_CLIENT_NAME = "Client-Name"
HEADER_VALUE_CLIENT_NAME = "WebGUI"
LISTING_MODE_DATA_LUA = "data_lua"
LISTING_MODE_REST = "rest"
# Prefer legacy data.lua, then FRITZ!OS 8.40+ REST listing.
LISTING_PROBE_ORDER = (LISTING_MODE_DATA_LUA, LISTING_MODE_REST)

DEFAULT_TIMEOUT = 10
DEFAULT_PROTOCOL = "https"
VERIFICATION_DELAY = 1.5

PROTOCOL_HTTP = "http"
PROTOCOL_HTTPS = "https"
PROTOCOLS_ALLOWED = (PROTOCOL_HTTP, PROTOCOL_HTTPS)
CONTENT_TYPE_JSON = "json"

HTTP_STATUS_OK = 200
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_NOT_FOUND = 404
HTTPS_FALLBACK_STATUS_CODES = (400, HTTP_STATUS_NOT_FOUND, 502, 503)

LOGIN_TAG_CHALLENGE = "Challenge"
LOGIN_TAG_SID = "SID"
LOGIN_TAG_BLOCKTIME = "BlockTime"
LOGIN_FORM_USERNAME = "username"
LOGIN_FORM_RESPONSE = "response"
INVALID_SID_VALUE = "0000000000000000"

LOG_LABEL_ACTIVATED = "activated"
LOG_LABEL_DEACTIVATED = "deactivated"
ACTIVE_STATE_STRINGS_TRUE = ("1", "true", "yes", "on")
HEADER_VALUE_APPLICATION_JSON = "application/json"
AUTH_HEADER_PREFIX = "AVM-SID "

NAME_FRITZBOX = "Fritz!Box"
DEFAULT_NAME_UNKNOWN = "Unknown"

ERROR_MSG_INVALID_SID = "Invalid SID"
ERROR_MSG_INVALID_SID_403 = "Invalid SID (HTTP 403)"
ERROR_MSG_INVALID_SID_HTML = "Invalid SID (HTML response)"
ERROR_MSG_VPN_PAYLOAD_MISSING = (
    "VPN connections payload missing from Fritz!Box response"
)
ERROR_MSG_LOGIN_FAILED_SID = (
    "Login failed: Invalid SID. This can be caused by: "
    "(1) Incorrect username or password, or "
    "(2) TR-064 not being enabled. "
    "Please check your credentials first, then verify that TR-064 (Permit access for apps) "
    "is enabled in the {name_fritzbox} under "
    "Home Network > Network > Network settings > Access Settings in the Home Network. "
    "Note: UPnP is only needed for automatic discovery via SSDP, not for API access."
)
