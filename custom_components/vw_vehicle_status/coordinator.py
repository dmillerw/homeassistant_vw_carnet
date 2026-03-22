from datetime import datetime, timedelta
import logging
from threading import Lock
from zoneinfo import ZoneInfo

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from python_vw_carnet import VWClient, VWClientError

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class VWVehicleStatusCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass,
        client: VWClient,
        client_lock: Lock,
        name: str,
        vehicle_id: str,
        vin: str | None,
        vehicle_name: str,
        scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self.client = client
        self.client_lock = client_lock
        self.vehicle_id = vehicle_id
        self.vin = vin
        self.vehicle_name = vehicle_name
        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} {vehicle_name} coordinator",
            update_interval=timedelta(seconds=scan_interval_seconds),
        )

    async def _async_update_data(self) -> dict:
        def _fetch() -> dict:
            try:
                with self.client_lock:
                    vehicle = self.client.get_vehicle(self.vehicle_id)
            except VWClientError as err:
                raise UpdateFailed(f"VW client request failed: {err}") from err
            except Exception as err:
                raise UpdateFailed(f"Unexpected VW update failure: {err}") from err

            data: dict = {
                "vin": self.vin,
                "vehicle_id": self.vehicle_id,
                "vehicle_name": self.vehicle_name,
                # Odometer: raw km value; sensors convert to mi if configured.
                "mileage_km": vehicle.data.currentMileage,
                "lock_status": vehicle.data.lockStatus,
                # Estimated combustion/hybrid range in km.
                "cruise_range_km": vehicle.data.powerStatus.cruiseRange,
                "last_parked_latitude": vehicle.data.lastParkedLocation.latitude,
                "last_parked_longitude": vehicle.data.lastParkedLocation.longitude,
                "last_parked_timestamp": datetime.fromtimestamp(
                    vehicle.data.lastParkedLocation.timestamp / 1000.0,
                    tz=ZoneInfo("America/Los_Angeles"),
                ),
                "last_seen": datetime.fromtimestamp(
                    vehicle.data.timestamp / 1000.0,
                    tz=ZoneInfo("America/Los_Angeles"),
                ),
            }

            try:
                with self.client_lock:
                    summary = self.client.get_ev_summary(self.vehicle_id)
                data["charging_status"] = summary.data.batteryAndPlugStatus.chargingStatus.chargeType
                data["charge_power"] = summary.data.batteryAndPlugStatus.chargingStatus.chargePower
                data["battery_capacity_percent"] = summary.data.batteryAndPlugStatus.batteryStatus.currentSOCPct
                data["remaining_charge_time"] = summary.data.batteryAndPlugStatus.chargingStatus.remainingChargingTimeToComplete
                data["preclimate_active"] = summary.data.climateStatus.climateStatusReport.climateStatusInd != "off"
            except Exception as err:
                _LOGGER.debug("EV summary unavailable for %s: %s", self.vehicle_id, err)

            return data

        return await self.hass.async_add_executor_job(_fetch)