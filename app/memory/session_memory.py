from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SessionEvent:
    problem: str
    category: str
    confidence: str
    created_at: str


class SessionMemory:
    def __init__(self, max_events: int = 100) -> None:
        self._events: deque[SessionEvent] = deque(maxlen=max_events)

    def add(self, problem: str, category: str, confidence: str) -> None:
        self._events.append(
            SessionEvent(
                problem=problem,
                category=category,
                confidence=confidence,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    def recent(self, limit: int = 10) -> list[dict]:
        return [event.__dict__ for event in list(self._events)[-limit:]]
