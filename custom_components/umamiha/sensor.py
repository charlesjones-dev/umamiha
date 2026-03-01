"""Sensor platform for Umami Analytics."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_WEBSITES, DOMAIN
from .coordinator import UmamiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert text to a slug suitable for entity IDs."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Umami sensors from a config entry."""
    coordinator: UmamiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    websites = entry.options.get(CONF_WEBSITES, [])

    entities = [
        UmamiVisitorSensor(coordinator, website)
        for website in websites
    ]
    async_add_entities(entities)


class UmamiVisitorSensor(CoordinatorEntity[UmamiDataUpdateCoordinator], SensorEntity):
    """Sensor showing active visitors for a Umami website."""

    _attr_icon = "mdi:chart-line"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "visitors"

    def __init__(
        self,
        coordinator: UmamiDataUpdateCoordinator,
        website: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._website_id = website["id"]
        self._website_name = website.get("name", website["id"])

        slug = _slugify(self._website_name)
        self._attr_unique_id = f"umamiha_{self._website_id}_visitors"
        self.entity_id = f"sensor.umami_{slug}_visitors"
        self._attr_name = f"Umami {self._website_name} Visitors"

    @property
    def _website_data(self) -> dict[str, Any] | None:
        """Get data for this website from coordinator."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._website_id)

    @property
    def native_value(self) -> int | None:
        """Return the active visitor count."""
        data = self._website_data
        if data is None:
            return None
        return data.get("visitors", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes for the card."""
        data = self._website_data
        if data is None:
            return {
                "website_name": self._website_name,
                "website_id": self._website_id,
                "countries": [],
                "urls": [],
                "series": [],
            }
        return {
            "website_name": self._website_name,
            "website_id": self._website_id,
            "countries": data.get("countries", []),
            "urls": data.get("urls", []),
            "series": data.get("series", []),
        }

    @property
    def available(self) -> bool:
        """Return True if coordinator has data for this website."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._website_id in self.coordinator.data
        )
