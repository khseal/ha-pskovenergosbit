"""Number entity for a new meter reading."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PskovenergosbitCoordinator
from .sensor import _device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PskovenergosbitCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NewReadingNumber(coordinator)])


class NewReadingNumber(CoordinatorEntity[PskovenergosbitCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Новое показание"
    _attr_icon = "mdi:pencil"
    _attr_native_min_value = 0
    _attr_native_max_value = 99999999
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_new_reading"
        self._attr_device_info = _device(coordinator)

    @property
    def native_value(self) -> float | None:
        if self.coordinator.pending_value is not None:
            return self.coordinator.pending_value
        meter = self.coordinator.data.meter if self.coordinator.data else None
        return meter.last if meter else None

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.pending_value = value
        self.async_write_ha_state()
