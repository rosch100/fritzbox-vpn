"""Config flow for FritzBox VPN integration."""

import ipaddress
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    DATA_COORDINATOR,
    DATA_KNOWN_UIDS_SWITCH,
    DATA_KNOWN_UIDS_SENSOR,
    DATA_KNOWN_UIDS_BINARY_SENSOR,
    DEFAULT_HOST,
    DEFAULT_UPDATE_INTERVAL,
    INTEGRATION_TITLE,
    OPTIONS_ACTION_CONFIGURE,
    OPTIONS_ACTION_CLEANUP,
    UNIQUE_ID_PREFIX,
    UNIQUE_ID_SUFFIXES,
    UPDATE_INTERVAL_MIN,
    UPDATE_INTERVAL_MAX,
    REPEATER_INDICATORS,
    FRITZBOX_SSDP_INDICATORS,
    ERROR_INDICATOR_AUTH,
    ERROR_INDICATOR_CONNECT,
    ERROR_KEY_UNKNOWN,
    ERROR_KEY_CANNOT_CONNECT,
    ERROR_KEY_INVALID_AUTH,
    ERROR_KEY_CONFIG_ENTRY_NOT_FOUND,
    mask_config_for_log,
)
from .coordinator import FritzBoxVPNSession, normalize_update_interval
from .fritz_config_source import get_existing_fritz_config

_LOGGER = logging.getLogger(__name__)


def _connection_uid_from_entity_unique_id(unique_id: str) -> Optional[str]:
    """Extract connection_uid from an entity unique_id. Returns None if not our format."""
    if not unique_id or not unique_id.startswith(UNIQUE_ID_PREFIX):
        return None
    rest = unique_id[len(UNIQUE_ID_PREFIX) :]
    for suffix in UNIQUE_ID_SUFFIXES:
        if rest.endswith("_" + suffix):
            return rest[: -len(suffix) - 1]
    return None


def _get_orphaned_entity_entries(
    hass: HomeAssistant, entry_id: str
) -> Tuple[Optional[List[er.RegistryEntry]], Optional[str]]:
    """Return entity registry entries for this config entry whose VPN connection is no longer present.
    Returns (list of entries to remove, None) on success, or (None, error_key) if integration/coordinator not ready.
    """
    if DOMAIN not in hass.data or entry_id not in hass.data[DOMAIN]:
        return (None, "integration_not_loaded")
    coordinator = hass.data[DOMAIN][entry_id].get(DATA_COORDINATOR)
    if not coordinator or not hasattr(coordinator, "data"):
        return (None, "coordinator_not_ready")
    current_uids = set(coordinator.data.keys()) if coordinator.data else set()
    registry = er.async_get(hass)
    to_remove = []
    for entry in er.async_entries_for_config_entry(registry, entry_id):
        uid = _connection_uid_from_entity_unique_id(entry.unique_id or "")
        if uid is not None and uid not in current_uids:
            to_remove.append(entry)
    return (to_remove, None)


def _remove_orphaned_entities_and_clear_known_uids(
    hass: HomeAssistant, entry_id: str, entries: List[er.RegistryEntry]
) -> None:
    """Remove given entities from the registry and remove their UIDs from known_uids sets."""
    if not entries:
        return
    registry = er.async_get(hass)
    for entry in entries:
        registry.async_remove(entry.entity_id)
        _LOGGER.info("Removed unavailable entity: %s (%s)", entry.entity_id, entry.unique_id)
    uids_removed = set()
    for e in entries:
        uid = _connection_uid_from_entity_unique_id(e.unique_id or "")
        if uid is not None:
            uids_removed.add(uid)
    if not uids_removed or entry_id not in hass.data.get(DOMAIN, {}):
        return
    store = hass.data[DOMAIN][entry_id]
    for key in (DATA_KNOWN_UIDS_SWITCH, DATA_KNOWN_UIDS_SENSOR, DATA_KNOWN_UIDS_BINARY_SENSOR):
        if key in store and isinstance(store[key], set):
            store[key] -= uids_removed


def _build_configure_schema(
    current_data: Dict[str, Any], current_options: Dict[str, Any]
) -> vol.Schema:
    """Build the configure step schema with defaults from current config/options."""
    default_password = current_data.get(CONF_PASSWORD, "") or current_data.get("password", "")
    default_update_interval = normalize_update_interval(
        current_options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )
    return vol.Schema({
        vol.Required(CONF_HOST, default=current_data.get(CONF_HOST) or DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=current_data.get(CONF_USERNAME) or ""): str,
        vol.Required(CONF_PASSWORD, default=default_password or ""): str,
        vol.Required(CONF_UPDATE_INTERVAL, default=default_update_interval): vol.All(
            vol.Coerce(int),
            vol.Range(min=UPDATE_INTERVAL_MIN, max=UPDATE_INTERVAL_MAX),
        ),
    })


def _validation_error_to_error_key(error_msg: str) -> str:
    """Map validation exception message to config flow error key."""
    msg_lower = error_msg.lower()
    if any(ind in msg_lower for ind in ERROR_INDICATOR_AUTH):
        return ERROR_KEY_INVALID_AUTH
    if any(ind in msg_lower for ind in ERROR_INDICATOR_CONNECT):
        return ERROR_KEY_CANNOT_CONNECT
    return ERROR_KEY_UNKNOWN


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
        vol.Required(CONF_HOST, default=DEFAULT_HOST): vol.All(str, validate_host),
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

        return {"title": f"{INTEGRATION_TITLE} ({data[CONF_HOST]})"}
    except Exception as err:
        error_msg = str(err)
        if any(ind in error_msg.lower() for ind in ERROR_INDICATOR_AUTH):
            _LOGGER.warning(
                "Authentication failed. Invalid SID can be caused by: (1) Incorrect username or password, or "
                "(2) TR-064 not being enabled. Please check credentials first, then verify TR-064 is enabled "
                "at: Home Network > Network > Network settings > Access Settings in the Home Network. "
                "Note: UPnP is only needed for automatic discovery, not for API access. "
                "Error: %s", error_msg
            )
            raise InvalidAuth from err
        _LOGGER.exception("Error validating input: %s", err)
        if any(ind in error_msg.lower() for ind in ERROR_INDICATOR_CONNECT):
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
        
        _LOGGER.debug("async_step_user called with user_input=%s", "provided" if user_input else "None (first call)")

        # Try to get config from existing FritzBox integration first
        # SSDP is only used as fallback if no existing integration is found
        if not user_input:
            _LOGGER.debug("No user_input provided, attempting autoconfiguration...")
            self._existing_config = await get_existing_fritz_config(self.hass)
            _LOGGER.debug("Autoconfiguration result: %s", "found config" if self._existing_config else "no config found")
            if self._existing_config:
                _LOGGER.debug("Found existing FritzBox Tools, using its configuration (SSDP will be skipped)")
                
                # Check if we have complete configuration (host, username, password)
                has_host = bool(self._existing_config.get(CONF_HOST))
                has_username = bool(self._existing_config.get(CONF_USERNAME))
                has_password = bool(self._existing_config.get(CONF_PASSWORD))
                
                # If we have all required credentials, try to validate the connection
                if has_host and has_username and has_password:
                    _LOGGER.debug("Complete autoconfiguration found (host, username, password). Testing connection...")
                    try:
                        info = await validate_input(self.hass, self._existing_config)
                        # Connection successful - create entry directly without showing form
                        _LOGGER.info("Autoconfiguration successful, integration entry created")
                        _LOGGER.debug("Saving config with keys: %s", list(self._existing_config.keys()))
                        _LOGGER.debug("Password present in config to save: %s", bool(self._existing_config.get(CONF_PASSWORD)))
                        
                        # Set unique_id to prevent duplicate entries
                        host = self._existing_config.get(CONF_HOST)
                        await self.async_set_unique_id(host)
                        self._abort_if_unique_id_configured()
                        
                        return self.async_create_entry(title=info["title"], data=self._existing_config)
                    except CannotConnect:
                        _LOGGER.warning("Autoconfiguration connection test failed: %s", ERROR_KEY_CANNOT_CONNECT)
                        errors["base"] = ERROR_KEY_CANNOT_CONNECT
                    except InvalidAuth:
                        _LOGGER.warning("Autoconfiguration connection test failed: %s", ERROR_KEY_INVALID_AUTH)
                        errors["base"] = ERROR_KEY_INVALID_AUTH
                    except Exception as err:
                        _LOGGER.warning("Autoconfiguration connection test failed: %s", err)
                        errors["base"] = ERROR_KEY_UNKNOWN
                    # If validation failed, fall through to show form with pre-filled values
                
                # Pre-fill with existing config (either incomplete or validation failed)
                default_password = self._existing_config.get(CONF_PASSWORD, "") if self._existing_config.get(CONF_PASSWORD) else ""
                schema = vol.Schema({
                    vol.Required(CONF_HOST, default=self._existing_config.get(CONF_HOST, DEFAULT_HOST)): vol.All(str, validate_host),
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
                errors["base"] = ERROR_KEY_CANNOT_CONNECT
            except InvalidAuth:
                errors["base"] = ERROR_KEY_INVALID_AUTH
            except Exception as err:
                error_msg = str(err)
                _LOGGER.exception("Unexpected exception during validation: %s", error_msg)
                errors["base"] = _validation_error_to_error_key(error_msg)
                if errors["base"] == ERROR_KEY_UNKNOWN:
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
        existing_config = await get_existing_fritz_config(self.hass)
        if existing_config:
            _LOGGER.debug("Existing FritzBox Tools found, aborting SSDP discovery")
            return self.async_abort(reason="already_configured")
        
        # Check if it's a FritzBox device (and specifically a router, not a repeater)
        # This check MUST happen before extracting host to avoid showing repeater IP
        if not self._is_fritzbox_device(discovery_info):
            _LOGGER.debug("SSDP discovery: Rejected device (not a FritzBox router)")
            return self.async_abort(reason="not_fritzbox")
        
        # Extract host from SSDP location
        host = self._extract_host_from_ssdp(discovery_info)
        if not host:
            _LOGGER.warning("SSDP discovery: Could not extract host from discovery info")
            return self.async_abort(reason="no_host")
        
        _LOGGER.debug("SSDP discovery: Found FritzBox router at %s", host)
        
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
        self._existing_config = await get_existing_fritz_config(self.hass)
        if self._existing_config:
            _LOGGER.debug("Existing FritzBox Tools found during SSDP, using its config instead of discovered host")
        
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
                default_host = self._existing_config.get(CONF_HOST, self._discovered_host or DEFAULT_HOST)
                default_username = self._existing_config.get(CONF_USERNAME, "")
                default_password = self._existing_config.get(CONF_PASSWORD, "") if self._existing_config.get(CONF_PASSWORD) else ""
                _LOGGER.debug("Using existing config for confirm step: host=%s, username=%s, password=%s",
                             default_host, default_username, "***" if default_password else "not set")
            else:
                default_host = self._discovered_host or DEFAULT_HOST
                default_username = ""
                default_password = ""
            
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST, default=default_host): vol.All(str, validate_host),
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
            errors["base"] = ERROR_KEY_CANNOT_CONNECT
        except InvalidAuth:
            errors["base"] = ERROR_KEY_INVALID_AUTH
        except Exception as err:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = _validation_error_to_error_key(str(err))
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
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, self._discovered_host or DEFAULT_HOST)): vol.All(str, validate_host),
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
        
        combined = f"{st} {usn} {server} {location}".lower()
        if hasattr(discovery_info, "ssdp_headers") and discovery_info.ssdp_headers:
            headers_str = " ".join(str(v) for v in discovery_info.ssdp_headers.values()).lower()
            combined += f" {headers_str}"
        is_fritzbox = any(ind in combined for ind in FRITZBOX_SSDP_INDICATORS)
        
        if not is_fritzbox:
            _LOGGER.debug("Device is not a FritzBox")
            return False
        
        is_repeater = any(ind in combined for ind in REPEATER_INDICATORS)
        if is_repeater:
            _LOGGER.debug("Rejecting FritzBox Repeater device (only routers accepted): %s", server)
            return False
        
        # Additional check: Only accept InternetGatewayDevice (routers)
        has_igd = "internetgatewaydevice" in combined or "igd" in combined
        
        if not has_igd:
            _LOGGER.debug("Device does not appear to be a router (no InternetGatewayDevice): %s", st)
            if "fritz!box" in combined:
                _LOGGER.debug("Accepting as FritzBox router (no IGD but FRITZ!Box): %s", server)
                return True
            _LOGGER.debug("Rejecting: No IGD and not clearly a router")
            return False

        _LOGGER.debug("Accepting FritzBox router device: %s", server)
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
        """Show menu: Configure or Remove unavailable entities."""
        if user_input is not None:
            if user_input.get("action") == OPTIONS_ACTION_CLEANUP:
                return await self.async_step_cleanup_confirm()
            return await self.async_step_configure()
        schema = vol.Schema(
            {
                vol.Required("action", default=OPTIONS_ACTION_CONFIGURE): vol.In(
                    {
                        OPTIONS_ACTION_CONFIGURE: "Configure (host, user, update interval)",
                        OPTIONS_ACTION_CLEANUP: "Remove unavailable entities",
                    }
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_cleanup_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Confirm removal of entities whose VPN connection is no longer on the Fritz!Box."""
        config_entry = self.hass.config_entries.async_get_entry(self._config_entry.entry_id)
        if not config_entry:
            return self.async_abort(reason=ERROR_KEY_CONFIG_ENTRY_NOT_FOUND)
        entry_id = config_entry.entry_id
        to_remove, error_key = _get_orphaned_entity_entries(self.hass, entry_id)
        if error_key is not None:
            return self.async_show_form(
                step_id="cleanup_confirm",
                data_schema=vol.Schema({}),
                errors={"base": error_key},
            )
        if user_input is not None and user_input.get("confirm") and to_remove:
            _remove_orphaned_entities_and_clear_known_uids(self.hass, entry_id, to_remove)
            await self.hass.config_entries.async_reload(entry_id)
        if user_input is not None or not to_remove:
            return self.async_create_entry(
                title="",
                data=config_entry.options or {},
            )
        schema = vol.Schema({vol.Required("confirm", default=False): bool})
        return self.async_show_form(
            step_id="cleanup_confirm",
            data_schema=schema,
        )

    async def async_step_configure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options (host, user, update interval)."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            # Get the current config entry to access its data
            config_entry = self.hass.config_entries.async_get_entry(self._config_entry.entry_id)
            if not config_entry:
                errors["base"] = ERROR_KEY_CONFIG_ENTRY_NOT_FOUND
                return self.async_show_form(step_id="configure", data_schema=vol.Schema({}), errors=errors)
            
            # If password is empty, keep the existing password
            if not user_input.get(CONF_PASSWORD):
                user_input[CONF_PASSWORD] = (config_entry.data or {}).get(CONF_PASSWORD, "")
            
            # Validate the new configuration
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = ERROR_KEY_CANNOT_CONNECT
            except InvalidAuth:
                errors["base"] = ERROR_KEY_INVALID_AUTH
            except Exception as err:
                error_msg = str(err)
                _LOGGER.exception("Unexpected exception during validation: %s", error_msg)
                errors["base"] = _validation_error_to_error_key(error_msg)
                if errors["base"] == ERROR_KEY_UNKNOWN:
                    _LOGGER.error("Unknown error details: %s", error_msg)
            else:
                # Separate core config (data) from options
                config_data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                # Ensure update interval is stored as integer (SSOT: coordinator.normalize_update_interval)
                update_interval = normalize_update_interval(
                    user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                )
                _LOGGER.debug("OptionsFlow: Saving update_interval: %d seconds", update_interval)
                options_data = {
                    CONF_UPDATE_INTERVAL: update_interval,
                }
                
                _LOGGER.debug("OptionsFlow: Updating config entry with data=%s, options=%s",
                             mask_config_for_log(config_data), options_data)
                
                # Update the config entry with new data and options
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data=config_data,
                    options=options_data,
                )
                
                # Verify the update was successful
                updated_entry = self.hass.config_entries.async_get_entry(config_entry.entry_id)
                if updated_entry:
                    _LOGGER.debug("OptionsFlow: Config entry updated. New options: %s", updated_entry.options)
                    _LOGGER.debug("OptionsFlow: Config entry data keys: %s", list(updated_entry.data.keys()))
                else:
                    _LOGGER.error("OptionsFlow: Failed to retrieve updated config entry")
                
                # Return the options data so they are properly saved
                # Note: async_create_entry must be called before reload to ensure options are saved
                result = self.async_create_entry(title="", data=options_data)
                
                # Reload the integration to apply the new configuration
                _LOGGER.debug("OptionsFlow: Reloading integration to apply new configuration")
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                _LOGGER.debug("OptionsFlow: Integration reloaded successfully")
                
                return result

        # Get the current config entry to access its data
        config_entry = self.hass.config_entries.async_get_entry(self._config_entry.entry_id)
        if not config_entry:
            errors["base"] = ERROR_KEY_CONFIG_ENTRY_NOT_FOUND
            return self.async_show_form(step_id="configure", data_schema=vol.Schema({}), errors=errors)
        
        # Pre-fill with current values
        current_data = config_entry.data or {}
        current_options = config_entry.options or {}
        _LOGGER.debug(
            "OptionsFlow: Current config_entry.data keys: %s, has password: %s",
            list(current_data.keys()),
            bool(current_data.get(CONF_PASSWORD)),
        )
        schema = _build_configure_schema(current_data, current_options)
        return self.async_show_form(
            step_id="configure",
            data_schema=schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
