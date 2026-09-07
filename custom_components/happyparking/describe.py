"""One place that turns a car record into words.

The notification and the logbook entry have to agree on how a car is named,
and the plate is the only part a person actually reads.
"""
from __future__ import annotations


def car_description(data: dict) -> str:
    """Name a car by its plate, falling back to whatever we do have."""
    if plate := (data.get("car_no") or "").strip():
        return plate
    if (vid := data.get("visit_car_id")) is not None:
        return f"visit {vid}"
    return "Unknown car"
