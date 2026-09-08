"""One visit list, and what has already been seen in it.

Household and visitor cars come from the same endpoint under a different
path segment and in the same record shape, so the engines treat them
identically. Everything that must NOT be shared between them lives here:
which visits have been seen, which are still awaiting an exit, and which
bus event and entity they surface as.
"""
from __future__ import annotations

from collections.abc import Callable


class Feed:
    """A single visit list (household or visitor)."""

    def __init__(self, kind: str, event_type: str, title: str) -> None:
        self.kind = kind
        self.event_type = event_type
        # Used to name the notification and to label the log line.
        self.title = title
        self.seen: set[str] = set()
        # Visits that have entered but not yet exited. Their rows sink down the
        # list as newer visits arrive, so a sweep must page deep enough to reach
        # them or their exit is never noticed.
        # visitCarId -> entry timestamp, so a sweep knows how far back
        # it has to read before every open visit is accounted for.
        self.open: dict[int, str] = {}
        # Until history has been read once, everything on the server looks new.
        # Emitting then would replay old events as fresh notifications. Each
        # list primes on its own: one of them failing must not silence the other.
        self.primed = False
        # Set by the feed's event entity once it exists, so the bus event can
        # name it and the described logbook row reaches that entity's Activity.
        self.logbook_entity_id: str | None = None
        self.listeners: set[Callable[[str, dict], None]] = set()

    def add_listener(self, cb: Callable[[str, dict], None]) -> Callable[[], None]:
        """Register an entity callback, returning its removal function."""
        self.listeners.add(cb)

        def _remove() -> None:
            self.listeners.discard(cb)

        return _remove
