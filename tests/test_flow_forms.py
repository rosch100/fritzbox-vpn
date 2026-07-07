"""Tests for flow_forms schemas and validation helpers."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from custom_components.fritzbox_vpn.const import (
    CONF_UPDATE_INTERVAL,
    ERROR_KEY_CANNOT_CONNECT,
    ERROR_KEY_INVALID_AUTH,
    ERROR_KEY_INVALID_HOST,
    ERROR_KEY_UNKNOWN,
)
from custom_components.fritzbox_vpn.flow_forms import (
    CannotConnect,
    InvalidAuth,
    configure_schema,
    configure_schema_for_resubmit,
    confirm_checkbox_schema,
    confirm_schema,
    credentials_defaults,
    fill_password_if_missing,
    reauth_schema,
    set_validation_error,
    validate_host,
    validate_host_on_submit,
    validate_input,
    validation_error_key,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.fixtures import MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME


def test_validate_host_hostname_rules() -> None:
    """Hostname validation covers length, charset, and edge characters."""
    with pytest.raises(vol.Invalid, match="too long"):
        validate_host("a" * 254)
    with pytest.raises(vol.Invalid, match="Invalid hostname"):
        validate_host("bad_host!")
    with pytest.raises(vol.Invalid, match="dot or hyphen"):
        validate_host("-bad.example")


def test_credentials_defaults_empty() -> None:
    """Empty config uses host fallback."""
    assert credentials_defaults(None, "fallback") == ("fallback", "", "")


def test_fill_password_if_missing() -> None:
    """Password is copied from sources when omitted in user input."""
    user_input: dict = {CONF_USERNAME: "u"}
    fill_password_if_missing(user_input, {CONF_PASSWORD: "secret"})
    assert user_input[CONF_PASSWORD] == "secret"


def test_validate_host_on_submit_sets_field_error() -> None:
    """Invalid host sets CONF_HOST error key."""
    errors: dict[str, str] = {}
    assert validate_host_on_submit({CONF_HOST: ".bad"}, errors) is False
    assert errors[CONF_HOST] == ERROR_KEY_INVALID_HOST


def test_configure_schema_invalid_host_fallback() -> None:
    """Invalid stored host falls back to default in configure schema."""
    schema = configure_schema({CONF_HOST: ".bad", CONF_USERNAME: "u"}, {})
    assert schema is not None


def _schema_field_default(schema: vol.Schema, field: str) -> object:
    """Return the voluptuous default for a schema field."""
    for marker in schema.schema:
        if marker.schema == field:
            default = marker.default
            return default() if callable(default) else default
    raise AssertionError(f"Field {field!r} not found in schema")


def test_configure_schema_for_resubmit_preserves_update_interval() -> None:
    """Re-shown configure forms keep a submitted update interval."""
    submitted = {
        CONF_HOST: "192.168.1.10",
        CONF_USERNAME: "user",
        CONF_UPDATE_INTERVAL: 60,
    }
    stale_options = {CONF_UPDATE_INTERVAL: 30}

    resubmit_schema = configure_schema_for_resubmit(submitted)
    stale_schema = configure_schema(submitted, stale_options)

    assert _schema_field_default(resubmit_schema, CONF_UPDATE_INTERVAL) == 60
    assert _schema_field_default(stale_schema, CONF_UPDATE_INTERVAL) == 30


def test_confirm_schema_with_current_input() -> None:
    """Confirm schema with current_input merges password from existing config."""
    schema = confirm_schema(
        {CONF_HOST: MOCK_HOST, CONF_USERNAME: "u", CONF_PASSWORD: "stored"},
        MOCK_HOST,
        current_input={CONF_HOST: MOCK_HOST, CONF_USERNAME: "u"},
    )
    assert schema is not None


def test_reauth_and_confirm_checkbox_schemas() -> None:
    """Reauth and confirm checkbox schemas are valid voluptuous schemas."""
    assert reauth_schema("user") is not None
    assert confirm_checkbox_schema() is not None


def test_validation_error_key_mapping() -> None:
    """Exception messages map to flow error keys."""
    assert validation_error_key("Login failed") == ERROR_KEY_INVALID_AUTH
    assert validation_error_key("connection refused") == ERROR_KEY_CANNOT_CONNECT
    assert validation_error_key("something else") == ERROR_KEY_UNKNOWN


def test_set_validation_error_branches() -> None:
    """set_validation_error handles typed and generic exceptions."""
    errors: dict[str, str] = {}
    set_validation_error(errors, CannotConnect(), log_unknown_details=False)
    assert errors["base"] == ERROR_KEY_CANNOT_CONNECT

    errors = {}
    set_validation_error(errors, InvalidAuth(), log_unknown_details=False)
    assert errors["base"] == ERROR_KEY_INVALID_AUTH

    errors = {}
    set_validation_error(errors, RuntimeError("login failed"), log_unknown_details=True)
    assert errors["base"] == ERROR_KEY_INVALID_AUTH

    errors = {}
    set_validation_error(errors, RuntimeError("weird"), log_unknown_details=True)
    assert errors["base"] == ERROR_KEY_UNKNOWN


@pytest.mark.asyncio
async def test_validate_input_success(hass: HomeAssistant) -> None:
    """validate_input returns title when session login succeeds."""
    session_mock = AsyncMock()
    session_mock.async_get_vpn_connections = AsyncMock(return_value={"x": {}})
    session_mock.async_close = AsyncMock()

    with patch(
        "custom_components.fritzbox_vpn.flow_forms.FritzConnectionVPNSession",
        return_value=session_mock,
    ):
        info = await validate_input(
            hass,
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert MOCK_HOST in info["title"]
    session_mock.async_close.assert_awaited_once()
