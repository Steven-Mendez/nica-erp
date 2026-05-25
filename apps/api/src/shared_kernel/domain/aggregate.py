from __future__ import annotations

from shared_kernel.domain.events import DomainEvent


class Entity[IdT]:
    """Has identity; equal by id."""

    __slots__ = ("_id",)

    def __init__(self, id_: IdT) -> None:
        self._id = id_

    @property
    def id(self) -> IdT:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._id))


class AggregateRoot[IdT](Entity[IdT]):
    """Root of an aggregate; collects domain events until pulled."""

    __slots__ = ("_events",)

    def __init__(self, id_: IdT) -> None:
        super().__init__(id_)
        self._events: list[DomainEvent] = []

    def _record(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Return and clear pending events."""
        events, self._events = self._events, []
        return events


__all__ = ["AggregateRoot", "Entity"]
