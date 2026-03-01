"""Config flow for Umami Analytics."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import CannotConnect, InvalidAuth, UmamiApiClient
from .const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    CONF_WEBSITES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class UmamiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Umami Analytics."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._url: str = ""
        self._username: str = ""
        self._password: str = ""
        self._client: UmamiApiClient | None = None
        self._websites: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Step 1: Connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._url = user_input[CONF_URL].rstrip("/")
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            parsed = urlparse(self._url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                errors["base"] = "invalid_url"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_URL): str,
                            vol.Required(CONF_USERNAME): str,
                            vol.Required(CONF_PASSWORD): str,
                        }
                    ),
                    errors=errors,
                )

            # Check if already configured
            await self.async_set_unique_id(self._url)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            self._client = UmamiApiClient(
                session, self._url, self._username, self._password
            )

            try:
                await self._client.login()
                self._websites = await self._client.get_websites()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.error(
                    "Unexpected error during Umami connection: %s",
                    type(err).__name__,
                )
                errors["base"] = "unknown"
            else:
                if not self._websites:
                    errors["base"] = "no_websites"
                else:
                    return await self.async_step_websites()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_websites(
        self, user_input: dict[str, Any] | None = None
    ):
        """Step 2: Website selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_ids = user_input[CONF_WEBSITES]
            # Build website list with names
            selected = [
                {"id": w["id"], "name": w.get("name", w.get("domain", w["id"]))}
                for w in self._websites
                if w["id"] in selected_ids
            ]

            return self.async_create_entry(
                title=f"Umami ({urlparse(self._url).hostname})",
                data={
                    CONF_URL: self._url,
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                },
                options={
                    CONF_WEBSITES: selected,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        # Build multi-select options
        website_options = {
            w["id"]: w.get("name", w.get("domain", w["id"]))
            for w in self._websites
        }

        return self.async_show_form(
            step_id="websites",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_WEBSITES): cv.multi_select(website_options),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> UmamiOptionsFlow:
        """Get the options flow."""
        return UmamiOptionsFlow()


class UmamiOptionsFlow(OptionsFlow):
    """Handle options for Umami Analytics."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage options."""
        if user_input is not None:
            # Fetch full website list to resolve names
            session = async_get_clientsession(self.hass)
            client = UmamiApiClient(
                session,
                self.config_entry.data[CONF_URL],
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )
            try:
                all_websites = await client.get_websites()
            except (CannotConnect, InvalidAuth, aiohttp.ClientError):
                all_websites = []

            selected_ids = user_input.get(CONF_WEBSITES, [])
            selected = [
                {"id": w["id"], "name": w.get("name", w.get("domain", w["id"]))}
                for w in all_websites
                if w["id"] in selected_ids
            ]

            return self.async_create_entry(
                title="",
                data={
                    CONF_WEBSITES: selected,
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                },
            )

        # Get current websites for defaults
        current_websites = self.config_entry.options.get(CONF_WEBSITES, [])
        current_ids = [w["id"] for w in current_websites]

        # Fetch available websites
        session = async_get_clientsession(self.hass)
        client = UmamiApiClient(
            session,
            self.config_entry.data[CONF_URL],
            self.config_entry.data[CONF_USERNAME],
            self.config_entry.data[CONF_PASSWORD],
        )
        try:
            all_websites = await client.get_websites()
        except (CannotConnect, InvalidAuth, aiohttp.ClientError):
            all_websites = current_websites

        website_options = {
            w["id"]: w.get("name", w.get("domain", w["id"]))
            for w in all_websites
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_WEBSITES,
                        default=current_ids,
                    ): cv.multi_select(website_options),
                }
            ),
        )
