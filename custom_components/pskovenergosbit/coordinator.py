"""Data update coordinator."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cabinet import AuthError, CabinetError, CabinetState, PskovenergosbitClient
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PskovenergosbitCoordinator(DataUpdateCoordinator[CabinetState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        hours = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds() / 3600)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=float(hours)),
        )
        self.entry = entry
        self.client = PskovenergosbitClient(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
        self.pending_value: float | None = None

    async def _async_update_data(self) -> CabinetState:
        try:
            return await self.hass.async_add_executor_job(self.client.fetch)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CabinetError as err:
            raise UpdateFailed(str(err)) from err

    async def async_submit(self, value: float, night: float | None = None) -> CabinetState:
        try:
            state = await self.hass.async_add_executor_job(
                self.client.submit, value, night
            )
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        self.pending_value = value
        self.async_set_updated_data(state)
        return state
