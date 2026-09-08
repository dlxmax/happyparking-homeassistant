"""Logbook entries for HappyParking car in/out.

Without this the logbook can only say "entered", because that is the whole
of an event entity's state. Which car it was is the one thing worth
recording, so the movement is described from the bus event instead, where
the plate is.
"""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_ICON,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_CAR, EVENT_VISITOR
from .describe import car_description

ICONS = {"entered": "mdi:car-arrow-right", "exited": "mdi:car-arrow-left"}
# Visitor rows say so, so a glance at the logbook separates a guest arriving
# from one of your own cars coming home.
NAMES = {EVENT_CAR: "HappyParking", EVENT_VISITOR: "HappyParking visitor"}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Register descriptions for the household and visitor car events."""

    def _describer(name: str) -> Callable[[Event], dict[str, str]]:
        @callback
        def async_describe_car_event(event: Event) -> dict[str, str]:
            data = event.data
            state = str(data.get("state") or "moved")
            gate = (
                data.get("entry_gate")
                if state == "entered"
                else data.get("exit_gate")
            )
            message = f"{car_description(data)} {state}"
            if gate:
                message = f"{message} at {gate}"
            entry = {
                LOGBOOK_ENTRY_NAME: name,
                LOGBOOK_ENTRY_MESSAGE: message,
                LOGBOOK_ENTRY_ICON: ICONS.get(state, "mdi:car"),
            }
            if entity_id := data.get("entity_id"):
                entry[LOGBOOK_ENTRY_ENTITY_ID] = entity_id
            return entry

        return async_describe_car_event

    for event_type, name in NAMES.items():
        async_describe_event(DOMAIN, event_type, _describer(name))
