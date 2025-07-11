"""The TCL AC HACS integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, PLATFORMS, CONF_USERNAME, CONF_PASSWORD, CONF_REGION
from .api import TclAcApi

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
    await api.authenticate()
    
    # Store API instance and prepare for other shared data
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinators": {},
        "all_devices_info": [] # Will be populated by the first platform that needs it (e.g., climate)
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Clean up shared data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok
