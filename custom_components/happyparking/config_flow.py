"""Config flow for HappyParking."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BASE_URL,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_SITE_CODE,
    CONF_USER_ID,
    CONF_VERIFY_SSL,
    DEFAULT_DEVICE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)


class HappyParkingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HappyParking."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            base = str(user_input[CONF_BASE_URL]).strip().rstrip("/")
            if not base.startswith("http"):
                errors[CONF_BASE_URL] = "invalid_url"
            else:
                await self.async_set_unique_id(f"{base}-{user_input[CONF_USER_ID]}")
                self._abort_if_unique_id_configured()
                user_input[CONF_BASE_URL] = base
                return self.async_create_entry(title="HappyParking", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_USER_ID): cv.positive_int,
                vol.Optional(CONF_SITE_CODE, default=""): str,
                vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
