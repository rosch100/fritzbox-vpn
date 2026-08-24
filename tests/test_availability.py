"""Tests for availability grace logic."""

from datetime import UTC, datetime, timedelta

from custom_components.fritzbox_vpn.availability import (
    entities_trusted,
    normalize_availability_mode,
    resolve_availability_mode,
    stale_grace_seconds,
)
from custom_components.fritzbox_vpn.const import (
    AVAILABILITY_MODE_GRACEFUL,
    AVAILABILITY_MODE_PERSISTENT,
    AVAILABILITY_MODE_STRICT,
    CONF_AVAILABILITY_MODE,
    DEFAULT_AVAILABILITY_MODE,
)


def test_normalize_availability_mode_defaults() -> None:
    """Unknown values fall back to graceful default."""
    assert normalize_availability_mode(None) == DEFAULT_AVAILABILITY_MODE
    assert normalize_availability_mode("invalid") == DEFAULT_AVAILABILITY_MODE
    assert normalize_availability_mode(AVAILABILITY_MODE_STRICT) == AVAILABILITY_MODE_STRICT


def test_resolve_availability_mode_precedence() -> None:
    """Options override config for availability mode."""
    assert (
        resolve_availability_mode(
            {CONF_AVAILABILITY_MODE: AVAILABILITY_MODE_STRICT},
            {CONF_AVAILABILITY_MODE: AVAILABILITY_MODE_PERSISTENT},
        )
        == AVAILABILITY_MODE_PERSISTENT
    )
    assert (
        resolve_availability_mode({CONF_AVAILABILITY_MODE: AVAILABILITY_MODE_STRICT}, {})
        == AVAILABILITY_MODE_STRICT
    )


def test_stale_grace_seconds() -> None:
    """Grace period scales with update interval."""
    assert stale_grace_seconds(30) == 60
    assert stale_grace_seconds(120) == 240


def test_entities_trusted_strict_mode() -> None:
    """Strict mode requires last_update_success."""
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    last_ok = now - timedelta(seconds=10)
    assert entities_trusted(
        mode=AVAILABILITY_MODE_STRICT,
        last_update_success=True,
        has_data=True,
        consecutive_failures=0,
        last_successful_poll=last_ok,
        update_interval_seconds=30,
        reauth_scheduled=False,
        now=now,
    )
    assert not entities_trusted(
        mode=AVAILABILITY_MODE_STRICT,
        last_update_success=False,
        has_data=True,
        consecutive_failures=1,
        last_successful_poll=last_ok,
        update_interval_seconds=30,
        reauth_scheduled=False,
        now=now,
    )


def test_entities_trusted_graceful_within_grace() -> None:
    """Graceful mode keeps entities trusted during short outages."""
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    last_ok = now - timedelta(seconds=30)
    assert entities_trusted(
        mode=AVAILABILITY_MODE_GRACEFUL,
        last_update_success=False,
        has_data=True,
        consecutive_failures=1,
        last_successful_poll=last_ok,
        update_interval_seconds=30,
        reauth_scheduled=False,
        now=now,
    )


def test_entities_trusted_graceful_after_grace_or_failures() -> None:
    """Graceful mode becomes untrusted after grace or failure streak."""
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    last_ok = now - timedelta(seconds=120)
    assert not entities_trusted(
        mode=AVAILABILITY_MODE_GRACEFUL,
        last_update_success=False,
        has_data=True,
        consecutive_failures=1,
        last_successful_poll=last_ok,
        update_interval_seconds=30,
        reauth_scheduled=False,
        now=now,
    )
    recent = now - timedelta(seconds=10)
    assert not entities_trusted(
        mode=AVAILABILITY_MODE_GRACEFUL,
        last_update_success=False,
        has_data=True,
        consecutive_failures=2,
        last_successful_poll=recent,
        update_interval_seconds=30,
        reauth_scheduled=False,
        now=now,
    )


def test_entities_trusted_persistent_mode() -> None:
    """Persistent mode keeps stale data available until auth failure."""
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    last_ok = now - timedelta(hours=2)
    assert entities_trusted(
        mode=AVAILABILITY_MODE_PERSISTENT,
        last_update_success=False,
        has_data=True,
        consecutive_failures=5,
        last_successful_poll=last_ok,
        update_interval_seconds=30,
        reauth_scheduled=False,
        now=now,
    )
    assert not entities_trusted(
        mode=AVAILABILITY_MODE_PERSISTENT,
        last_update_success=False,
        has_data=True,
        consecutive_failures=0,
        last_successful_poll=last_ok,
        update_interval_seconds=30,
        reauth_scheduled=True,
        now=now,
    )


def test_entities_trusted_requires_data() -> None:
    """No data means entities are never trusted."""
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    assert not entities_trusted(
        mode=AVAILABILITY_MODE_PERSISTENT,
        last_update_success=False,
        has_data=False,
        consecutive_failures=0,
        last_successful_poll=now,
        update_interval_seconds=30,
        reauth_scheduled=False,
        now=now,
    )
