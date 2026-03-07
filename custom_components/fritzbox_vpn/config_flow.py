"""Config flow for FritzBox VPN integration."""

import ipaddress
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    DATA_COORDINATOR,
    DATA_KNOWN_UIDS_KEYS,
    DEFAULT_HOST,
    DEFAULT_UPDATE_INTERVAL,
    INTEGRATION_TITLE,
    OPTIONS_ACTION_CONFIGURE,
    OPTIONS_ACTION_CLEANUP,
    OPTIONS_ACTION_REPAIR_ENTITY_IDS,
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
    password_from_sources,
)
from .coordinator import FritzBoxVPNSession, normalize_update_interval
from .fritz_config_source import get_existing_fritz_config

_LOGGER = logging.getLogger(__name__)


def _connection_uid_from_entity_unique_id(unique_id: str) -> Optional[str]:
    """Connection UID from entity unique_id; None if not our format."""
    if not unique_id or not unique_id.startswith(UNIQUE_ID_PREFIX):
        return None
    rest = unique_id[len(UNIQUE_ID_PREFIX) :]
    for suffix in UNIQUE_ID_SUFFIXES:
        if rest.endswith("_" + suffix):
            return rest[: -len(suffix) - 1]
    return None


def _resolve_current_uids(
    hass: HomeAssistant, entry_id: str
) -> Tuple[Optional[Set[str]], Optional[str]]:
    """Current VPN UIDs from coordinator.data. Returns (uids, None) or (None, error_key)."""
    if DOMAIN not in hass.data or entry_id not in hass.data[DOMAIN]:
        return (None, "integration_not_loaded")
    coordinator = hass.data[DOMAIN][entry_id].get(DATA_COORDINATOR)
    if not coordinator or not hasattr(coordinator, "data"):
        return (None, "coordinator_not_ready")
    current_uids = set(coordinator.data.keys()) if coordinator.data else set()
    return (current_uids, None)


def _get_orphaned_entity_entries(
    hass: HomeAssistant,
    entry_id: str,
    current_uids: Optional[Set[str]] = None,
) -> Tuple[Optional[List[er.RegistryEntry]], Optional[str]]:
    """Orphaned entity entries for this entry (VPN no longer present). Returns (entries, None) or (None, error_key)."""
    if current_uids is None:
        current_uids, error_key = _resolve_current_uids(hass, entry_id)
        if error_key is not None:
            return (None, error_key)
    registry = er.async_get(hass)
    to_remove = []
    for entry in er.async_entries_for_config_entry(registry, entry_id):
        uid = _connection_uid_from_entity_unique_id(entry.unique_id or "")
        if uid is not None and uid not in current_uids:
            to_remove.append(entry)
    return (to_remove, None)


def _uids_from_entries(entries: List[er.RegistryEntry]) -> Set[str]:
    """Connection UIDs from entity registry entries."""
    uids: Set[str] = set()
    for e in entries:
        uid = _connection_uid_from_entity_unique_id(e.unique_id or "")
        if uid is not None:
            uids.add(uid)
    return uids


_ENTITY_ID_OBJECT_ID_SUFFIX_RE = re.compile(r"^(.+)_(\d+)$")


def _entity_id_base(entity_id: str) -> Optional[str]:
    """Base entity_id when object_id has numeric suffix (_2, _3, …), else None."""
    if not entity_id or "." not in entity_id:
        return None
    domain, object_id = entity_id.split(".", 1)
    match = _ENTITY_ID_OBJECT_ID_SUFFIX_RE.match(object_id)
    if not match:
        return None
    return f"{domain}.{match.group(1)}"


def _get_entity_id_suffix_repairs(
    registry: er.EntityRegistry, entry_id: str
) -> List[Tuple[er.RegistryEntry, str]]:
    """(suffixed entry, base_entity_id) pairs where base exists for same config entry."""
    all_entries = er.async_entries_for_config_entry(registry, entry_id)
    by_entity_id = {e.entity_id: e for e in all_entries}
    result: List[Tuple[er.RegistryEntry, str]] = []
    for entry in all_entries:
        base = _entity_id_base(entry.entity_id)
        if not base:
            continue
        base_entry = by_entity_id.get(base)
        if not base_entry or base_entry.id == entry.id:
            continue
        result.append((entry, base))
    return result


def repair_entity_id_suffixes(
    hass: HomeAssistant, entry_id: str
) -> Tuple[int, List[str]]:
    """Remove stale base entity and assign its entity_id to suffixed entry. Returns (count, messages)."""
    registry = er.async_get(hass)
    repairs = _get_entity_id_suffix_repairs(registry, entry_id)
    messages: List[str] = []
    for suffixed_entry, base_entity_id in repairs:
        try:
            registry.async_remove(base_entity_id)
            registry.async_update_entity(suffixed_entry.entity_id, new_entity_id=base_entity_id)
            messages.append(f"{suffixed_entry.entity_id} → {base_entity_id}")
            _LOGGER.info("Repaired entity ID: %s → %s", suffixed_entry.entity_id, base_entity_id)
        except Exception as err:
            _LOGGER.warning("Failed to repair %s → %s: %s", suffixed_entry.entity_id, base_entity_id, err)
    return (len(messages), messages)


def _remove_orphaned_entities_and_clear_known_uids(
    hass: HomeAssistant,
    entry_id: str,
    entries: List[er.RegistryEntry],
    remove_from_registry: bool = True,
) -> None:
    """Clear known_uids for UIDs no longer present; optionally remove from entity/device registry."""
    if not entries:
        return

    uids_removed = _uids_from_entries(entries)

    if remove_from_registry:
        entity_registry = er.async_get(hass)
        device_ids_affected = set()
        for entry in entries:
            if entry.device_id:
                device_ids_affected.add(entry.device_id)
            entity_registry.async_remove(entry.entity_id)
            _LOGGER.info("Removed unavailable entity: %s (%s)", entry.entity_id, entry.unique_id)

        device_registry = dr.async_get(hass)
        for uid in uids_removed:
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, entry_id, uid)}
            )
            if device:
                device_registry.async_remove_device(device.id)
                _LOGGER.info(
                    "Removed unavailable device for connection UID: %s (device_id: %s)",
                    uid,
                    device.id,
                )
                device_ids_affected.discard(device.id)

        for dev_id in device_ids_affected:
            device = device_registry.async_get(dev_id)
            if not device:
                continue
            if not entity_registry.async_entries_for_device(dev_id):
                device_registry.async_remove_device(dev_id)
                _LOGGER.info(
                    "Removed empty device (no entities left): %s (device_id: %s)",
                    device.name_by_user or device.name,
                    dev_id,
                )

    if not uids_removed or entry_id not in hass.data.get(DOMAIN, {}):
        return
    store = hass.data[DOMAIN][entry_id]
    for key in DATA_KNOWN_UIDS_KEYS:
        if key in store and isinstance(store[key], set):
            store[key] -= uids_removed


def _build_configure_schema(
    current_data: Dict[str, Any], current_options: Dict[str, Any]
) -> vol.Schema:
    """Configure step schema with defaults from current config/options."""
    host_default, username_default, password_default = _credentials_defaults_from_config(current_data)
    default_update_interval = normalize_update_interval(
        current_options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )
    return vol.Schema({
        **_credentials_schema_keys(host_default, username_default, password_default),
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


def _fill_password_if_missing(
    user_input: Dict[str, Any], *sources: Optional[Mapping[str, Any]]
) -> None:
    """Set user_input password from first non-empty source if missing."""
    if user_input.get(CONF_PASSWORD):
        return
    user_input[CONF_PASSWORD] = password_from_sources(*sources)


def validate_host(host: str) -> str:
    """Validate host is a valid IP address or hostname."""
    if not host or not isinstance(host, str):
        raise vol.Invalid("Host must be a non-empty string")

    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass

    if len(host) > 253:
        raise vol.Invalid("Hostname too long (max 253 characters)")

    if not all(c.isalnum() or c in ('.', '-') for c in host):
        raise vol.Invalid("Invalid hostname format")

    if host.startswith('.') or host.endswith('.') or host.startswith('-') or host.endswith('-'):
        raise vol.Invalid("Hostname cannot start or end with dot or hyphen")

    return host


def _credentials_schema(
    host_default: str, username_default: str, password_default: str
) -> vol.Schema:
    """Credentials form (host, username, password) with given defaults."""
    return vol.Schema(_credentials_schema_keys(host_default, username_default, password_default))


def _credentials_defaults_from_config(
    config: Optional[Mapping[str, Any]],
    host_fallback: str = DEFAULT_HOST,
    extra_password_sources: Tuple[Optional[Mapping[str, Any]], ...] = (),
) -> Tuple[str, str, str]:
    """(host, username, password) for credential form from config or fallbacks."""
    if not config:
        return (host_fallback, "", "")
    host = config.get(CONF_HOST) or host_fallback
    username = config.get(CONF_USERNAME) or ""
    password = password_from_sources(config, *extra_password_sources)
    return (host, username, password)


def _credentials_schema_keys(
    host_default: str, username_default: str, password_default: str
) -> Dict[Any, Any]:
    """Vol schema keys for host, username, password."""
    return {
        vol.Required(CONF_HOST, default=host_default): vol.All(str, validate_host),
        vol.Required(CONF_USERNAME, default=username_default): str,
        vol.Required(CONF_PASSWORD, default=password_default): str,
    }


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that we can connect to the FritzBox. VPN connections are discovered during setup."""
    session = FritzBoxVPNSession(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data[CONF_USERNAME],
        password_from_sources(data),
    )

    try:
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
        self._discovered_host: Optional[str] = None
        self._existing_config: Optional[Dict[str, Any]] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        errors: Dict[str, str] = {}

        if user_input is None:
            self._existing_config = await get_existing_fritz_config(self.hass)
            if self._existing_config:
                has_host = bool(self._existing_config.get(CONF_HOST))
                has_username = bool(self._existing_config.get(CONF_USERNAME))
                has_password = bool(password_from_sources(self._existing_config))
                if has_host and has_username and has_password:
                    try:
                        info = await validate_input(self.hass, self._existing_config)
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
            schema = _credentials_schema(*_credentials_defaults_from_config(self._existing_config))
            return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

        _fill_password_if_missing(user_input, self._existing_config)
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
            host = user_input.get(CONF_HOST)
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        schema = _credentials_schema(*_credentials_defaults_from_config(user_input))
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """Handle SSDP discovery (fallback if no existing integration found)."""
        existing_config = await get_existing_fritz_config(self.hass)
        if existing_config:
            return self.async_abort(reason="already_configured")

        if not self._is_fritzbox_device(discovery_info):
            return self.async_abort(reason="not_fritzbox")

        host = self._extract_host_from_ssdp(discovery_info)
        if not host:
            return self.async_abort(reason="no_host")

        unique_id = host
        if discovery_info.ssdp_usn:
            usn_parts = discovery_info.ssdp_usn.split("::")
            if usn_parts and usn_parts[0].startswith("uuid:"):
                unique_id = usn_parts[0].replace("uuid:", "")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self._discovered_host = host
        self.context["title_placeholders"] = {"host": host}

        self._existing_config = await get_existing_fritz_config(self.hass)
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        errors: Dict[str, str] = {}
        
        if user_input is None:
            host_default, username_default, password_default = _credentials_defaults_from_config(
                self._existing_config, self._discovered_host or DEFAULT_HOST
            )
            return self.async_show_form(
                step_id="confirm",
                data_schema=_credentials_schema(host_default, username_default, password_default),
                description_placeholders={"host": host_default},
            )

        _fill_password_if_missing(user_input, self._existing_config)

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
            host = user_input.get(CONF_HOST)
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        host_default, username_default, password_default = _credentials_defaults_from_config(
            user_input, self._discovered_host or DEFAULT_HOST, (self._existing_config,)
        )
        return self.async_show_form(
            step_id="confirm",
            data_schema=_credentials_schema(host_default, username_default, password_default),
            errors=errors,
        )

    @staticmethod
    def _is_fritzbox_device(discovery_info: SsdpServiceInfo) -> bool:
        """Check if the discovered device is a FritzBox router (not a repeater)."""
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
            return False

        is_repeater = any(ind in combined for ind in REPEATER_INDICATORS)
        if is_repeater:
            return False

        has_igd = "internetgatewaydevice" in combined or "igd" in combined

        if not has_igd:
            if "fritz!box" in combined:
                return True
            return False

        return True

    @staticmethod
    def _extract_host_from_ssdp(discovery_info: SsdpServiceInfo) -> Optional[str]:
        """Extract host IP from SSDP discovery info."""
        if discovery_info.ssdp_location:
            try:
                parsed = urlparse(discovery_info.ssdp_location)
                if parsed.hostname:
                    return parsed.hostname
            except Exception:
                pass

        if hasattr(discovery_info, "ssdp_headers") and discovery_info.ssdp_headers:
            location = discovery_info.ssdp_headers.get("location")
            if location:
                try:
                    parsed = urlparse(location)
                    if parsed.hostname:
                        return parsed.hostname
                except Exception:
                    pass

        if discovery_info.ssdp_usn:
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
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for FritzBox VPN."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry

    def _get_current_entry(self) -> Optional[config_entries.ConfigEntry]:
        """Current config entry or None if removed."""
        return self.hass.config_entries.async_get_entry(self._config_entry.entry_id)

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Options menu: configure, cleanup, or repair entity ID suffixes."""
        if user_input is not None:
            if user_input.get("action") == OPTIONS_ACTION_CLEANUP:
                return await self.async_step_cleanup_confirm()
            if user_input.get("action") == OPTIONS_ACTION_REPAIR_ENTITY_IDS:
                return await self.async_step_repair_entity_ids_confirm()
            return await self.async_step_configure()
        choices = {
            OPTIONS_ACTION_CONFIGURE: "Configure (host, user, update interval)",
        }
        to_remove, error_key = _get_orphaned_entity_entries(
            self.hass, self._config_entry.entry_id
        )
        if error_key is None and to_remove:
            choices[OPTIONS_ACTION_CLEANUP] = "Remove unavailable entities"
        registry = er.async_get(self.hass)
        repairs = _get_entity_id_suffix_repairs(registry, self._config_entry.entry_id)
        if repairs:
            choices[OPTIONS_ACTION_REPAIR_ENTITY_IDS] = (
                f"Repair entity IDs ({len(repairs)} with _2, _3, … → base ID)"
            )
        schema = vol.Schema(
            {
                vol.Required("action", default=OPTIONS_ACTION_CONFIGURE): vol.In(choices),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_cleanup_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Confirm removal of entities for VPN connections no longer on the Fritz!Box."""
        config_entry = self._get_current_entry()
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

    async def async_step_repair_entity_ids_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Confirm repair of entity IDs (_2, _3, … → base ID)."""
        config_entry = self._get_current_entry()
        if not config_entry:
            return self.async_abort(reason=ERROR_KEY_CONFIG_ENTRY_NOT_FOUND)
        entry_id = config_entry.entry_id
        registry = er.async_get(self.hass)
        repairs = _get_entity_id_suffix_repairs(registry, entry_id)
        if user_input is not None and user_input.get("confirm") and repairs:
            count, messages = repair_entity_id_suffixes(self.hass, entry_id)
            if count:
                await self.hass.config_entries.async_reload(entry_id)
            return self.async_create_entry(title="", data=config_entry.options or {})
        if not repairs:
            return self.async_create_entry(title="", data=config_entry.options or {})
        schema = vol.Schema({vol.Required("confirm", default=False): bool})
        return self.async_show_form(
            step_id="repair_entity_ids_confirm",
            data_schema=schema,
        )

    async def async_step_configure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        errors: Dict[str, str] = {}
        config_entry = self._get_current_entry()
        if not config_entry:
            return self.async_abort(reason=ERROR_KEY_CONFIG_ENTRY_NOT_FOUND)

        if user_input is not None:
            _fill_password_if_missing(user_input, config_entry.data or {})

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
                config_data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                update_interval = normalize_update_interval(
                    user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                )
                options_data = {CONF_UPDATE_INTERVAL: update_interval}

                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data=config_data,
                    options=options_data,
                )

                result = self.async_create_entry(title="", data=options_data)
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                return result

        current_data = config_entry.data or {}
        current_options = config_entry.options or {}
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
