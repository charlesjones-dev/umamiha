"""Umami Analytics integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UmamiApiClient
from .const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    CONF_WEBSITES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VERSION,
)
from .coordinator import UmamiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CARD_URL = "/umamiha/umami-analytics-card.js"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Umami Analytics from a config entry."""
    session = async_get_clientsession(hass)
    client = UmamiApiClient(
        session,
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    await client.login()

    websites = entry.options.get(CONF_WEBSITES, [])
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = UmamiDataUpdateCoordinator(
        hass, client, websites, scan_interval
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await _register_frontend(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _register_frontend(hass: HomeAssistant) -> None:
    """Register the custom Lovelace card JS file and auto-add as Lovelace resource."""
    # Skip if already registered (happens on entry reload after options change)
    if hass.data.get(f"{DOMAIN}_frontend_registered"):
        return
    hass.data[f"{DOMAIN}_frontend_registered"] = True

    from homeassistant.components.http import StaticPathConfig

    card_path = str(Path(__file__).parent / "www" / "umami-analytics-card.js")

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, card_path, False)]
    )

    # Auto-register as a Lovelace resource so users don't have to manually add it
    try:
        resources = hass.data.get("lovelace_resources")
        if resources is not None:
            existing = [
                r for r in resources.async_items()
                if r.get("url", "").startswith(CARD_URL)
            ]
            if not existing:
                await resources.async_create_item(
                    {"res_type": "module", "url": f"{CARD_URL}?v={VERSION}"}
                )
        else:
            _LOGGER.debug(
                "Lovelace resources not available; "
                "user may need to add resource manually"
            )
    except Exception:
        _LOGGER.warning("Failed to auto-register Lovelace resource", exc_info=True)
