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

        # Try to get config from existing FritzBox integration
        if not user_input:
            self._existing_config = await self._get_existing_fritz_config()
            if self._existing_config:
                _LOGGER.info("Found existing FritzBox integration, using its configuration")
                # Pre-fill with existing config
                schema = vol.Schema({
                    vol.Required(CONF_HOST, default=self._existing_config.get(CONF_HOST, "192.168.178.1")): str,
                    vol.Required(CONF_USERNAME, default=self._existing_config.get(CONF_USERNAME, "")): str,
                    vol.Required(CONF_PASSWORD, default=""): str,  # Don't pre-fill password for security
                })
            else:
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
        """Handle SSDP discovery."""
        _LOGGER.debug("SSDP discovery: %s", discovery_info)
        
        # Check if it's a FritzBox device
        if not self._is_fritzbox_device(discovery_info):
            return self.async_abort(reason="not_fritzbox")
        
        # Extract host from SSDP location
        host = self._extract_host_from_ssdp(discovery_info)
        if not host:
            return self.async_abort(reason="no_host")
        
        # Check if already configured
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()
        
        self._discovered_host = host
        self.context["title_placeholders"] = {"host": host}
        
        # Try to get config from existing FritzBox integration
        self._existing_config = await self._get_existing_fritz_config()
        
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle discovery confirmation."""
        errors: Dict[str, str] = {}
        
        if user_input is None:
            # Pre-fill with discovered host and existing config if available
            default_host = self._discovered_host or "192.168.178.1"
            default_username = self._existing_config.get(CONF_USERNAME, "") if self._existing_config else ""
            
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
        """Check if the discovered device is a FritzBox."""
        # Check for FritzBox identifiers in SSDP
        st = discovery_info.ssdp_st or ""
        usn = discovery_info.ssdp_usn or ""
        server = discovery_info.ssdp_server or ""
        
        # FritzBox devices typically have these identifiers
        fritzbox_indicators = [
            "fritz.box",
            "fritzbox",
            "fritz!box",
            "avm",
            "FRITZ!Box",
        ]
        
        combined = f"{st} {usn} {server}".lower()
        return any(indicator.lower() in combined for indicator in fritzbox_indicators)

    @staticmethod
    def _extract_host_from_ssdp(discovery_info: ssdp.SsdpServiceInfo) -> Optional[str]:
        """Extract host IP from SSDP discovery info."""
        # Try to get host from location URL
        if discovery_info.ssdp_location:
            try:
                parsed = urlparse(discovery_info.ssdp_location)
                return parsed.hostname
            except Exception:
                pass
        
        # Try to get from headers
        if hasattr(discovery_info, "ssdp_headers") and discovery_info.ssdp_headers:
            location = discovery_info.ssdp_headers.get("location")
            if location:
                try:
                    parsed = urlparse(location)
                    return parsed.hostname
                except Exception:
                    pass
        
        return None

    async def _get_existing_fritz_config(self) -> Optional[Dict[str, Any]]:
        """Get configuration from existing FritzBox integration if available."""
        try:
            # Check for official FritzBox integration (domain: "fritz")
            fritz_entries = [
                entry
                for entry in self.hass.config_entries.async_entries("fritz")
                if entry.state in (config_entries.ConfigEntryState.LOADED, config_entries.ConfigEntryState.NOT_LOADED)
            ]
            
            if fritz_entries:
                # Use the first available FritzBox entry
                entry = fritz_entries[0]
                config_data = entry.data
                
                # Extract relevant config - try different possible key names
                host = config_data.get(CONF_HOST) or config_data.get("host") or config_data.get("hosts", [None])[0] if isinstance(config_data.get("hosts"), list) else None
                username = config_data.get(CONF_USERNAME) or config_data.get("username")
                password = config_data.get(CONF_PASSWORD) or config_data.get("password")
                
                if host:
                    return {
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    }
        except Exception as err:
            _LOGGER.debug("Could not get existing FritzBox config: %s", err)
        
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

