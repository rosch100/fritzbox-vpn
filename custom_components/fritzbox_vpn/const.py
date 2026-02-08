"""Constants for FritzBox VPN integration."""

DOMAIN = "fritzbox_vpn"

# Configuration keys
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "update_interval"

# Default values
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

# Status constants
STATUS_CONNECTED = "connected"
STATUS_ENABLED = "enabled"
STATUS_DISABLED = "disabled"
STATUS_UNKNOWN = "unknown"
