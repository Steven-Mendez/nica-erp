"""EventBus port + in-process implementation.

Domain events stay intra-context and are dispatched synchronously here.
Inter-context (integration) events travel through the outbox — not this bus.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Protocol

from shared_kernel.domain.events import DomainEvent

Handler = Callable[[DomainEvent], None]


class EventBus(Protocol):
    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None: ...
    def publish(self, event: DomainEvent) -> None: ...


class InProcessEventBus:
    """Synchronous dispatcher for domain events within a single process."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            handler(event)
