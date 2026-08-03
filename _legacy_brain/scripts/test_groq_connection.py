"""Phase 1.4 — LLMClient smoke test (Groq path).

Runs one live call through llm_client.call(purpose="extract_entities", ...),
asserts Groq responded with a non-empty string. org_id=None so nothing is
written to llm_usage (we only validate the wire + parse).

Usage:
    cd genios-brain && python scripts/test_groq_connection.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from any CWD — ensure the genios-brain root is on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm import llm_client  # noqa: E402


def main() -> int:
    try:
        reply = llm_client.call(
            org_id=None,
            purpose="extract_entities",
            prompt='Return the single JSON object {"ok": true}. No other text.',
            temperature=0.0,
            max_tokens=32,
        )
    except Exception as e:
        print(f"FAIL: LLM call raised: {e}")
        return 1

    if not reply or not reply.strip():
        print("FAIL: empty response from Groq")
        return 1

    print(f"OK: Groq responded ({len(reply)} chars): {reply.strip()[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
