"""
Manages multi-turn diagnostic conversations.
Each session tracks the problem, accumulated answers, and current phase.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ConversationTurn:
    role: str  # "user" | "assistant"
    content: str
    questions: list[str] = field(default_factory=list)
    diagnostic: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ConversationSession:
    session_id: str
    original_problem: str = ""
    category: str = "general"
    turns: list[ConversationTurn] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    question_index: int = 0
    pending_questions: list[str] = field(default_factory=list)
    resolved: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConversationManager:
    """In-memory store of active diagnostic conversations."""

    def __init__(self, max_sessions: int = 200) -> None:
        self._sessions: dict[str, ConversationSession] = {}
        self._max = max_sessions

    def create(self, session_id: str = "") -> ConversationSession:
        sid = session_id or uuid.uuid4().hex[:16]
        # Evict oldest if full
        if len(self._sessions) >= self._max:
            oldest = next(iter(self._sessions))
            del self._sessions[oldest]
        session = ConversationSession(session_id=sid)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> ConversationSession | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str = "") -> ConversationSession:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.create(session_id)

    def end(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.resolved = True

    def cleanup(self) -> int:
        """Remove resolved sessions older than 1 hour."""
        now = datetime.now(timezone.utc)
        to_remove = []
        for sid, s in self._sessions.items():
            if s.resolved:
                to_remove.append(sid)
        for sid in to_remove:
            del self._sessions[sid]
        return len(to_remove)
