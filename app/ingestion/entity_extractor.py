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
except:
    HAS_GEMINI_FALLBACK = False

# Rate limiting settings for Groq
# Groq: 30 requests/minute, so we can go much faster!
RATE_LIMIT_DELAY = 2  # 2 seconds = 30 requests/minute with buffer


def extract_email_intelligence(
    subject: str, body: str = "", sender_name: str = None
) -> Dict:
    """
    Extract comprehensive intelligence from an email using LLM.

    Returns:
        Dict with keys: sentiment, intent, summary, commitments, topics
    """

    prompt = f"""Given this email, extract the following information and return ONLY valid JSON:

EMAIL:
Subject: {subject}
From: {sender_name or "Unknown"}
Body: {body[:2000]}  

Extract:
1. "summary": One sentence summary of what was discussed (max 150 chars)
2. "sentiment": A number from -1.0 (very negative) to 1.0 (very positive). 0 is neutral.
3. "intent": Choose ONE from: follow_up, request, commitment, introduction, negotiation, update, question, other
4. "commitments": Array of specific promises or action items mentioned (empty array if none)
5. "topics": Array of 2-5 key topics or themes discussed (e.g., ["fundraising", "product demo", "pricing"])

Return ONLY this JSON structure:
{{
  "summary": "...",
  "sentiment": 0.0,
  "intent": "...",
  "commitments": [],
  "topics": []
}}
"""

    try:
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Use Groq API (OpenAI-compatible)
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a precise data extraction assistant. Always return valid JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=500,
                )

                result_text = response.choices[0].message.content.strip()

                # Remove markdown code blocks if present
                if result_text.startswith("```"):
                    result_text = result_text.split("```")[1]
                    if result_text.startswith("json"):
                        result_text = result_text[4:]

                result = json.loads(result_text)

                # Validate and clean up the result
                return {
                    "summary": str(result.get("summary", ""))[:200],
                    "sentiment": float(
                        max(-1.0, min(1.0, result.get("sentiment", 0.0)))
                    ),
                    "intent": str(result.get("intent", "other")),
                    "commitments": [
                        str(c)[:200] for c in result.get("commitments", [])[:10]
                    ],
                    "topics": [str(t)[:50] for t in result.get("topics", [])[:5]],
                }

            except Exception as api_error:
                error_str = str(api_error)

                # Check if it's a rate limit error
                if "429" in error_str or "rate_limit" in error_str.lower():
                    retry_count += 1

                    wait_time = RATE_LIMIT_DELAY * (
                        retry_count + 1
                    )  # Exponential backoff

                    if retry_count < max_retries:
                        print(
                            f"⏳ Rate limit hit, waiting {wait_time}s before retry {retry_count}/{max_retries}..."
                        )
                        time.sleep(wait_time)
                    else:
                        print(f"❌ Max retries reached for rate limit")
                        # Try Gemini fallback if available
                        if HAS_GEMINI_FALLBACK:
                            print("🔄 Falling back to Gemini...")
                            return _extract_with_gemini(prompt)
                        raise
                else:
                    # Not a rate limit error, try Gemini fallback
                    if HAS_GEMINI_FALLBACK and retry_count == 0:
                        print(f"⚠️ Groq error: {error_str[:100]}, trying Gemini...")
                        return _extract_with_gemini(prompt)
                    raise

    except Exception as e:
        print(f"⚠️ LLM extraction failed, using body fallback: {e}")
        # Use email body (first 200 chars) as summary instead of just subject
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
            "commitments": [],
            "topics": [],
        }


def _extract_with_gemini(prompt: str) -> Dict:
    """Fallback extraction using Gemini."""
    if not HAS_GEMINI_FALLBACK:
        raise Exception("Gemini fallback not available")

    try:
        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()

        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)

        return {
            "summary": str(result.get("summary", ""))[:200],
            "sentiment": float(max(-1.0, min(1.0, result.get("sentiment", 0.0)))),
            "intent": str(result.get("intent", "other")),
            "commitments": [str(c)[:200] for c in result.get("commitments", [])[:10]],
            "topics": [str(t)[:50] for t in result.get("topics", [])[:5]],
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
    except:
        # Fallback to Gemini
        if HAS_GEMINI_FALLBACK:
            try:
                response = gemini_model.generate_content(prompt)
                return float(response.text.strip())
            except:
                return 0.0
        return 0.0
