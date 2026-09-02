"""Home Assistant integration for Pskovenergosbyt personal cabinet."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .cabinet import AuthError, CabinetError
from .const import ATTR_NIGHT, ATTR_VALUE, DOMAIN, PLATFORMS, SERVICE_SUBMIT
from .coordinator import PskovenergosbitCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SUBMIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VALUE): vol.Coerce(float),
        vol.Optional(ATTR_NIGHT): vol.Coerce(float),
        vol.Optional("entry_id"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = PskovenergosbitCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_submit(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        coordinator_obj: PskovenergosbitCoordinator | None = None
        if entry_id:
            coordinator_obj = hass.data[DOMAIN].get(entry_id)
        elif len(hass.data[DOMAIN]) == 1:
            coordinator_obj = next(iter(hass.data[DOMAIN].values()))
        else:
            coordinator_obj = next(iter(hass.data[DOMAIN].values()), None)
        if coordinator_obj is None:
            raise HomeAssistantError("Интеграция Псковэнергосбыт не настроена")
        try:
            await coordinator_obj.async_submit(
                call.data[ATTR_VALUE],
                call.data.get(ATTR_NIGHT),
            )
        except AuthError as err:
            raise HomeAssistantError(f"Ошибка входа: {err}") from err
        except CabinetError as err:
            raise HomeAssistantError(str(err)) from err

    if not hass.services.has_service(DOMAIN, SERVICE_SUBMIT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SUBMIT,
            _async_submit,
            schema=SUBMIT_SCHEMA,
        )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SUBMIT)
    return unload_ok
