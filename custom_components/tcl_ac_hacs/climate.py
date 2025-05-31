# custom_components/tcl_ac_hacs/climate.py
import logging
from typing import Any, Dict, List, Optional
from datetime import timedelta

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
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

# Define the HVAC modes your AC supports. Start simple.
SUPPORTED_HVAC_MODES = [HVACMode.OFF, HVACMode.COOL] # Add HEAT, AUTO, FAN_ONLY etc. as supported

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

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"tcl_ac_{device_id}",
            update_method=lambda dev_id=device_id: _async_update_data(api, dev_id),
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        # Fetch initial data
        await coordinator.async_config_entry_first_refresh()
        
        coordinators[device_id] = coordinator
        entities_to_add.append(TclClimateEntity(coordinator, api, device_info_data))
        _LOGGER.info(f"Climate Setup: Prepared entity for device {device_info_data.get('nickName', device_id)}")

    if entities_to_add:
        async_add_entities(entities_to_add, update_before_add=True)
        _LOGGER.info(f"Added {len(entities_to_add)} TCL AC climate entities.")
    else:
        _LOGGER.warning("No TCL AC climate entities were added.")


async def _async_update_data(api: TclAcApi, device_id: str) -> Dict[str, Any]:
    """Fetch data for a single TCL AC device."""
    _LOGGER.debug(f"Coordinator: Updating data for device {device_id}")
    try:
        # The get_devices method fetches all devices. We need to find ours.
        all_devices_response = await api.get_devices() # This also handles auth
        if all_devices_response and "data" in all_devices_response:
            for device_data in all_devices_response["data"]:
                if device_data.get("deviceId") == device_id:
                    _LOGGER.debug(f"Coordinator: Found data for {device_id}: {device_data}")
                    return device_data # This is the state for our specific device
            _LOGGER.warning(f"Coordinator: Device {device_id} not found in API response during update.")
            raise UpdateFailed(f"Device {device_id} not found in API response.")
        else:
            _LOGGER.error(f"Coordinator: Failed to fetch devices or malformed response for {device_id}")
            raise UpdateFailed("Failed to fetch devices or malformed API response.")
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

    def __init__(self, coordinator: DataUpdateCoordinator, api: TclAcApi, device_data: Dict[str, Any]):
        """Initialize the TCL AC climate entity."""
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_data.get("deviceId")
        self._device_name = device_data.get("nickName", f"TCL AC {self._device_id[:6]}")
        self._attr_name = self._device_name # Entity name will be this

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
        
        # Supported features - start basic
        self._attr_supported_features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        # If you add target temp:
        # self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        
        # Update attributes based on initial data right away
        self._update_attrs(device_data)


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(f"Entity {self.unique_id}: Coordinator update received. Data: {self.coordinator.data}")
        if self.coordinator.data and self.coordinator.data.get("deviceId") == self._device_id:
            self._update_attrs(self.coordinator.data)
            self.async_write_ha_state()
        else:
            _LOGGER.warning(f"Entity {self.unique_id}: Mismatched device ID in coordinator data or no data.")


    def _update_attrs(self, data: Optional[Dict[str, Any]] = None):
        """Update entity attributes from API data."""
        if data is None:
            _LOGGER.debug(f"Entity {self.unique_id}: No data provided for attribute update.")
            # Potentially mark as unavailable or retain last known state
            # For now, we do nothing if no data, relying on coordinator to provide it
            return

        _LOGGER.debug(f"Entity {self.unique_id}: Updating attributes with data: {data}")
        
        # Example: Extract power state. API response format dependent.
        # The 'status' field in get_things seems to be a JSON string.
        device_status_str = data.get("status")
        actual_status = {}
        if device_status_str:
            try:
                actual_status = json.loads(device_status_str)
                _LOGGER.debug(f"Entity {self.unique_id}: Parsed device status: {actual_status}")
            except json.JSONDecodeError:
                _LOGGER.error(f"Entity {self.unique_id}: Could not parse device status JSON: {device_status_str}")
        
        power_state = actual_status.get("powerSwitch") # 0 for off, 1 for on
        if power_state == 1:
            self._attr_hvac_mode = HVACMode.COOL # Or whatever the active mode is if available
        elif power_state == 0:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            # If powerSwitch is not present or has an unexpected value, HVAC mode is unknown
            # This might happen if the device is offline or status is not fully reported
            _LOGGER.warning(f"Entity {self.unique_id}: powerSwitch state is unknown or not 0/1: {power_state}. Current HVAC mode: {self._attr_hvac_mode}")
            # Keep previous mode or set to OFF or UNKNOWN depending on preference.
            # self._attr_hvac_mode = HVACMode.OFF # Fallback, or None

        # Example for current temperature (if available in 'actual_status')
        # current_temp = actual_status.get("currentTemperature")
        # if current_temp is not None:
        #    self._attr_current_temperature = float(current_temp)

        # Example for target temperature (if available)
        # target_temp = actual_status.get("targetTemperature")
        # if target_temp is not None:
        #    self._attr_target_temperature = float(target_temp)
        #    if ClimateEntityFeature.TARGET_TEMPERATURE not in self._attr_supported_features:
        #        self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        _LOGGER.debug(f"Entity {self.unique_id}: Updated HVAC mode to {self._attr_hvac_mode}")


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
        elif hvac_mode in [HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO, HVACMode.FAN_ONLY]: # Add other modes if supported
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
            self._attr_hvac_mode = HVACMode.COOL # Assume COOL when turned on, adjust if state known
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

    # Implement other methods like async_set_temperature if your AC supports it
    # async def async_set_temperature(self, **kwargs: Any) -> None:
    #     """Set new target temperature."""
    #     temperature = kwargs.get(ATTR_TEMPERATURE)
    #     if temperature is None:
    #         return
    #     _LOGGER.info(f"Entity {self.unique_id}: Setting temperature to {temperature}")
    #     try:
    #         await self._api.control_device(self._device_id, {"targetTemperature": temperature}) # Example command
    #         self._attr_target_temperature = temperature
    #         self.async_write_ha_state()
    #         await self.coordinator.async_request_refresh()
    #     except (TclApiError, TclAuthError) as e:
    #         _LOGGER.error(f"Entity {self.unique_id}: Error setting temperature: {e}")
