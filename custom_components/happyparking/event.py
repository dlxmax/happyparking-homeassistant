"""Event entity that fires on each household car in/out."""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_TYPES
from .coordinator import HappyParkingCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the HappyParking event entity."""
    coordinator: HappyParkingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HappyParkingCarEvent(coordinator, entry)])


class HappyParkingCarEvent(EventEntity):
    """Fires 'entered'/'exited' with the car record as attributes."""

    _attr_name = "HappyParking car in/out"
    _attr_icon = "mdi:car-arrow-right"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: HappyParkingCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_car"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._coordinator.add_listener(self._handle))

    @callback
    def _handle(self, state: str, data: dict) -> None:
        self._trigger_event(state, data)
        self.async_write_ha_state()
