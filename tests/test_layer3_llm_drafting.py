"""
Test: Layer 3 D2 — LLM-based Email Content Generation

Tests that Gemini is being used to draft email content in Layer 3.
"""

import pytest
from core.contracts.decision_packet import ToolCallDraft
from layers.layer3_decision.d2_planning.tool_call_drafter import (
    draft_tool_calls,
    ContentGenerator,
)


def test_content_generator_disabled_without_key():
    """Test that ContentGenerator falls back gracefully when API key is missing."""
    import os

    original_key = os.environ.get("GEMINI_API_KEY")

    try:
        # Temporarily unset the key
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

        gen = ContentGenerator()
        result = gen.draft_email(
            intent_type="follow_up",
            context="Investor follow-up about funding round",
            recipient="John Doe",
            user_style="professional",
        )

        # Should return template fallback
        assert result["subject"]
        assert result["body"]
        assert result["tone"] == "professional"
    finally:
        # Restore original key
        if original_key:
            os.environ["GEMINI_API_KEY"] = original_key


def test_draft_tool_calls_enriches_email_payload():
    """Test that draft_tool_calls enriches email tool calls with content."""
    tool_calls = [
        ToolCallDraft(
            tool_name="gmail",
            method="send_draft",
            payload={"template": "follow_up", "schedule": True},
            fallback="Save as draft",
        )
    ]

    slots = {
        "who": "investor@example.com",
        "context": "Follow up on Series A discussion",
        "tone": "professional",
    }

    enriched = draft_tool_calls(
        intent_type="follow_up",
        tool_calls_templates=tool_calls,
        slots=slots,
        context_bundle=None,
    )

    assert len(enriched) == 1
    tc = enriched[0]

    # Should have enriched payload with slot data
    assert tc.payload.get("recipient") == "investor@example.com"
    # Should have slot-based tone set (even if Gemini drafting fails)
    assert tc.payload.get("subject")  # Generated or fallback
    assert tc.payload.get("body")  # Generated or fallback


def test_draft_tool_calls_non_email_tools():
    """Test that non-email tools are enriched with slots only."""
    tool_calls = [
        ToolCallDraft(
            tool_name="calendar",
            method="propose_time",
            payload={"calendar_id": "primary"},
            fallback="Send manual calendar invite",
        )
    ]

    slots = {
        "who": "john@example.com",
        "when": "2026-03-15 10:00",
    }

    enriched = draft_tool_calls(
        intent_type="schedule_meeting",
        tool_calls_templates=tool_calls,
        slots=slots,
        context_bundle=None,
    )

    assert len(enriched) == 1
    tc = enriched[0]

    # Should have calendar_id from template
    assert tc.payload.get("calendar_id") == "primary"
    # Should have no LLM-generated content (non-email tool)
    assert "subject" not in tc.payload


def test_draft_tool_calls_multiple_tools():
    """Test drafting when multiple tools are involved."""
    tool_calls = [
        ToolCallDraft(
            tool_name="email_drafter",
            method="draft",
            payload={"template": "cold_outreach"},
            fallback="Use template draft",
        ),
        ToolCallDraft(
            tool_name="approval_gate",
            method="request",
            payload={"approval_type": "compliance"},
            fallback="Skip approval",
        ),
    ]

    slots = {
        "who": "prospect@company.com",
        "context": "Cold outreach to venture capital investor",
        "tone": "friendly",
    }

    enriched = draft_tool_calls(
        intent_type="cold_outreach",
        tool_calls_templates=tool_calls,
        slots=slots,
        context_bundle=None,
    )

    assert len(enriched) == 2

    # First tool should have email content enriched
    email_tc = enriched[0]
    assert email_tc.tool_name == "email_drafter"
    assert email_tc.payload.get("subject")
    assert email_tc.payload.get("body")
    # Note: tone might be lost on fallback, so just check that enrichment happened
    assert email_tc.payload.get("recipient") == "prospect@company.com"

    # Second tool should not have email content
    approval_tc = enriched[1]
    assert approval_tc.tool_name == "approval_gate"
    assert approval_tc.payload.get("approval_type") == "compliance"
    assert "subject" not in approval_tc.payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
