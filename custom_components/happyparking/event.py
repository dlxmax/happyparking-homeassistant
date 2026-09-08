"""Event entities that fire on each car in/out.

Household and visitor cars get one entity each, so that history, logbook
Activity and any entity-scoped automation keep them apart without needing
to filter on an attribute.
"""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_TYPES, KIND_HOUSEHOLD
from .coordinator import HappyParkingCoordinator
from .feed import Feed

NAMES = {
    KIND_HOUSEHOLD: ("HappyParking car in/out", "mdi:car-arrow-right"),
}
VISITOR_NAME = ("HappyParking visitor in/out", "mdi:car-multiple")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up one event entity per visit list."""
    coordinator: HappyParkingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HappyParkingCarEvent(coordinator, entry, feed) for feed in coordinator.feeds
    )


class HappyParkingCarEvent(EventEntity):
    """Fires 'entered'/'exited' with the car record as attributes."""

    _attr_event_types = EVENT_TYPES

    def __init__(
        self, coordinator: HappyParkingCoordinator, entry: ConfigEntry, feed: Feed
    ) -> None:
        self._coordinator = coordinator
        self._feed = feed
        name, icon = NAMES.get(feed.kind, VISITOR_NAME)
        self._attr_name = name
        self._attr_icon = icon
        # The household entity keeps the unique id it has always had, so its
        # entity id and history survive visitor support being added.
        self._attr_unique_id = (
            f"{entry.entry_id}_car"
            if feed.kind == KIND_HOUSEHOLD
            else f"{entry.entry_id}_{feed.kind}"
        )

    async def async_added_to_hass(self) -> None:
        # So the coordinator can name this entity on the bus event, which is
        # what lands the plate in this entity's own Activity list.
        self._feed.logbook_entity_id = self.entity_id
        self.async_on_remove(self._feed.add_listener(self._handle))

    @callback
    def _handle(self, state: str, data: dict) -> None:
        self._trigger_event(state, data)
        self.async_write_ha_state()
