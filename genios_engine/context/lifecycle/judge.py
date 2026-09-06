"""L2.7.7-U1 step 4 · VALIDATE — where a description becomes a decision, deterministically.

This module is the answer to *"the model must not be handed the close."* Everything above it
describes; everything below it obeys. The judgement is a fixed cascade with no model in it:

    1. is this a speaker we weigh at all?            (machine / unattributable → nothing)
    2. is it about something we asked about?         (doc 12 case 8 — unscoped is refused)
    3. is an intention being read as a completion?   (doc 12 case 1 — hard negative)
    4. does the quote exist in the source?           (ALG-08, imported — doc 12 rule 5)
    4b. is it THIS sender's sentence, and unnegated?  (`textguard` — the two ALG-08 is silent on)
    5. how much is that worth, from that speaker?    (doc 07's authority table, integer bp)
    6. does it cover everything, or only some of it? (doc 12 case 2 — PARTIAL is a real state)
    7. is it above the floor, and is it long enough? (doc 12 case 4 — never on a one-liner)

EVERY TIE GOES THE SAFE WAY, because the two errors do not cost the same: a missed resolution is
one unnecessary nudge, an invented one loses the thread and the founder never learns it happened.
So: an unparseable answer rejects rather than retries, an unverified quote rejects rather than
downgrades, a mixed scope becomes PARTIAL rather than RESOLVED, and anything under the floor goes
to a human queue rather than onto a card.

THE ONE ASYMMETRY IN THE OTHER DIRECTION IS DELIBERATE: `CONTRADICTED` — *"actually not yet"* —
applies with a verified quote and any weighable speaker, with NO floor. Re-opening a situation
that had been closed costs a nudge; leaving it closed costs the thread. The floors exist to stop
us CLOSING things, and applying them to a re-open would point the whole cascade backwards.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from genios_engine.capture.validate.spans import (
    _CONFIDENCE_FACTOR,
    SpanVerdict,
    verify_span,
)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.context.lifecycle.authority import (
    authority_bp,
    is_ignored_speaker,
    role_for_scope,
)
from genios_engine.context.lifecycle.textguard import (
    in_quoted_history,
    negator_in_clause,
)
from genios_engine.context.lifecycle.contract import (
    CERTAINTY_BP,
    CERTAINTY_INTENT,
    CLOSE_FLOOR_BP,
    DECISION_APPLY,
    DECISION_REJECT,
    DECISION_REVIEW,
    REVIEW_FLOOR_BP,
    ROLE_MACHINE,
    SHORT_MESSAGE_CHARS,
    VERDICT_CONTRADICTED,
    VERDICT_NOT_RESOLVED,
    VERDICT_PARTIALLY_RESOLVED,
    VERDICT_RESOLVED,
    Message,
    Obligation,
    ResolutionClaim,
    ResolutionDescription,
)

__all__ = ["SITUATION_SCOPE", "judge"]

#: The id a claim uses when it is about the situation as a whole rather than a listed obligation.
#: A renewal with no per-obligation breakdown is a real shape and it is still resolvable; the
#: sentinel keeps "scope must name something" true for it instead of carving out an exception.
SITUATION_SCOPE = "situation"

#: The four ALG-08 grades that mean the words are really in the source. Named here so the
#: acceptance rule ("an unverified span → no resolution") reads as one membership test.
_VERIFIED_GRADES = frozenset({SpanVerdict.VERIFIED, SpanVerdict.VERIFIED_WHITESPACE,
                              SpanVerdict.VERIFIED_RELOCATED, SpanVerdict.VERIFIED_FUZZY})


def _span_for(description: ResolutionDescription, message: Message) -> EvidenceSpan | None:
    """The model's quote as an `EvidenceSpan`, repairing ONLY its arithmetic.

    `EvidenceSpan` refuses a span whose quote is not as long as the range it names (CV-01), so a
    model that miscounted its own offsets cannot even be handed to ALG-08 — and "the model
    miscounted" is a different fault from "the model invented a sentence", which is the one thing
    this whole path exists to catch. The end offset is therefore recomputed from the quote's own
    length, and ALG-08 then decides whether the words are actually there: if they are not at the
    stated start it grades RELOCATED or FUZZY and discounts accordingly, and if they are nowhere
    it grades UNVERIFIED and the claim dies. The repair moves a coordinate, never a word.
    """
    quote = description.quote
    for start, end in ((description.start_offset, description.end_offset),
                       (description.start_offset, description.start_offset + len(quote))):
        try:
            return EvidenceSpan(source_ref=message.source_ref, quote=quote,
                                start_offset=start, end_offset=end)
        except (ValueError, TypeError):
            continue
    return None


def _scoped(description: ResolutionDescription,
            obligations: Sequence[Obligation]) -> tuple[Obligation, ...]:
    """The obligations the model actually named, in the order they were offered."""
    named = set(description.scope)
    return tuple(ob for ob in obligations if ob.obligation_id in named)


def _claim(description: ResolutionDescription, message: Message, *, verdict: str,
           scope: Iterable[str], role: str, authority: int, certainty_bp: int,
           effective: int, decision: str, reason: str, span_verdict: str = "",
           quote: str = "", start: int = 0, end: int = 0, situation_id: str,
           model: str) -> ResolutionClaim:
    return ResolutionClaim(
        situation_id=situation_id, event_id=message.event_id, stated_at=message.occurred_at,
        verdict=verdict, certainty=description.certainty, scope=tuple(scope),
        speaker_email=message.sender_email, speaker_role=role, authority_bp=authority,
        certainty_bp=certainty_bp, effective_bp=effective, decision=decision, reason=reason,
        quote=quote, source_ref=message.source_ref if quote else "", start_offset=start,
        end_offset=end, span_verdict=span_verdict,
        raw_confidence_bp=description.raw_confidence_bp, model=model)


def judge(description: ResolutionDescription, *, situation_id: str, message: Message,
          obligations: Sequence[Obligation], internal_emails: Iterable[str] = (),
          model: str = "") -> ResolutionClaim:
    """One description → one claim, with the receipt for whatever it decided.

    Always returns a claim, never None and never an exception: a rejection is a RESULT here, and
    it is stored, because "we looked at this message and it said nothing" is what stops the next
    drain from paying to look at it again, and "we looked and refused it" is the only way anyone
    can later ask whether the refusals were right.
    """
    scoped = _scoped(description, obligations)
    role = role_for_scope(message.sender_email, scoped, internal_emails=internal_emails)
    authority = 0 if is_ignored_speaker(role) else authority_bp(role)
    certainty_bp = CERTAINTY_BP[description.certainty]

    def reject(reason: str, *, verdict: str | None = None, span_verdict: str = "",
               quote: str = "", start: int = 0, end: int = 0) -> ResolutionClaim:
        return _claim(description, message, verdict=verdict or description.verdict,
                      scope=description.scope, role=role or ROLE_MACHINE, authority=authority,
                      certainty_bp=certainty_bp, effective=0, decision=DECISION_REJECT,
                      reason=reason, span_verdict=span_verdict, quote=quote, start=start,
                      end=end, situation_id=situation_id, model=model)

    # 1 · the speaker. Belt and braces: the gate already refused these before spending a call,
    # and a second check here is what makes the judge safe to call from a replay or a backfill
    # that did not go through the gate.
    if is_ignored_speaker(role):
        return reject("speaker is a service account or unattributable — ignored entirely")

    # 2 · nothing to decide. Recorded rather than dropped: the row is what stops this message
    # being re-read, and re-reading it would produce the same answer at the same price.
    if description.verdict == VERDICT_NOT_RESOLVED:
        return reject("the message states no completion")

    # 3 · an intention is not a completion (doc 12 case 1). Checked BEFORE the span so that a
    # perfectly-quoted "we should wrap this up" cannot ride a verified receipt into the floor
    # comparison. The band is zero-weighted as well; this is the lock, that is the belt.
    if (description.certainty == CERTAINTY_INTENT
            and description.verdict in (VERDICT_RESOLVED, VERDICT_PARTIALLY_RESOLVED)):
        return reject("forward-looking intent, not a completion statement",
                      verdict=VERDICT_NOT_RESOLVED)

    # 4 · the receipt. ALG-08, imported — doc 12's cross-cutting rule 5.
    span = _span_for(description, message)
    if span is None:
        return reject("the quote could not be expressed as a span")
    grade, resolved_span = verify_span(span, message.text)
    if grade not in _VERIFIED_GRADES:
        return reject("the quoted sentence is not in the message", span_verdict=grade.value,
                      quote=description.quote, start=description.start_offset,
                      end=description.end_offset)
    quote, start, end = (resolved_span.quote, resolved_span.start_offset,
                         resolved_span.end_offset)
    # ALG-08's own penalty for a weaker grade, imported rather than restated: a relocated quote
    # keeps 9/10 and a fuzzy one 7/10. A second copy of these fractions is a second policy.
    num, den = _CONFIDENCE_FACTOR[grade]
    certainty_bp = certainty_bp * num // den

    # 5 · what it is worth from this speaker. Integer basis points throughout — `9000 * 6000 //
    # 10000` is 5400 everywhere, forever.
    effective = certainty_bp * authority // 10_000

    # A contradiction re-opens, and it does not have to clear a floor to do it. See the module
    # docstring: the floors exist to stop us closing things.
    if description.verdict == VERDICT_CONTRADICTED:
        return _claim(description, message, verdict=VERDICT_CONTRADICTED,
                      scope=description.scope or (SITUATION_SCOPE,), role=role,
                      authority=authority, certainty_bp=certainty_bp, effective=effective,
                      decision=DECISION_APPLY,
                      reason="a later statement contradicts the resolution — latest wins",
                      span_verdict=grade.value, quote=quote, start=start, end=end,
                      situation_id=situation_id, model=model)

    # 4b · TWO THINGS ALG-08 DOES NOT ANSWER. It has just proved the words are in the source; it
    # is silent about WHERE in the source they are and about whether they are negated, and each
    # of those closes a live thread on a sentence that does not say what the claim says it says.
    # See `textguard.py`. Both are placed BELOW the contradiction branch on purpose: a
    # contradiction is the reopen path, its quote is SUPPOSED to carry a negator, and guarding
    # the reopen would point the cascade backwards.
    if in_quoted_history(message.text, start, end):
        # The completion sentence is in the reply history — someone else's words, from an earlier
        # message, quoted by a sender who may well be disputing them. Verified, and worthless.
        return reject("the quoted sentence is in the reply history, not in this message",
                      verdict=VERDICT_NOT_RESOLVED, span_verdict=grade.value, quote=quote,
                      start=start, end=end)
    negator = negator_in_clause(message.text, start, end)
    if negator is not None:
        return reject(
            f"the quoted sentence is negated by {negator!r} in its own clause",
            verdict=VERDICT_NOT_RESOLVED, span_verdict=grade.value, quote=quote,
            start=start, end=end)

    # 2b · scope. A verdict that names no obligation we asked about is about something else in
    # the same thread (doc 12 case 8), and applying it would close the wrong thing.
    if obligations and not scoped:
        return reject("the verdict names no obligation from this situation",
                      verdict=VERDICT_NOT_RESOLVED, span_verdict=grade.value, quote=quote,
                      start=start, end=end)
    if not obligations and SITUATION_SCOPE not in description.scope and description.scope:
        return reject("the verdict names an obligation this situation does not have",
                      verdict=VERDICT_NOT_RESOLVED, span_verdict=grade.value, quote=quote,
                      start=start, end=end)

    # 6 · everything, or only some of it (doc 12 case 2). The DOWNGRADE is deterministic and it
    # is not the model's to make: three of five commitments discharged is a partial resolution
    # however confidently the sentence is written, and a whole-situation close would drop the
    # other two with nobody told.
    covered = {ob.obligation_id for ob in scoped}
    outstanding = [ob for ob in obligations if ob.obligation_id not in covered]
    verdict = description.verdict
    note = ""
    if verdict == VERDICT_RESOLVED and outstanding:
        verdict = VERDICT_PARTIALLY_RESOLVED
        note = (f" — downgraded from RESOLVED: covers {len(covered)} of {len(obligations)} "
                "open obligations")
    scope_out = tuple(ob.obligation_id for ob in scoped) or (SITUATION_SCOPE,)

    # 7 · the floors, and the one-liner rule (doc 12 case 4).
    if len(message.text.strip()) < SHORT_MESSAGE_CHARS and effective >= CLOSE_FLOOR_BP:
        decision, reason = DECISION_REVIEW, (
            f"a single short message never closes a situation on its own ("
            f"{len(message.text.strip())} characters){note}")
    elif effective >= CLOSE_FLOOR_BP:
        decision, reason = DECISION_APPLY, (
            f"{description.certainty} stated by {role}, {effective} bp{note}")
    elif effective >= REVIEW_FLOOR_BP:
        decision, reason = DECISION_REVIEW, (
            f"{description.certainty} stated by {role} is {effective} bp, below the "
            f"{CLOSE_FLOOR_BP} bp close floor — held for a human{note}")
    else:
        decision, reason = DECISION_REJECT, (
            f"{description.certainty} stated by {role} is {effective} bp, below the "
            f"{REVIEW_FLOOR_BP} bp review floor{note}")

    return _claim(description, message, verdict=verdict, scope=scope_out, role=role,
                  authority=authority, certainty_bp=certainty_bp, effective=effective,
                  decision=decision, reason=reason, span_verdict=grade.value, quote=quote,
                  start=start, end=end, situation_id=situation_id, model=model)
