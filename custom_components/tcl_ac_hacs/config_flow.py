# custom_components/tcl_ac_hacs/config_flow.py
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import TclAcApi, TclAuthError, TclApiError
from .const import (
    DOMAIN, 
    CONF_USERNAME, 
    CONF_PASSWORD,
    CONF_SELECTED_DEVICES,
)

_LOGGER = logging.getLogger(__name__)

class TclAcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TCL AC Controller."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._all_devices: Dict[str, str] = {} # device_id: nickName

    async def _test_credentials(self, username: str, password: str) -> Optional[Dict[str, str]]:
        """Test credentials and return available devices if successful."""
        session = async_get_clientsession(self.hass)
        api = TclAcApi(session, username, password)
        try:
            _LOGGER.info(f"ConfigFlow: Testing credentials for {username}")
            devices_response = await api.get_devices()
            _LOGGER.debug(f"ConfigFlow: Get devices response: {devices_response}")
            
            if devices_response and "data" in devices_response:
                discovered_devices = {}
                for device in devices_response["data"]:
                    # Ensure essential keys exist
                    if "deviceId" in device and "nickName" in device:
                        discovered_devices[device["deviceId"]] = device["nickName"]
                    else:
                        _LOGGER.warning(f"Device found with missing deviceId or nickName: {device}")
                _LOGGER.info(f"ConfigFlow: Discovered {len(discovered_devices)} devices.")
                return discovered_devices
            _LOGGER.warning("ConfigFlow: No 'data' in devices response or empty response.")
            return {} # No devices found or malformed response
        except TclAuthError:
            _LOGGER.warning(f"ConfigFlow: Authentication failed for {username}")
            return None # Indicates auth error
        except TclApiError as e:
            _LOGGER.error(f"ConfigFlow: API error while fetching devices: {e}")
            raise # Propagate other API errors to show in UI
        except Exception as e:
            _LOGGER.error(f"ConfigFlow: Unexpected error: {e}", exc_info=True)
            raise # Propagate other errors

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            try:
                available_devices = await self._test_credentials(self._username, self._password)
                if available_devices is None: # Auth error specifically
                    errors["base"] = "invalid_auth"
                elif isinstance(available_devices, dict):
                    self._all_devices = available_devices
                    if not self._all_devices:
                        return self.async_abort(reason="no_devices_found")
                    # Unique ID based on username to prevent multiple entries for same account
                    await self.async_set_unique_id(self._username.lower())
                    self._abort_if_unique_id_configured()
                    return await self.async_step_select_devices()
                
            except TclApiError:
                errors["base"] = "cannot_connect" # Generic API error
            except Exception: # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception in user step")
                errors["base"] = "unknown"

        # Show user form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_select_devices(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle the device selection step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            selected_device_ids = user_input.get(CONF_SELECTED_DEVICES, [])
            if not selected_device_ids:
                errors[CONF_SELECTED_DEVICES] = "no_device_selected"
            else:
                _LOGGER.info(f"ConfigFlow: User selected devices: {selected_device_ids}")
                return self.async_create_entry(
                    title=self._username, # Or a more descriptive title
                    data={
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        # Store selected device IDs in data, not options, for initial setup
                        CONF_SELECTED_DEVICES: selected_device_ids 
                    },
                )

        if not self._all_devices:
             _LOGGER.error("ConfigFlow: No devices available to select, aborting.")
             return self.async_abort(reason="no_devices_found_at_selection")


        # Prepare device selection schema
        # The keys for vol.Optional/Required in multi_select are what get returned.
        # The values are the display names.
        device_options = {
            device_id: f"{name} ({device_id[:8]}...)" for device_id, name in self._all_devices.items()
        }
        
        _LOGGER.debug(f"ConfigFlow: Device options for selection: {device_options}")

        return self.async_show_form(
            step_id="select_devices",
            data_schema=vol.Schema({
                vol.Required(CONF_SELECTED_DEVICES): cv.multi_select(device_options),
            }),
            errors=errors,
            description_placeholders={"username": self._username}
        )

    # Optional: Implement re-authentication if credentials change
    # async def async_step_reauth(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # ...

    # Optional: Implement options flow to change selected devices later
    # @staticmethod
    # @callback
    # def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
    #     return TclAcOptionsFlowHandler(config_entry)

# class TclAcOptionsFlowHandler(config_entries.OptionsFlow):
# ... (for allowing users to change selected devices after setup)
