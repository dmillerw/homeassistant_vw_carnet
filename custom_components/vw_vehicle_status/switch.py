from functools import partial
from threading import Lock

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from python_vw_carnet import VWClient

from .const import CONF_NAME, DOMAIN
from .coordinator import VWVehicleStatusCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: VWClient = entry_data["client"]
    client_lock: Lock = entry_data["client_lock"]
    entities = [
        VWPreclimateSwitch(
            coordinator=coordinator,
            entry_name=entry.data[CONF_NAME],
            client=client,
            client_lock=client_lock,
            entry_id=entry.entry_id,
        )
        for coordinator in entry_data["coordinators"].values()
    ]
    async_add_entities(entities)


class VWPreclimateSwitch(CoordinatorEntity[VWVehicleStatusCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VWVehicleStatusCoordinator,
        entry_name: str,
        client: VWClient,
        client_lock: Lock,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_name = entry_name
        self._client = client
        self._client_lock = client_lock
        self._attr_name = f"{coordinator.vehicle_name} Preclimate"
        self._attr_unique_id = f"{entry_id}_{coordinator.vehicle_id}_preclimate"

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
    def is_on(self) -> bool:
        value = self.coordinator.data.get("preclimate_active")
        return bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(
            partial(_start_preclimate, self._client, self._client_lock, self.coordinator.vehicle_id)
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(
            partial(_stop_preclimate, self._client, self._client_lock, self.coordinator.vehicle_id)
        )
        await self.coordinator.async_request_refresh()


def _start_preclimate(client: VWClient, client_lock: Lock, vehicle_id: str) -> None:
    with client_lock:
        client.start_ev_preclimate(vehicle_id)


def _stop_preclimate(client: VWClient, client_lock: Lock, vehicle_id: str) -> None:
    with client_lock:
        client.stop_ev_preclimate(vehicle_id)
