"""Button to submit meter readings."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .cabinet import CabinetError
from .const import DOMAIN
from .coordinator import PskovenergosbitCoordinator
from .sensor import _device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PskovenergosbitCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SubmitButton(coordinator)])


class SubmitButton(CoordinatorEntity[PskovenergosbitCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Отправить показания"
    _attr_icon = "mdi:upload"

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_submit"
        self._attr_device_info = _device(coordinator)

    async def async_press(self) -> None:
        value = self.coordinator.pending_value
        if value is None:
            meter = self.coordinator.data.meter if self.coordinator.data else None
            value = meter.last if meter else None
        if value is None:
            raise HomeAssistantError("Сначала задайте новое показание")
        try:
            await self.coordinator.async_submit(value)
        except CabinetError as err:
            raise HomeAssistantError(str(err)) from err
