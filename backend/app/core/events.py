"""Bus de eventos in-process.

No hay broker ni Redis: la app corre en una sola maquina. El bus existe para
desacoplar efectos secundarios (invalidar cache, log de auditoria, metricas)
del caso de uso que los provoca.

Topicos actuales:
- ``measurement.created``  payload: {"astronaut_code": str, "site": str}
- ``measurement.imported`` payload: {"astronaut_code": str, "created": int}
- ``astronaut.created``    payload: {"astronaut_code": str}
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers[topic].append(handler)

    def publish(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        event = payload or {}
        for handler in self._subscribers.get(topic, []):
            try:
                handler(event)
            except Exception:  # un suscriptor roto no debe tumbar la request
                logger.exception("event handler failed topic=%s handler=%s", topic, handler)

    def clear(self) -> None:
        self._subscribers.clear()


bus = EventBus()
