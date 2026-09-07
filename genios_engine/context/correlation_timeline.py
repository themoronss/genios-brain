"""L2.3.4 · BLG-06 — cross-timeline correlation: the condition somebody set in May, met in August.

Doc 03 calls this Globe's Opportunity Intelligence surface and *"the surface people remember"*:
*"a partner said they'd revisit once you had two enterprise references. You closed the second 11
days ago."* Nothing else in this system connects those two moments, because no human is holding
both in mind and the two events share no thread, no counterparty field and no window — they are
four months apart, which is precisely why the connection is worth anything.

WHAT THE DOC ACTUALLY SPECIFIES, and it is worth stating because the phrase "cross timeline"
suggests something else. This is NOT "two things that happened at the same time are one event" —
that join is L2.3.1 Cross Tool, which is built. L2.3.4 is DORMANT CONDITION SATISFACTION, and the
five ordered steps are the doc's own:

    1. STORE      a `Commitment` with `is_conditional=true` and a `condition_text` (L1 v2 already
                  extracts both) becomes a DORMANT CONDITION
    2. INDEX      parse the condition into a checkable predicate — deterministic first
    3. SWEEP      on each drain, re-evaluate every open condition against the CURRENT world
    4. SATISFY    newly true -> `condition_satisfied` carrying BOTH evidence spans: the original
                  statement AND the satisfying fact
    5. HALF-LIFE  a satisfied condition decays — full strength 30 days, then declines

**Step 4's two spans are the whole point.** The card must show the sentence from May *and* the
fact from August; either alone is unconvincing, and `SatisfiedCondition` refuses to exist without
both wherever a fact is what satisfied it.

THE THREE REFUSALS, which are the feature and not a shortfall:

  * **An unparseable condition never auto-fires.** Doc 03's first failure mode is a rhetorical
    condition matched — nagging somebody about a throwaway line — and its stated mitigation is
    that only a conditional commitment with a PARSEABLE predicate fires; the rest are review-only.
    `review_required` is where they go, and a review queue is a surface, not a silence.
  * **An unknown world is not a false one.** A predicate whose subject the world cannot see
    answers `UNKNOWN`, never `NOT_YET`. The difference matters on the day the source connects:
    `NOT_YET` says we looked and it has not happened, and saying that about something we cannot
    see is the same false negative inference `contracts/quality` exists to prevent.
  * **A satisfied condition ages.** Globe: *"a satisfied condition has a short half-life — act
    while the evidence is fresh."* `strength_bp` decays it in integer basis points, so a
    three-month-old satisfaction cannot arrive looking like today's.

M-5 IS NOT HERE, DELIBERATELY. Doc 03 puts semantic condition parsing at M-5 (T2), and the same
doc's group acceptance gate greps every `context/correlation*.py` for a model client and requires
zero matches. Both are satisfied the only way they can both be: deterministic parsing covers
dates, counts and named events, and everything else goes to the review queue rather than to a
guess. The escalation seam is `parse_condition` returning `None` — one function, one call site,
and the place M-5 attaches when it is built behind its own gate.

DETERMINISM — no clock, no float, no model. `eval_time` is a parameter everywhere it is needed;
the half-life is integer basis points computed by shifts and integer division; every collection is
sorted before it is traversed.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from genios_engine.context.analytic.publish import close_derived_facts, publish_derived_fact
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment, DecisionState, EntityMention
from genios_engine.contracts.validators import require_aware
from genios_engine.contracts.visibility import PARTICIPANTS
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.timeline")

#: Read out of the same two tables L1 files into — see `correlation_dependency` for why the
#: landing table is joined for world time rather than the extraction's own row date.
EXTRACTION_TABLE = "l1_extraction_results"
EVENT_TABLE = "source_events"

#: The derived fields this module owns, under one prefix so the sweep can close its own rows
#: without reaching a fact anybody else wrote.
FACT_PREFIX = "derived.timeline"
FIELD_DORMANT = f"{FACT_PREFIX}.dormant_condition"
FIELD_SATISFIED = f"{FACT_PREFIX}.condition_satisfied"
FIELD_REVIEW = f"{FACT_PREFIX}.condition_review"
#: `publish_derived_fact` keys the rest of the `fact_version_id` on (node, field, PERIOD) and
#: scopes both its open-row lookup and its close by this prefix, so the sweep can only ever
#: supersede or retire a row THIS module wrote. Rows written under the old period-less shape
#: (`fv_tl:<field>:<node>`) still begin with it and are absorbed rather than orphaned.
VERSION_PREFIX = "fv_tl"
VALUE_TYPE = "dormant_condition"

#: WHO THESE THREE FACTS MAY REACH — stated, because `publish_derived_fact` refuses to default it.
#: `contracts/visibility` states the law the old writer's inline `'org'` was quietly widening:
#: *the audience of a derived insight can never be wider than the audience of the evidence it came
#: from.*
#:
#: ALL THREE ARE `PARTICIPANTS`, and unlike the dependency pass — which splits, because its
#: `blocked_count` is one bare integer about its own subject — nothing here splits, because every
#: row this module writes is BUILT out of quoted text. `_satisfied_json` carries `statement` (the
#: sentence from May) beside `satisfied_by` (the fact from August), both as `EvidenceSpan`s with
#: their verbatim quotes; `_dormant_json` carries `condition_text` and the statement span. The
#: two-span requirement is the whole design of this correlator — a satisfaction with one receipt
#: is refused — so a row here without republished sentences does not exist. That is thread content
#: carried onto a node, and L1 stamps a mail event `participants` precisely so it cannot reach
#: someone who was not on the thread; `'org'` widened every one of them.
#:
#: `graph_facts` has no principals column (only `source_events` does), so this records the
#: CEILING — narrower than the tenant, the named people are on the source events — which is the
#: most this table can honestly say, and strictly more than `'org'` said.
TIMELINE_VISIBILITY_SCOPE = PARTICIPANTS

#: How far back a sweep looks for conditions and for the facts that satisfy them. Longer than the
#: dependency window on purpose: the entire value here is that the two moments are MONTHS apart,
#: and a window that only spans weeks would answer the question a thread already answers.
CONDITION_WINDOW_DAYS = 400

#: Step 5. Full strength for this many days, then a halving every this many days after it.
FULL_STRENGTH_DAYS = 30
HALF_LIFE_DAYS = 30
#: Below this the satisfaction is stale — Globe's "act while the evidence is fresh", stated as a
#: number so a card has a rule to apply rather than an adjective.
STALE_STRENGTH_BP = 1000
#: How far the halving is carried before it is simply stale. 2^7 of 10000 is 78 bp, well under
#: the floor, so this is a bound on arithmetic rather than a policy.
MAX_HALVINGS = 7

MAX_CONDITIONS_PER_SWEEP = 2000
MAX_FACT_WRITES_PER_SWEEP = 2000


# =================================================================================================
# STEP 2 — THE PREDICATE VOCABULARY
# =================================================================================================

class PredicateKind(str, Enum):
    """What kind of thing has to become true. Three, because three are what a rule can settle."""

    #: "two enterprise references" -> a counted population reaching a threshold.
    COUNT = "count"
    #: "after funding closes" -> a named thing having happened.
    EVENT = "event"
    #: "after March 1" -> an instant having passed. Satisfied by the calendar, not by a fact.
    INSTANT = "instant"


class Verdict(str, Enum):
    """The four answers, and the distinction the middle two carry.

    `NOT_YET` and `UNKNOWN` are separate for the reason `contracts/quality.AbsenceType` separates
    `GENUINELY_ABSENT` from `UNKNOWABLE`: "we counted and there is one" and "we cannot count this
    at all" read identically as "not satisfied" and license completely different things.
    """

    SATISFIED = "satisfied"
    NOT_YET = "not_yet"
    UNKNOWN = "unknown"
    #: No parseable predicate. Never auto-fires; goes to the review queue.
    REVIEW_ONLY = "review_only"


@dataclass(frozen=True, slots=True)
class ConditionPredicate:
    """A condition, made checkable. One shape for all three kinds so a store holds one row type.

    `world_key` is the join: it is what the predicate looks up, and what a world builder has to
    have produced. Keeping the key ON the predicate rather than deriving it at evaluation time is
    what makes an unparseable condition impossible to evaluate by accident — no key, no lookup.
    """

    kind: PredicateKind
    #: `count:<type>:<field>=<value>` · `count:<type>` · `event:<key>` · `instant`
    world_key: str
    #: The count a COUNT predicate must reach. 1 for an EVENT. Meaningless for an INSTANT.
    threshold: int = 1
    #: The instant an INSTANT predicate waits for. None for the other two.
    instant: datetime | None = None
    #: The phrase this was parsed from, verbatim, so a card can show what we thought it meant.
    source_phrase: str = ""


@dataclass(frozen=True, slots=True)
class ConditionVocabulary:
    """WHAT WORDS THIS TENANT'S WORLD CAN ANSWER FOR. Declared, never inferred.

    This is the component's honesty boundary. "Two enterprise references" is only checkable if
    something in the world counts references and knows which are enterprise; a parser that mapped
    the phrase onto whatever node type looked closest would produce a predicate that evaluates,
    answers, and is wrong — which is worse than the review queue by exactly the margin that
    matters. So the nouns and qualifiers a predicate may use are DECLARED here, and a phrase
    outside the declaration is unparseable rather than approximated.

    Extending it is a one-line `with_terms` on a value, not a code change, so a tenant whose pack
    knows what a "reference" is can say so.
    """

    #: noun (singular, lowercased) -> the entity type the world counts it as.
    nouns: Mapping[str, str] = field(default_factory=dict)
    #: qualifier -> (fact field, value) narrowing the count.
    qualifiers: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    #: event phrase (normalised) -> the event key the world publishes.
    events: Mapping[str, str] = field(default_factory=dict)

    def with_terms(self, *, nouns: Mapping[str, str] | None = None,
                   qualifiers: Mapping[str, tuple[str, str]] | None = None,
                   events: Mapping[str, str] | None = None) -> ConditionVocabulary:
        return ConditionVocabulary(nouns={**self.nouns, **(nouns or {})},
                                   qualifiers={**self.qualifiers, **(qualifiers or {})},
                                   events={**self.events, **(events or {})})


def default_condition_vocabulary() -> ConditionVocabulary:
    """The terms THIS build's world can actually answer for today, and no others.

    Every noun here maps onto a member of L1's closed `ENTITY_TYPE` vocabulary, because the
    shipped world builder counts entity mentions and a noun mapping to a type nothing publishes
    would parse into a predicate that answers `UNKNOWN` for ever — a silent accumulation, which is
    doc 03's third failure mode. Every event key maps onto a decision subject the world publishes
    when a decision reaches `made`.
    """
    return ConditionVocabulary(
        nouns={"customer": "organization", "customers": "organization",
               "client": "organization", "clients": "organization",
               "account": "organization", "accounts": "organization",
               "company": "organization", "companies": "organization",
               "reference": "organization", "references": "organization",
               "vendor": "vendor", "vendors": "vendor",
               "product": "product", "products": "product",
               "project": "project", "projects": "project",
               "document": "document", "documents": "document",
               "case study": "document", "case studies": "document"},
        qualifiers={"enterprise": ("account.segment", "enterprise"),
                    "paying": ("account.status", "paying"),
                    "signed": ("account.status", "signed")},
        events={"funding closes": "funding_closed", "funding close": "funding_closed",
                "the funding closes": "funding_closed",
                "the round closes": "funding_closed",
                "legal confirms": "legal_confirmed", "legal approves": "legal_confirmed",
                "the contract is signed": "contract_signed",
                "the audit completes": "audit_completed"})


_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                 "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
                 "a": 1, "an": 1, "another": 1}

_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
           "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
           "december": 12}

#: The lead-ins a condition wears. Stripped before parsing so "once we have two customers" and
#: "when we have two customers" are one predicate rather than two near-misses.
_LEAD_IN = re.compile(
    r"^(?:once|after|when|as soon as|provided|assuming|if|only if|subject to)\s+", re.IGNORECASE)
_HAVE = re.compile(r"^(?:we|you|they|i)?\s*(?:have|has|had|get|got|reach|reaches|hit|hits|"
                   r"close|closes|closed|sign|signs|signed|land|lands|landed)\s+", re.IGNORECASE)
_AT_LEAST = re.compile(r"^(?:at\s+least|atleast|a\s+minimum\s+of|minimum)\s+", re.IGNORECASE)
_COUNT = re.compile(r"^(\d{1,4}|[a-z]+)\s+(.+)$", re.IGNORECASE)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTH_DAY = re.compile(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
                        re.IGNORECASE)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower()).strip(" .!?;:")


def parse_condition(condition_text: str, *, vocabulary: ConditionVocabulary | None = None,
                    stated_at: datetime | None = None) -> ConditionPredicate | None:
    """STEP 2 — a stated condition becomes something the sweep can check, or becomes None.

    None is a real answer and the common one. Doc 03: *"anything it cannot parse is stored for
    human review rather than guessed at."* A parser that reached for the nearest plausible
    reading would turn every rhetorical aside — "let's talk once things settle down" — into a
    predicate that eventually evaluates true and nags somebody about a throwaway line.

    ORDER MATTERS AND IS NOT ARBITRARY. A date is tried first because "after March 1" contains a
    number and a noun and would otherwise parse as a count of "1 marches". A count is tried before
    an event because "after we have two enterprise references" wears an event's lead-in and is a
    count; only what survives both is looked up as a named event.
    """
    vocab = vocabulary or default_condition_vocabulary()
    raw = str(condition_text or "").strip()
    text = _normalise(raw)
    if not text:
        return None

    instant = _parse_instant(text, stated_at=stated_at)
    if instant is not None:
        return ConditionPredicate(kind=PredicateKind.INSTANT, world_key="instant",
                                  instant=instant, source_phrase=raw)

    stripped = _HAVE.sub("", _LEAD_IN.sub("", text)).strip()
    count = _parse_count(stripped, vocab)
    if count is not None:
        return ConditionPredicate(kind=PredicateKind.COUNT, world_key=count[0],
                                  threshold=count[1], source_phrase=raw)

    for phrase in (stripped, text, _LEAD_IN.sub("", text).strip()):
        key = vocab.events.get(phrase)
        if key:
            return ConditionPredicate(kind=PredicateKind.EVENT, world_key=f"event:{key}",
                                      threshold=1, source_phrase=raw)
    return None


def _parse_instant(text: str, *, stated_at: datetime | None) -> datetime | None:
    """A calendar date, or None. Whole days in UTC — the layer's one clock discipline.

    A bare month-day with no year is resolved against the STATEMENT's year, never against a
    running clock: "revisit after March 1" said in December 2025 means March 2026, and answering
    that from a wall clock would give a sweep replayed next year a different predicate for the
    same sentence.
    """
    from datetime import timezone

    found = _ISO_DATE.search(text)
    if found:
        year, month, day = (int(part) for part in found.groups())
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
    found = _MONTH_DAY.search(text)
    if not found:
        return None
    month_name, day, year = found.group(1), int(found.group(2)), found.group(3)
    month = _MONTHS.get(month_name)
    if month is None:
        return None
    base_year = int(year) if year else (stated_at.year if stated_at else None)
    if base_year is None:
        return None
    try:
        resolved = datetime(base_year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    if not year and stated_at is not None and resolved < stated_at:
        # "after March 1", said in December: the March that has not happened yet.
        resolved = resolved.replace(year=base_year + 1)
    return resolved


def _parse_count(text: str, vocab: ConditionVocabulary) -> tuple[str, int] | None:
    """`<n> [qualifier] <noun>` against the DECLARED vocabulary, or None."""
    body = _AT_LEAST.sub("", text).strip()
    found = _COUNT.match(body)
    if not found:
        return None
    head, rest = found.group(1).lower(), _normalise(found.group(2))
    if head.isdigit():
        threshold = int(head)
    elif head in _NUMBER_WORDS:
        threshold = _NUMBER_WORDS[head]
    else:
        return None
    if threshold <= 0:
        return None

    words = rest.split(" ")
    for cut in range(len(words)):
        qualifier_words, noun_phrase = words[:cut], " ".join(words[cut:])
        entity_type = vocab.nouns.get(noun_phrase)
        if entity_type is None:
            continue
        if not qualifier_words:
            return (f"count:{entity_type}", threshold)
        if len(qualifier_words) != 1:
            return None                      # two qualifiers is a phrase we did not declare
        narrowing = vocab.qualifiers.get(qualifier_words[0])
        if narrowing is None:
            return None                      # an undeclared qualifier is not a count we can check
        return (f"count:{entity_type}:{narrowing[0]}={narrowing[1]}", threshold)
    return None


# =================================================================================================
# STEP 1 — THE DORMANT CONDITION
# =================================================================================================

@dataclass(frozen=True, slots=True)
class DormantCondition:
    """One conditional promise, parked until its condition becomes true.

    `subject_node_id` is who the card will be about — the resolved counterparty, never a raw
    name. A condition with no resolved subject is not stored: it would be a finding with nobody
    to show it to, and inventing a subject is the same false-identity failure the dependency
    traversal refuses.
    """

    condition_id: str
    subject_node_id: str
    #: Who promised, and what — L1's own `Commitment.actor` / `.action`, unrewritten.
    actor: str
    action: str
    #: The condition verbatim, so the card shows the reader why this was not treated as a deadline.
    condition_text: str
    #: THE FIRST OF THE TWO SPANS — the sentence from May.
    statement_evidence: tuple[EvidenceSpan, ...]
    #: World time of the message the promise was made in.
    stated_at: datetime
    #: None when nothing deterministic could read it. Such a condition is review-only, for ever,
    #: until a human or M-5 gives it a predicate — and never auto-fires in the meantime.
    predicate: ConditionPredicate | None = None
    event_id: str = ""

    @property
    def review_required(self) -> bool:
        return self.predicate is None


def condition_id_for(*, subject_node_id: str, actor: str, action: str,
                     condition_text: str) -> str:
    """A content address, so the same promise read twice is one dormant condition.

    Deliberately NOT keyed on the event: the same commitment restated in a later message is the
    same commitment, and an event-keyed id would park two copies of one promise and satisfy them
    both — two identical cards, four months later, with no way for a reader to tell them apart.
    """
    payload = "\x1f".join((subject_node_id, _normalise(actor), _normalise(action),
                           _normalise(condition_text)))
    return f"cond_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def store_condition(commitment: Commitment, *, subject_node_id: str, stated_at: datetime,
                    event_id: str = "",
                    vocabulary: ConditionVocabulary | None = None) -> DormantCondition | None:
    """STEP 1 + 2 — a conditional commitment becomes a dormant condition, or is refused.

    Refused when it is not conditional, when it states no condition, or when the promise has no
    resolved subject. The first two are the doc's own gate (`is_conditional` AND `condition_text`
    — an unconditional promise is a deadline and belongs to the commitment tracker, not here).
    """
    if not commitment.is_conditional or not str(commitment.condition_text or "").strip():
        return None
    subject = str(subject_node_id or "").strip()
    if not subject:
        return None
    condition_text = str(commitment.condition_text).strip()
    return DormantCondition(
        condition_id=condition_id_for(subject_node_id=subject, actor=commitment.actor,
                                      action=commitment.action, condition_text=condition_text),
        subject_node_id=subject, actor=commitment.actor, action=commitment.action,
        condition_text=condition_text, statement_evidence=tuple(commitment.evidence),
        stated_at=require_aware(stated_at, "stated_at"),
        predicate=parse_condition(condition_text, vocabulary=vocabulary, stated_at=stated_at),
        event_id=str(event_id or ""))


# =================================================================================================
# STEP 3 — THE WORLD, AND WHAT IT CAN ANSWER FOR
# =================================================================================================

@dataclass(frozen=True, slots=True)
class WorldFact:
    """One thing the world can currently say, with the receipt that says it.

    THE SECOND OF THE TWO SPANS lives here. A world entry with no evidence can satisfy nothing:
    "you closed the second enterprise reference" with nothing to quote is the half of the card
    doc 03 calls unconvincing on its own, and a satisfaction built on it would be a claim about
    the customer's business with no source.
    """

    key: str
    value: int
    evidence: tuple[EvidenceSpan, ...]
    #: When the world last moved on this key — the instant step 5's half-life is measured from.
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ConditionWorld:
    """What is currently true, keyed the way predicates ask.

    ABSENT IS NOT ZERO. A key the world has never published answers `UNKNOWN`; a key it publishes
    at a value below the threshold answers `NOT_YET`. Conflating them is how a condition about a
    source nobody has connected quietly reads as "we checked, it has not happened".
    """

    facts: Mapping[str, WorldFact] = field(default_factory=dict)

    def get(self, key: str) -> WorldFact | None:
        return self.facts.get(key)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.facts))


@dataclass(frozen=True, slots=True)
class ConditionVerdict:
    """One evaluation: the answer, and — when it is `SATISFIED` — what made it true."""

    verdict: Verdict
    satisfying: WorldFact | None = None

    @property
    def satisfied(self) -> bool:
        return self.verdict is Verdict.SATISFIED


def evaluate(condition: DormantCondition, world: ConditionWorld, *,
             eval_time: datetime) -> ConditionVerdict:
    """STEP 3 — is it true NOW? `eval_time` is a parameter; nothing here reads a clock."""
    at = require_aware(eval_time, "eval_time")
    predicate = condition.predicate
    if predicate is None:
        return ConditionVerdict(Verdict.REVIEW_ONLY)
    if predicate.kind is PredicateKind.INSTANT:
        if predicate.instant is None:
            return ConditionVerdict(Verdict.REVIEW_ONLY)
        return ConditionVerdict(
            Verdict.SATISFIED if predicate.instant <= at else Verdict.NOT_YET,
            # An instant is satisfied by the calendar. There is no second span and none is
            # claimed — `SatisfiedCondition` knows this is the one kind that has no fact behind
            # it, so nothing downstream can render an empty receipt as a citation.
            satisfying=WorldFact(key=predicate.world_key, value=1, evidence=(),
                                 observed_at=predicate.instant)
            if predicate.instant <= at else None)
    found = world.get(predicate.world_key)
    if found is None:
        return ConditionVerdict(Verdict.UNKNOWN)
    if found.value < predicate.threshold:
        return ConditionVerdict(Verdict.NOT_YET)
    if not found.evidence:
        # The world says so and cannot show why. Refused rather than fired: a satisfaction with
        # one span is the unconvincing half of the card, and a card nobody believes is worse than
        # no card because it spends the trust the next one needs.
        return ConditionVerdict(Verdict.UNKNOWN)
    return ConditionVerdict(Verdict.SATISFIED, satisfying=found)


# =================================================================================================
# STEPS 4 AND 5 — THE SATISFACTION, AND ITS HALF-LIFE
# =================================================================================================

def strength_bp(*, satisfied_at: datetime, eval_time: datetime) -> int:
    """STEP 5 — how much a satisfaction is still worth, in integer basis points.

    Full strength for `FULL_STRENGTH_DAYS`, then a halving every `HALF_LIFE_DAYS`, interpolated
    linearly WITHIN each half-life so the number moves every day rather than falling off a cliff
    once a month — a step function would make two conditions satisfied a day apart rank a factor
    of two apart, which is an artefact of the arithmetic rather than of the world.

    Integer basis points and integer division throughout: this number is compared, ranked and
    stored, and a float would make two replays of one sweep disagree in the last digit and sort
    differently. A satisfaction dated in the future is full strength, not negative — clock skew
    between a source and a sweep is not a reason to discard a real fact.
    """
    at = require_aware(eval_time, "eval_time")
    since = require_aware(satisfied_at, "satisfied_at")
    days = (at - since).days
    if days <= FULL_STRENGTH_DAYS:
        return 10_000
    elapsed = days - FULL_STRENGTH_DAYS
    halvings, into = divmod(elapsed, HALF_LIFE_DAYS)
    if halvings >= MAX_HALVINGS:
        return 0
    high = 10_000 >> halvings
    low = high >> 1
    value = high - (high - low) * into // HALF_LIFE_DAYS
    return value if value >= STALE_STRENGTH_BP else 0


@dataclass(frozen=True, slots=True)
class SatisfiedCondition:
    """STEP 4 — `condition_satisfied`, carrying BOTH spans or refusing to exist.

    The constructor is the enforcement point, not a downstream renderer's `if`: the sentence from
    May and the fact from August are what make this claim checkable, and a satisfaction that
    carried one of them would be rendered by every consumer as though it carried both.
    """

    condition: DormantCondition
    satisfying: WorldFact
    #: When the world became true — the half-life's origin, and never the sweep's own instant.
    satisfied_at: datetime
    strength_bp: int

    def __post_init__(self) -> None:
        if not self.condition.statement_evidence:
            raise ValueError(
                "a satisfied condition requires the ORIGINAL statement's evidence — the card has "
                "to show the sentence from May, and a claim with no receipt is a guess")
        instant_kind = (self.condition.predicate is not None
                        and self.condition.predicate.kind is PredicateKind.INSTANT)
        if not self.satisfying.evidence and not instant_kind:
            raise ValueError(
                "a satisfied condition requires the SATISFYING fact's evidence — doc 03: both "
                "spans, because either alone is unconvincing (an instant predicate is the one "
                "exception: it is satisfied by the calendar, which has no sentence to quote)")

    @property
    def stale(self) -> bool:
        """Below the freshness floor. Globe: act while the evidence is fresh."""
        return self.strength_bp < STALE_STRENGTH_BP


def satisfy(condition: DormantCondition, world: ConditionWorld, *,
            eval_time: datetime,
            verdict: ConditionVerdict | None = None) -> SatisfiedCondition | None:
    """Evaluate, and build the satisfaction when — and only when — it is genuinely true.

    `verdict` lets a caller that has ALREADY evaluated hand its answer in rather than pay for a
    second evaluation — `correlate_timeline` needs the verdict for its other three branches, and
    before this argument existed it built the `SatisfiedCondition` itself, which left this
    function without a production caller and put two copies of "when has a dormant condition come
    true, and how strongly" in one module.
    """
    verdict = verdict if verdict is not None else evaluate(condition, world, eval_time=eval_time)
    if not verdict.satisfied or verdict.satisfying is None:
        return None
    satisfied_at = verdict.satisfying.observed_at
    return SatisfiedCondition(
        condition=condition, satisfying=verdict.satisfying, satisfied_at=satisfied_at,
        strength_bp=strength_bp(satisfied_at=satisfied_at, eval_time=eval_time))


@dataclass(frozen=True, slots=True)
class TimelineCorrelation:
    """One pass over a tenant's dormant conditions: what fired, what waits, what needs a human."""

    satisfied: tuple[SatisfiedCondition, ...] = ()
    waiting: tuple[DormantCondition, ...] = ()
    unknown: tuple[DormantCondition, ...] = ()
    review: tuple[DormantCondition, ...] = ()

    @property
    def fresh(self) -> tuple[SatisfiedCondition, ...]:
        return tuple(found for found in self.satisfied if not found.stale)


def correlate_timeline(conditions: Sequence[DormantCondition], world: ConditionWorld, *,
                       eval_time: datetime) -> TimelineCorrelation:
    """STEP 3 over every open condition. The pure entry point; the sweep is this plus I/O."""
    at = require_aware(eval_time, "eval_time")
    satisfied: list[SatisfiedCondition] = []
    waiting: list[DormantCondition] = []
    unknown: list[DormantCondition] = []
    review: list[DormantCondition] = []
    for condition in sorted(conditions, key=lambda item: item.condition_id):
        # `satisfy` rather than a second copy of it. This branch used to re-derive the
        # satisfaction — the same `evaluate`, the same `SatisfiedCondition`, the same
        # `strength_bp` — which left `satisfy` a public function with no production caller and
        # two places that had to agree for ever about when a dormant condition has come true.
        verdict = evaluate(condition, world, eval_time=at)
        found = satisfy(condition, world, eval_time=at, verdict=verdict)
        if found is not None:
            satisfied.append(found)
        elif verdict.verdict is Verdict.NOT_YET:
            waiting.append(condition)
        elif verdict.verdict is Verdict.UNKNOWN:
            unknown.append(condition)
        else:
            review.append(condition)
    return TimelineCorrelation(satisfied=tuple(satisfied), waiting=tuple(waiting),
                               unknown=tuple(unknown), review=tuple(review))


# =================================================================================================
# THE WORLD BUILDER — what L1's own claim stream can answer for, and nothing more
# =================================================================================================

@dataclass(frozen=True, slots=True)
class ClaimRecord:
    """One event's claims, with the world time they were made at. The reader's unit of work."""

    event_id: str
    occurred_at: datetime
    commitments: tuple[Commitment, ...] = ()
    decisions: tuple[DecisionState, ...] = ()
    entities: tuple[EntityMention, ...] = ()


def build_world(records: Sequence[ClaimRecord], *,
                vocabulary: ConditionVocabulary | None = None,
                qualifier_facts: Mapping[str, Mapping[str, str]] | None = None) -> ConditionWorld:
    """Build the world from L1's own evidenced claims — never from a fact with no span.

    WHY NOT `graph_facts`. It would be the obvious source and it cannot satisfy step 4:
    `graph_source_refs.evidence` stores `{"text": ...}` with no offsets, so a fact read back from
    the graph cannot produce an `EvidenceSpan` that anybody can check. L1's claims carry the real
    span, so the satisfying half of the card is quotable — which is the entire requirement.

    COUNTS ARE OF DISTINCT SURFACE FORMS, not of mentions. Ten emails naming one customer are one
    customer; counting mentions would satisfy "two enterprise customers" from a single thread.

    `qualifier_facts` is how a narrowed count is answered: `{surface_form: {field: value}}`,
    supplied by the caller from whatever it actually knows. Absent, a narrowed key is simply not
    published and the predicate answers `UNKNOWN` — never `NOT_YET`, because nobody counted.
    """
    vocab = vocabulary or default_condition_vocabulary()
    narrowing = {str(k).strip().lower(): v for k, v in (qualifier_facts or {}).items()}

    seen: dict[str, dict[str, tuple[datetime, tuple[EvidenceSpan, ...]]]] = {}
    events: dict[str, WorldFact] = {}

    for record in sorted(records, key=lambda item: (item.occurred_at, item.event_id)):
        for entity in record.entities:
            if not entity.evidence:
                continue
            surface = _normalise(entity.surface_form)
            if not surface:
                continue
            bucket = seen.setdefault(entity.entity_type, {})
            held = bucket.get(surface)
            if held is None or record.occurred_at > held[0]:
                bucket[surface] = (record.occurred_at, tuple(entity.evidence))
        for decision in record.decisions:
            if decision.state != "made" or not decision.evidence:
                continue
            key = vocab.events.get(_normalise(decision.subject))
            if key is None:
                continue
            world_key = f"event:{key}"
            held_event = events.get(world_key)
            if held_event is None or record.occurred_at > held_event.observed_at:
                events[world_key] = WorldFact(key=world_key, value=1,
                                              evidence=tuple(decision.evidence),
                                              observed_at=record.occurred_at)

    facts: dict[str, WorldFact] = dict(events)
    for entity_type, members in seen.items():
        facts[f"count:{entity_type}"] = _counted(f"count:{entity_type}", members.values())
        for field_name, value in sorted({pair for terms in narrowing.values()
                                         for pair in terms.items()}):
            matching = [entry for surface, entry in members.items()
                        if narrowing.get(surface, {}).get(field_name) == value]
            if not matching:
                continue
            key = f"count:{entity_type}:{field_name}={value}"
            facts[key] = _counted(key, matching)
    return ConditionWorld(facts=facts)


def _counted(key: str, entries: Iterable[tuple[datetime, tuple[EvidenceSpan, ...]]]) -> WorldFact:
    """One counted population, dated and evidenced by its MOST RECENT member.

    The newest member is the right receipt and the right date: it is the one that pushed the count
    over the line, and step 5's half-life is measured from when the condition BECAME true rather
    than from when the first of its members appeared.
    """
    members = sorted(entries, key=lambda entry: entry[0])
    latest = members[-1]
    return WorldFact(key=key, value=len(members), evidence=latest[1], observed_at=latest[0])


# =================================================================================================
# THE READ — conditional commitments and world claims, out of L1's store
# =================================================================================================

_CLAIMS_SQL = (
    "select e.event_id as event_id, e.occurred_at as occurred_at, x.output as output "
    f"from {EXTRACTION_TABLE} x "
    f"join {EVENT_TABLE} e on e.event_id = x.event_id and e.org_id = x.org_id "
    "where x.org_id = :org and e.occurred_at >= :since and e.occurred_at <= :until "
    "  and (jsonb_array_length(coalesce(x.output -> 'commitments', '[]'::jsonb)) > 0 "
    "    or jsonb_array_length(coalesce(x.output -> 'decision_states', '[]'::jsonb)) > 0 "
    "    or jsonb_array_length(coalesce(x.output -> 'entity_mentions', '[]'::jsonb)) > 0) "
    "order by e.occurred_at desc, e.event_id limit :cap")


def _spans(entries: Any) -> list[EvidenceSpan]:
    out: list[EvidenceSpan] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(EvidenceSpan(source_ref=entry["source_ref"], quote=entry["quote"],
                                    start_offset=entry["start_offset"],
                                    end_offset=entry["end_offset"],
                                    verified=bool(entry.get("verified", False))))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _record_of(row: Any) -> ClaimRecord | None:
    """One stored extraction back into typed claims. Rebuilt THROUGH the contracts, so a cached
    row written before a validator existed cannot enter the sweep wearing a shape nothing
    checks."""
    output = row.output if isinstance(row.output, dict) else {}
    commitments: list[Commitment] = []
    for entry in output.get("commitments") or []:
        if not isinstance(entry, dict):
            continue
        try:
            commitments.append(Commitment(
                actor=entry["actor"], action=entry["action"],
                beneficiary=entry.get("beneficiary"),
                is_conditional=bool(entry.get("is_conditional", False)),
                condition_text=entry.get("condition_text"),
                evidence=_spans(entry.get("evidence")),
                confidence_bp=entry.get("confidence_bp", 5000)))
        except (KeyError, TypeError, ValueError):
            continue
    decisions: list[DecisionState] = []
    for entry in output.get("decision_states") or []:
        if not isinstance(entry, dict):
            continue
        try:
            decisions.append(DecisionState(
                subject=entry["subject"], state=entry["state"],
                blocked_on=entry.get("blocked_on"), owner=entry.get("owner"),
                evidence=_spans(entry.get("evidence")),
                confidence_bp=entry.get("confidence_bp", 5000)))
        except (KeyError, TypeError, ValueError):
            continue
    entities: list[EntityMention] = []
    for entry in output.get("entity_mentions") or []:
        if not isinstance(entry, dict):
            continue
        try:
            entities.append(EntityMention(
                surface_form=entry["surface_form"], entity_type=entry["entity_type"],
                canonical_hint=entry.get("canonical_hint"),
                evidence=_spans(entry.get("evidence")),
                confidence_bp=entry.get("confidence_bp", 5000)))
        except (KeyError, TypeError, ValueError):
            continue
    if not (commitments or decisions or entities):
        return None
    return ClaimRecord(event_id=row.event_id, occurred_at=row.occurred_at,
                       commitments=tuple(commitments), decisions=tuple(decisions),
                       entities=tuple(entities))


def read_claim_records(engine, org_id: str, *, eval_time: datetime,
                       window_days: int = CONDITION_WINDOW_DAYS,
                       cap: int = MAX_CONDITIONS_PER_SWEEP) -> tuple[ClaimRecord, ...]:
    """Every evidenced claim inside the window. Never raises into a sweep — see the dependency
    reader's docstring for why an unreadable store must be fewer findings and not a 500."""
    at = require_aware(eval_time, "eval_time")
    if engine is None:
        return ()
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            rows = list(conn.execute(text(_CLAIMS_SQL), {
                "org": org_id, "since": at - timedelta(days=window_days), "until": at,
                "cap": cap}))
    except Exception:      # noqa: BLE001 — an unreadable claim store is no conditions, never a 500
        _log.warning("could not read conditional commitments for org=%s", org_id, exc_info=True)
        return ()
    return tuple(record for record in (_record_of(row) for row in rows) if record is not None)


def conditions_from(records: Sequence[ClaimRecord], resolve, *,
                    vocabulary: ConditionVocabulary | None = None) -> tuple[DormantCondition, ...]:
    """STEP 1 over a claim stream. `resolve` is the injected identity cascade — the beneficiary
    first (a promise is about who it is owed TO), the actor second.

    One condition per content address: the same promise restated across three emails is one
    dormant condition, and the EARLIEST statement is the one kept, because "you said in May" is
    the sentence the card is built on.
    """
    found: dict[str, DormantCondition] = {}
    for record in sorted(records, key=lambda item: (item.occurred_at, item.event_id)):
        for commitment in record.commitments:
            subject = None
            for candidate in (commitment.beneficiary, commitment.actor):
                if candidate:
                    subject = resolve(candidate)
                if subject:
                    break
            if not subject:
                continue
            condition = store_condition(commitment, subject_node_id=subject,
                                        stated_at=record.occurred_at, event_id=record.event_id,
                                        vocabulary=vocabulary)
            if condition is not None and condition.condition_id not in found:
                found[condition.condition_id] = condition
    return tuple(found[key] for key in sorted(found))


# =================================================================================================
# THE SWEEP — the wired entry point `context/runner.process_pending` calls
# =================================================================================================

@dataclass(frozen=True, slots=True)
class TimelineSweep:
    """What one sweep did, in numbers the drain's return value carries."""

    conditions: int = 0
    satisfied: int = 0
    waiting: int = 0
    unknown: int = 0
    review: int = 0
    facts_written: int = 0
    #: Rows whose open version already held exactly this value, so nothing was written for them.
    #: The honest half of the count: a sweep re-confirming a hundred unchanged dormant conditions
    #: produces no new fact, and reporting those as writes is how write amplification hides.
    facts_unchanged: int = 0
    #: Rows retired because they stopped being true. Soft-closed, never deleted.
    facts_closed: int = 0
    #: This sweep hit `MAX_FACT_WRITES_PER_SWEEP` and left rows unpublished — surfaced through the
    #: drain's return value rather than computed and discarded at its edge.
    budget_exhausted: bool = False


def _satisfied_json(found: SatisfiedCondition) -> dict[str, Any]:
    """Both spans, side by side, in the shape the card renders. The two-span requirement made
    literal: `statement` is the sentence from May and `satisfied_by` is the fact from August."""
    return {
        "condition_id": found.condition.condition_id, "actor": found.condition.actor,
        "action": found.condition.action, "condition_text": found.condition.condition_text,
        "stated_at": found.condition.stated_at.isoformat(),
        "satisfied_at": found.satisfied_at.isoformat(),
        "strength_bp": found.strength_bp, "stale": found.stale,
        "world_key": found.satisfying.key, "world_value": found.satisfying.value,
        "statement": [span.model_dump(mode="json") for span in found.condition.statement_evidence],
        "satisfied_by": [span.model_dump(mode="json") for span in found.satisfying.evidence],
    }


def _dormant_json(condition: DormantCondition) -> dict[str, Any]:
    return {
        "condition_id": condition.condition_id, "actor": condition.actor,
        "action": condition.action, "condition_text": condition.condition_text,
        "stated_at": condition.stated_at.isoformat(),
        "predicate": None if condition.predicate is None else {
            "kind": condition.predicate.kind.value, "world_key": condition.predicate.world_key,
            "threshold": condition.predicate.threshold,
            "instant": None if condition.predicate.instant is None
            else condition.predicate.instant.isoformat()},
        "statement": [span.model_dump(mode="json") for span in condition.statement_evidence],
    }


def _fact_rows(correlation: TimelineCorrelation, *, limit: int = MAX_FACT_WRITES_PER_SWEEP
               ) -> tuple[list[tuple[str, str, dict[str, Any]]], bool]:
    """One row per (node, field), the same bound the dependency pass carries and for the same
    reason: a row per condition would grow with every promise a tenant has ever made.

    Returns whether the cap CUT anything, so the drain can say so. The truncation is stable (by
    node) and stays that way for the reason `correlation_dependency._fact_rows` sets out at
    length: this pass closes the rows it did not publish, so rotating the order would retire the
    tail on one sweep and re-open it on the next, and a dormant condition would flap between
    "waiting" and "gone" every period."""
    rows: list[tuple[str, str, dict[str, Any]]] = []

    by_node: dict[str, list[SatisfiedCondition]] = {}
    for found in correlation.satisfied:
        by_node.setdefault(found.condition.subject_node_id, []).append(found)
    for node in sorted(by_node):
        ordered = sorted(by_node[node], key=lambda item: (-item.strength_bp,
                                                          item.condition.condition_id))
        rows.append((node, FIELD_SATISFIED, {"satisfied": [_satisfied_json(f) for f in ordered]}))

    dormant: dict[str, list[DormantCondition]] = {}
    for condition in (*correlation.waiting, *correlation.unknown):
        dormant.setdefault(condition.subject_node_id, []).append(condition)
    for node in sorted(dormant):
        ordered = sorted(dormant[node], key=lambda item: item.condition_id)
        rows.append((node, FIELD_DORMANT, {"open": [_dormant_json(c) for c in ordered]}))

    review: dict[str, list[DormantCondition]] = {}
    for condition in correlation.review:
        review.setdefault(condition.subject_node_id, []).append(condition)
    for node in sorted(review):
        ordered = sorted(review[node], key=lambda item: item.condition_id)
        rows.append((node, FIELD_REVIEW, {"review": [_dormant_json(c) for c in ordered]}))

    return rows[:limit], len(rows) > limit


def _write_facts(conn, *, org_id: str, rows: Sequence[tuple[str, str, dict[str, Any]]],
                 now: datetime) -> tuple[int, int, int]:
    """Publish this sweep's answer and CLOSE this module's rows that are no longer true.

    Identical in shape to the dependency pass's writer and identical in reasoning: published
    through `analytic/publish.publish_derived_fact` so a replay never MOVES an existing row's
    `valid_from`, and stale rows are closed with `valid_to` rather than deleted, because an as-of
    read of last week has to keep its answer and this whole layer is soft-delete-only.

    The old copy here ended its conflict clause with `valid_from = excluded.valid_from`, which
    moved the window of a row that already existed: a dormant condition first published in March
    and re-confirmed by September's sweep read back as `[September, inf)`, so
    `read_graph(as_of=March)` said GeniOS had never heard of a promise it had recorded in March.
    A condition that goes quiet and comes back is now two stints under two period-keyed ids, not
    one row claiming to have been true all along.

    `keep` is the ids the publisher RETURNED. An unchanged fact keeps the id of the period it was
    first published in, so a caller that rebuilt the id from (node, field) would close exactly the
    rows it meant to keep.

    Returns `(written, unchanged, closed)`.
    """
    prefix = f"{VERSION_PREFIX}:"
    written = unchanged = 0
    keep: list[str] = []
    for node_id, field_name, value in rows:
        published = publish_derived_fact(
            conn, org_id=org_id, subject_node_id=node_id, field=field_name, value=value,
            eval_time=now, value_type=VALUE_TYPE,
            visibility_scope=TIMELINE_VISIBILITY_SCOPE,
            version_prefix=prefix, fact_id=f"f_tl:{field_name}:{node_id}")
        keep.append(published.version_id)
        if published.wrote:
            written += 1
        else:
            unchanged += 1
    closed = close_derived_facts(conn, org_id=org_id, version_prefix=prefix, keep=keep,
                                 eval_time=now)
    return written, unchanged, closed


def refresh_dormant_conditions(store, org_id: str, *, eval_time: datetime,
                               window_days: int = CONDITION_WINDOW_DAYS,
                               cap: int = MAX_CONDITIONS_PER_SWEEP,
                               vocabulary: ConditionVocabulary | None = None,
                               qualifier_facts: Mapping[str, Mapping[str, str]] | None = None,
                               ) -> TimelineSweep:
    """BLG-06, end to end, for one org. Called from `context/runner.process_pending`.

    ON THE DRAIN and UNCONDITIONAL, like every other L2 sweep: a dormant condition becomes true
    because the WORLD moved, not because new mail arrived about the promise, and the whole
    premise is that the two moments are months apart. Gating this on "did this thread get a reply"
    would guarantee the one surface people remember never fires.
    """
    at = require_aware(eval_time, "eval_time")
    records = read_claim_records(store.engine, org_id, eval_time=at, window_days=window_days,
                                 cap=cap)
    if not records:
        with store.engine.begin() as conn:
            _, _, closed = _write_facts(conn, org_id=org_id, rows=(), now=at)
        return TimelineSweep(facts_closed=closed)

    from genios_engine.context.correlation_dependency import graph_endpoint_resolver

    with store.engine.connect() as conn:
        conditions = conditions_from(records, graph_endpoint_resolver(conn, org_id=org_id),
                                     vocabulary=vocabulary)
    world = build_world(records, vocabulary=vocabulary, qualifier_facts=qualifier_facts)
    correlation = correlate_timeline(conditions, world, eval_time=at)

    rows, exhausted = _fact_rows(correlation)
    with store.engine.begin() as conn:
        written, unchanged, closed = _write_facts(conn, org_id=org_id, rows=rows, now=at)
    return TimelineSweep(conditions=len(conditions), satisfied=len(correlation.satisfied),
                         waiting=len(correlation.waiting), unknown=len(correlation.unknown),
                         review=len(correlation.review), facts_written=written,
                         facts_unchanged=unchanged, facts_closed=closed,
                         budget_exhausted=exhausted)


__all__ = ["CONDITION_WINDOW_DAYS", "EXTRACTION_TABLE", "FACT_PREFIX", "FIELD_DORMANT",
           "FIELD_REVIEW", "FIELD_SATISFIED", "FULL_STRENGTH_DAYS", "HALF_LIFE_DAYS",
           "MAX_CONDITIONS_PER_SWEEP", "MAX_FACT_WRITES_PER_SWEEP", "MAX_HALVINGS",
           "STALE_STRENGTH_BP", "TIMELINE_VISIBILITY_SCOPE", "VALUE_TYPE", "VERSION_PREFIX",
           "ClaimRecord",
           "ConditionPredicate",
           "ConditionVerdict", "ConditionVocabulary", "ConditionWorld", "DormantCondition",
           "PredicateKind", "SatisfiedCondition", "TimelineCorrelation", "TimelineSweep",
           "Verdict", "WorldFact", "build_world", "condition_id_for", "conditions_from",
           "correlate_timeline", "default_condition_vocabulary", "evaluate", "parse_condition",
           "read_claim_records", "refresh_dormant_conditions", "satisfy", "store_condition",
           "strength_bp"]
