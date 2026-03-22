from functools import partial

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from python_vw_carnet import VWClient

from .const import (
    CONF_DISTANCE_UNIT,
    CONF_EMAIL,
    CONF_NAME,
    DEFAULT_DISTANCE_UNIT,
    DISTANCE_UNIT_MI,
    DOMAIN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SESSION_PATH,
    CONF_SPIN,
    DEFAULT_SCAN_INTERVAL,
    KM_TO_MI,
)
from .coordinator import VWVehicleStatusCoordinator


@dataclass(frozen=True, kw_only=True)
class VWVehicleSensorDescription(SensorEntityDescription):
    value_key: str
    # If True, the raw coordinator value is in km and should be converted when mi is configured
    is_distance: bool = False


SENSORS: tuple[VWVehicleSensorDescription, ...] = (
    VWVehicleSensorDescription(
        key="last_seen",
        name="Last Seen",
        icon="mdi:eye",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_key="last_seen",
   ),
    # ── Distance sensors (raw km in coordinator) ──────────────────────────
    VWVehicleSensorDescription(
        key="mileage",
        name="Mileage",
        icon="mdi:counter",
        device_class=SensorDeviceClass.DISTANCE,
        value_key="mileage_km",
        is_distance=True,
    ),
    # ── Distance sensors (raw km in coordinator) ──────────────────────────
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
    # ── EV / charging ────────────────────────────────────────────────────
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
    # ── Vehicle status ────────────────────────────────────────────────────
    VWVehicleSensorDescription(
        key="lock_status",
        name="Lock Status",
        icon="mdi:car-key",
        value_key="lock_status",
    ),
    # ── Location ──────────────────────────────────────────────────────────
    VWVehicleSensorDescription(
        key="last_parked_timestamp",
        name="Last Parked At",
        icon="mdi:eye",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_key="last_parked_timestamp",
    )
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    session_path = entry.data.get(CONF_SESSION_PATH) or None
    client = await hass.async_add_executor_job(
        partial(
            VWClient,
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            spin=entry.data[CONF_SPIN],
            session_path=session_path,
        )
    )

    coordinator = VWVehicleStatusCoordinator(
        hass,
        client,
        entry.data[CONF_NAME],
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [VWVehicleSensor(coordinator, entry, description) for description in SENSORS]
    )


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
        self._distance_unit: str = entry.data.get(CONF_DISTANCE_UNIT, DEFAULT_DISTANCE_UNIT)
        self._entry_name: str = entry.data[CONF_NAME]
        self._attr_name = f"{self._entry_name} {description.name}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        vin = self.coordinator.data.get("vin") if self.coordinator.data else None
        return DeviceInfo(
            identifiers={(DOMAIN, vin or self._attr_unique_id)},
            name=self._entry_name,
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
            "latitude": self.coordinator.data.get("last_parked_latitude"),
            "longitude": self.coordinator.data.get("last_parked_longitude")
        }
