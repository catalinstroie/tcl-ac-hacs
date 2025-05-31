# custom_components/tcl_ac_hacs/__init__.py
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TclAcApi, TclAuthError
from .const import DOMAIN, PLATFORMS, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TCL AC Controller from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD] # Should be stored securely

    session = async_get_clientsession(hass)
    api = TclAcApi(session, username, password)

    try:
        _LOGGER.info("Attempting initial authentication during setup.")
        # Perform an initial check to ensure credentials are valid
        # get_devices also calls ensure_authenticated
        await api.get_devices() 
    except TclAuthError as e:
        _LOGGER.error(f"Authentication failed for {username}: {e}")
        return False # Abort setup if auth fails
    except Exception as e:
        _LOGGER.error(f"Failed to initialize TCL API: {e}", exc_info=True)
        return False

    hass.data[DOMAIN][entry.entry_id] = api
    
    # Forward setup to platforms (climate)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Successfully unloaded TCL AC Controller entry.")

    return unload_ok
