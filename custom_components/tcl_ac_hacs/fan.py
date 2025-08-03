# custom_components/tcl_ac_hacs/fan.py
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
    # SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH are not directly importable
    # or may be deprecated depending on HA version. We'll use string literals.
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)


from .api import TclAcApi, TclApiError, TclAuthError
from .const import (
    DOMAIN,
    CONF_SELECTED_DEVICES,
    API_PARAM_NEW_WIND_SET_MODE,
    API_PARAM_NEW_WIND_STRENGTH,
    API_PARAM_NEW_WIND_AUTO_SWITCH,
    API_PARAM_NEW_WIND_SWITCH, # Added for explicit on/off
    API_FRESH_AIR_MODE_FRESH,
    API_FRESH_AIR_MODE_BREATHING,
    API_FRESH_AIR_MODE_EXHAUST,
    API_FRESH_AIR_MODE_PURIFICATION,
    API_FRESH_AIR_AUTO_OFF,
    API_FRESH_AIR_AUTO_ON,
    PRESET_FRESH_AIR_FRESH,
    PRESET_FRESH_AIR_BREATHING,
    PRESET_FRESH_AIR_EXHAUST,
    PRESET_FRESH_AIR_PURIFICATION,
    FAN_SPEED_LOW, # Imported from .const
    FAN_SPEED_MEDIUM, # Imported from .const
    FAN_SPEED_HIGH, # Imported from .const
    FAN_SPEED_AUTO, # Custom "auto" speed if API supports it via newWindAutoSwitch
)

_LOGGER = logging.getLogger(__name__)

# Define the preset modes for the fan entity
SUPPORTED_PRESET_MODES = [
    PRESET_FRESH_AIR_FRESH,
    PRESET_FRESH_AIR_BREATHING,
    PRESET_FRESH_AIR_EXHAUST,
    PRESET_FRESH_AIR_PURIFICATION,
]

# Mapping HA preset modes to API values for newWindSetMode
HA_PRESET_TO_API_MODE = {
    PRESET_FRESH_AIR_FRESH: API_FRESH_AIR_MODE_FRESH,
    PRESET_FRESH_AIR_BREATHING: API_FRESH_AIR_MODE_BREATHING,
    PRESET_FRESH_AIR_EXHAUST: API_FRESH_AIR_MODE_EXHAUST,
    PRESET_FRESH_AIR_PURIFICATION: API_FRESH_AIR_MODE_PURIFICATION,
}
API_MODE_TO_HA_PRESET = {v: k for k, v in HA_PRESET_TO_API_MODE.items()}

# API newWindStrength values (1, 2, 3)
API_SPEED_VALUES = [1, 2, 3] 

# Mapping HA speeds to API values
# For simplicity, let's map HA's LOW, MEDIUM, HIGH to API's 1, 2, 3
HA_SPEED_TO_API_STRENGTH = {
    FAN_SPEED_LOW: 1,
    FAN_SPEED_MEDIUM: 2,
    FAN_SPEED_HIGH: 3,
}
API_STRENGTH_TO_HA_SPEED = {v: k for k, v in HA_SPEED_TO_API_STRENGTH.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TCL Fresh Air fan entities from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    api: TclAcApi = entry_data["api"]
    coordinators: Dict[str, DataUpdateCoordinator] = entry_data["coordinators"]
    all_devices_info: List[Dict[str, Any]] = entry_data["all_devices_info"] # Should be populated by climate or other earlier platform

    selected_device_ids: List[str] = entry.data.get(CONF_SELECTED_DEVICES, [])
    entities_to_add = []

    if not all_devices_info:
        _LOGGER.warning("Fan Setup: all_devices_info is not populated. Climate platform might not have run or failed. Cannot set up fans.")
        return

    for device_id in selected_device_ids:
        coordinator = coordinators.get(device_id)
        if not coordinator:
            _LOGGER.warning(f"Fan Setup: No coordinator found for device_id {device_id}. Skipping fan entity.")
            continue

        if not coordinator.data:
            _LOGGER.warning(f"Fan Setup: Coordinator for device {device_id} has no data. Skipping fan entity.")
            # It's assumed the coordinator, if existing, would have been populated with data by climate.py
            continue
            
        device_info_data = next((d for d in all_devices_info if d.get("deviceId") == device_id), None)
        if not device_info_data:
            _LOGGER.warning(f"Fan Setup: No device_info_data found for device_id {device_id} in all_devices_info. Skipping fan entity.")
            continue
        
        entities_to_add.append(TclFreshAirFan(coordinator, api, device_info_data, device_id))

    if entities_to_add:
        async_add_entities(entities_to_add, update_before_add=False) # Data should be fresh from coordinator
        _LOGGER.info(f"Added {len(entities_to_add)} TCL Fresh Air fan entities.")

class TclFreshAirFan(CoordinatorEntity, FanEntity):
    """Representation of a TCL Fresh Air Fan."""

    _attr_has_entity_name = True
    _attr_name = "Fresh Air" # Will be prefixed by device name

    def __init__(self, coordinator: DataUpdateCoordinator, api: TclAcApi, device_info_data: Dict[str, Any], device_id: str):
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_id
        self._device_name = device_info_data.get("nickName", f"TCL AC {device_id[:6]}") # Used for unique_id and device_info

        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_fresh_air"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device_id)}, # Links to the same device as climate
            "name": self._device_name,
            "manufacturer": "TCL",
            # model and sw_version can be inherited from the main device if available
        }

        self._attr_supported_features = (
            FanEntityFeature.PRESET_MODE |
            FanEntityFeature.SET_SPEED |  # For named speeds via speed_list + async_set_speed
            FanEntityFeature.TURN_ON |
            FanEntityFeature.TURN_OFF
        )
        self._attr_preset_modes = SUPPORTED_PRESET_MODES
        
        # Initialize attributes
        self._attr_is_on = None
        self._attr_percentage = None # Explicitly set to None if not used
        self._attr_speed: Optional[str] = None # Current named speed
        self._attr_preset_mode = None
        # self._attr_speed_count is not needed if we use speed_list

        self._update_attrs(coordinator.data) # Initial update

    @property
    def speed_list(self) -> list[str]:
        """Get the list of available speeds."""
        return [FAN_SPEED_LOW, FAN_SPEED_MEDIUM, FAN_SPEED_HIGH, FAN_SPEED_AUTO]

    # Remove percentage_step as we are moving to named speeds primarily
    # @property
    # def percentage_step(self) -> float:
    #    """Return the step size for percentage."""
    #    return 100 / self._attr_speed_count

    @property # Added for current speed
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        return self._attr_speed

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(f"Fresh Air Fan {self.unique_id}: Coordinator update. Data: {self.coordinator.data}")
        self._update_attrs(self.coordinator.data)
        self.async_write_ha_state()

    def _update_attrs(self, data: Optional[Dict[str, Any]] = None):
        """Update entity attributes from API data (device shadow)."""
        if data is None or "state" not in data or "reported" not in data["state"]:
            _LOGGER.debug(f"Fresh Air Fan {self.unique_id}: No data or malformed data for attribute update.")
            self._attr_is_on = None # Or False, to indicate it's off or state unknown
            self._attr_percentage = None
            self._attr_preset_mode = None
            return

        reported_state = data["state"]["reported"]
        _LOGGER.debug(f"Fresh Air Fan {self.unique_id}: Reported state: {reported_state}")

        # Determine if fan is on based on newWindSwitch.
        # This is the primary and most reliable source of the on/off state.
        # The fan is 'on' if and only if newWindSwitch is 1.
        new_wind_switch_state = reported_state.get(API_PARAM_NEW_WIND_SWITCH)
        self._attr_is_on = (new_wind_switch_state == 1)
        
        strength = reported_state.get(API_PARAM_NEW_WIND_STRENGTH)
        auto_switch = reported_state.get(API_PARAM_NEW_WIND_AUTO_SWITCH)

        # Update preset mode
        api_mode = reported_state.get(API_PARAM_NEW_WIND_SET_MODE)
        self._attr_preset_mode = API_MODE_TO_HA_PRESET.get(api_mode)

        # Update speed
        if auto_switch == API_FRESH_AIR_AUTO_ON:
            self._attr_speed = FAN_SPEED_AUTO
        elif strength is not None and strength in API_STRENGTH_TO_HA_SPEED:
            self._attr_speed = API_STRENGTH_TO_HA_SPEED[strength]
        elif self._attr_is_on: # If it's on but speed is unknown, perhaps set to a default or None
            self._attr_speed = None # Or a default like FAN_SPEED_LOW
        else: # Off
            self._attr_speed = None # No speed when off (or could be previous speed)

        _LOGGER.debug(f"Fresh Air Fan {self.unique_id}: Updated: On={self._attr_is_on}, Preset={self._attr_preset_mode}, Speed={self._attr_speed}, Strength={strength}, AutoSwitch={auto_switch}")

    async def async_turn_on(self, speed: Optional[str] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        _LOGGER.info(f"Fresh Air Fan {self.unique_id}: Turning ON. Speed: {speed}, Preset: {preset_mode}")
        
        command_payload = {"switch_state": 1}

        if preset_mode is not None:
            if preset_mode not in self.preset_modes:
                _LOGGER.warning(f"Fresh Air Fan {self.unique_id}: Unsupported preset mode for turn_on: {preset_mode}")
            else:
                command_payload["mode"] = HA_PRESET_TO_API_MODE.get(preset_mode)
                self._attr_preset_mode = preset_mode # Optimistic

        if speed is not None:
            if speed.lower() == FAN_SPEED_AUTO.lower():
                command_payload["strength"] = 0 # As per mitmproxy for auto
                command_payload["auto_switch"] = API_FRESH_AIR_AUTO_ON
                self._attr_speed = FAN_SPEED_AUTO # Optimistic
            elif speed.lower() in HA_SPEED_TO_API_STRENGTH:
                command_payload["strength"] = HA_SPEED_TO_API_STRENGTH[speed.lower()]
                command_payload["auto_switch"] = API_FRESH_AIR_AUTO_OFF # Manual speed
                self._attr_speed = speed.lower() # Optimistic
            else:
                _LOGGER.warning(f"Fresh Air Fan {self.unique_id}: Unsupported speed for turn_on: {speed}")
        elif not preset_mode and not self._attr_is_on: 
            # If just "turn_on" and it's off, send switch_state=1. Device will use last/default.
            # If we want to force a default speed (e.g. low), add it to command_payload here.
            # command_payload["strength"] = HA_SPEED_TO_API_STRENGTH[FAN_SPEED_LOW]
            # command_payload["auto_switch"] = API_FRESH_AIR_AUTO_OFF
            pass

        try:
            await self._api.async_set_fresh_air(self._device_id, **command_payload)
            self._attr_is_on = True
            self.async_write_ha_state()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Fresh Air Fan {self.unique_id}: Error turning on/setting params: {e}")
        
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info(f"Fresh Air Fan {self.unique_id}: Turning OFF")
        try:
            await self._api.async_set_fresh_air(self._device_id, switch_state=0)
            self._attr_is_on = False
            self._attr_speed = None # No speed when off
            self.async_write_ha_state()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Fresh Air Fan {self.unique_id}: Error turning off: {e}")
        await self.coordinator.async_request_refresh()

    async def async_set_speed(self, speed: str) -> None:
        _LOGGER.info(f"Fresh Air Fan {self.unique_id}: Setting speed to {speed}")
        
        api_strength = None
        auto_switch_val = API_FRESH_AIR_AUTO_OFF

        if speed.lower() == FAN_SPEED_AUTO.lower():
            api_strength = 0 # As per mitmproxy log for auto mode
            auto_switch_val = API_FRESH_AIR_AUTO_ON
        elif speed.lower() in HA_SPEED_TO_API_STRENGTH:
            api_strength = HA_SPEED_TO_API_STRENGTH[speed.lower()]
        else:
            _LOGGER.warning(f"Fresh Air Fan {self.unique_id}: Unsupported speed: {speed}")
            return

        try:
            await self._api.async_set_fresh_air(
                self._device_id,
                switch_state=1, # Ensure it's on
                strength=api_strength,
                auto_switch=auto_switch_val
            )
            self._attr_speed = speed.lower()
            self._attr_is_on = True
            self.async_write_ha_state()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Fresh Air Fan {self.unique_id}: Error setting speed: {e}")
        await self.coordinator.async_request_refresh()
        
    # Remove async_set_percentage as we are using named speeds with async_set_speed
    # async def async_set_percentage(self, percentage: int) -> None:
    #     ...

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        _LOGGER.info(f"Fresh Air Fan {self.unique_id}: Setting preset mode to {preset_mode}")
        if preset_mode not in SUPPORTED_PRESET_MODES:
            _LOGGER.warning(f"Fresh Air Fan {self.unique_id}: Unsupported preset mode: {preset_mode}")
            return

        api_mode = HA_PRESET_TO_API_MODE.get(preset_mode)
        if api_mode is None: # Should not happen if preset_mode is in SUPPORTED_PRESET_MODES
            _LOGGER.error(f"Fresh Air Fan {self.unique_id}: No API mapping for preset mode: {preset_mode}")
            return
            
        try:
            # When setting a preset, ensure the fan is switched on.
            # If it needs a default speed with the mode, add strength here.
            # For now, assume setting mode on its own is fine if already on,
            # or newWindSwitch=1 will resume last/default speed.
            await self._api.async_set_fresh_air(
                self._device_id, 
                switch_state=1, # Ensure it's on
                mode=api_mode
            )
            self._attr_preset_mode = preset_mode
            self._attr_is_on = True
            self.async_write_ha_state()
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"Fresh Air Fan {self.unique_id}: Error setting preset mode: {e}")
        await self.coordinator.async_request_refresh()

# Note on "auto" speed for Fresh Air:
# The current implementation uses SET_SPEED (percentage) for manual speeds.
# To implement a dedicated "auto" speed, we would need to:
# 1. Add `FAN_SPEED_AUTO` to `SUPPORTED_SPEEDS` (if using named speeds) or handle it in `set_percentage`.
# 2. Modify `async_set_percentage` or add `async_set_speed` to handle an "auto" input.
#    This would involve calling `self._api.async_set_fresh_air` with `auto_switch=API_FRESH_AIR_AUTO_ON`
#    and `strength=0` (based on mitmproxy logs for auto speed).
# 3. Update `_update_attrs` to correctly set `self._attr_percentage` or `self._attr_speed`
#    when `auto_switch == API_FRESH_AIR_AUTO_ON` is reported.
# For now, "auto" speed for fresh air is primarily controlled by the device/app, and HA controls manual speeds.
# The `_update_attrs` sets percentage to 100 if auto_switch is on, as a placeholder.
