"""Device triggers for HappyParking: a car or a visitor entering or leaving.

Each one is the bus event the integration already fires, narrowed to this
device and one direction, so an automation built from the editor shows up in
the device's Related list without anyone typing an id. An optional plate
narrows it further to particular cars.
"""
from __future__ import annotations

import inspect
import re
from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_CAR, EVENT_VISITOR

CONF_PLATE = "plate"

# type -> (bus event, direction)
TRIGGERS: dict[str, tuple[str, str]] = {
    "car_entered": (EVENT_CAR, "entered"),
    "car_exited": (EVENT_CAR, "exited"),
    "visitor_entered": (EVENT_VISITOR, "entered"),
    "visitor_exited": (EVENT_VISITOR, "exited"),
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGERS),
        vol.Optional(CONF_PLATE): str,
    }
)

_NOISE = re.compile(r"[\s\-]")


def _normalise(plate: str) -> str:
    return _NOISE.sub("", plate)


def plate_terms(value: str | None) -> list[str]:
    """Split "12가3456, 7890" into the terms a plate is checked against."""
    return [t for t in (_normalise(p) for p in (value or "").split(",")) if t]


def plate_matches(car_no: str | None, terms: list[str]) -> bool:
    """A plate matches a term it ends with: the whole plate, or its last digits.

    Spaces and hyphens are ignored on both sides, since the app and people
    write plates both with and without them.
    """
    if not terms:
        return True
    plate = _normalise(car_no or "")
    return bool(plate) and any(plate.endswith(term) for term in terms)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Offer all four; a disabled visitor list simply never fires its two."""
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in TRIGGERS
    ]


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """Let the editor offer the optional plate filter."""
    return {"extra_fields": vol.Schema({vol.Optional(CONF_PLATE): str})}


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for this device's event in one direction, optionally for some plates."""
    event_type, state = TRIGGERS[config[CONF_TYPE]]
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: event_type,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                "state": state,
            },
        }
    )
    terms = plate_terms(config.get(CONF_PLATE))
    if terms:
        inner = action

        # Async, not a bare function: HassJob would run a bare one in a thread.
        async def action(  # noqa: F811 - the narrowed action replaces the original
            run_variables: dict[str, Any], context: Context | None = None
        ) -> Any:
            event = run_variables.get("trigger", {}).get("event")
            car_no = event.data.get("car_no") if event is not None else None
            if not plate_matches(car_no, terms):
                return None
            result = inner(run_variables, context)
            if inspect.isawaitable(result):
                result = await result
            return result

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
