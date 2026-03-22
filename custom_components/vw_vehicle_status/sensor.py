from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DISTANCE_UNIT,
    CONF_NAME,
    DEFAULT_DISTANCE_UNIT,
    DISTANCE_UNIT_MI,
    DOMAIN,
    KM_TO_MI,
)
from .coordinator import VWVehicleStatusCoordinator


@dataclass(frozen=True, kw_only=True)
class VWVehicleSensorDescription(SensorEntityDescription):
    value_key: str
    is_distance: bool = False


SENSORS: tuple[VWVehicleSensorDescription, ...] = (
    VWVehicleSensorDescription(
        key="last_seen",
        name="Last Seen",
        icon="mdi:eye",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_key="last_seen",
    ),
    VWVehicleSensorDescription(
        key="mileage",
        name="Mileage",
        icon="mdi:counter",
        device_class=SensorDeviceClass.DISTANCE,
        value_key="mileage_km",
        is_distance=True,
    ),
    VWVehicleSensorDescription(
        key="next_maintenance_milestone",
        name="Next Maintenance Milestone",
        icon="mdi:counter",
        device_class=SensorDeviceClass.DISTANCE,
        value_key="next_maintenance_milestone",
        is_distance=True,
    ),
    VWVehicleSensorDescription(
        key="cruise_range",
        name="Estimated Range",
        icon="mdi:gas-station",
        device_class=SensorDeviceClass.DISTANCE,
        value_key="cruise_range_km",
        is_distance=True,
    ),
    VWVehicleSensorDescription(
        key="charging_status",
        name="Charging Status",
        icon="mdi:ev-station",
        value_key="charging_status",
    ),
    VWVehicleSensorDescription(
        key="charge_power",
        name="Charge Power",
        icon="mdi:flash",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="kW",
        value_key="charge_power",
    ),
    VWVehicleSensorDescription(
        key="charge_rate",
        name="Charge Rate",
        icon="mdi:flash",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="kW",
        value_key="charge_rate",
    ),
    VWVehicleSensorDescription(
        key="remaining_charge_time",
        name="Remaining Charge Time",
        icon="mdi:flash",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="m",
        value_key="remaining_charge_time",
    ),
    VWVehicleSensorDescription(
        key="battery_capacity_percent",
        name="Battery Capacity",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        value_key="battery_capacity_percent",
    ),
    VWVehicleSensorDescription(
        key="lock_status",
        name="Lock Status",
        icon="mdi:car-key",
        value_key="lock_status",
    ),
    VWVehicleSensorDescription(
        key="last_parked_timestamp",
        name="Last Parked At",
        icon="mdi:eye",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_key="last_parked_timestamp",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[VWVehicleSensor] = []
    entry_data = hass.data[DOMAIN][entry.entry_id]

    for coordinator in entry_data["coordinators"].values():
        await coordinator.async_config_entry_first_refresh()
        entities.extend(
            VWVehicleSensor(coordinator, entry, description) for description in SENSORS
        )
    async_add_entities(entities)


class VWVehicleSensor(CoordinatorEntity[VWVehicleStatusCoordinator], SensorEntity):
    entity_description: VWVehicleSensorDescription

    def __init__(
        self,
        coordinator: VWVehicleStatusCoordinator,
        entry: ConfigEntry,
        description: VWVehicleSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._distance_unit: str = entry.data.get(
            CONF_DISTANCE_UNIT, DEFAULT_DISTANCE_UNIT
        )
        self._entry_name: str = entry.data[CONF_NAME]
        self._attr_name = (
            f"{self._entry_name} {coordinator.vehicle_name} {description.name}"
        )
        self._attr_unique_id = (
            f"{entry.entry_id}_{coordinator.vehicle_id}_{description.key}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        vin = self.coordinator.data.get("vin") if self.coordinator.data else None
        return DeviceInfo(
            identifiers={(DOMAIN, vin or self.coordinator.vehicle_id)},
            name=f"{self._entry_name} {self.coordinator.vehicle_name}",
            manufacturer="Volkswagen",
            serial_number=vin,
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.is_distance:
            return "mi" if self._distance_unit == DISTANCE_UNIT_MI else "km"
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self):
        value = self.coordinator.data.get(self.entity_description.value_key)
        if value is None:
            return None
        if self.entity_description.is_distance and self._distance_unit == DISTANCE_UNIT_MI:
            return round(value * KM_TO_MI, 1)
        return value

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "vin": self.coordinator.data.get("vin"),
            "vehicle_id": self.coordinator.data.get("vehicle_id"),
            "vehicle_name": self.coordinator.data.get("vehicle_name"),
            "latitude": self.coordinator.data.get("last_parked_latitude"),
            "longitude": self.coordinator.data.get("last_parked_longitude"),
        }
