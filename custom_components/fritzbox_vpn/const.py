"""Constants for FritzBox VPN integration."""

DOMAIN = "fritzbox_vpn"

# Configuration keys
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Default values
DEFAULT_UPDATE_INTERVAL = 30  # seconds
DEFAULT_TIMEOUT = 10  # seconds

# API endpoints
API_LOGIN = "/login_sid.lua"
API_DATA = "/data.lua"
API_VPN_CONNECTION = "/api/v0/generic/vpn/connection/{uid}"

# Data keys
DATA_COORDINATOR = "coordinator"
DATA_FRITZ_SESSION = "fritz_session"

