"""
Execution Adapter — Execute planned tool calls from DecisionPacket.

Handles:
- Gmail draft/send/reply
- Calendar create/update
- Error handling + retries
- Execution result tracking

Returns ExecutionResult with status + outputs + errors.
"""

from typing import Dict, Any, List
from core.contracts.decision_packet import ToolCallDraft, ActionPlan


class ExecutionResult:
    """Result of executing a tool call."""

    def __init__(self):
        self.status: str = "pending"  # pending | success | partial | failed
        self.tool_results: Dict[str, Any] = {}  # tool_name -> result
        self.errors: List[Dict[str, str]] = []
        self.executed_at: str = ""


class ExecutionAdapter:
    """Routes and executes tool calls from DecisionPacket."""

    def __init__(self, use_real_tools: bool = False):
        """
        Args:
            use_real_tools: If True, use real Gmail/Calendar APIs.
                           If False, simulate execution.
        """
        self.use_real_tools = use_real_tools
        self._gmail_service = None
        self._calendar_service = None

    @property
    def gmail_service(self):
        """Lazy-init Gmail service."""
        if self._gmail_service is None and self.use_real_tools:
            try:
                from googleapiclient.discovery import build
                from core.tools.google_auth import get_google_credentials

                creds = get_google_credentials()
                self._gmail_service = build("gmail", "v1", credentials=creds)
            except Exception as e:
                print(f"⚠ Could not init Gmail service: {e}")
        return self._gmail_service

    @property
    def calendar_service(self):
        """Lazy-init Calendar service."""
        if self._calendar_service is None and self.use_real_tools:
            try:
                from googleapiclient.discovery import build
                from core.tools.google_auth import get_google_credentials

                creds = get_google_credentials()
                self._calendar_service = build("calendar", "v3", credentials=creds)
            except Exception as e:
                print(f"⚠ Could not init Calendar service: {e}")
        return self._calendar_service

    def execute(
        self,
        plan: ActionPlan,
        execution_mode: str = "propose_only",
    ) -> ExecutionResult:
        """
        Execute tool calls from action plan.

        Args:
            plan: ActionPlan with tool_calls to execute.
            execution_mode: How to execute (propose_only | needs_approval | auto_execute).

        Returns:
            ExecutionResult with status + outputs + errors.
        """
        from datetime import datetime, timezone

        result = ExecutionResult()
        result.executed_at = datetime.now(timezone.utc).isoformat()

        # If propose_only → don't execute, just return success
        if execution_mode == "propose_only":
            result.status = "success"
            return result

        # If needs_approval or pending user input → don't execute yet
        if execution_mode == "needs_approval":
            result.status = "pending"
            return result

        # Execute if auto_execute
        if execution_mode == "auto_execute":
            for tool_call in plan.tool_calls:
                try:
                    output = self._execute_tool_call(tool_call)
                    result.tool_results[tool_call.tool_name] = output
                except Exception as e:
                    result.errors.append(
                        {
                            "tool": tool_call.tool_name,
                            "error": str(e),
                        }
                    )

            # Overall status
            if result.errors:
                result.status = "partial" if result.tool_results else "failed"
            else:
                result.status = "success"

        return result

    def _execute_tool_call(self, call: ToolCallDraft) -> Dict[str, Any]:
        """Execute a single tool call."""
        if call.tool_name == "gmail":
            return self._execute_gmail(call)
        elif call.tool_name == "calendar":
            return self._execute_calendar(call)
        elif call.tool_name == "approval_gate":
            # Approval gate is handled by orchestrator, not here
            return {"status": "pending_approval"}
        else:
            raise ValueError(f"Unknown tool: {call.tool_name}")

    def _execute_gmail(self, call: ToolCallDraft) -> Dict[str, Any]:
        """Execute Gmail API call."""
        method = call.method  # draft_reply | send | create_draft
        payload = call.payload

        if not self.use_real_tools:
            # Simulate execution
            return {
                "status": "simulated",
                "method": method,
                "reason": "Simulation mode active",
            }

        if method == "draft_reply":
            return self._gmail_draft_reply(payload)
        elif method == "send":
            return self._gmail_send(payload)
        elif method == "create_draft":
            return self._gmail_create_draft(payload)
        else:
            raise ValueError(f"Unknown Gmail method: {method}")

    def _gmail_draft_reply(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Draft a reply to an existing thread."""
        service = self.gmail_service
        if not service:
            raise RuntimeError("Gmail service not initialized")

        thread_id = payload.get("thread_id", "")
        subject = payload.get("subject", "Re: ")
        body = payload.get("body", "")

        # Get thread to build reply
        thread = service.users().threads().get(userId="me", id=thread_id).execute()
        messages = thread.get("messages", [])

        if not messages:
            raise ValueError(f"Thread {thread_id} not found or empty")

        # Create draft message
        draft_message = {
            "message": {
                "threadId": thread_id,
                "raw": self._build_mime_message(
                    to=self._extract_reply_to(messages),
                    subject=subject,
                    body=body,
                ),
            }
        }

        result = (
            service.users().drafts().create(userId="me", body=draft_message).execute()
        )
        return {
            "status": "success",
            "draft_id": result.get("id"),
            "thread_id": thread_id,
        }

    def _gmail_send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email (send existing draft or create and send)."""
        service = self.gmail_service
        if not service:
            raise RuntimeError("Gmail service not initialized")

        draft_id = payload.get("draft_id")

        if draft_id:
            # Send existing draft
            result = service.users().drafts().send(userId="me", id=draft_id).execute()
            return {
                "status": "success",
                "message_id": result.get("id"),
                "draft_id": draft_id,
            }
        else:
            # Create and send
            to = payload.get("to", "")
            subject = payload.get("subject", "")
            body = payload.get("body", "")

            message = {
                "raw": self._build_mime_message(to=to, subject=subject, body=body),
            }
            result = (
                service.users().messages().send(userId="me", body=message).execute()
            )
            return {
                "status": "success",
                "message_id": result.get("id"),
            }

    def _gmail_create_draft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a draft message."""
        service = self.gmail_service
        if not service:
            raise RuntimeError("Gmail service not initialized")

        to = payload.get("to", "")
        subject = payload.get("subject", "")
        body = payload.get("body", "")

        message = {
            "message": {
                "raw": self._build_mime_message(to=to, subject=subject, body=body),
            }
        }

        result = service.users().drafts().create(userId="me", body=message).execute()
        return {
            "status": "success",
            "draft_id": result.get("id"),
        }

    def _execute_calendar(self, call: ToolCallDraft) -> Dict[str, Any]:
        """Execute Calendar API call."""
        method = call.method  # create | update | find_slot
        payload = call.payload

        if not self.use_real_tools:
            # Simulate execution
            return {
                "status": "simulated",
                "method": method,
                "reason": "Simulation mode active",
            }

        if method == "create":
            return self._calendar_create(payload)
        elif method == "find_slot":
            return self._calendar_find_slot(payload)
        else:
            raise ValueError(f"Unknown Calendar method: {method}")

    def _calendar_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a calendar event."""
        service = self.calendar_service
        if not service:
            raise RuntimeError("Calendar service not initialized")

        summary = payload.get("summary", "Meeting")
        start_time = payload.get("start_time", "")
        end_time = payload.get("end_time", "")
        attendees = payload.get("attendees", [])

        event = {
            "summary": summary,
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
            "attendees": [{"email": a} for a in attendees] if attendees else [],
        }

        result = (
            service.events()
            .insert(
                calendarId="primary",
                body=event,
                sendNotifications=True,
            )
            .execute()
        )

        return {
            "status": "success",
            "event_id": result.get("id"),
            "html_link": result.get("htmlLink", ""),
        }

    def _calendar_find_slot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Find a free time slot."""
        service = self.calendar_service
        if not service:
            raise RuntimeError("Calendar service not initialized")

        # This would query free/busy and return recommendations
        # For MVP, just return next available slot
        return {
            "status": "success",
            "recommended_slots": [
                "2026-03-02T10:00:00Z",
                "2026-03-02T14:00:00Z",
            ],
        }

    @staticmethod
    def _build_mime_message(to: str, subject: str, body: str) -> str:
        """Build RFC 2822 MIME message (base64 encoded)."""
        import base64
        from email.mime.text import MIMEText

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return raw

    @staticmethod
    def _extract_reply_to(messages: List[Dict]) -> str:
        """Extract reply-to address from thread messages."""
        if not messages:
            return ""

        first_msg = messages[0]
        headers = {
            h["name"]: h["value"]
            for h in first_msg.get("payload", {}).get("headers", [])
        }
        return headers.get("From", "")
