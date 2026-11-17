"""In-process telemetry: counters and recent events. Feeds the AI Reliability Copilot.

On Google Cloud the same events also go to Cloud Logging as structured logs.
"""

import logging
from collections import Counter, deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

log = logging.getLogger("kognisync.telemetry")


class Telemetry:
    def __init__(self, clock: Callable[[], datetime], max_events: int = 200):
        self.clock = clock
        self.counters: Counter[str] = Counter()
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)

    def incr(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    def event(self, kind: str, **fields: Any) -> None:
        self.incr(kind)
        record = {"kind": kind, "at": self.clock().isoformat(), **fields}
        self.events.append(record)
        log.info("event", extra={"event": record})

    def snapshot(self) -> dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "recent_events": list(self.events)[-50:],
        }
