# custom_components/tcl_ac_hacs/climate.py
import logging
from typing import Any, Dict, List, Optional
from datetime import timedelta
# import asyncio # No longer needed after removing sync turn_on/off

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

SUPPORTED_HVAC_MODES = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO, HVACMode.FAN_ONLY, HVACMode.DRY]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TCL AC climate entities from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    api: TclAcApi = entry_data["api"]
    coordinators: Dict[str, DataUpdateCoordinator] = entry_data["coordinators"]
    all_devices_info: List[Dict[str, Any]] = entry_data["all_devices_info"]

    selected_device_ids: List[str] = entry.data.get(CONF_SELECTED_DEVICES, [])
    entities_to_add = []

    if not selected_device_ids:
        _LOGGER.warning("No devices selected for TCL AC climate setup.")
        return

    if not all_devices_info:
        _LOGGER.error("Climate Setup: all_devices_info is not populated (should be done by __init__.py). Cannot set up climate entities.")
        return

    for device_id in selected_device_ids:
        device_info_data = next((d for d in all_devices_info if d.get("deviceId") == device_id), None)
        if not device_info_data:
            _LOGGER.warning(f"Climate Setup: Device info for {device_id} not found in all_devices_info. Skipping climate entity.")
            continue

        coordinator = coordinators.get(device_id)
        if not coordinator:
            _LOGGER.warning(f"Climate Setup: No coordinator found for device {device_id}. This should have been created in __init__.py. Skipping climate entity.")
            continue
        
        if not coordinator.data: # Check if coordinator has initial data
            _LOGGER.warning(f"Climate Setup: Coordinator for device {device_id} has no initial data (should be populated by __init__.py). Skipping climate entity.")
            continue

        _LOGGER.info(f"Climate Setup: Preparing climate entity for device {device_info_data.get('nickName', device_id)}")
        entity = TclClimateEntity(coordinator, api, device_info_data, coordinator.data)
        entities_to_add.append(entity)

    if entities_to_add:
        async_add_entities(entities_to_add, update_before_add=False) 
        _LOGGER.info(f"Added {len(entities_to_add)} TCL AC climate entities.")
    else:
        _LOGGER.warning("No TCL AC climate entities were added for this setup.")

# The _async_update_data_local function is removed as it's no longer used.
# Coordinator's update method is defined in __init__.py's _async_update_data_static.

class TclClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a TCL AC Unit."""

    _attr_has_entity_name = True
    
    def __init__(self, coordinator: DataUpdateCoordinator, api: TclAcApi, device_data: Dict[str, Any], device_shadow_data: Dict[str, Any]):
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_data.get("deviceId")
        device_name_default = f"TCL AC {self._device_id[:6]}" if self._device_id else "TCL AC"
        self._device_name = device_data.get("nickName", device_name_default)
        self._attr_name = self._device_name 
        # self._device_shadow_data = device_shadow_data # Not needed if using coordinator.data

        _LOGGER.info(f"Initializing TCLClimateEntity: {self._device_name} (ID: {self._device_id})")
        # _LOGGER.debug(f"Initial device data for {self._device_id}: {device_data}") # device_data is metadata
        _LOGGER.debug(f"Initial shadow data for {self._device_id}: {self.coordinator.data}")


        self._attr_unique_id = f"{DOMAIN}_{self._device_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "TCL",
            "model": device_data.get("deviceType", "Air Conditioner"),
        }

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = SUPPORTED_HVAC_MODES
        self._attr_hvac_mode = HVACMode.OFF 
        
        self._attr_min_temp = 16.0
        self._attr_max_temp = 31.0
        self._attr_target_temperature_step = 0.5
        
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON | 
            ClimateEntityFeature.TURN_OFF |
            ClimateEntityFeature.TARGET_TEMPERATURE
        )
        # Call _update_attrs with the initial data from the coordinator
        self._update_attrs(self.coordinator.data)


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(f"Entity {self.unique_id}: Coordinator update received. Data: {self.coordinator.data}")
        self._update_attrs(self.coordinator.data)
        self.async_write_ha_state()


    def _update_attrs(self, data: Optional[Dict[str, Any]] = None): # Removed device_id param, use self._device_id
        """Update entity attributes from API data."""
        if data is None:
            _LOGGER.debug(f"Entity {self.unique_id}: No data for attribute update from coordinator.")
            return

        reported_state = data.get("state", {}).get("reported", {})
        if not reported_state:
            _LOGGER.debug(f"Entity {self.unique_id}: Reported state is empty or not found in coordinator data.")
            return

        _LOGGER.debug(f"Entity {self.unique_id}: Updating attributes with reported_state: {reported_state}")

        power_state = reported_state.get("powerSwitch")
        target_temp = reported_state.get("targetTemperature")
        current_temp = reported_state.get("currentTemperature")
        mode = reported_state.get("workMode") # This is the API's mode

        if target_temp is not None:
            self._attr_target_temperature = float(target_temp)
        if current_temp is not None:
            self._attr_current_temperature = float(current_temp)

        hvac_mode = HVACMode.OFF
        hvac_action = HVACAction.OFF

        if power_state == 1: # If powered on
            if mode == 0: # API Auto
                hvac_mode = HVACMode.AUTO
                hvac_action = HVACAction.IDLE 
            elif mode == 1: # API Cool
                hvac_mode = HVACMode.COOL
                hvac_action = HVACAction.COOLING
            elif mode == 2: # API Dry
                hvac_mode = HVACMode.DRY
                hvac_action = HVACAction.DRYING
            elif mode == 3: # API Fan Only
                hvac_mode = HVACMode.FAN_ONLY
                hvac_action = HVACAction.FAN
            elif mode == 4: # API Heat
                hvac_mode = HVACMode.HEAT
                hvac_action = HVACAction.HEATING
            else:
                _LOGGER.warning(f"Entity {self.unique_id}: Unknown workMode '{mode}' reported by API. Defaulting to COOL if on.")
                hvac_mode = HVACMode.COOL 
                hvac_action = HVACAction.COOLING
        
        self._attr_hvac_mode = hvac_mode
        self._attr_hvac_action = hvac_action

        _LOGGER.debug(f"Entity {self.unique_id}: Updated HVAC mode to {self._attr_hvac_mode}, action: {self._attr_hvac_action}, target_temp: {self._attr_target_temperature}, current_temp: {self._attr_current_temperature}")

    @property
    def hvac_mode(self) -> HVACMode | None:
        return self._attr_hvac_mode

    @property # Added for hvac_action
    def hvac_action(self) -> HVACAction | None:
        return self._attr_hvac_action

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        _LOGGER.info(f"Entity {self.unique_id}: Setting HVAC mode to {hvac_mode}")
        API_WORK_MODE_MAP = {
            HVACMode.AUTO: 0,
            HVACMode.COOL: 1,
            HVACMode.DRY: 2,
            HVACMode.FAN_ONLY: 3,
            HVACMode.HEAT: 4,
        }

        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode in API_WORK_MODE_MAP:
            try:
                await self._api.set_power(self._device_id, True)
                api_mode = API_WORK_MODE_MAP[hvac_mode]
                await self._api.control_device(self._device_id, {"workMode": api_mode})
                self._attr_hvac_mode = hvac_mode 
                self.async_write_ha_state()
            except (TclApiError, TclAuthError) as e:
                _LOGGER.error(f"Entity {self.unique_id}: Error setting HVAC mode to {hvac_mode}: {e}")
            except Exception as e:
                _LOGGER.exception(f"Entity {self.unique_id}: Unexpected error setting HVAC mode to {hvac_mode}: {e}")
        else:
            _LOGGER.warning(f"Entity {self.unique_id}: Unsupported HVAC mode: {hvac_mode}")
            return
        
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        _LOGGER.info(f"Entity {self.unique_id}: Turning ON")
        try:
            await self._api.set_power(self._device_id, True)
            await self.coordinator.async_request_refresh()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Entity {self.unique_id}: Error turning on: {e}")

    async def async_turn_off(self) -> None:
        _LOGGER.info(f"Entity {self.unique_id}: Turning OFF")
        try:
            await self._api.set_power(self._device_id, False)
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF # Explicitly set action to OFF
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Entity {self.unique_id}: Error turning off: {e}")

    def turn_on(self) -> None: # Should be removed if only async is used
        """Turn the entity on."""
        # This is a synchronous method, prefer async_turn_on in HA
        # For direct calls if needed, but usually not from HA core logic.
        # Consider removing or marking as not for HA use.
        _LOGGER.warning("Synchronous turn_on called. Consider using async_turn_on.")
        asyncio.run_coroutine_threadsafe(self.async_turn_on(), self.hass.loop).result()


    def turn_off(self) -> None: # Should be removed if only async is used
        """Turn the entity off."""
        _LOGGER.warning("Synchronous turn_off called. Consider using async_turn_off.")
        asyncio.run_coroutine_threadsafe(self.async_turn_off(), self.hass.loop).result()


    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning(f"Entity {self.unique_id}: No temperature provided.")
            return

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

# Ensure _async_update_data is defined if it was part of the user's pasted code, otherwise it's fine.
# It was defined above the class in the user's paste.
# The TclClimateEntity class definition ends here.
# The duplicated _async_update_data and the loop from user's paste are removed as they were context, not part of the class.
# The initial _async_update_data at the top level of the file is the correct one.
