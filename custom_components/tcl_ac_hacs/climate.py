# custom_components/tcl_ac_hacs/climate.py
import logging
from typing import Any, Dict, List, Optional
from datetime import timedelta

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import TclAcApi, TclApiError, TclAuthError
from .const import DOMAIN, CONF_SELECTED_DEVICES, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Define the HVAC modes your AC supports.
SUPPORTED_HVAC_MODES = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO, HVACMode.FAN_ONLY, HVACMode.DRY] # Add modes as supported

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TCL AC climate entities from a config entry."""
    api: TclAcApi = hass.data[DOMAIN][entry.entry_id]
    selected_device_ids: List[str] = entry.data.get(CONF_SELECTED_DEVICES, [])

    if not selected_device_ids:
        _LOGGER.warning("No devices selected for TCL AC controller setup.")
        return

    coordinators: Dict[str, DataUpdateCoordinator] = {}
    entities_to_add = []

    all_devices_info = []
    try:
        _LOGGER.info("Climate Setup: Fetching all devices to get initial info.")
        device_list_response = await api.get_devices()
        if device_list_response and "data" in device_list_response:
            all_devices_info = device_list_response["data"]
        else:
            _LOGGER.error("Climate Setup: Failed to fetch initial device list or list is malformed.")
            # Optionally, you could proceed without full initial info, but it's risky
            # For now, we'll continue and hope individual coordinators can fetch their device
    except (TclApiError, TclAuthError) as e:
        _LOGGER.error(f"Climate Setup: Error fetching device list: {e}")
        # Cannot proceed if we can't get any device info
        return


    for device_id in selected_device_ids:
        # Find the specific device info from the fetched list
        device_info_data = next((d for d in all_devices_info if d.get("deviceId") == device_id), None)
        
        if not device_info_data:
            _LOGGER.warning(f"Climate Setup: Device ID {device_id} selected but not found in API response. Skipping.")
            continue

        try:
            # Fetch device shadow before creating the entity
            device_shadow_data = await api.get_device_shadow(device_id)
            if not device_shadow_data:
                _LOGGER.warning(f"Climate Setup: Device {device_id} shadow not found during setup. Skipping entity creation.")
                continue
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Climate Setup: Error fetching device shadow for {device_id}: {e}")
            continue

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"tcl_ac_{device_id}",
            update_method=lambda dev_id=device_id: _async_update_data(api, dev_id),
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        coordinators[device_id] = coordinator
        _LOGGER.info(f"Climate Setup: Preparing entity for device {device_info_data.get('nickName', device_id)} with device_id: {device_id} and device_info_data: {device_info_data}")
        entity = TclClimateEntity(coordinator, api, device_info_data, device_shadow_data)
        entities_to_add.append(entity)
        _LOGGER.info(f"Climate Setup: Prepared entity for device {device_info_data.get('nickName', device_id)}")

        # Fetch initial data (this will now use the shadow data fetched above)
        # await coordinator.async_config_entry_first_refresh()
        coordinator.data = device_shadow_data
        entity._update_attrs(coordinator.data, device_id=device_id)

    if entities_to_add:
        async_add_entities(entities_to_add, update_before_add=True)
        _LOGGER.info(f"Added {len(entities_to_add)} TCL AC climate entities.")
    else:
        _LOGGER.warning("No TCL AC climate entities were added.")


async def _async_update_data(api: TclAcApi, device_id: str) -> Dict[str, Any]:
    """Fetch data for a single TCL AC device."""
    _LOGGER.debug(f"Coordinator: Updating data for device {device_id}")
    try:
        # Use the get_device_shadow method to fetch the device's shadow state
        device_data = await api.get_device_shadow(device_id)
        if not device_data:
            _LOGGER.warning(f"Coordinator: Device {device_id} shadow not found in API response during update.")
            raise UpdateFailed(f"Device {device_id} shadow not found in API response.")
        _LOGGER.debug(f"Coordinator: Found shadow data for {device_id}: {device_data}")
        return device_data
    except TclAuthError as err:
        _LOGGER.error(f"Coordinator: Authentication error updating {device_id}: {err}")
        # This will typically be handled by ensure_authenticated, but if it bubbles up, re-raise
        raise UpdateFailed(f"Authentication error: {err}") from err
    except TclApiError as err:
        _LOGGER.error(f"Coordinator: API error updating {device_id}: {err}")
        raise UpdateFailed(f"API error: {err}") from err
    except Exception as err:
        _LOGGER.error(f"Coordinator: Unexpected error updating {device_id}: {err}", exc_info=True)
        raise UpdateFailed(f"Unexpected error: {err}") from err


class TclClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a TCL AC Unit."""

    _attr_has_entity_name = True # Use if your entity name is part of device name
    # Or set _attr_name directly if you want full control

    def __init__(self, coordinator: DataUpdateCoordinator, api: TclAcApi, device_data: Dict[str, Any], device_shadow_data: Dict[str, Any]):
        """Initialize the TCL AC climate entity."""
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_data.get("deviceId")
        self._device_name = device_data.get("nickName", f"TCL AC {self._device_id[:6]}")
        self._attr_name = self._device_name # Entity name will be this
        self._device_shadow_data = device_shadow_data

        _LOGGER.info(f"Initializing TCLClimateEntity: {self._device_name} (ID: {self._device_id})")
        _LOGGER.debug(f"Initial device data for {self._device_id}: {device_data}")

        self._attr_unique_id = f"{DOMAIN}_{self._device_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "TCL",
            "model": device_data.get("deviceType", "Air Conditioner"), # Or more specific if available
            # "sw_version": device_data.get("firmwareVersion"), # If available
        }

        # Set static attributes (can be expanded based on device capabilities)
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS # Assuming Celsius
        self._attr_hvac_modes = SUPPORTED_HVAC_MODES
        self._attr_hvac_mode = HVACMode.OFF # Initialize with default mode
        
        # Temperature attributes
        self._attr_min_temp = 16.0
        self._attr_max_temp = 31.0
        self._attr_target_temperature_step = 0.5
        
        # Supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON | 
            ClimateEntityFeature.TURN_OFF |
            ClimateEntityFeature.TARGET_TEMPERATURE
        )

        # Update attributes based on initial data right away
        self._update_attrs(self._device_shadow_data, device_id=self._device_id)


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(f"Entity {self.unique_id}: Coordinator update received. Data: {self.coordinator.data}")
        coordinator_device_id = None
        if (
            self.coordinator.data
            and "state" in self.coordinator.data
            and "reported" in self.coordinator.data["state"]
        ):
            reported = self.coordinator.data["state"]["reported"]
            if reported:
                coordinator_device_id = reported.get("deviceId")
            else:
                coordinator_device_id = None
        if coordinator_device_id and coordinator_device_id == self._device_id:
            self._update_attrs(self.coordinator.data, device_id=self._device_id)
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                f"Entity {self.unique_id}: Mismatched device ID in coordinator data or no data. "
                f"Entity device_id: {self._device_id}, Coordinator deviceId: {coordinator_device_id}"
            )
            _LOGGER.debug(f"Entity {self.unique_id}: Coordinator data: {self.coordinator.data}")
            if self.coordinator.data and "state" in self.coordinator.data:
                _LOGGER.debug(f"Entity {self.unique_id}: Coordinator state data: {self.coordinator.data['state']}")


    def _update_attrs(self, data: Optional[Dict[str, Any]] = None, device_id: str = None):
        """Update entity attributes from API data."""
        if data is None:
            _LOGGER.debug(f"Entity {self.unique_id}: No data provided for attribute update.")
            return

        if device_id is None:
            _LOGGER.warning(f"Entity {self.unique_id}: Device ID not provided for attribute update.")
            return

        _LOGGER.debug(f"Entity tcl_ac_hacs_{device_id}: Updating attributes with data: {data}")
        _LOGGER.debug(f"Entity tcl_ac_hacs_{device_id}: data: {data}")
        
        # Extract power state and other attributes from the API response
        reported_state = data.get("state", {}).get("reported", {})
        _LOGGER.debug(f"Entity tcl_ac_hacs_{device_id}: reported_state: {reported_state}")

        power_state = reported_state.get("powerSwitch")  # 0 for off, 1 for on
        target_temp = reported_state.get("targetTemperature")
        current_temp = reported_state.get("currentTemperature")
        mode = reported_state.get("workMode")

        _LOGGER.debug(f"Entity tcl_ac_hacs_{device_id}: powerSwitch: {power_state}, target_temp: {target_temp}, current_temp: {current_temp}, mode: {mode}")

        if power_state is not None:
            _LOGGER.debug(f"Entity tcl_ac_hacs_{device_id}: Extracted powerSwitch: {power_state}")
        if target_temp is not None:
            _LOGGER.debug(f"Entity tcl_ac_hacs_{device_id}: Extracted targetTemperature: {target_temp}")
        if current_temp is not None:
            _LOGGER.debug(f"Entity tcl_ac_hacs_{device_id}: Extracted currentTemperature: {current_temp}")

        if target_temp is not None:
            self._attr_target_temperature = float(target_temp)

        if current_temp is not None:
            self._attr_current_temperature = float(current_temp)

        hvac_mode = HVACMode.OFF
        if power_state == 1:
            # Set HVAC mode based on device's operating mode
            if mode == 0:  # Assuming 0 is COOL, adjust as necessary
                hvac_mode = HVACMode.COOL
            elif mode == 1:  # Assuming 1 is HEAT, adjust as necessary
                hvac_mode = HVACMode.HEAT
            elif mode == 2: # Assuming 2 is AUTO, adjust as necessary
                hvac_mode = HVACMode.AUTO
            elif mode == 4: # Assuming 4 is FAN_ONLY, adjust as necessary
                hvac_mode = HVACMode.FAN_ONLY
            elif mode == 3: # Assuming 3 is DRY, adjust as necessary
                hvac_mode = HVACMode.DRY
            else:
                hvac_mode = HVACMode.COOL # Default to cool if unknown
        self._attr_hvac_mode = hvac_mode

        hvac_action = HVACAction.OFF
        if power_state == 1:
            if mode == 0:
                hvac_action = HVACAction.COOLING
            elif mode == 1:
                hvac_action = HVACAction.HEATING
            elif mode == 2:
                hvac_action = HVACAction.IDLE
            elif mode == 3:
                hvac_action = HVACAction.DRYING
            elif mode == 4:
                hvac_action = HVACAction.FAN
            else:
                hvac_action = HVACAction.IDLE
        self._attr_hvac_action = hvac_action

        _LOGGER.debug(f"Entity {self.unique_id}: Updated HVAC mode to {self._attr_hvac_mode}, "
                      f"target_temperature={self._attr_target_temperature}, "
                      f"current_temperature={self._attr_current_temperature}, "
                      f"hvac_action={self._attr_hvac_action}")

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current HVAC mode."""
        # This is now set by _update_attrs
        return self._attr_hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.info(f"Entity {self.unique_id}: Setting HVAC mode to {hvac_mode}")
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode in [HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO, HVACMode.FAN_ONLY, HVACMode.DRY]: # Add other modes if supported
            # For now, COOL implies turning ON.
            # A more sophisticated AC might have separate commands for mode and power.
            # The 'powerSwitch' seems to be the primary control.
            # If there's a separate 'mode' command, call it here.
            # For now, we assume setting a mode (other than OFF) also turns it on.
            await self.async_turn_on() 
            # If your AC has explicit mode commands (e.g., {"mode": "cool"}), send them here.
            # e.g., await self._api.control_device(self._device_id, {"mode": hvac_mode.value})
        else:
            _LOGGER.warning(f"Entity {self.unique_id}: Unsupported HVAC mode: {hvac_mode}")
            return
        
        # After sending command, optimistically update state and request refresh
        self._attr_hvac_mode = hvac_mode 
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the climate entity on."""
        _LOGGER.info(f"Entity {self.unique_id}: Turning ON")
        try:
            await self._api.set_power(self._device_id, True)
            # Set HVAC mode to COOL when turning on, adjust if a different mode is active
            self._attr_hvac_mode = HVACMode.COOL
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Entity {self.unique_id}: Error turning on: {e}")

    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        _LOGGER.info(f"Entity {self.unique_id}: Turning OFF")
        try:
            await self._api.set_power(self._device_id, False)
            self._attr_hvac_mode = HVACMode.OFF
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Entity {self.unique_id}: Error turning off: {e}")

    def turn_on(self) -> None:
        """Turn the entity on."""
        asyncio.run_coroutine_threadsafe(self.async_turn_on(), self.hass.loop)

    def turn_off(self) -> None:
        """Turn the entity off."""
        asyncio.run_coroutine_threadsafe(self.async_turn_off(), self.hass.loop)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning(f"Entity {self.unique_id}: No temperature provided.")
            return

        # Validate temperature is within allowed range
        if not (self._attr_min_temp <= temperature <= self._attr_max_temp):
            _LOGGER.error(
                f"Entity {self.unique_id}: Temperature {temperature} is outside valid range "
                f"({self._attr_min_temp} - {self._attr_max_temp})"
            )
            return

        _LOGGER.info(f"Entity {self.unique_id}: Setting temperature to {temperature}")
        try:
            await self._api.set_temperature(self._device_id, temperature)
            self._attr_target_temperature = temperature
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Entity {self.unique_id}: Error setting temperature: {e}")
        except Exception as e:
            _LOGGER.exception(f"Entity {self.unique_id}: Unexpected error setting temperature: {e}")
