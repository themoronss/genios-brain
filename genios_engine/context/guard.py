from __future__ import annotations

import unicodedata

# B4 — Guard wall. Deterministic, no LLM. The load-bearing rule: "evidence or it didn't
# happen." Every extracted candidate must quote an EXACT substring of the source content
# (normalized) — no paraphrase, no fuzzy. Candidates that fail are dropped, not committed.


def _norm(s: str) -> str:
    # NFKC → casefold → collapse whitespace (design G2-02)
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return " ".join(s.split())


def evidence_ok(content: str, evidence_text: str, *, min_len: int = 3) -> bool:
    """True iff evidence_text is an exact (normalized) substring of the source content."""
    if not evidence_text or len(evidence_text.strip()) < min_len:
        return False
    return _norm(evidence_text) in _norm(content)


def keep_grounded(content: str, items: list, key: str = "evidence_text") -> list:
    """Filter a candidate list to only those whose evidence quotes the source exactly."""
    return [it for it in items
            if isinstance(it, dict) and evidence_ok(content, str(it.get(key, "")))]
