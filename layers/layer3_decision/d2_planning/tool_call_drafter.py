"""
D2.3 — Tool Call Drafter

Generates tool call payloads with structured, constrained LLM calls.

For email drafting:
- Uses Gemini to generate email content
- Applies tone + style preferences from ContextBundle
- Enforces structured JSON output
- Single LLM call per decision

For other tools:
- Payload provided from template + slots
"""

import json
import os
from typing import Optional

import google.generativeai as genai
from pydantic import BaseModel, Field

from core.contracts.context_bundle import ContextBundle
from core.contracts.decision_packet import ToolCallDraft

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# ============================================================================
# Output Schemas (JSON-serializable)
# ============================================================================


class EmailDraftOutput(BaseModel):
    """Structured output from Gemini for email drafting."""

    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content")
    tone: str = Field(..., description="Detected tone: formal, casual, urgent, etc.")
    summary: Optional[str] = Field(None, description="1-2 sentence summary of message")


# ============================================================================
# Content Generator
# ============================================================================


class ContentGenerator:
    """Generate structured content using Gemini API."""

    def __init__(self):
        if not GEMINI_API_KEY:
            self.enabled = False
            return
        self.enabled = True
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = (
            "gemini-2.5-flash"  # Fastest model, optimized for streaming & low-latency
        )

    def draft_email(
        self,
        intent_type: str,
        context: str,
        recipient: Optional[str] = None,
        user_style: Optional[str] = None,
        thread_context: Optional[str] = None,
    ) -> dict:
        """
        Draft email content using Gemini.

        If GEMINI_API_KEY is not set, returns template placeholders.

        Args:
            intent_type: "follow_up", "reply_email", "cold_outreach", etc.
            context: Context information (e.g., from ContextBundle)
            recipient: Recipient name/email
            user_style: User's preferred tone (e.g., "formal", "casual", "urgent")
            thread_context: Existing email thread (if reply)

        Returns:
            dict with subject, body, tone, summary
        """
        if not self.enabled:
            # Fallback when API key not available
            return {
                "subject": f"[Template] {intent_type} to {recipient or 'Recipient'}",
                "body": f"[Template email body for {intent_type}]\n\nContext: {context}",
                "tone": user_style or "professional",
                "summary": None,
            }

        prompt = self._build_email_prompt(
            intent_type, context, recipient, user_style, thread_context
        )

        try:
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=500,
                ),
            )

            # Parse response as JSON
            response_text = response.text.strip()

            # Extract JSON if wrapped in markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text)
            return {
                "subject": data.get("subject", ""),
                "body": data.get("body", ""),
                "tone": data.get("tone", user_style or "professional"),
                "summary": data.get("summary"),
            }
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            # Fallback if parsing or API call fails
            return {
                "subject": "Follow-up",
                "body": f"[Could not generate email content: {type(e).__name__}]",
                "tone": user_style or "professional",
                "summary": None,
            }

    def _build_email_prompt(
        self,
        intent_type: str,
        context: str,
        recipient: Optional[str],
        user_style: Optional[str],
        thread_context: Optional[str],
    ) -> str:
        """Build the Gemini prompt for email drafting."""

        style_instruction = (
            f"Tone: {user_style}" if user_style else "Tone: professional"
        )

        thread_info = (
            f"\n\nExisting thread context:\n{thread_context}" if thread_context else ""
        )

        prompt = f"""You are an email composer. Draft an email for the following:

Intent: {intent_type}
Recipient: {recipient or "Not specified"}
Context: {context}
{style_instruction}
{thread_info}

Generate a structured JSON response with exactly these fields:
{{
    "subject": "Email subject line",
    "body": "Full email body",
    "tone": "one of: formal, casual, urgent, friendly, professional",
    "summary": "1-2 sentence summary of what you're communicating"
}}

Requirements:
- Subject: concise, clear
- Body: natural language, 100-300 words
- Tone: must match the requested style
- Summary: brief recap of the message intent

Respond with ONLY the JSON, no other text."""

        return prompt


# ============================================================================
# Tool Call Drafter
# ============================================================================


def draft_tool_calls(
    intent_type: str,
    tool_calls_templates: list[ToolCallDraft],
    slots: dict[str, str],
    context_bundle: Optional[ContextBundle] = None,
) -> list[ToolCallDraft]:
    """
    Enrich tool call templates with actual payloads.

    For email drafting (follow_up, reply_email, cold_outreach):
        - Call Gemini to generate email content (if API key available)
        - Embed generated content in tool payload
        - Falls back to template placeholders if GEMINI_API_KEY not set

    For other tools:
        - Use slots to fill template payloads

    Args:
        intent_type: Canonical intent type
        tool_calls_templates: List of ToolCallDraft from template
        slots: Extracted slots (who, what, when, channel, template, context, tone)
        context_bundle: Optional ContextBundle for additional context

    Returns:
        List of enriched ToolCallDraft objects with payloads
    """
    enriched_calls = []

    for tc in tool_calls_templates:
        enriched = tc.model_copy()
        enriched.payload = {**tc.payload}

        # Enrich with slots
        if slots.get("who"):
            enriched.payload["recipient"] = slots["who"]
        if slots.get("template"):
            enriched.payload["template"] = slots["template"]
        if slots.get("when"):
            enriched.payload["schedule_time"] = slots["when"]

        # If this is an email drafting tool call, call Gemini
        if tc.tool_name == "email_drafter" or (
            tc.tool_name == "gmail" and tc.method in ["send_draft", "reply", "send_new"]
        ):
            try:
                generated_content = _draft_email_content(
                    intent_type, slots, context_bundle
                )
                enriched.payload["subject"] = generated_content["subject"]
                enriched.payload["body"] = generated_content["body"]
                enriched.payload["tone"] = generated_content["tone"]
                if generated_content.get("summary"):
                    enriched.payload["summary"] = generated_content["summary"]
            except Exception as e:
                # Fallback to template if LLM fails
                print(
                    f"⚠ Email drafting failed ({type(e).__name__}): {e}. Using template fallback."
                )
                enriched.payload["subject"] = slots.get(
                    "subject", f"Email to {slots.get('who', 'recipient')}"
                )
                enriched.payload["body"] = slots.get(
                    "body", f"[Email body for {intent_type}]"
                )

        enriched_calls.append(enriched)

    return enriched_calls


def _draft_email_content(
    intent_type: str,
    slots: dict[str, str],
    context_bundle: Optional[ContextBundle],
) -> dict:
    """
    Call Gemini to draft email content.

    Returns fallback template content if API key not available.

    Returns:
        dict with subject, body, tone, summary
    """
    generator = ContentGenerator()

    # Extract context for Gemini
    context_text = slots.get("context", "")
    if context_bundle:
        # Use context from bundle if available
        context_text = (
            f"Metadata: {context_bundle.metadata.get('keywords', [])}\n"
            + f"Background: {slots.get('context', '')}"
        )

    recipient = slots.get("who", "")
    user_style = slots.get("tone", "professional")
    thread_context = slots.get("thread_context")

    return generator.draft_email(
        intent_type=intent_type,
        context=context_text,
        recipient=recipient,
        user_style=user_style,
        thread_context=thread_context,
    )
