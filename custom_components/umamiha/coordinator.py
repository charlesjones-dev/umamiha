"""Data update coordinator for Umami Analytics."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, UmamiApiClient

_LOGGER = logging.getLogger(__name__)

SERIES_REFRESH_SECONDS = 300  # Refresh 24h sparkline series every 5 minutes


class UmamiDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch data from Umami for all configured websites."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: UmamiApiClient,
        websites: list[dict],
        update_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Umami Analytics",
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client
        self.websites = websites
        self._series_cache: dict[str, list[dict]] = {}
        self._series_last_fetch: float = 0

    def _should_fetch_series(self) -> bool:
        """Check if enough time has passed to refresh the 24h series data."""
        return (time.monotonic() - self._series_last_fetch) >= SERIES_REFRESH_SECONDS

    async def _fetch_website_data(
        self, website_id: str, fetch_series: bool
    ) -> dict[str, Any]:
        """Fetch data for a single website. Series is only fetched when due."""
        visitors = await self.client.get_active_visitors(website_id)

        # Skip realtime fetch when no active visitors to reduce egress
        if visitors > 0:
            realtime = await self.client.get_realtime(website_id)
        else:
            realtime = {"countries": [], "urls": []}

        if fetch_series:
            series = await self.client.get_pageview_series(website_id)
            self._series_cache[website_id] = series
        else:
            series = self._series_cache.get(website_id, [])

        return {
            "visitors": visitors,
            "countries": realtime["countries"],
            "urls": realtime["urls"],
            "series": series,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Umami for all websites."""
        try:
            fetch_series = self._should_fetch_series()
            results = await asyncio.gather(
                *[
                    self._fetch_website_data(w["id"], fetch_series)
                    for w in self.websites
                ],
                return_exceptions=True,
            )
            if fetch_series:
                self._series_last_fetch = time.monotonic()

            data: dict[str, Any] = {}
            for website, result in zip(self.websites, results):
                if isinstance(result, Exception):
                    _LOGGER.warning(
                        "Failed to fetch data for %s: %s",
                        website.get("name", website["id"]),
                        result,
                    )
                    # Preserve previous data on partial failure
                    if self.data and website["id"] in self.data:
                        data[website["id"]] = self.data[website["id"]]
                    continue
                data[website["id"]] = result

            if not data and self.websites:
                raise UpdateFailed("Failed to fetch data for all websites")

            return data

        except CannotConnect as err:
            raise UpdateFailed(f"Cannot connect to Umami: {err}") from err
