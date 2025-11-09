"""Config flow for FritzBox VPN integration."""

import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD

from .const import DOMAIN
from .coordinator import FritzBoxVPNSession

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="192.168.178.1"): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = FritzBoxVPNSession(
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD]
    )

    try:
        # Try to get a session and fetch VPN connections
        await session.async_get_session()
        connections = await session.async_get_vpn_connections()
        await session.async_close()

        if not connections:
            raise CannotConnect("No VPN connections found on FritzBox")

        return {"title": f"FritzBox VPN ({data[CONF_HOST]})"}
    except Exception as err:
        _LOGGER.exception("Error validating input: %s", err)
        if "Login failed" in str(err) or "Invalid SID" in str(err):
            raise InvalidAuth from err
        if "Failed to get login page" in str(err):
            raise CannotConnect from err
        raise CannotConnect from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FritzBox VPN."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_host: Optional[str] = None
        self._existing_config: Optional[Dict[str, Any]] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        # Try to get config from existing FritzBox integration first
        # SSDP is only used as fallback if no existing integration is found
        if not user_input:
            self._existing_config = await self._get_existing_fritz_config()
            if self._existing_config:
                _LOGGER.info("Found existing FritzBox integration, using its configuration (SSDP will be skipped)")
                # Pre-fill with existing config
                schema = vol.Schema({
                    vol.Required(CONF_HOST, default=self._existing_config.get(CONF_HOST, "192.168.178.1")): str,
                    vol.Required(CONF_USERNAME, default=self._existing_config.get(CONF_USERNAME, "")): str,
                    vol.Required(CONF_PASSWORD, default=""): str,  # Don't pre-fill password for security
                })
            else:
                _LOGGER.debug("No existing FritzBox integration found, SSDP discovery will be used as fallback")
                schema = STEP_USER_DATA_SCHEMA
        else:
            schema = STEP_USER_DATA_SCHEMA

        if user_input is not None:
            # If password is empty and we have existing config, try to use existing password
            # Note: This only works if the existing integration is configured
            if not user_input.get(CONF_PASSWORD) and self._existing_config and self._existing_config.get(CONF_PASSWORD):
                user_input[CONF_PASSWORD] = self._existing_config.get(CONF_PASSWORD)
            
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle SSDP discovery (fallback if no existing integration found)."""
        _LOGGER.debug("SSDP discovery: %s", discovery_info)
        
        # First check if we already have an existing FritzBox integration
        # SSDP is only used as fallback
        existing_config = await self._get_existing_fritz_config()
        if existing_config:
            _LOGGER.info("Existing FritzBox integration found, aborting SSDP discovery")
            return self.async_abort(reason="already_configured")
        
        # Check if it's a FritzBox device (and specifically a router, not a repeater)
        # This check MUST happen before extracting host to avoid showing repeater IP
        if not self._is_fritzbox_device(discovery_info):
            _LOGGER.info("SSDP discovery: Rejected device (not a FritzBox router)")
            return self.async_abort(reason="not_fritzbox")
        
        # Extract host from SSDP location
        host = self._extract_host_from_ssdp(discovery_info)
        if not host:
            _LOGGER.warning("SSDP discovery: Could not extract host from discovery info")
            return self.async_abort(reason="no_host")
        
        _LOGGER.info("SSDP discovery: Found FritzBox router at %s", host)
        
        # Try to get a more stable unique ID from USN or use host as fallback
        # USN typically contains device identifier like: uuid:device-uuid::urn:schemas-upnp-org:device:InternetGatewayDevice:1
        unique_id = host  # Default to host
        if discovery_info.ssdp_usn:
            # Try to extract UUID from USN
            usn_parts = discovery_info.ssdp_usn.split("::")
            if usn_parts and usn_parts[0].startswith("uuid:"):
                unique_id = usn_parts[0].replace("uuid:", "")
                _LOGGER.debug("Using UUID from USN as unique_id: %s", unique_id)
        
        # Check if already configured
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        
        self._discovered_host = host
        self.context["title_placeholders"] = {"host": host}
        
        # Try to get config from existing FritzBox integration (should be None at this point)
        # But check again in case it was added between the first check and now
        self._existing_config = await self._get_existing_fritz_config()
        if self._existing_config:
            _LOGGER.info("Existing FritzBox integration found during SSDP, using its config instead of discovered host")
        
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle discovery confirmation."""
        errors: Dict[str, str] = {}
        
        if user_input is None:
            # Pre-fill with existing config if available (has priority over discovered host)
            # This ensures we use the router IP from existing integration, not the repeater
            if self._existing_config:
                default_host = self._existing_config.get(CONF_HOST, self._discovered_host or "192.168.178.1")
                default_username = self._existing_config.get(CONF_USERNAME, "")
                _LOGGER.info("Using existing config for confirm step: host=%s, username=%s", default_host, default_username)
            else:
                default_host = self._discovered_host or "192.168.178.1"
                default_username = ""
            
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST, default=default_host): str,
                    vol.Required(CONF_USERNAME, default=default_username): str,
                    vol.Required(CONF_PASSWORD): str,
                }),
                description_placeholders={"host": default_host},
            )
        
        # If password is empty and we have existing config, try to use existing password
        # Note: This only works if the existing integration is configured
        if not user_input.get(CONF_PASSWORD) and self._existing_config and self._existing_config.get(CONF_PASSWORD):
            user_input[CONF_PASSWORD] = self._existing_config.get(CONF_PASSWORD)
        
        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)
        
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, self._discovered_host or "192.168.178.1")): str,
                vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    @staticmethod
    def _is_fritzbox_device(discovery_info: ssdp.SsdpServiceInfo) -> bool:
        """Check if the discovered device is a FritzBox router (not a repeater).
        
        This method specifically rejects repeaters and only accepts routers.
        SSDP discovery is used as fallback, so we want to ensure we only find
        the main router, not any repeaters in the network.
        """
        # Check for FritzBox identifiers in SSDP
        st = discovery_info.ssdp_st or ""
        usn = discovery_info.ssdp_usn or ""
        server = discovery_info.ssdp_server or ""
        location = discovery_info.ssdp_location or ""
        
        # FritzBox devices typically have these identifiers
        fritzbox_indicators = [
            "fritz.box",
            "fritzbox",
            "fritz!box",
            "avm",
            "FRITZ!Box",
            "FRITZ",
        ]
        
        # Check in all SSDP fields
        combined = f"{st} {usn} {server} {location}".lower()
        
        # Also check in headers if available
        if hasattr(discovery_info, "ssdp_headers") and discovery_info.ssdp_headers:
            headers_str = " ".join(str(v) for v in discovery_info.ssdp_headers.values()).lower()
            combined += f" {headers_str}"
        
        # First check if it's a FritzBox device
        is_fritzbox = any(indicator.lower() in combined for indicator in fritzbox_indicators)
        
        if not is_fritzbox:
            _LOGGER.debug("Device is not a FritzBox")
            return False
        
        # IMPORTANT: Reject repeaters - only accept routers
        # Repeaters typically have "Repeater" or "WLAN Repeater" in the server string
        # Also check for "fritz!wlan repeater" or similar patterns
        repeater_indicators = [
            "repeater",
            "wlan repeater",
            "fritz!wlan repeater",
            "fritz!wlanrepeater",
        ]
        
        # Check for repeater indicators (case-insensitive)
        combined_lower = combined.lower()
        if any(indicator.lower() in combined_lower for indicator in repeater_indicators):
            _LOGGER.info("✗ Rejecting FritzBox Repeater device (only routers are accepted): %s", server)
            return False
        
        # Additional check: Only accept InternetGatewayDevice (routers)
        # Repeaters might use different device types
        has_igd = "internetgatewaydevice" in combined_lower or "igd" in combined_lower
        
        if not has_igd:
            _LOGGER.debug("Device does not appear to be a router (no InternetGatewayDevice): %s", st)
            # Still accept if it's clearly a FritzBox router (has FRITZ!Box in server, no repeater)
            if "fritz!box" in combined_lower and not any(ind.lower() in combined_lower for ind in repeater_indicators):
                _LOGGER.info("✓ Accepting as FritzBox router based on server string (no IGD but FRITZ!Box): %s", server)
                return True
            _LOGGER.debug("Rejecting: No IGD and not clearly a router")
            return False
        
        # Final check: Make absolutely sure it's not a repeater
        if any(indicator.lower() in combined_lower for indicator in repeater_indicators):
            _LOGGER.info("✗ Rejecting FritzBox Repeater device (final check): %s", server)
            return False
        
        _LOGGER.info("✓ Accepting FritzBox router device: %s", server)
        return True

    @staticmethod
    def _extract_host_from_ssdp(discovery_info: ssdp.SsdpServiceInfo) -> Optional[str]:
        """Extract host IP from SSDP discovery info."""
        # Try to get host from location URL (primary method)
        if discovery_info.ssdp_location:
            try:
                parsed = urlparse(discovery_info.ssdp_location)
                if parsed.hostname:
                    return parsed.hostname
            except Exception as err:
                _LOGGER.debug("Failed to parse ssdp_location: %s", err)
        
        # Try to get from headers
        if hasattr(discovery_info, "ssdp_headers") and discovery_info.ssdp_headers:
            location = discovery_info.ssdp_headers.get("location")
            if location:
                try:
                    parsed = urlparse(location)
                    if parsed.hostname:
                        return parsed.hostname
                except Exception as err:
                    _LOGGER.debug("Failed to parse location from headers: %s", err)
        
        # Try to get from USN (fallback - contains hostname sometimes)
        if discovery_info.ssdp_usn:
            # USN format: uuid:device-uuid::urn:schemas-upnp-org:device:InternetGatewayDevice:1
            # Sometimes contains hostname
            usn_lower = discovery_info.ssdp_usn.lower()
            if "fritz.box" in usn_lower:
                return "fritz.box"
        
        _LOGGER.warning("Could not extract host from SSDP discovery info")
        return None

    async def _get_existing_fritz_config(self) -> Optional[Dict[str, Any]]:
        """Get configuration from existing FritzBox integration if available.
        
        Checks for:
        - Official FritzBox integration (domain: "fritz")
        - FritzBox Tools integration (domain: "fritzbox_tools" or "fritzbox")
        
        Based on Home Assistant core integration patterns:
        https://github.com/home-assistant/core/tree/dev/homeassistant/components/fritz
        """
        # First, let's check ALL available domains to see what's actually installed
        _LOGGER.debug("Checking for existing FritzBox integrations...")
        all_domains = set()
        for entry in self.hass.config_entries.async_entries():
            all_domains.add(entry.domain)
            # Log all FritzBox-related domains
            if "fritz" in entry.domain.lower() or "avm" in entry.domain.lower():
                _LOGGER.info("Found potential FritzBox integration: domain='%s', title='%s', entry_id='%s'", 
                           entry.domain, entry.title, entry.entry_id)
        
        _LOGGER.debug("All available domains: %s", sorted(all_domains))
        
        # Possible domain names for FritzBox integrations (order matters - check most common first)
        # Official integration uses "fritz", FritzBox Tools uses "fritzbox_tools"
        possible_domains = ["fritz", "fritzbox_tools", "fritzbox", "fritzbox_tools_plus"]
        
        for domain in possible_domains:
            try:
                # Check for existing FritzBox integration
                fritz_entries = [
                    entry
                    for entry in self.hass.config_entries.async_entries(domain)
                    if entry.state in (
                        config_entries.ConfigEntryState.LOADED,
                        config_entries.ConfigEntryState.NOT_LOADED,
                        config_entries.ConfigEntryState.SETUP_ERROR,  # Also check entries with setup errors
                    )
                ]
                
                _LOGGER.debug("Domain '%s': Found %d entries", domain, len(fritz_entries))
                
                if fritz_entries:
                    # Filter out repeaters - only use router entries
                    # Repeaters typically have "Repeater" in the title
                    router_entries = [
                        entry
                        for entry in fritz_entries
                        if "repeater" not in entry.title.lower()
                    ]
                    
                    # If we have router entries, use those; otherwise fall back to all entries
                    entries_to_use = router_entries if router_entries else fritz_entries
                    
                    if router_entries:
                        _LOGGER.info("Domain '%s': Filtered out %d repeater(s), using %d router entry/entries", 
                                   domain, len(fritz_entries) - len(router_entries), len(router_entries))
                    else:
                        _LOGGER.warning("Domain '%s': No router entries found, using first entry (might be a repeater)", domain)
                    
                    # Use the first available router entry (or first entry if no routers found)
                    entry = entries_to_use[0]
                    
                    _LOGGER.info("Found existing FritzBox integration '%s' with entry_id: %s", domain, entry.entry_id)
                    _LOGGER.info("Entry title: %s", entry.title)
                    _LOGGER.info("Entry source: %s", getattr(entry, 'source', 'unknown'))
                    _LOGGER.info("Entry unique_id: %s", getattr(entry, 'unique_id', 'unknown'))
                    
                    # Try to get config from data first
                    # Home Assistant stores config in entry.data, options in entry.options
                    config_data = entry.data or {}
                    _LOGGER.info("Config data keys: %s", list(config_data.keys()))
                    _LOGGER.info("Config data (masked): %s", {k: v if k not in ['password', 'pass'] else '***' for k, v in config_data.items()})
                    
                    # Also check options
                    options_data = entry.options or {}
                    _LOGGER.info("Options data keys: %s", list(options_data.keys()))
                    if options_data:
                        _LOGGER.info("Options data (masked): %s", {k: v if k not in ['password', 'pass'] else '***' for k, v in options_data.items()})
                    
                    # Extract relevant config - try different possible key names
                    # Official integration uses: host, username, password
                    # FritzBox Tools might use different keys
                    host = (
                        config_data.get(CONF_HOST) 
                        or config_data.get("host")
                        or (config_data.get("hosts", [None])[0] if isinstance(config_data.get("hosts"), list) and config_data.get("hosts") else None)
                        or config_data.get("hostname")
                        or config_data.get("ip_address")
                        or options_data.get(CONF_HOST)
                        or options_data.get("host")
                    )
                    
                    username = (
                        config_data.get(CONF_USERNAME)
                        or config_data.get("username")
                        or config_data.get("user")
                        or options_data.get(CONF_USERNAME)
                        or options_data.get("username")
                    )
                    
                    password = (
                        config_data.get(CONF_PASSWORD)
                        or config_data.get("password")
                        or config_data.get("pass")
                        or options_data.get(CONF_PASSWORD)
                        or options_data.get("password")
                    )
                    
                    # For FritzBox Tools, credentials might be in a nested structure
                    # Check if there's a "data" key with nested config
                    if not host and "data" in config_data:
                        nested_data = config_data.get("data", {})
                        host = host or nested_data.get("host") or nested_data.get(CONF_HOST)
                        username = username or nested_data.get("username") or nested_data.get(CONF_USERNAME)
                        password = password or nested_data.get("password") or nested_data.get(CONF_PASSWORD)
                    
                    if host:
                        _LOGGER.info(
                            "✓ Using config from existing FritzBox integration '%s': host=%s, username=%s, password=%s",
                            domain,
                            host,
                            username if username else "not found",
                            "***" if password else "not found"
                        )
                        return {
                            CONF_HOST: host,
                            CONF_USERNAME: username or "",
                            CONF_PASSWORD: password or "",
                        }
                    else:
                        _LOGGER.warning(
                            "✗ Found FritzBox integration '%s' but could not extract host. "
                            "Config keys: %s, Options keys: %s",
                            domain, list(config_data.keys()), list(options_data.keys())
                        )
                        # Log full config for debugging (password masked)
                        _LOGGER.warning("Full config_data: %s", {k: v if k not in ['password', 'pass'] else '***' for k, v in config_data.items()})
                        if options_data:
                            _LOGGER.warning("Full options_data: %s", {k: v if k not in ['password', 'pass'] else '***' for k, v in options_data.items()})
                        
            except KeyError:
                # Domain doesn't exist, try next one
                _LOGGER.debug("Domain '%s' not found (KeyError), trying next", domain)
                continue
            except Exception as err:
                _LOGGER.warning("Error checking domain '%s': %s", domain, err)
                _LOGGER.exception("Full exception details:")
                continue
        
        _LOGGER.warning("✗ No existing FritzBox integration found with usable configuration")
        _LOGGER.info("Searched domains: %s", possible_domains)
        _LOGGER.info("Available domains in system: %s", sorted(all_domains))
        return None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for FritzBox VPN."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

