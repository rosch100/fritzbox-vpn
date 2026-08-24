"""Availability grace logic for FritzBox VPN entities."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    AVAILABILITY_GRACE_INTERVAL_FACTOR,
    AVAILABILITY_GRACE_MAX_FAILURES,
    AVAILABILITY_GRACE_MIN_SECONDS,
    AVAILABILITY_MODE_PERSISTENT,
    AVAILABILITY_MODE_STRICT,
    AVAILABILITY_MODES,
    CONF_AVAILABILITY_MODE,
    DEFAULT_AVAILABILITY_MODE,
)

_LOGGER = logging.getLogger(__name__)


def normalize_availability_mode(value: Any) -> str:
    """Return a valid availability mode string."""
    if isinstance(value, str) and value in AVAILABILITY_MODES:
        return value
    if value is not None:
        _LOGGER.warning(
            "Invalid availability_mode value %r, using default %s",
            value,
            DEFAULT_AVAILABILITY_MODE,
        )
    return DEFAULT_AVAILABILITY_MODE


def resolve_availability_mode(
    config: Mapping[str, Any],
    options: Mapping[str, Any] | None,
) -> str:
    """Resolve availability mode from options, then config, then default."""
    options_dict = options or {}
    value = (
        options_dict.get(CONF_AVAILABILITY_MODE)
        or config.get(CONF_AVAILABILITY_MODE)
        or DEFAULT_AVAILABILITY_MODE
    )
    return normalize_availability_mode(value)


def stale_grace_seconds(update_interval_seconds: int) -> int:
    """Grace period before graceful mode marks entities unavailable."""
    return max(
        AVAILABILITY_GRACE_MIN_SECONDS,
        AVAILABILITY_GRACE_INTERVAL_FACTOR * update_interval_seconds,
    )


def entities_trusted(
    *,
    mode: str,
    last_update_success: bool,
    has_data: bool,
    consecutive_failures: int,
    last_successful_poll: datetime | None,
    update_interval_seconds: int,
    reauth_scheduled: bool,
    now: datetime | None = None,
) -> bool:
    """True when coordinator data may still be shown as available entities."""
    if reauth_scheduled:
        return False
    if last_update_success:
        return True
    if not has_data:
        return False
    if mode == AVAILABILITY_MODE_STRICT:
        return False
    if mode == AVAILABILITY_MODE_PERSISTENT:
        return True
    if consecutive_failures >= AVAILABILITY_GRACE_MAX_FAILURES:
        return False
    if last_successful_poll is None:
        return False
    current = now if now is not None else dt_util.utcnow()
    elapsed = (current - last_successful_poll).total_seconds()
    return elapsed <= stale_grace_seconds(update_interval_seconds)
