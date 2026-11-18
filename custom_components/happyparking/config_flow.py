"""Config flow for HappyParking."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BASE_URL,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_SITE_CODE,
    CONF_USER_ID,
    CONF_VERIFY_SSL,
    CONF_ENABLE_PUSH,
    CONF_ENABLE_NOTIFY,
    CONF_ENABLE_VISITORS,
    CONF_KAKAO_ID,
    CONF_LOGIN_ID,
    CONF_PASSWORD,
    CREDENTIAL_KEYS,
    DEFAULT_DEVICE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DEFAULT_ENABLE_PUSH,
    DEFAULT_ENABLE_NOTIFY,
    DEFAULT_ENABLE_VISITORS,
    DOMAIN,
)
from .discovery import (
    DiscoveryError,
    cloud_token_for,
    config_from_token,
    login_url,
    parse_pasted_login,
    server_host,
    token_for_kakao_id,
    token_for_password,
)

CONF_LOGIN_TOKEN = "login_token"

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
        vol.Optional(CONF_ENABLE_PUSH, default=DEFAULT_ENABLE_PUSH): bool,
        vol.Optional(CONF_ENABLE_NOTIFY, default=DEFAULT_ENABLE_NOTIFY): bool,
        vol.Optional(
            CONF_ENABLE_VISITORS, default=DEFAULT_ENABLE_VISITORS
        ): bool,
    }
)


class HappyParkingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Discover the parking server from a HappyParking login."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Take the token from a HappyParking login and read the settings out of it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            pasted = str(user_input.get(CONF_LOGIN_TOKEN) or "").strip()
            if not pasted:
                # An empty box is the way out for anyone who cannot use a browser.
                return await self.async_step_other()
            try:
                return await self._from_pasted_login(pasted)
            except DiscoveryError as err:
                errors["base"] = err.key

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_LOGIN_TOKEN, default=""): str}),
            errors=errors,
            description_placeholders={"login_url": login_url()},
        )

    async def async_step_other(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the ways in that do not involve a browser login."""
        return self.async_show_menu(step_id="other", menu_options=["password", "manual"])

    async def _from_pasted_login(self, pasted: str) -> ConfigFlowResult:
        """Read the settings out of whatever the login handed back."""
        token, kakao_id = parse_pasted_login(pasted)
        if token is None:
            token = await token_for_kakao_id(
                async_get_clientsession(self.hass), str(kakao_id)
            )
            # A Kakao id is what lets the bridge sign itself in again later.
            return await self._create(
                {**config_from_token(token), CONF_KAKAO_ID: str(kakao_id)}
            )
        return await self._create(config_from_token(token))

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sign in with a HappyParking id and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            login_id = str(user_input[CONF_LOGIN_ID]).strip()
            password = str(user_input[CONF_PASSWORD])
            try:
                token = await token_for_password(
                    async_get_clientsession(self.hass), login_id, password
                )
                return await self._create(
                    {
                        **config_from_token(token),
                        CONF_LOGIN_ID: login_id,
                        CONF_PASSWORD: password,
                    }
                )
            except DiscoveryError as err:
                errors["base"] = err.key

        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOGIN_ID): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the server details directly, for when a login is not possible."""
        errors: dict[str, str] = {}
        if user_input is not None:
            base = str(user_input[CONF_BASE_URL]).strip().rstrip("/")
            if not base.startswith(("http://", "https://")):
                errors[CONF_BASE_URL] = "invalid_url"
            else:
                return await self._create(
                    {
                        CONF_BASE_URL: base,
                        CONF_USER_ID: int(user_input[CONF_USER_ID]),
                        CONF_SITE_CODE: str(user_input.get(CONF_SITE_CODE) or "").strip(),
                    }
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_URL): str,
                    vol.Required(CONF_USER_ID): cv.positive_int,
                    vol.Optional(CONF_SITE_CODE, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The push endpoints need a sign-in the bridge can renew on its own."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Take a Kakao id, or a HappyParking id and password, and check it."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            kakao_id = str(user_input.get(CONF_KAKAO_ID) or "").strip()
            login_id = str(user_input.get(CONF_LOGIN_ID) or "").strip()
            password = str(user_input.get(CONF_PASSWORD) or "")
            if kakao_id:
                # Take the bare number, or the address landed on after login.
                try:
                    _, parsed = parse_pasted_login(kakao_id)
                except DiscoveryError:
                    parsed = None
                kakao_id = parsed or kakao_id
            if kakao_id:
                credentials = {CONF_KAKAO_ID: kakao_id}
            elif login_id and password:
                credentials = {CONF_LOGIN_ID: login_id, CONF_PASSWORD: password}
            else:
                credentials = {}
                errors["base"] = "no_credentials"
            if credentials:
                try:
                    token = await cloud_token_for(
                        async_get_clientsession(self.hass), credentials
                    )
                    owner = config_from_token(token)[CONF_USER_ID]
                    if owner != int(entry.data[CONF_USER_ID]):
                        errors["base"] = "wrong_account"
                except DiscoveryError as err:
                    errors["base"] = err.key
            if not errors:
                kept = {k: v for k, v in entry.data.items() if k not in CREDENTIAL_KEYS}
                return self.async_update_reload_and_abort(
                    entry, data={**kept, **credentials}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_KAKAO_ID, default=""): str,
                    vol.Optional(CONF_LOGIN_ID, default=""): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={"login_url": login_url()},
        )

    async def _create(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Store a discovered configuration as a config entry."""
        label = data[CONF_SITE_CODE] or server_host(data[CONF_BASE_URL])
        await self.async_set_unique_id(f"{label}-{data[CONF_USER_ID]}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=f"HappyParking ({label})", data=data)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return HappyParkingOptionsFlow()


class HappyParkingOptionsFlow(OptionsFlow):
    """Tune how this bridge talks to the parking server."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
