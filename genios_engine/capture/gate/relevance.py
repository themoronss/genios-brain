from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from genios_engine.capture.gate.context import GateContext
from genios_engine.contracts.prepared_content import PreparedContent


@dataclass
class RelevanceVerdict:
    relevant: bool
    relevance: float
    domains: list[str] = field(default_factory=list)
    reason: str | None = None
    # What the gate should DO with this verdict. "" lets the gate fall back to the legacy
    # rule (relevant→route, else park). The LLM classifier sets it explicitly so it can
    # DROP confident junk (the deterministic classifier never drops — it only parks).
    disposition: str = ""            # "" | "keep" | "park" | "drop"


class RelevanceClassifier(Protocol):
    """S2 relevance gate (defense-in-depth). The gate slot is identical whether this
    is deterministic or an LLM — at LLM-integration time we swap in a temp-0 classifier
    and NOTHING else in the pipeline changes."""

    def classify(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict: ...


_BUSINESS = re.compile(
    r"\b(deal|pricing|contract|invoice|payment|meeting|proposal|budget|renewal|issue|"
    r"ticket|demo|quote|order|refund|escalat\w*|cancel\w*|approv\w*|sign|overdue|"
    r"security|compliance|legal|kitna|payment pending)\b",
    re.I,
)


class DeterministicRelevanceClassifier:
    """Safe default + dev impl — no LLM. Known sender or business keyword → relevant;
    otherwise low relevance (parks for review, never a hard drop)."""

    name = "relevance-deterministic-1"

    def classify(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict:
        if ctx.sender_known:
            return RelevanceVerdict(True, 0.90, reason="known_sender")
        text = prepared.clean_text if prepared else (ctx.raw.get("snippet") or "")
        if _BUSINESS.search(text):
            return RelevanceVerdict(True, 0.70, reason="business_keyword")
        return RelevanceVerdict(False, 0.30, reason="no_business_signal")

_GATE_PROMPT = """You are a junk filter deciding whether ONE email should enter a company's \
business-intelligence knowledge graph. This is the LAST filter before storage.

The graph is for REAL work relationships and decisions. The test: is a specific HUMAN writing to \
this person, or is there a live deal / meeting / interview / commitment / customer / prospect / \
vendor / support thread they must personally READ or REPLY to?

DROP when it is an automated, one-to-many, or self-service message with no human expecting a \
reply — even if it contains numbers, money, or PDF attachments:
- marketing / promotions / offers / product announcements / newsletters / digests
- OTP / verification / login codes, password resets, social-network reminders
- subscription / plan / account notices, bank / broker / wallet / payment-app STATEMENTS, \
auto-receipts, statement PDFs
- marketplace or platform listings & alerts (property, jobs, shopping, rides, etc.)
- automated matchmaking / profile-digest emails ("you matched", co-founder or candidate profile \
lists) and repeated event-platform auto-pings ("event updated") — a digest of many people or event \
notifications, not one person writing to you
An automated account statement or a marketplace notification is NOT business intelligence, \
however much data it carries — there is no relationship and nothing to act on.

KEEP when a real named person is corresponding, or there is a genuine deal, meeting, interview, \
commitment, question, complaint, or an invoice/contract from a vendor they actually work with — \
anything a founder must personally read or reply to. When genuinely torn between a real person \
and an automated system, KEEP (a wrong drop loses real signal; a wrong keep is only scored down).

Return ONLY JSON, no prose:
{{"disposition":"keep"|"drop","relevance":0.0-1.0,"reason":"<=6 words"}}

SOURCE: {source}
EMAIL:
{content}"""


_GATE_BATCH_PROMPT = """You are a junk filter deciding which of SEVERAL emails should enter a \
company's business-intelligence knowledge graph. This is the LAST filter before storage.

The graph is for REAL work relationships and decisions. For EACH email the test is: is a specific \
HUMAN writing to this person, or is there a live deal / meeting / interview / commitment / customer \
/ prospect / vendor / support thread they must personally READ or REPLY to?

DROP an email when it is automated, one-to-many, or self-service with no human expecting a reply — \
marketing / promotions / newsletters / digests; OTP / verification / login codes; subscription / \
account / bank / broker / wallet STATEMENTS and auto-receipts; marketplace or job / property / \
shopping listings & alerts; automated matchmaking or profile-digest / event-ping emails. An \
automated statement or marketplace notification is NOT business intelligence however much data it \
carries.

KEEP when a real named person is corresponding, or there is a genuine deal, meeting, interview, \
commitment, question, complaint, or an invoice/contract from a vendor they actually work with. When \
genuinely torn between a real person and an automated system, KEEP (a wrong drop loses real signal; \
a wrong keep is only scored down).

You are given {n} emails, each with an index. Return ONLY a JSON array, one object per email, no \
prose. You MUST return exactly {n} objects, one for each index 0..{last}:
[{{"i":0,"disposition":"keep"|"drop","relevance":0.0-1.0}}, ...]

EMAILS:
{emails}"""


class LLMRelevanceClassifier:
    """S2 LLM junk-gate — the single reliable filter that keeps noise OUT of the graph.

    Never runs on a known sender (whitelisted, no spend). It is the ONE place allowed to DROP on
    judgment; it FAILS OPEN (keep) on any LLM/parse error so an infra hiccup never silently discards
    real mail. `llm` is any object exposing `.call(prompt, max_tokens=)`.

    BATCHING: prime() classifies a whole page's emails in a few batched LLM calls (default 12/call)
    and caches the verdict per source_object_id; classify() then reads the cache — cutting ~N calls
    to ~N/12. It is fail-safe: any batch error, parse failure, or count mismatch simply leaves those
    ids uncached, so classify() falls back to the per-email call and NOTHING changes but speed.
    """

    name = "relevance-llm-1"

    def __init__(self, llm, batch_size: int = 12, *, cost_sink=None, org_id: str | None = None) -> None:
        self._llm = llm
        self._batch_size = max(1, int(batch_size))
        self._cache: dict[str, RelevanceVerdict] = {}       # source_object_id -> verdict (this run)
        # This gate runs on EVERY unknown-sender email, so it is a real line item — it was spending
        # tokens without appearing in llm_costs, which made reported spend lower than the actual
        # Anthropic bill. Optional so the classifier stays usable without a store (tests, dev).
        self._cost_sink = cost_sink
        self._org_id = org_id

    def bind_costs(self, cost_sink, org_id: str) -> "LLMRelevanceClassifier":
        """Attach cost recording once the org is known (the classifier is built before the sync)."""
        self._cost_sink, self._org_id = cost_sink, org_id
        return self

    def _record(self, res) -> None:
        if self._cost_sink is None or not self._org_id:
            return
        try:
            self._cost_sink(org_id=self._org_id, model=getattr(res, "model", "") or self._llm.model,
                            purpose="relevance_gate",
                            input_tokens=getattr(res, "input_tokens", 0) or 0,
                            output_tokens=getattr(res, "output_tokens", 0) or 0,
                            success=bool(getattr(res, "ok", True)),
                            error=getattr(res, "error", None))
        except Exception:      # noqa: BLE001 — accounting must never break capture
            pass

    # ---- batch pre-classification (called once per page, before per-event capture) ----
    def prime(self, objects) -> None:
        """Batch-classify a page of RawObjects; cache verdicts by source_object_id. Best-effort:
        any failure leaves ids uncached → classify() falls back to the single-email path."""
        from genios_engine.capture.preprocess.preprocess import preprocess
        items = []                                          # (oid, masked_content)
        for o in objects or []:
            oid = getattr(o, "source_object_id", None)
            raw = getattr(o, "raw", None) or {}
            if not oid or oid in self._cache or getattr(o, "actor_type", "") == "agent":
                continue                                    # already gated (e.g. by the connector) → skip re-call
            subject = raw.get("subject") or ""
            snippet = raw.get("snippet") or raw.get("body") or ""
            try:                                            # SAME PII masking as the single path
                masked = preprocess(f"{subject}\n\n{snippet}", event_id=oid, mask_phone=False).clean_text
            except Exception:      # noqa: BLE001
                masked = f"{subject}\n{snippet}"
            masked = (masked or "").strip()[:600]
            if masked:
                items.append((oid, masked))
        for i in range(0, len(items), self._batch_size):
            try:
                self._classify_chunk(items[i:i + self._batch_size])
            except Exception:      # noqa: BLE001 — a bad chunk just isn't cached → per-email fallback
                continue

    def _classify_chunk(self, chunk) -> None:
        if not chunk:
            return
        emails = "\n\n".join(f"[{idx}] {content}" for idx, (_oid, content) in enumerate(chunk))
        res = self._llm.call(
            _GATE_BATCH_PROMPT.format(n=len(chunk), last=len(chunk) - 1, emails=emails),
            max_tokens=40 * len(chunk) + 60)
        self._record(res)
        if not res.ok:
            return
        arr = res.parsed if isinstance(res.parsed, list) else (res.parsed or {}).get("results")
        if not isinstance(arr, list) or len(arr) != len(chunk):   # count mismatch → don't trust it
            return
        for item in arr:
            if not isinstance(item, dict):
                return
            try:
                idx = int(item.get("i"))
            except (TypeError, ValueError):
                return
            if not (0 <= idx < len(chunk)):
                return
            self._cache[chunk[idx][0]] = _verdict_from(item)

    def verdict_for(self, source_object_id: str):
        """The primed (batched) verdict for an id, or None if it wasn't cached. Lets the connector
        gate on the cheap snippet FIRST and skip the slow full-body fetch for confident drops."""
        return self._cache.get(source_object_id)

    def classify(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict:
        if ctx.sender_known:                                  # already trusted — never spend a call
            return RelevanceVerdict(True, 0.90, disposition="keep", reason="known_sender")
        oid = getattr(ctx.event, "source_object_id", None)
        if oid and oid in self._cache:                        # batched verdict — no extra LLM call
            return self._cache[oid]
        subject = ctx.raw.get("subject") or ""
        body = (prepared.clean_text if prepared else (ctx.raw.get("snippet") or ""))[:1500]
        content = f"Subject: {subject}\n{body}".strip()
        if not content:                                       # nothing to judge → don't drop blind
            return RelevanceVerdict(True, 0.50, disposition="keep", reason="empty_pass")
        res = self._llm.call(_GATE_PROMPT.format(source=ctx.event.source, content=content),
                             max_tokens=120)
        self._record(res)
        if not res.ok:                                        # fail OPEN — never lose mail on an error
            return RelevanceVerdict(True, 0.50, disposition="keep", reason="gate_llm_unavailable")
        return _verdict_from(res.parsed)


def _verdict_from(p: dict) -> RelevanceVerdict:
    disp = str((p or {}).get("disposition", "keep")).lower()
    if disp not in ("keep", "drop"):
        disp = "keep"
    try:
        rel = max(0.0, min(1.0, float(p.get("relevance", 0.5) or 0.5)))
    except (TypeError, ValueError):
        rel = 0.5
    return RelevanceVerdict(relevant=(disp == "keep"), relevance=rel, disposition=disp,
                            reason=str((p or {}).get("reason", "") or "")[:60])
