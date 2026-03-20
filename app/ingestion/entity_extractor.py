import os
import json
import time
from typing import Dict, List, Optional
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Groq (primary)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Fallback to Gemini if needed
try:
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GEMINI_API_KEY", "YOUR_KEY"))
    gemini_model = genai.GenerativeModel("gemini-2.5-flash")
    HAS_GEMINI_FALLBACK = True
except Exception:
    HAS_GEMINI_FALLBACK = False

# Rate limiting settings for Groq
RATE_LIMIT_DELAY = 2


# ── Fix D: Prompt injection sanitization ────────────────────────────────

# Patterns that attackers embed in email bodies to hijack LLM behaviour
_INJECTION_PATTERNS = [
    r"(?i)system\s*:",  # SYSTEM:
    r"(?i)ignore\s+(previous|above|all)",  # Ignore previous instructions
    r"(?i)disregard\s+(previous|above|all)",
    r"(?i)forget\s+(previous|above|all)",
    r"(?i)you\s+are\s+now",  # You are now a different AI
    r"(?i)act\s+as\s+(if|a|an)",  # Act as if / Act as a
    r"<\|system\|>",  # LLaMA system tag
    r"<\|im_start\|>",  # ChatML start tag
    r"<\|im_end\|>",
    r"\[INST\]",  # Mistral instruction tags
    r"\[/INST\]",
    r"(?i)prompt\s*injection",
    r"(?i)jailbreak",
    r"(?i)new\s+instructions?",
]

import re as _re

_COMPILED_PATTERNS = [_re.compile(p) for p in _INJECTION_PATTERNS]


def sanitize_email_body(text: str) -> str:
    """
    Strip prompt injection patterns from email body before passing to LLM.
    Replaces matched patterns with [REDACTED] so the extraction still works
    but the injection attempt is neutralised.

    Args:
        text: Raw email body or thread context string

    Returns:
        Sanitized string safe to pass to Groq/Gemini
    """
    if not text:
        return text

    sanitized = text
    for pattern in _COMPILED_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)

    return sanitized


# ── Update 2: Valid contact role values ─────────────────────────────────
VALID_CONTACT_ROLES = {
    "investor",
    "customer",
    "vendor",
    "partner",
    "candidate",
    "team",
    "lead",
    "advisor",
    "media",
    "other",
}


def extract_email_intelligence(
    subject: str,
    body: str = "",
    sender_name: str = None,
    is_reply: bool = False,
    thread_context: str = "",
) -> Dict:
    """
    Extract comprehensive intelligence from an email using LLM.
    Thread-aware: accepts prior conversation context so commitments buried
    in earlier messages in the chain are visible to the extraction.

    Args:
        subject: Email subject line
        body: Email body text (current message only)
        sender_name: Name of sender (for context)
        is_reply: Whether this email is a reply (affects interaction_type)
        thread_context: Prior messages in same thread (from build_thread_context)

    Returns:
        Dict with: sentiment, intent, summary, commitments (hard + soft), topics,
                   interaction_type, engagement_level, contact_role
    """

    # ── Fix D: Sanitize before passing to LLM ──
    safe_body = sanitize_email_body(body[:3000])
    safe_thread_context = sanitize_email_body(thread_context)

    # Build thread context section for prompt
    thread_section = ""
    if safe_thread_context and safe_thread_context.strip():
        thread_section = f"""
PREVIOUS MESSAGES IN THIS THREAD (read carefully — commitments may be buried here):
{safe_thread_context}

---
CURRENT MESSAGE TO ANALYSE:"""
    else:
        thread_section = "\nEMAIL TO ANALYSE:"

    prompt = f"""You are extracting relationship intelligence from a business email.
{thread_section}
Subject: {subject}
From: {sender_name or "Unknown"}
Body: {safe_body}

Extract the following and return ONLY valid JSON:

1. "summary": One sentence of what was discussed or decided (max 150 chars)
2. "sentiment": Float -1.0 (very negative) to 1.0 (very positive). 0 = neutral.
3. "intent": ONE of: follow_up, request, commitment, introduction, negotiation, update, question, other
4. "interaction_type": ONE of: email_reply, email_one_way, commitment, other
5. "commitments": Array of ALL promises made — include BOTH firm AND soft commitments.
   Each item: {{"text": "what was promised", "owner": "them or us", "due_signal": "date mention or null", "confidence": 0.0-1.0}}
   - Firm commitments (clear explicit promise): confidence 0.8-1.0
   - Soft commitments ("maybe", "I'll try", "we should", "sometime next week"): confidence 0.3-0.6
   - Include ALL commitments regardless of confidence — do not filter any out
6. "topics": Array of 2-5 key business topics (e.g. ["Series A", "product demo", "retention data"])
7. "engagement_level": "high" (detailed/thoughtful response), "medium" (standard reply), "low" (one-liner)
8. "contact_role": ONE of: investor, customer, vendor, partner, candidate, team, lead, advisor, media, other
   — Based on the conversation context, classify the sender's business relationship to us.
9. "is_human_email": true if sent by a real person, false if automated/marketing/transactional/notification.
   — A real person writes with personal tone, context, and expects a reply.
   — Automated = newsletters, alerts, receipts, job notifications, bank alerts, promotional offers.

IMPORTANT: If the thread context above contains a commitment (e.g. "send retention data", "intro to VP"),
include it in the commitments array even if the current message doesn't repeat it.

Return ONLY this JSON — no markdown, no explanation:
{{
  "summary": "...",
  "sentiment": 0.0,
  "intent": "...",
  "interaction_type": "email_reply",
  "commitments": [{{"text": "...", "owner": "them", "due_signal": null, "confidence": 0.9}}],
  "topics": [],
  "engagement_level": "medium",
  "contact_role": "other",
  "is_human_email": true
}}
"""

    try:
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a precise data extraction assistant. Always return valid JSON only. No markdown.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=700,
                )

                result_text = response.choices[0].message.content.strip()

                # Remove markdown code blocks if present
                if result_text.startswith("```"):
                    result_text = result_text.split("```")[1]
                    if result_text.startswith("json"):
                        result_text = result_text[4:]

                result = json.loads(result_text)

                # Separate hard and soft commitments
                all_commitments = result.get("commitments", [])
                cleaned_commitments = []
                for c in all_commitments[:15]:
                    conf = float(c.get("confidence", 0.5))
                    cleaned_commitments.append(
                        {
                            "text": str(c.get("text", ""))[:200],
                            "owner": str(c.get("owner", "them")),
                            "due_signal": c.get("due_signal"),
                            "confidence": round(max(0.0, min(1.0, conf)), 2),
                            # Tag soft commitments so downstream can distinguish
                            "is_soft": conf < 0.7,
                        }
                    )

                # Update 2: Validate and normalize contact_role
                raw_role = str(result.get("contact_role", "other")).lower().strip()
                contact_role = raw_role if raw_role in VALID_CONTACT_ROLES else "other"

                return {
                    "summary": str(result.get("summary", ""))[:200],
                    "sentiment": float(
                        max(-1.0, min(1.0, result.get("sentiment", 0.0)))
                    ),
                    "intent": str(result.get("intent", "other")),
                    "interaction_type": str(
                        result.get("interaction_type", "email_one_way")
                    ),
                    "engagement_level": str(result.get("engagement_level", "medium")),
                    "commitments": cleaned_commitments,
                    "topics": [str(t)[:50] for t in result.get("topics", [])[:5]],
                    "contact_role": contact_role,
                    "is_human_email": bool(result.get("is_human_email", True)),
                }

            except Exception as api_error:
                error_str = str(api_error)

                if "429" in error_str or "rate_limit" in error_str.lower():
                    retry_count += 1
                    wait_time = RATE_LIMIT_DELAY * (retry_count + 1)

                    if retry_count < max_retries:
                        print(
                            f"⏳ Rate limit hit, waiting {wait_time}s before retry {retry_count}/{max_retries}..."
                        )
                        time.sleep(wait_time)
                    else:
                        print(f"❌ Max retries reached for rate limit")
                        if HAS_GEMINI_FALLBACK:
                            print("🔄 Falling back to Gemini...")
                            return _extract_with_gemini(prompt)
                        raise
                else:
                    if HAS_GEMINI_FALLBACK and retry_count == 0:
                        print(f"⚠️ Groq error: {error_str[:100]}, trying Gemini...")
                        return _extract_with_gemini(prompt)
                    raise

    except Exception as e:
        print(f"⚠️ LLM extraction failed, using body fallback: {e}")
        fallback_summary = ""
        if body and body.strip():
            fallback_summary = body.strip()[:200]
        elif subject:
            fallback_summary = subject[:200]
        else:
            fallback_summary = "No content available"

        return {
            "summary": fallback_summary,
            "sentiment": 0.0,
            "intent": "other",
            "interaction_type": "email_one_way" if not is_reply else "email_reply",
            "engagement_level": "low",
            "commitments": [],
            "topics": [],
            "contact_role": "other",
            "is_human_email": True,  # assume human on fallback
        }


def _extract_with_gemini(prompt: str) -> Dict:
    """Fallback extraction using Gemini."""
    if not HAS_GEMINI_FALLBACK:
        raise Exception("Gemini fallback not available")

    try:
        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)

        all_commitments = result.get("commitments", [])
        cleaned_commitments = []
        for c in all_commitments[:15]:
            conf = float(c.get("confidence", 0.5))
            cleaned_commitments.append(
                {
                    "text": str(c.get("text", ""))[:200],
                    "owner": str(c.get("owner", "them")),
                    "due_signal": c.get("due_signal"),
                    "confidence": round(max(0.0, min(1.0, conf)), 2),
                    "is_soft": conf < 0.7,
                }
            )

        # Update 2: Validate contact_role from Gemini response too
        raw_role = str(result.get("contact_role", "other")).lower().strip()
        contact_role = raw_role if raw_role in VALID_CONTACT_ROLES else "other"

        return {
            "summary": str(result.get("summary", ""))[:200],
            "sentiment": float(max(-1.0, min(1.0, result.get("sentiment", 0.0)))),
            "intent": str(result.get("intent", "other")),
            "interaction_type": str(result.get("interaction_type", "email_one_way")),
            "engagement_level": str(result.get("engagement_level", "medium")),
            "commitments": cleaned_commitments,
            "topics": [str(t)[:50] for t in result.get("topics", [])[:5]],
            "contact_role": contact_role,
            "is_human_email": bool(result.get("is_human_email", True)),
        }
    except Exception as e:
        print(f"❌ Gemini fallback also failed: {e}")
        raise


def analyze_sentiment(text: str) -> float:
    """
    Simple sentiment analysis (backwards compatibility).
    Use extract_email_intelligence() for full extraction.
    """
    prompt = f"""
Rate sentiment of this email from -1 to 1.

{text}
Return only the number.
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=10,
        )
        return float(response.choices[0].message.content.strip())
    except Exception:
        if HAS_GEMINI_FALLBACK:
            try:
                response = gemini_model.generate_content(prompt)
                return float(response.text.strip())
            except Exception:
                return 0.0
        return 0.0


# ── Update 1.1: Signal Score Computation ────────────────────────────────


def compute_signal_score(intelligence: Dict, body: str = "") -> float:
    """
    Compute signal strength score (0.0-1.0) based on email intelligence.

    Higher scores = more important interactions that should surface in context.

    Scoring breakdown:
        +0.4 if intent is commitment or request (high-value signal)
        +0.2 if engagement_level is high (thoughtful/detailed response)
        +0.2 if body > 80 words (substantial content)
        +0.3 if has commitments (concrete promises made)

    Args:
        intelligence: Dict from extract_email_intelligence()
        body: Email body text (for word count)

    Returns:
        float: Signal score 0.0-1.0

    Example:
        >>> intel = {"intent": "commitment", "engagement_level": "high", "commitments": [...]}
        >>> compute_signal_score(intel, "Long detailed email..." * 20)
        0.9  # High signal: commitment + high engagement + long + has commitments
    """
    score = 0.0

    # Intent signal (commitment/request = high value)
    intent = intelligence.get("intent", "other")
    if intent in ["commitment", "request"]:
        score += 0.4

    # Engagement signal (high engagement = thoughtful response)
    engagement_level = intelligence.get("engagement_level", "medium")
    if engagement_level == "high":
        score += 0.2

    # Length signal (substantial content)
    word_count = len((body or "").split())
    if word_count > 80:
        score += 0.2

    # Commitment signal (concrete promises)
    commitments = intelligence.get("commitments", [])
    if commitments and len(commitments) > 0:
        score += 0.3

    # Clamp to [0.0, 1.0]
    return round(min(score, 1.0), 3)
