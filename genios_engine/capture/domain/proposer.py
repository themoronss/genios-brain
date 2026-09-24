"""L1.6.6-U6 · THE DOMAIN PROPOSER — the one thing in this step that reads more words than a regex.

A keyword table only knows the language somebody thought to write down in advance. A real mailbox
is mostly ordinary sentences — *"can you send that across"*, *"are we still on for Thursday"* — and
a footwear exporter's core domain (*"container held at Nhava Sheva, BIS certificate pending, L/C
expires Friday"*) matches none of the four shipped patterns. `hints.py` says so itself.

⛔ **WHY THIS IS ITS OWN MODEL CALL AND NOT A FIELD ON LLM-2's PROMPT.** The cost check that runs
before a step is built (the step-4 lesson) found this and it decided the architecture:

    `vocabulary_fingerprint()` folds in every closed set in `semantic/vocabulary._SETS`, and it is
    a component of the `l1_extraction_results` cache key. Adding a `domain` set to LLM-2's
    vocabulary would move the fingerprint and **re-extract the entire corpus — a second full model
    bill on top of step 4's.**

Four things follow from the separation, and all four are reasons to keep it:

    cache        untouched. `test_the_extraction_cache_fingerprint_is_untouched` holds the line.
    metering     it needs its own `purpose` anyway; a separate site gives that for free.
    cost         it can be SKIPPED — see `MIN_CHARS_FOR_A_PROPOSAL`. Impossible inside LLM-2.
    failure      it can fail without failing extraction. A dead proposer must never stop a
                 message landing, so every error path returns "no proposal" and the deterministic
                 keyword hints stand alone.

**THE MODEL PROPOSES; IT DOES NOT DECIDE.** Doctrine 1 of this layer — *a model may DESCRIBE, never
SCORE*. What comes back is a list of names, each validated by `ontology.validate_proposal`, and a
name outside the registered set is RECORDED as `proposed_unknown` rather than accepted or dropped.
The confidence attached to an accepted proposal is a fixed constant this module owns, not a number
the model returned: letting a model's self-reported certainty become a stored confidence is exactly
the scoring this architecture forbids.

**IT NEVER FILTERS.** Whatever this returns is MERGED with the keyword hints, never substituted for
them. §9 of the step: *tag, never route, never drop*.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from genios_engine.capture.domain.ontology import PROPOSED_UNKNOWN, validate_proposal

log = logging.getLogger(__name__)

#: The metering purpose this site records under. It is a STRING CONSTANT rather than a literal at
#: the call, because `tests/test_every_llm_call_site_is_metered.py` reads the register and the
#: register has to name something a human can grep for.
PURPOSE = "domain_proposal"

#: Below this many characters, no model call is made. E10.
#:
#: *"thanks"*, *"+1"*, *"sounds good"* — a message this short has no domain to read and spending a
#: call on it is pure cost at scale. The FALLBACK still applies to it, so it is not invisible; it
#: is simply not worth a token. This is the concrete saving the separate-call architecture buys.
MIN_CHARS_FOR_A_PROPOSAL = 80

#: What an ACCEPTED proposal is worth, in integer basis points.
#:
#: BELOW `CONFIDENCE_BP["keyword"]` (6000) ON PURPOSE. A keyword match is a fact about the text —
#: the words "term sheet" are or are not there. A proposal is a reading of it. When both fire, the
#: deterministic one should be the one a downstream reader leans on, and when only the proposal
#: fires it is still far above the fallback's 1000, which is the whole point of having it.
#:
#: IT IS A CONSTANT, NOT THE MODEL'S OWN NUMBER. A model's self-reported certainty becoming a
#: stored confidence is the "model may describe, never score" line being crossed.
PROPOSAL_CONFIDENCE_BP = 4500

#: At most this many domains from one message. A proposer returning six names has not read the
#: message, it has listed the taxonomy — and `coverage.is_indiscriminate` is the metric that makes
#: that visible across a sweep. This is the per-message bound on the same failure.
MAX_PROPOSALS = 3

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


class LLMResponse(Protocol):
    parsed: dict[str, Any]
    raw: str
    ok: bool
    error: str | None


class LLMClient(Protocol):
    """INJECTED, exactly as `esqe/relevance.py` and `semantic/extractor.py` state it.

    `capture/` must not learn its transport from `context/`, and a test proves the no-call paths
    by passing a client that RAISES rather than by reading a counter that could be stale.
    """

    @property
    def model(self) -> str: ...

    def call(self, prompt: str, *, max_tokens: int = 4096) -> LLMResponse: ...


@dataclass(frozen=True, slots=True)
class DomainProposal:
    """One name the model put forward, and what the ontology made of it."""

    domain: str
    accepted: bool
    outcome: str

    @property
    def is_unknown(self) -> bool:
        return self.outcome == PROPOSED_UNKNOWN


@dataclass(frozen=True, slots=True)
class ProposalOutcome:
    """Everything one proposal call produced, including the reason it produced nothing.

    `skipped_reason` is not decoration. A proposer that returns nothing because the message was
    four words long and one that returns nothing because the provider timed out are different
    facts, and a caller that cannot tell them apart cannot tell a cheap sweep from a broken one.
    """

    proposals: tuple[DomainProposal, ...] = ()
    called: bool = False
    skipped_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def accepted(self) -> tuple[str, ...]:
        """The registered names, in order. What the merge actually consumes."""
        return tuple(p.domain for p in self.proposals if p.accepted)

    @property
    def unknown(self) -> tuple[str, ...]:
        """Real names this deployment does not run — the rows a reviewer should see."""
        return tuple(p.domain for p in self.proposals if p.is_unknown)


def build_prompt(text: str, *, registered: frozenset[str]) -> str:
    """The proposal prompt. The registered set is SHOWN, and a name outside it is still allowed.

    Offering the list and then accepting only the list would make the model's one useful
    contribution impossible: telling us about a domain we do not run. So the instruction asks for
    the closest registered names AND permits a new one, and `ontology.validate_proposal` is what
    sorts the two afterwards. That is the same division doc 04 draws everywhere — the model
    describes, the validator decides.
    """
    names = ", ".join(sorted(registered))
    return (
        "You label a business message with the domains it belongs to.\n\n"
        f"KNOWN DOMAINS: {names}\n\n"
        "Rules:\n"
        "- Answer with JSON only: {\"domains\": [\"name\", ...]}\n"
        f"- At most {MAX_PROPOSALS} names, most relevant first.\n"
        "- Prefer a KNOWN domain when one fits.\n"
        "- If the message is genuinely about something not in the list, name it in one or two "
        "lowercase words rather than forcing a poor fit.\n"
        "- Do not explain. Do not score. Do not invent a domain to fill the list — fewer is "
        "better than wrong.\n\n"
        "MESSAGE:\n"
        f"{text}\n")


def _names_from(response: Any) -> list[str]:
    """The `domains` array out of whatever shape came back, defensively.

    A malformed answer yields NOTHING and never raises. This is an enrichment: the message has
    already been captured, it already has its deterministic hints, and a proposer that could throw
    would make an optional improvement into a capture failure.
    """
    payload = getattr(response, "parsed", None)
    if not isinstance(payload, dict) or not payload:
        raw = str(getattr(response, "raw", "") or "")
        fenced = _FENCE.search(raw)
        try:
            payload = json.loads(fenced.group(1) if fenced else raw)
        except Exception:                      # noqa: BLE001 — a bad answer is not an exception
            return []
    if not isinstance(payload, dict):
        return []
    names = payload.get("domains")
    if isinstance(names, str):                 # a model answering with one bare name
        names = [names]
    if not isinstance(names, (list, tuple)):
        return []
    return [n for n in names if isinstance(n, str)][:MAX_PROPOSALS]


def propose_domains(text: str | None, *, llm: LLMClient | None,
                    registered: frozenset[str] | None = None) -> ProposalOutcome:
    """Ask the model which domains this message belongs to. Never raises, never filters.

    Returns an empty outcome — with `skipped_reason` saying which — when there is no client, no
    text, or too little text to be worth a call. Every one of those is a normal operating state
    and none of them is an error.
    """
    from genios_engine.capture.domain.ontology import registered_domains

    if llm is None:
        return ProposalOutcome(skipped_reason="no_client")
    body = (text or "").strip()
    if not body:
        return ProposalOutcome(skipped_reason="no_text")
    if len(body) < MIN_CHARS_FOR_A_PROPOSAL:
        # E10. The fallback still applies, so the message is not invisible — it is just not worth
        # a token. At a mailbox's scale this is most of the saving the separate call buys.
        return ProposalOutcome(skipped_reason="too_short")

    known = registered if registered is not None else registered_domains()
    try:
        response = llm.call(build_prompt(body, registered=known), max_tokens=256)
    except Exception as exc:                   # noqa: BLE001 — E7: a dead proposer never fails capture
        log.warning("domain proposer unavailable (%s); keyword hints stand alone", exc)
        return ProposalOutcome(skipped_reason="call_failed")

    if not getattr(response, "ok", False):
        return ProposalOutcome(called=True, skipped_reason="answer_not_ok",
                               input_tokens=int(getattr(response, "input_tokens", 0) or 0),
                               output_tokens=int(getattr(response, "output_tokens", 0) or 0))

    seen: dict[str, DomainProposal] = {}
    for name in _names_from(response):
        verdict = validate_proposal(name)
        if not verdict.domain:                 # malformed — names nothing, so nothing to review
            continue
        seen.setdefault(verdict.domain, DomainProposal(
            domain=verdict.domain, accepted=verdict.accepted, outcome=verdict.outcome))

    return ProposalOutcome(proposals=tuple(seen.values()), called=True,
                           input_tokens=int(getattr(response, "input_tokens", 0) or 0),
                           output_tokens=int(getattr(response, "output_tokens", 0) or 0))


__all__ = ["MAX_PROPOSALS", "MIN_CHARS_FOR_A_PROPOSAL", "PROPOSAL_CONFIDENCE_BP", "PURPOSE",
           "DomainProposal", "LLMClient", "LLMResponse", "ProposalOutcome", "build_prompt",
           "propose_domains"]
