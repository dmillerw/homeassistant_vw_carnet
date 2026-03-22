from functools import partial
from threading import Lock
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from python_vw_carnet import VWClient

from .coordinator import VWVehicleStatusCoordinator
from .const import (
    CONF_EMAIL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SESSION_PATH,
    CONF_SPIN,
    DEFAULT_SCAN_INTERVAL,
)
from .const import DOMAIN, PLATFORMS


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    session_path = entry.data.get(CONF_SESSION_PATH) or None
    client_lock = Lock()
    client = await hass.async_add_executor_job(
        partial(
            VWClient,
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            spin=entry.data[CONF_SPIN],
            session_path=session_path,
        )
    )
    garage = await hass.async_add_executor_job(partial(_get_garage, client, client_lock))

    coordinators: dict[str, VWVehicleStatusCoordinator] = {}
    for vehicle in garage.data.vehicles:
        vehicle_name = _format_vehicle_name(vehicle)
        coordinator = VWVehicleStatusCoordinator(
            hass,
            client,
            client_lock,
            entry.data[CONF_NAME],
            vehicle.vehicleId,
            vehicle.vin,
            vehicle_name,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        coordinators[vehicle.vehicleId] = coordinator

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "client_lock": client_lock,
        "garage": garage,
        "coordinators": coordinators,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if entry_data is not None and entry_data.get("client") is not None:
            await hass.async_add_executor_job(entry_data["client"].close)
    return unload_ok


def _get_garage(client: VWClient, client_lock: Lock) -> Any:
    with client_lock:
        return client.get_garage()


def _format_vehicle_name(vehicle: Any) -> str:
    model_name = getattr(vehicle, "modelName", None) or vehicle.vehicleId
    model_year = getattr(vehicle, "modelYear", None)
    if model_year:
        return f"{model_year} {model_name}"
    return model_name
