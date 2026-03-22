import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from python_vw_carnet import VWClient

from .const import (
    CONF_DISTANCE_UNIT,
    CONF_EMAIL,
    CONF_SCAN_INTERVAL,
    CONF_SESSION_PATH,
    CONF_SPIN,
    DEFAULT_DISTANCE_UNIT,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DISTANCE_UNIT_KM,
    DISTANCE_UNIT_MI,
    DOMAIN,
)


class VWVehicleStatusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(self._validate_input, user_input)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_EMAIL].lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SPIN): str,
                    vol.Optional(CONF_SESSION_PATH, default=""): str,
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                    vol.Optional(CONF_DISTANCE_UNIT, default=DEFAULT_DISTANCE_UNIT): vol.In(
                        [DISTANCE_UNIT_KM, DISTANCE_UNIT_MI]
                    ),
                }
            ),
            errors=errors,
        )

    def _validate_input(self, data: dict) -> None:
        session_path = data.get(CONF_SESSION_PATH) or None
        client = VWClient(
            email=data[CONF_EMAIL],
            password=data[CONF_PASSWORD],
            spin=data[CONF_SPIN],
            session_path=session_path,
        )
        try:
            client.get_garage(force=True)
        finally:
            client.close()
