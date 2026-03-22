from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from python_vw_carnet import VWClient, VWClientError

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class VWVehicleStatusCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, client: VWClient, name: str, scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL) -> None:
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} coordinator",
            update_interval=timedelta(seconds=scan_interval_seconds),
        )

    async def _async_update_data(self) -> dict:
        def _fetch() -> dict:
            try:
                vehicle = self.client.get_vehicle_status()
            except VWClientError as err:
                raise UpdateFailed(f"VW client request failed: {err}") from err
            except Exception as err:
                raise UpdateFailed(f"Unexpected VW update failure: {err}") from err

            data: dict = {
                "vin": self.client.state.vin,
                "vehicle_id": self.client.state.vehicle_id,
                # Odometer — raw km value; sensors convert to mi if configured
                "mileage_km": vehicle.current_mileage,
                "lock_status": vehicle.lock_status,
                # Estimated combustion/hybrid range in km
                "cruise_range_km": vehicle.cruise_range,
                "last_parked_latitude": vehicle.last_parked_latitude,
                "last_parked_longitude": vehicle.last_parked_longitude,
                "last_parked_timestamp": datetime.fromtimestamp(vehicle.raw["lastParkedLocation"]["timestamp"] / 1000.0, tz=ZoneInfo("America/Los_Angeles")),
                "last_seen": datetime.fromtimestamp(vehicle.raw["timestamp"] / 1000.0, tz=ZoneInfo("America/Los_Angeles")),
                "next_maintenance_milestone": vehicle.raw["nextMaintenanceMilestone"]["absoluteMileage"]
            }

            # EV summary — may not be present for non-EV or unavailable
            try:
                summary = self.client.get_ev_summary()
                #data["last_seen"] = summary.battery_status.raw["carCapturedTimestamp"]
                data["charging_status"] = summary.charging_status.current_charge_state
                data["charge_power"] = summary.charging_status.charge_power
               # data["charge_rate"] = summary.charging_status.raw["chargeRate"] if "chargeRate" in summary.charging_status.raw else 0,
                data["battery_capacity_percent"] = summary.battery_status.current_soc_pct
                data["remaining_charge_time"] = summary.charging_status.raw["remainingChargingTimeToComplete"]
            except Exception as err:
                _LOGGER.debug("EV summary unavailable: %s", err)

            return data

        return await self.hass.async_add_executor_job(_fetch)
