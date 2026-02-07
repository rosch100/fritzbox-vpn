"""Config flow for FritzBox VPN integration."""

import ipaddress
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
from .coordinator import FritzBoxVPNSession

_LOGGER = logging.getLogger(__name__)

def validate_host(host: str) -> str:
    """Validate host is a valid IP address or hostname."""
    if not host or not isinstance(host, str):
        raise vol.Invalid("Host must be a non-empty string")
    
    # Try IP address first
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    
    # Check if it's a valid hostname
    if len(host) > 253:
        raise vol.Invalid("Hostname too long (max 253 characters)")
    
    # Basic hostname validation (alphanumeric, dots, hyphens)
    if not all(c.isalnum() or c in ('.', '-') for c in host):
        raise vol.Invalid("Invalid hostname format")
    
    # Must not start or end with dot or hyphen
    if host.startswith('.') or host.endswith('.') or host.startswith('-') or host.endswith('-'):
        raise vol.Invalid("Hostname cannot start or end with dot or hyphen")
    
    return host


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="192.168.178.1"): vol.All(str, validate_host),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect to the FritzBox.
    
    Only validates the connection to the FritzBox itself, not the presence of VPN connections.
    VPN connections are automatically discovered during integration setup.
    """
    session = FritzBoxVPNSession(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD]
    )

    try:
        # Try to get a session to validate credentials and connection
        # We don't check for VPN connections here - they will be discovered automatically
        await session.async_get_session()
        await session.async_close()

        return {"title": f"Fritz!Box VPN ({data[CONF_HOST]})"}
    except Exception as err:
        error_msg = str(err)
        if "Login failed" in error_msg or "Invalid SID" in error_msg:
            _LOGGER.warning(
                "Authentication failed. Invalid SID can be caused by: (1) Incorrect username or password, or "
                "(2) TR-064 not being enabled. Please check credentials first, then verify TR-064 is enabled "
                "at: Home Network > Network > Network settings > Access Settings in the Home Network. "
                "Note: UPnP is only needed for automatic discovery, not for API access. "
                "Error: %s", error_msg
            )
            raise InvalidAuth from err
        _LOGGER.exception("Error validating input: %s", err)
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
        
        _LOGGER.info("async_step_user called with user_input=%s", "provided" if user_input else "None (first call)")

        # Try to get config from existing FritzBox integration first
        # SSDP is only used as fallback if no existing integration is found
        if not user_input:
            _LOGGER.info("No user_input provided, attempting autoconfiguration...")
            self._existing_config = await self._get_existing_fritz_config()
            _LOGGER.info("Autoconfiguration result: %s", "found config" if self._existing_config else "no config found")
            if self._existing_config:
                _LOGGER.info("Found existing FritzBox Tools, using its configuration (SSDP will be skipped)")
                
                # Check if we have complete configuration (host, username, password)
                has_host = bool(self._existing_config.get(CONF_HOST))
                has_username = bool(self._existing_config.get(CONF_USERNAME))
                has_password = bool(self._existing_config.get(CONF_PASSWORD))
                
                # If we have all required credentials, try to validate the connection
                if has_host and has_username and has_password:
                    _LOGGER.info("Complete autoconfiguration found (host, username, password). Testing connection...")
                    try:
                        info = await validate_input(self.hass, self._existing_config)
                        # Connection successful - create entry directly without showing form
                        _LOGGER.info("Autoconfiguration successful! Creating integration entry automatically.")
                        _LOGGER.debug("Saving config with keys: %s", list(self._existing_config.keys()))
                        _LOGGER.debug("Password present in config to save: %s", bool(self._existing_config.get(CONF_PASSWORD)))
                        
                        # Set unique_id to prevent duplicate entries
                        host = self._existing_config.get(CONF_HOST)
                        await self.async_set_unique_id(host)
                        self._abort_if_unique_id_configured()
                        
                        return self.async_create_entry(title=info["title"], data=self._existing_config)
                    except CannotConnect:
                        _LOGGER.warning("Autoconfiguration connection test failed: cannot_connect")
                        errors["base"] = "cannot_connect"
                    except InvalidAuth:
                        _LOGGER.warning("Autoconfiguration connection test failed: invalid_auth")
                        errors["base"] = "invalid_auth"
                    except Exception as err:
                        _LOGGER.warning("Autoconfiguration connection test failed: %s", err)
                        errors["base"] = "unknown"
                    # If validation failed, fall through to show form with pre-filled values
                
                # Pre-fill with existing config (either incomplete or validation failed)
                default_password = self._existing_config.get(CONF_PASSWORD, "") if self._existing_config.get(CONF_PASSWORD) else ""
                schema = vol.Schema({
                    vol.Required(CONF_HOST, default=self._existing_config.get(CONF_HOST, "192.168.178.1")): str,
                    vol.Required(CONF_USERNAME, default=self._existing_config.get(CONF_USERNAME, "")): str,
                    vol.Required(CONF_PASSWORD, default=default_password): str,
                })
            else:
                _LOGGER.debug("No existing FritzBox Tools found, SSDP discovery will be used as fallback")
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
            except Exception as err:
                error_msg = str(err)
                _LOGGER.exception("Unexpected exception during validation: %s", error_msg)
                # Try to extract more specific error information
                if "Login failed" in error_msg or "Invalid SID" in error_msg:
                    errors["base"] = "invalid_auth"
                elif "Failed to get login page" in error_msg or "Connection" in error_msg:
                    errors["base"] = "cannot_connect"
                else:
                    # For unknown errors, log the full error but still show a user-friendly message
                    errors["base"] = "unknown"
                    _LOGGER.error("Unknown error details: %s", error_msg)
            else:
                # Set unique_id to prevent duplicate entries
                host = user_input.get(CONF_HOST)
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """Handle SSDP discovery (fallback if no existing integration found)."""
        _LOGGER.debug("SSDP discovery: %s", discovery_info)
        
        # First check if we already have an existing FritzBox integration
        # SSDP is only used as fallback
        existing_config = await self._get_existing_fritz_config()
        if existing_config:
            _LOGGER.info("Existing FritzBox Tools found, aborting SSDP discovery")
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
            _LOGGER.info("Existing FritzBox Tools found during SSDP, using its config instead of discovered host")
        
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
                default_password = self._existing_config.get(CONF_PASSWORD, "") if self._existing_config.get(CONF_PASSWORD) else ""
                _LOGGER.info("Using existing config for confirm step: host=%s, username=%s, password=%s", 
                           default_host, default_username, "***" if default_password else "not set")
            else:
                default_host = self._discovered_host or "192.168.178.1"
                default_username = ""
                default_password = ""
            
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST, default=default_host): str,
                    vol.Required(CONF_USERNAME, default=default_username): str,
                    vol.Required(CONF_PASSWORD, default=default_password): str,
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
            # Set unique_id to prevent duplicate entries
            host = user_input.get(CONF_HOST)
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=info["title"], data=user_input)
        
        # Pre-fill password from existing config if available and not provided
        default_password = ""
        if self._existing_config and self._existing_config.get(CONF_PASSWORD):
            default_password = self._existing_config.get(CONF_PASSWORD)
        elif user_input and user_input.get(CONF_PASSWORD):
            default_password = user_input.get(CONF_PASSWORD)
        
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, self._discovered_host or "192.168.178.1")): str,
                vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=default_password): str,
            }),
            errors=errors,
        )

    @staticmethod
    def _is_fritzbox_device(discovery_info: SsdpServiceInfo) -> bool:
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
    def _extract_host_from_ssdp(discovery_info: SsdpServiceInfo) -> Optional[str]:
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
        _LOGGER.info("Checking for existing FritzBox Tools...")
        all_domains = set()
        fritz_related_entries = []
        for entry in self.hass.config_entries.async_entries():
            all_domains.add(entry.domain)
            # Log all FritzBox-related domains
            if "fritz" in entry.domain.lower() or "avm" in entry.domain.lower():
                fritz_related_entries.append(entry)
                _LOGGER.info("Found potential FritzBox integration: domain='%s', title='%s', entry_id='%s', state='%s'", 
                           entry.domain, entry.title, entry.entry_id, entry.state)
        
        _LOGGER.info("All available domains: %s", sorted(all_domains))
        _LOGGER.info("Found %d FritzBox-related entries across all domains", len(fritz_related_entries))
        
        # If we already found FritzBox-related entries, prioritize checking those domains first
        # This avoids checking domains that don't have any entries
        found_domains = set(entry.domain for entry in fritz_related_entries)
        
        # Possible domain names for FritzBox integrations (order matters - check most common first)
        # Official integration uses "fritz", FritzBox Tools uses "fritzbox_tools"
        possible_domains = ["fritz", "fritzbox_tools", "fritzbox", "fritzbox_tools_plus"]
        
        # Reorder: check domains that have entries first
        prioritized_domains = [d for d in possible_domains if d in found_domains]
        prioritized_domains.extend([d for d in possible_domains if d not in found_domains])
        
        _LOGGER.info("Checking domains in order: %s (found entries in: %s)", prioritized_domains, list(found_domains))
        
        for domain in prioritized_domains:
            try:
                # Check for existing FritzBox integration
                # Get all entries first to see what we have
                all_entries = list(self.hass.config_entries.async_entries(domain))
                _LOGGER.info("Domain '%s': Found %d total entries", domain, len(all_entries))
                
                # Log all entries with their states
                for entry in all_entries:
                    _LOGGER.info("  Entry '%s' (entry_id: %s) has state: %s", entry.title, entry.entry_id, entry.state)
                
                # Check for existing FritzBox integration
                # Accept all states except FAILED_UNLOAD and SETUP_IN_PROGRESS
                # Note: We accept NOT_LOADED and SETUP_ERROR states as they may still have valid config
                excluded_states = (
                    config_entries.ConfigEntryState.FAILED_UNLOAD,
                    config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
                )
                fritz_entries = [
                    entry
                    for entry in all_entries
                    if entry.state not in excluded_states
                ]
                
                _LOGGER.info("Domain '%s': Found %d entries after filtering by state (excluded states: %s)", 
                           domain, len(fritz_entries), [s.name for s in excluded_states])
                if len(fritz_entries) < len(all_entries):
                    excluded_entries = [e for e in all_entries if e.state in excluded_states]
                    _LOGGER.info("Domain '%s': Excluded %d entries due to state: %s", 
                               domain, len(excluded_entries), 
                               [(e.title, e.state.name) for e in excluded_entries])
                
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
                    
                    # Prefer entries that have credentials (username/password) in addition to host
                    # This ensures we get a fully configured entry, not just one with an IP
                    entries_with_creds = []
                    for entry in entries_to_use:
                        config_data = entry.data or {}
                        options_data = entry.options or {}
                        
                        _LOGGER.info("Checking entry '%s' (entry_id: %s) for credentials", entry.title, entry.entry_id)
                        _LOGGER.info("  Config data keys: %s", list(config_data.keys()))
                        _LOGGER.info("  Options data keys: %s", list(options_data.keys()))
                        
                        # Check if entry has username or password
                        # Try all possible key names
                        # Note: Home Assistant stores credentials directly in entry.data
                        # Based on actual config entries, credentials are stored as:
                        # {"host": "...", "username": "...", "password": "...", "port": ...}
                        has_username = bool(
                            config_data.get(CONF_USERNAME) or 
                            config_data.get("username") or 
                            config_data.get("user") or
                            options_data.get(CONF_USERNAME) or 
                            options_data.get("username") or
                            options_data.get("user")
                        )
                        has_password = bool(
                            config_data.get(CONF_PASSWORD) or 
                            config_data.get("password") or 
                            config_data.get("pass") or
                            options_data.get(CONF_PASSWORD) or 
                            options_data.get("password") or
                            options_data.get("pass")
                        )
                        
                        _LOGGER.debug("  Has username: %s, Has password: %s", has_username, has_password)
                        if not has_username and not has_password:
                            _LOGGER.debug("  Entry '%s' has no credentials (config keys: %s, options keys: %s)", 
                                        entry.title, list(config_data.keys()), list(options_data.keys()))
                        
                        if has_username or has_password:
                            entries_with_creds.append(entry)
                            _LOGGER.info("  ✓ Entry '%s' has credentials (username: %s, password: %s)", 
                                       entry.title, has_username, has_password)
                    
                    # Use entry with credentials if available, otherwise use first router entry
                    if entries_with_creds:
                        entry = entries_with_creds[0]
                        _LOGGER.info("Domain '%s': Found %d entry/entries with credentials, using first one", domain, len(entries_with_creds))
                    else:
                        entry = entries_to_use[0]
                        _LOGGER.warning("Domain '%s': No entries with credentials found, using first router entry (credentials may be missing)", domain)
                    
                    _LOGGER.info("Found existing FritzBox Tools '%s' with entry_id: %s", domain, entry.entry_id)
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
                            "✓ Using config from existing FritzBox Tools '%s': host=%s, username=%s, password=%s",
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
                        # Log full config for debugging (password masked) - only in debug mode
                        _LOGGER.debug("Full config_data: %s", {k: v if k not in ['password', 'pass'] else '***' for k, v in config_data.items()})
                        if options_data:
                            _LOGGER.debug("Full options_data: %s", {k: v if k not in ['password', 'pass'] else '***' for k, v in options_data.items()})
                        
            except KeyError:
                # Domain doesn't exist, try next one
                _LOGGER.debug("Domain '%s' not found (KeyError), trying next", domain)
                continue
            except Exception as err:
                _LOGGER.warning("Error checking domain '%s': %s", domain, err)
                _LOGGER.exception("Full exception details:")
                continue
        
        _LOGGER.warning("✗ No existing FritzBox Tools found with usable configuration")
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
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            # Get the current config entry to access its data
            config_entry = self.hass.config_entries.async_get_entry(self._config_entry.entry_id)
            if not config_entry:
                errors["base"] = "config_entry_not_found"
                return self.async_show_form(step_id="init", data_schema=vol.Schema({}), errors=errors)
            
            # If password is empty, keep the existing password
            if not user_input.get(CONF_PASSWORD):
                user_input[CONF_PASSWORD] = config_entry.data.get(CONF_PASSWORD, "")
            
            # Validate the new configuration
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as err:
                error_msg = str(err)
                _LOGGER.exception("Unexpected exception during validation: %s", error_msg)
                # Try to extract more specific error information
                if "Login failed" in error_msg or "Invalid SID" in error_msg:
                    errors["base"] = "invalid_auth"
                elif "Failed to get login page" in error_msg or "Connection" in error_msg:
                    errors["base"] = "cannot_connect"
                else:
                    # For unknown errors, log the full error but still show a user-friendly message
                    errors["base"] = "unknown"
                    _LOGGER.error("Unknown error details: %s", error_msg)
            else:
                # Separate core config (data) from options
                config_data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                # Ensure update interval is stored as integer
                update_interval = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                _LOGGER.debug("OptionsFlow: Received update_interval from user_input: %s (type: %s)", 
                             update_interval, type(update_interval).__name__)
                
                if isinstance(update_interval, str):
                    try:
                        update_interval = int(update_interval)
                    except (ValueError, TypeError):
                        _LOGGER.warning("OptionsFlow: Failed to convert update_interval '%s' to int, using default", 
                                       update_interval)
                        update_interval = DEFAULT_UPDATE_INTERVAL
                elif not isinstance(update_interval, int):
                    try:
                        update_interval = int(update_interval) if update_interval else DEFAULT_UPDATE_INTERVAL
                    except (ValueError, TypeError):
                        _LOGGER.warning("OptionsFlow: Failed to convert update_interval '%s' to int, using default", 
                                       update_interval)
                        update_interval = DEFAULT_UPDATE_INTERVAL
                
                # Validate range
                if update_interval < 5 or update_interval > 300:
                    _LOGGER.warning("OptionsFlow: update_interval %d is out of range (5-300), using default", 
                                   update_interval)
                    update_interval = DEFAULT_UPDATE_INTERVAL
                
                _LOGGER.info("OptionsFlow: Saving update_interval: %d seconds", update_interval)
                options_data = {
                    CONF_UPDATE_INTERVAL: update_interval,
                }
                
                _LOGGER.info("OptionsFlow: Updating config entry with data=%s, options=%s", 
                            {k: v if k != CONF_PASSWORD else "***" for k, v in config_data.items()}, 
                            options_data)
                
                # Update the config entry with new data and options
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data=config_data,
                    options=options_data,
                )
                
                # Verify the update was successful
                updated_entry = self.hass.config_entries.async_get_entry(config_entry.entry_id)
                if updated_entry:
                    _LOGGER.info("OptionsFlow: Config entry updated. New options: %s", updated_entry.options)
                    _LOGGER.info("OptionsFlow: Config entry data keys: %s", list(updated_entry.data.keys()))
                else:
                    _LOGGER.error("OptionsFlow: Failed to retrieve updated config entry!")
                
                # Return the options data so they are properly saved
                # Note: async_create_entry must be called before reload to ensure options are saved
                result = self.async_create_entry(title="", data=options_data)
                
                # Reload the integration to apply the new configuration
                _LOGGER.info("OptionsFlow: Reloading integration to apply new configuration...")
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                _LOGGER.info("OptionsFlow: Integration reloaded successfully")
                
                return result

        # Get the current config entry to access its data
        config_entry = self.hass.config_entries.async_get_entry(self._config_entry.entry_id)
        if not config_entry:
            errors["base"] = "config_entry_not_found"
            return self.async_show_form(step_id="init", data_schema=vol.Schema({}), errors=errors)
        
        # Pre-fill with current values
        current_data = config_entry.data
        current_options = config_entry.options or {}
        
        # Pre-fill password from current config if available
        # Log for debugging (password masked)
        _LOGGER.debug("OptionsFlow: Current config_entry.data keys: %s", list(current_data.keys()))
        _LOGGER.debug("OptionsFlow: Has password in data: %s", bool(current_data.get(CONF_PASSWORD)))
        
        # Try to get password from data - it should be there if it was saved
        default_password = current_data.get(CONF_PASSWORD, "")
        if not default_password:
            # Also try alternative key names
            default_password = current_data.get("password", "")
        
        # Get update interval from options or use default
        default_update_interval = current_options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        # Ensure default is an integer
        if not isinstance(default_update_interval, int):
            try:
                default_update_interval = int(default_update_interval)
            except (ValueError, TypeError):
                default_update_interval = DEFAULT_UPDATE_INTERVAL
        
        _LOGGER.debug("OptionsFlow: Using default_update_interval=%d for schema", default_update_interval)
        
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=current_data.get(CONF_HOST, "192.168.178.1")): str,
            vol.Required(CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD, default=default_password): str,
            vol.Required(CONF_UPDATE_INTERVAL, default=default_update_interval): vol.All(
                vol.Coerce(int),
                vol.Range(min=5, max=300)
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
