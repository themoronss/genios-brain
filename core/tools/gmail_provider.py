"""
Gmail Provider — Read-only

Fetches email threads/messages using the Gmail API.
Read-only scope: gmail.readonly

Returns normalized tool state that matches the MockGmailProvider shape:
    {
        "last_reply_days_ago": int,
        "thread_exists": bool,
        "unread_count": int,
        "threads": [...],       # extra: recent thread subjects
    }
"""

from datetime import datetime, timezone
from layers.layer1_retrieval.r3_tools.provider_base import ToolProvider


class GmailProvider(ToolProvider):
    """Real Gmail provider — read-only access."""

    def __init__(self):
        self._service = None

    @property
    def tool_name(self) -> str:
        return "gmail"

    def supports(self, intent_type: str) -> bool:
        return intent_type in ("follow_up", "reply_email", "send_email", "cold_outreach")

    @property
    def service(self):
        """Lazy-init Gmail service."""
        if self._service is None:
            from googleapiclient.discovery import build
            from core.tools.google_auth import get_google_credentials
            creds = get_google_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch(self, entities: list[str], workspace_id: str) -> dict:
        """
        Fetch recent email threads for the given entities.

        Args:
            entities: Entity names to search for in email threads.
            workspace_id: Current workspace (unused for Gmail).

        Returns:
            Normalized tool state dict.
        """
        try:
            return self._fetch_real(entities)
        except Exception as e:
            # Graceful degradation — return stale data on error
            return {
                "tool_name": "gmail",
                "result_summary": {
                    "last_reply_days_ago": 0,
                    "thread_exists": False,
                    "unread_count": 0,
                    "threads": [],
                    "error": str(e),
                },
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": 60,
            }

    def _fetch_real(self, entities: list[str]) -> dict:
        """Actual Gmail API calls."""
        now = datetime.now(timezone.utc)

        # Build search query from entities
        query_parts = []
        for entity in entities:
            query_parts.append(f'"{entity}"')
        query = " OR ".join(query_parts) if query_parts else "in:inbox"

        # List threads matching the entity
        result = (
            self.service.users()
            .threads()
            .list(userId="me", q=query, maxResults=5)
            .execute()
        )
        threads_data = result.get("threads", [])

        # Get thread details
        threads_summary = []
        last_reply_days_ago = 0
        unread_count = 0

        for thread_info in threads_data[:5]:
            thread = (
                self.service.users()
                .threads()
                .get(userId="me", id=thread_info["id"], format="metadata",
                     metadataHeaders=["Subject", "From", "Date"])
                .execute()
            )

            messages = thread.get("messages", [])
            if not messages:
                continue

            # Extract subject and date from the latest message
            last_msg = messages[-1]
            headers = {
                h["name"]: h["value"]
                for h in last_msg.get("payload", {}).get("headers", [])
            }

            subject = headers.get("Subject", "No subject")
            from_addr = headers.get("From", "Unknown")
            date_str = headers.get("Date", "")

            threads_summary.append({
                "subject": subject,
                "from": from_addr,
                "message_count": len(messages),
                "snippet": last_msg.get("snippet", "")[:100],
            })

            # Check unread
            labels = last_msg.get("labelIds", [])
            if "UNREAD" in labels:
                unread_count += 1

            # Calculate days since last reply
            internal_date_ms = int(last_msg.get("internalDate", 0))
            if internal_date_ms:
                msg_time = datetime.fromtimestamp(internal_date_ms / 1000, tz=timezone.utc)
                days_ago = (now - msg_time).days
                last_reply_days_ago = max(last_reply_days_ago, days_ago)

        return {
            "tool_name": "gmail",
            "query": query,
            "result_summary": {
                "last_reply_days_ago": last_reply_days_ago,
                "thread_exists": len(threads_data) > 0,
                "unread_count": unread_count,
                "threads": threads_summary,
            },
            "fetched_at": now.isoformat(),
            "ttl_seconds": 60,
        }
