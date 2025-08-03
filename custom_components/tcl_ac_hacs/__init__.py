"""The TCL AC HACS integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from functools import partial # Added for coordinator

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, PLATFORMS, CONF_USERNAME, CONF_PASSWORD, 
    CONF_SELECTED_DEVICES, DEFAULT_SCAN_INTERVAL
)
from .api import TclAcApi, TclApiError, TclAuthError

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TCL AC HACS from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Initialize API with credentials from config entry
    api = TclAcApi(
        session=aiohttp_client.async_get_clientsession(hass),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD]
    )
    
    # Perform authentication
    try:
        await api.authenticate()
    except TclAuthError as e:
        _LOGGER.error(f"Authentication failed: {e}")
        # No need to raise ConfigEntryNotReady, auth errors are handled by config flow
        return False # Indicate setup failure
    except TclApiError as e:
        _LOGGER.error(f"API error during authentication: {e}")
        raise ConfigEntryNotReady(f"API error during authentication: {e}") from e
    
    entry_data = {
        "api": api,
        "coordinators": {},
        "all_devices_info": []
    }
    # Do not assign to hass.data yet, only if all critical fetches succeed.

    # Fetch all devices info once
    try:
        _LOGGER.info("Fetching all devices info during integration setup.")
        device_list_response = await api.get_devices()
        if device_list_response and "data" in device_list_response:
            entry_data["all_devices_info"] = device_list_response["data"]
            _LOGGER.debug(f"Fetched {len(entry_data['all_devices_info'])} device(s) info.")
        else:
            _LOGGER.error("Failed to fetch initial device list or list is malformed.")
            raise ConfigEntryNotReady("Failed to fetch device list during setup.")
    except (TclApiError, TclAuthError) as e: # TclAuthError could happen if token expired between authenticate and get_devices
        _LOGGER.error(f"API error fetching device list: {e}")
        raise ConfigEntryNotReady(f"API error fetching device list: {e}") from e
    except Exception as e: # Catch any other unexpected error
        _LOGGER.error(f"Unexpected error fetching device list: {e}", exc_info=True)
        raise ConfigEntryNotReady(f"Unexpected error fetching device list: {e}") from e

    if not entry_data["all_devices_info"]:
        _LOGGER.warning("No devices found on the account.")
        # Still proceed to set up hass.data and forward, platforms will handle no devices.
    
    # Create coordinators for selected devices
    selected_device_ids = entry.data.get(CONF_SELECTED_DEVICES, [])
    if not selected_device_ids:
        _LOGGER.warning("No devices selected in config entry for setup.")
    
    for device_id in selected_device_ids:
        # Ensure this device is in the fetched list before creating coordinator
        device_info = next((d for d in entry_data["all_devices_info"] if d.get("deviceId") == device_id), None)
        if not device_info:
            _LOGGER.warning(f"Device ID {device_id} was selected but not found in the fetched device list. Skipping coordinator setup for it.")
            continue

        try:
            _LOGGER.info(f"Setting up coordinator for device_id: {device_id}")
            # Fetch initial shadow data for this specific device
            device_shadow_data = await api.get_device_shadow(device_id)
            # Not checking if shadow is empty here, coordinator can start with empty data if needed, though less ideal.
            # Platforms should handle empty coordinator.data if necessary.

            coordinator = DataUpdateCoordinator(
                hass,
                _LOGGER,
                name=f"tcl_ac_device_{device_id}",
                update_method=partial(_async_update_data_static, hass, api, device_id),
                update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            )
            if device_shadow_data: # Populate initial data if successfully fetched
                coordinator.data = device_shadow_data
            else:
                _LOGGER.warning(f"Device {device_id} shadow was not found or empty during setup. Coordinator will start without data.")
            
            # Perform initial refresh to ensure data is available for platforms
            # This is crucial if platforms expect data immediately.
            # However, if shadow was fetched, it's already initial data.
            # If shadow fetch failed, first_refresh will try again.
            if not coordinator.data : # Only if data is still missing
                 _LOGGER.info(f"Performing initial refresh for coordinator of device {device_id} as shadow was not available.")
                 await coordinator.async_config_entry_first_refresh()


            entry_data["coordinators"][device_id] = coordinator
            _LOGGER.info(f"Coordinator created for device_id: {device_id}")

        except UpdateFailed as e: # Catch UpdateFailed from first_refresh specifically
            _LOGGER.error(f"Initial data refresh failed for device {device_id}: {e}. Entities may not be set up correctly.")
            # Continue, platform will handle missing coordinator data.
        except (TclApiError, TclAuthError) as e:
            _LOGGER.error(f"API error setting up coordinator for device {device_id}: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error setting up coordinator for device {device_id}: {e}", exc_info=True)

    hass.data[DOMAIN][entry.entry_id] = entry_data # Now assign fully prepared entry_data
    
    # Set up platforms
    _LOGGER.info(f"Forwarding setup to platforms: {PLATFORMS}")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def _async_update_data_static(hass: HomeAssistant, api: TclAcApi, device_id: str) -> dict:
    """Fetch data for a single TCL AC device for the coordinator."""
    _LOGGER.info(f"Coordinator update triggered for device {device_id}")
    try:
        device_data = await api.get_device_shadow(device_id)
        if not device_data:
            _LOGGER.warning(f"Static Coordinator Update: Device {device_id} shadow not found.")
            raise UpdateFailed(f"Device {device_id} shadow not found.")
        _LOGGER.info(f"Coordinator update successful for device {device_id}")
        return device_data
    except TclAuthError as err:
        _LOGGER.error(f"Static Coordinator Update: Auth error for {device_id}: {err}")
        raise UpdateFailed(f"Authentication error: {err}") from err
    except TclApiError as err:
        _LOGGER.error(f"Static Coordinator Update: API error for {device_id}: {err}")
        raise UpdateFailed(f"API error: {err}") from err
    except Exception as err:
        _LOGGER.error(f"Static Coordinator Update: Unexpected error for {device_id}: {err}", exc_info=True)
        raise UpdateFailed(f"Unexpected error: {err}") from err

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Clean up shared data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok
