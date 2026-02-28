"""
R3.1 — Tool Provider Base

Abstract interface for tool state providers + mock Gmail provider for MVP.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone


class ToolProvider(ABC):
    """Base class for all tool state providers."""

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Unique name of the tool (e.g. 'gmail', 'calendar')."""
        ...

    @abstractmethod
    def supports(self, intent_type: str) -> bool:
        """Whether this provider is relevant for the given intent type."""
        ...

    @abstractmethod
    def fetch(self, entities: list[str], workspace_id: str) -> dict:
        """
        Fetch current tool state.

        Args:
            entities: Entity names to fetch state for.
            workspace_id: Current workspace.

        Returns:
            Normalized tool state dict.
        """
        ...


class MockGmailProvider(ToolProvider):
    """Mock Gmail provider for development/testing."""

    @property
    def tool_name(self) -> str:
        return "gmail"

    def supports(self, intent_type: str) -> bool:
        return intent_type in ("follow_up", "reply_email", "send_email", "cold_outreach")

    def fetch(self, entities: list[str], workspace_id: str) -> dict:
        return {
            "tool_name": "gmail",
            "query": f"threads for {', '.join(entities) if entities else 'unknown'}",
            "result_summary": {
                "last_reply_days_ago": 10,
                "thread_exists": True,
                "unread_count": 0,
            },
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 60,
        }


class MockCalendarProvider(ToolProvider):
    """Mock Calendar provider for development/testing."""

    @property
    def tool_name(self) -> str:
        return "calendar"

    def supports(self, intent_type: str) -> bool:
        return intent_type in ("schedule_meeting",)

    def fetch(self, entities: list[str], workspace_id: str) -> dict:
        return {
            "tool_name": "calendar",
            "query": "free slots next 7 days",
            "result_summary": {
                "next_free_slot": "2026-03-01T10:00:00Z",
                "busy_slots_today": 3,
            },
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 120,
        }
