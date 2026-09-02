"""Sensors for Pskovenergosbit."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PskovenergosbitCoordinator


def _device(coordinator: PskovenergosbitCoordinator) -> DeviceInfo:
    account = coordinator.data.account if coordinator.data else coordinator.entry.entry_id
    return DeviceInfo(
        identifiers={(DOMAIN, account)},
        name="Псковэнергосбыт",
        manufacturer="АО Псковэнергосбыт",
        model="Личный кабинет",
        configuration_url="https://epd.pskovenergosbit.ru/",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PskovenergosbitCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LastReadingSensor(coordinator),
            LastDateSensor(coordinator),
            AccountSensor(coordinator),
            MeterNumberSensor(coordinator),
            AddressSensor(coordinator),
            OwnerSensor(coordinator),
            StatusSensor(coordinator),
        ]
    )


class _Base(CoordinatorEntity[PskovenergosbitCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PskovenergosbitCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = _device(coordinator)


class LastReadingSensor(_Base):
    _attr_name = "Последние показания"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator, "reading")

    @property
    def native_value(self) -> float | None:
        meter = self.coordinator.data.meter if self.coordinator.data else None
        return meter.last if meter else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        meter = data.meter if data else None
        if not data or not meter:
            return {}
        return {
            "account": data.account,
            "meter": meter.counter_number,
            "service": meter.service,
            "last_date": meter.last_date,
        }


class LastDateSensor(_Base):
    _attr_name = "Дата передачи"
    _attr_icon = "mdi:calendar"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator, "last_date")

    @property
    def native_value(self) -> str | None:
        meter = self.coordinator.data.meter if self.coordinator.data else None
        return meter.last_date if meter else None


class AccountSensor(_Base):
    _attr_name = "Лицевой счёт"
    _attr_icon = "mdi:identifier"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator, "account")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.account if self.coordinator.data else None


class MeterNumberSensor(_Base):
    _attr_name = "Номер счётчика"
    _attr_icon = "mdi:barcode"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator, "meter")

    @property
    def native_value(self) -> str | None:
        meter = self.coordinator.data.meter if self.coordinator.data else None
        return meter.counter_number if meter else None


class AddressSensor(_Base):
    _attr_name = "Адрес"
    _attr_icon = "mdi:home-map-marker"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator, "address")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.address if self.coordinator.data else None


class OwnerSensor(_Base):
    _attr_name = "Владелец"
    _attr_icon = "mdi:account"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator, "owner")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.owner if self.coordinator.data else None


class StatusSensor(_Base):
    _attr_name = "Состояние"
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator: PskovenergosbitCoordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str:
        if self.coordinator.last_update_success and self.coordinator.data:
            return "ok"
        if self.coordinator.last_exception:
            return "error"
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict:
        err = self.coordinator.last_exception
        return {"error": str(err) if err else None}
