"""N-3's model site (T2) — the ONLY place a language model touches Organization-brain discovery.

WHAT THE MODEL IS ASKED FOR, AND WHY THAT SHAPE IS THE WHOLE DESIGN
-------------------------------------------------------------------
It is asked for POINTERS, not for content. Every field it returns is either a token from a closed
set or a substring of the document it was shown:

    category              one of `ORG_RULE_CATEGORIES` — a closed set, checked
    subject_type          a lowercase class word that must APPEAR in the quote, checked
    quote / offsets       a verbatim span, verified byte-for-byte by ALG-08
    threshold_as_written  the characters of the amount, IN the quote — never a number
    approver_as_written   the words naming the approver, IN the quote

It is never asked to compute an amount, to summarise, to paraphrase, or to judge. `parse_money`
turns the characters into integer minor units, `verify_span` proves the sentence exists, and
`resolve_approver_node` turns the words into a node id. So the worst a badly-behaved model can
do is propose a candidate that CLG-09 refuses and counts — it cannot invent a threshold, because
it never emits one, and it cannot invent a sentence, because the sentence is checked against the
document.

temperature 0, one call per document, no retry loop: this is not on any hot path, and a
stochastic second opinion about which sentences are rules would make the run irreproducible for
no gain. A failure returns nothing; `org_rule_ingest` records `extractor_failed` and the document
stays unread rather than half-read.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.packs.brains.org_discovery import ORG_RULE_CATEGORIES, RULE_BEARING_CANON_KINDS

#: How much of one canon document the model is shown. Offsets are into THIS text, so the cap is
#: also the honest boundary of what a span can point at — a rule stated past it is simply not
#: discovered rather than discovered against coordinates that do not exist. Uploads already chunk
#: at `upload_routes.CHUNK_CHARS`, so this only bites on a very long hand-written policy.
MAX_DOCUMENT_CHARS = 24_000

#: One structured extraction. Bounded because a policy document with more than this many distinct
#: binding rules is a document nobody has read either.
MAX_RULES = 20

PROMPT = """You are reading ONE internal company document and extracting the RULES it states.

DOCUMENT KIND: {kind}
DOCUMENT TITLE: {title}
DOCUMENT TEXT (character offsets start at 0):
<<<DOC
{text}
DOC

A RULE is a statement the company BINDS ITSELF TO: it has a condition (when it applies), a
consequence (what must or must not happen), and, for approvals, an authority (who signs).
A description, an aspiration, an explanation or an example is NOT a rule.

Return STRICT JSON, no prose, no markdown:

{{"rules": [
  {{"category": one of {categories},
    "subject_type": a single lowercase word naming the class of thing governed
                    (contract, expense, hiring, discount, refund, legal, vendor, ...),
                    and it MUST appear in the quote,
    "quote": the EXACT sentence from DOCUMENT TEXT, copied character for character,
    "start_offset": integer index where the quote starts in DOCUMENT TEXT,
    "end_offset": integer index one past where it ends (end - start == len(quote)),
    "threshold_as_written": the amount EXACTLY as it appears inside the quote
                            ("$50,000", "Rs 25,00,000", "20%") or null if the rule names none,
    "approver_as_written": the words in the quote naming who approves
                           ("the founder", "CFO", "finance@acme.com") or null}}
]}}

HARD RULES — a candidate that breaks any of them is discarded by a validator, so do not guess:
1. COPY the quote. Do not fix typos, do not re-wrap lines, do not shorten. It is checked
   character for character against DOCUMENT TEXT.
2. NEVER compute or normalise a number. `threshold_as_written` must be a literal substring of
   the quote. If the quote says "fifty thousand dollars", write that, not "$50,000".
3. `subject_type` and `approver_as_written` must both be present in the quote.
4. If the document states no binding rule, return {{"rules": []}}. An empty answer is correct
   and expected; inventing a rule is the only wrong answer.
5. At most {max_rules} rules. Prefer the ones that name a threshold or an approver.
"""


class LLMOrgRuleExtractor:
    """The production extractor. Wraps the shared `LLMClient` (temp 0, lenient JSON parse)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def propose(self, *, text: str, kind: str, title: str) -> Sequence[Mapping[str, Any]]:
        prompt = PROMPT.format(kind=kind, title=title, text=text[:MAX_DOCUMENT_CHARS],
                               categories=json.dumps(sorted(ORG_RULE_CATEGORIES)),
                               max_rules=MAX_RULES)
        result = self._client.call(prompt, max_tokens=4096)
        if not getattr(result, "ok", False):
            # Surfaced as an empty proposal set, never as a partial one. The caller records
            # `extractor_failed` on the run receipt and the document stays UNREAD, so the next
            # sweep tries it again — a half-read policy is worse than an unread one.
            raise RuntimeError(getattr(result, "error", None) or "extractor call failed")
        rules = (result.parsed or {}).get("rules")
        if not isinstance(rules, list):
            raise RuntimeError("extractor returned no `rules` array")
        return [r for r in rules[:MAX_RULES] if isinstance(r, dict)]


def make_org_rule_extractor(client: Any | None = None) -> LLMOrgRuleExtractor | None:
    """The wiring seam. Returns None when no model is configured — a skipped run, not a crash.

    None is a real answer: on a deployment with no Anthropic key (CI, and every hermetic test
    process — `tests/conftest.py` clears the key deliberately) there is no T2 site, and the honest
    behaviour is that discovery does not run rather than that it runs against a stub.
    """
    if client is None:
        from genios_engine.platform.wiring import make_llm_client
        client = make_llm_client()
    return None if client is None else LLMOrgRuleExtractor(client)


def rule_bearing_kinds() -> tuple[str, ...]:
    """The canon kinds a T2 extraction is ever paid for. Sorted, for a stable SQL parameter."""
    return tuple(sorted(RULE_BEARING_CANON_KINDS))


__all__ = ["LLMOrgRuleExtractor", "MAX_DOCUMENT_CHARS", "MAX_RULES", "PROMPT",
           "make_org_rule_extractor", "rule_bearing_kinds"]
