"""Source for existing FritzBox/AVM integration config.

Used by the config flow to reuse host/username/password from an existing
Fritz or FritzBox Tools integration. Repeaters are filtered out (no WireGuard).
"""

import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD

from .const import (
    FRITZ_INTEGRATION_DOMAINS,
    REPEATER_INDICATORS,
    mask_config_for_log,
)

_LOGGER = logging.getLogger(__name__)


async def get_existing_fritz_config(hass: HomeAssistant) -> Optional[Dict[str, Any]]:
    """Get configuration from existing FritzBox/AVM integration if available.

    Checks for:
    - Official FritzBox integration (domain: "fritz")
    - FritzBox Tools integration (domain: "fritzbox_tools" or "fritzbox")

    Repeaters are excluded (no WireGuard). Returns dict with CONF_HOST, CONF_USERNAME,
    CONF_PASSWORD or None if no usable config found.
    """
    _LOGGER.debug("Checking for existing FritzBox Tools...")
    all_domains = set()
    fritz_related_entries = []
    for entry in hass.config_entries.async_entries():
        all_domains.add(entry.domain)
        if "fritz" in entry.domain.lower() or "avm" in entry.domain.lower():
            fritz_related_entries.append(entry)
            _LOGGER.debug(
                "Found potential FritzBox integration: domain='%s', title='%s', entry_id='%s', state='%s'",
                entry.domain, entry.title, entry.entry_id, entry.state,
            )
    _LOGGER.debug("All available domains: %s", sorted(all_domains))
    _LOGGER.debug("Found %d FritzBox-related entries across all domains", len(fritz_related_entries))

    found_domains = set(entry.domain for entry in fritz_related_entries)
    prioritized_domains = [d for d in FRITZ_INTEGRATION_DOMAINS if d in found_domains]
    prioritized_domains.extend([d for d in FRITZ_INTEGRATION_DOMAINS if d not in found_domains])
    _LOGGER.debug("Checking domains in order: %s (found entries in: %s)", prioritized_domains, list(found_domains))

    excluded_states = (
        config_entries.ConfigEntryState.FAILED_UNLOAD,
        config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )

    for domain in prioritized_domains:
        try:
            all_entries = list(hass.config_entries.async_entries(domain))
            _LOGGER.debug("Domain '%s': Found %d total entries", domain, len(all_entries))
            for entry in all_entries:
                _LOGGER.debug("  Entry '%s' (entry_id: %s) has state: %s", entry.title, entry.entry_id, entry.state)

            fritz_entries = [
                entry
                for entry in all_entries
                if entry.state not in excluded_states
            ]
            _LOGGER.debug(
                "Domain '%s': Found %d entries after filtering by state (excluded states: %s)",
                domain, len(fritz_entries), [s.name for s in excluded_states],
            )
            if len(fritz_entries) < len(all_entries):
                excluded_entries = [e for e in all_entries if e.state in excluded_states]
                _LOGGER.debug(
                    "Domain '%s': Excluded %d entries due to state: %s",
                    domain, len(excluded_entries),
                    [(e.title, e.state.name) for e in excluded_entries],
                )

            if not fritz_entries:
                continue

            router_entries = [
                entry
                for entry in fritz_entries
                if not any(ind in (entry.title or "").lower() for ind in REPEATER_INDICATORS)
            ]
            if not router_entries:
                _LOGGER.debug(
                    "Domain '%s': Nur Repeater gefunden (%d Einträge), überspringe – keine Konfiguration von Repeatern",
                    domain, len(fritz_entries),
                )
                continue
            entries_to_use = router_entries
            _LOGGER.debug(
                "Domain '%s': %d Repeater ausgeblendet, nutze %d Router-Eintrag/Einträge",
                domain, len(fritz_entries) - len(router_entries), len(router_entries),
            )

            entries_with_creds = []
            for entry in entries_to_use:
                config_data = entry.data or {}
                options_data = entry.options or {}
                _LOGGER.debug("Checking entry '%s' (entry_id: %s) for credentials", entry.title, entry.entry_id)
                _LOGGER.debug("  Config data keys: %s", list(config_data.keys()))
                _LOGGER.debug("  Options data keys: %s", list(options_data.keys()))
                has_username = bool(
                    config_data.get(CONF_USERNAME)
                    or config_data.get("username")
                    or config_data.get("user")
                    or options_data.get(CONF_USERNAME)
                    or options_data.get("username")
                    or options_data.get("user")
                )
                has_password = bool(
                    config_data.get(CONF_PASSWORD)
                    or config_data.get("password")
                    or config_data.get("pass")
                    or options_data.get(CONF_PASSWORD)
                    or options_data.get("password")
                )
                _LOGGER.debug("  Has username: %s, Has password: %s", has_username, has_password)
                if not has_username and not has_password:
                    _LOGGER.debug(
                        "  Entry '%s' has no credentials (config keys: %s, options keys: %s)",
                        entry.title, list(config_data.keys()), list(options_data.keys()),
                    )
                if has_username or has_password:
                    entries_with_creds.append(entry)
                    _LOGGER.debug("  Entry '%s' has credentials (username: %s, password: %s)",
                                 entry.title, has_username, has_password)

            entry = entries_with_creds[0] if entries_with_creds else entries_to_use[0]
            _LOGGER.debug("Found existing FritzBox Tools '%s' with entry_id: %s", domain, entry.entry_id)
            _LOGGER.debug("Entry title: %s", entry.title)
            _LOGGER.debug("Entry source: %s", getattr(entry, "source", "unknown"))
            _LOGGER.debug("Entry unique_id: %s", getattr(entry, "unique_id", "unknown"))

            config_data = entry.data or {}
            _LOGGER.debug("Config data keys: %s", list(config_data.keys()))
            _LOGGER.debug("Config data (masked): %s", mask_config_for_log(config_data))
            options_data = entry.options or {}
            _LOGGER.debug("Options data keys: %s", list(options_data.keys()))
            if options_data:
                _LOGGER.debug("Options data (masked): %s", mask_config_for_log(options_data))

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
            if not host and "data" in config_data:
                nested_data = config_data.get("data", {})
                host = host or nested_data.get("host") or nested_data.get(CONF_HOST)
                username = username or nested_data.get("username") or nested_data.get(CONF_USERNAME)
                password = password or nested_data.get("password") or nested_data.get(CONF_PASSWORD)

            if host:
                _LOGGER.debug(
                    "Using config from existing FritzBox Tools '%s': host=%s, username=%s, password=%s",
                    domain, host, username if username else "not found", "***" if password else "not found",
                )
                return {
                    CONF_HOST: host,
                    CONF_USERNAME: username or "",
                    CONF_PASSWORD: password or "",
                }
            _LOGGER.warning(
                "✗ Found FritzBox integration '%s' but could not extract host. Config keys: %s, Options keys: %s",
                domain, list(config_data.keys()), list(options_data.keys()),
            )
            _LOGGER.debug("Full config_data: %s", mask_config_for_log(config_data))
            if options_data:
                _LOGGER.debug("Full options_data: %s", mask_config_for_log(options_data))

        except KeyError:
            _LOGGER.debug("Domain '%s' not found (KeyError), trying next", domain)
            continue
        except Exception as err:
            _LOGGER.warning("Error checking domain '%s': %s", domain, err)
            _LOGGER.exception("Full exception details:")
            continue

    _LOGGER.warning("No existing FritzBox Tools found with usable configuration")
    _LOGGER.debug("Searched domains: %s", FRITZ_INTEGRATION_DOMAINS)
    _LOGGER.debug("Available domains in system: %s", sorted(all_domains))
    return None
