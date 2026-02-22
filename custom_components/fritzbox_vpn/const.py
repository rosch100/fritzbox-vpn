"""Constants for FritzBox VPN integration."""

DOMAIN = "fritzbox_vpn"

CONF_UPDATE_INTERVAL = "update_interval"

# Default values
DEFAULT_HOST = "192.168.178.1"
HOST_FALLBACK_UNKNOWN = "unknown"
DEFAULT_UPDATE_INTERVAL = 30  # seconds
UPDATE_INTERVAL_MIN = 5
UPDATE_INTERVAL_MAX = 3600  # 1 hour
RETRY_AFTER_SECONDS = 300  # 5 min backoff after fetch errors (reduces reconnect storm)
DEFAULT_TIMEOUT = 10  # seconds
DEFAULT_PROTOCOL = "https"  # Use HTTPS by default for security
VERIFICATION_DELAY = 1.5  # seconds - delay to wait for VPN status change to take effect

# API endpoints
API_LOGIN = "/login_sid.lua"
API_DATA = "/data.lua"
API_VPN_CONNECTION = "/api/v0/generic/vpn/connection/{uid}"

# Data keys
DATA_COORDINATOR = "coordinator"
DATA_FRITZ_SESSION = "fritz_session"

# Device/entity defaults
MANUFACTURER_AVM = "AVM"
NAME_FRITZBOX = "Fritz!Box"
MODEL_FRITZBOX = "Fritz!Box"
MODEL_WIREGUARD_VPN = "WireGuard VPN"
DEFAULT_NAME_UNKNOWN = "Unknown"
INTEGRATION_TITLE = "Fritz!Box VPN"
# Fallback when translation is unavailable; normal title comes from config.notification.auth_error_title
NOTIFICATION_TITLE_AUTH_ERROR = "Fritz!Box VPN: Authentifizierungsfehler"

# Config flow error keys (must match translation keys in en.json / de.json)
ERROR_KEY_UNKNOWN = "unknown"
ERROR_KEY_CANNOT_CONNECT = "cannot_connect"
ERROR_KEY_INVALID_AUTH = "invalid_auth"
ERROR_KEY_CONFIG_ENTRY_NOT_FOUND = "config_entry_not_found"

CONFIG_URL_INTEGRATIONS = "/config/integrations"


def auth_error_notification_id(host: str) -> str:
    """Return the persistent notification ID for auth errors."""
    return f"{DOMAIN}_auth_error_{host or HOST_FALLBACK_UNKNOWN}"


def mask_config_for_log(data: dict) -> dict:
    """Return a copy of the config dict with sensitive keys masked."""
    return {k: "***" if k in SENSITIVE_CONFIG_KEYS else v for k, v in data.items()}

# Status constants
STATUS_CONNECTED = "connected"
STATUS_ENABLED = "enabled"
STATUS_DISABLED = "disabled"
STATUS_UNKNOWN = "unknown"

# SSDP: FritzBox device indicators (lowercase for comparison)
FRITZBOX_SSDP_INDICATORS = (
    "fritz.box",
    "fritzbox",
    "fritz!box",
    "avm",
    "fritz",
)

# Domains to check for existing Fritz/AVM integration
FRITZ_INTEGRATION_DOMAINS = ("fritz", "fritzbox_tools", "fritzbox", "fritzbox_tools_plus")

SENSITIVE_CONFIG_KEYS = ("password", "pass", "username", "user")

# Repeater detection (used in SSDP and config entry filtering; repeaters have no WireGuard)
REPEATER_INDICATORS = (
    "repeater",
    "wlan repeater",
    "fritz!wlan repeater",
    "fritz!wlanrepeater",
)

# Error message substrings for mapping validation/session errors
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
