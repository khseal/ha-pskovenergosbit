"""Config flow for Pskovenergosbit."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .cabinet import AuthError, CabinetError, PskovenergosbitClient
from .const import CONF_SCAN_INTERVAL, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate(hass: HomeAssistant, username: str, password: str) -> str:
    client = PskovenergosbitClient(username, password)
    try:
        state = await hass.async_add_executor_job(client.fetch)
    except AuthError as err:
        raise InvalidAuth from err
    except CabinetError as err:
        raise CannotConnect from err
    return state.account or username


class CannotConnect(HomeAssistantError):
    """Cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Invalid auth."""


class PskovenergosbitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            try:
                unique = await _validate(self.hass, username, password)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Псковэнергосбыт",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PskovenergosbitOptionsFlow:
        return PskovenergosbitOptionsFlow()


class PskovenergosbitOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        hours = self.config_entry.options.get(CONF_SCAN_INTERVAL, 6)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=hours): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=72)
                    ),
                }
            ),
        )
