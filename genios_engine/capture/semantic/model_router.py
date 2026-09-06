"""ALG-05 · L1.4.10 — the model router: which tier reads this, decided before anything reads it.

The cost lever of Layer 1, and the one component whose whole design is a refusal. A T3 model on
every newsletter is the fastest way to a bill nobody approved; a T1 model on a forty-page
contract is the fastest way to a wrong renewal date. Both mistakes are made by the same missing
decision, so the decision is made here, once, from counts.

**The critical constraint: deterministic inputs only.** Every term in the score is either a
length, a boolean the envelope already carries, or a count produced by the W2 structural parser
(`capture/structural/tokens.py`, L1.3.5-U2, `router_counts`). Nothing is inferred, and in
particular no model is asked which model should run — that would spend a call to decide whether
to spend a call, and it would make the answer unreproducible on replay, which is the property
the whole L1.4.9 cache depends on. *"This went to T3 because it had 4 currency tokens and 3 date
strings"* is a sentence somebody can check against the stored tokens; *"the model felt it was
complex"* is not.

**Two units.**

* **U1 · `decide_tier`** — the score, the bands, the two overrides, and the itemised
  contributions that make the total re-derivable by hand.
* **U2 · `record`** — the budget ledger the second override reads, and the demotion counter doc
  04's FAILURE MODES require be *"monitored and surfaced in the admin console"*. A demotion that
  is decided but never counted is a silent downgrade, which is the exact failure the visible
  `tier_demoted` flag exists to prevent — the flag makes one call honest, the counter makes the
  pattern visible.

**Demotion is visible, never silent.** When the org's daily T3 allowance is gone a T3 request
comes back T2 *with `tier_demoted` set and `requested_tier` preserved*, so the stored extraction
says what it was owed as well as what it got. Persistent demotion then means the budget is
wrong, not the router — a conclusion nobody can reach from a T2 row that looks like every other
T2 row.

**Pure.** Integer arithmetic only (no float anywhere: the score is points, the demotion rate is
basis points), no clock, no database, no model. The day boundary the budget resets on is the
caller's; this module is handed a budget and returns the next one.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from genios_engine.capture.semantic.profiles import PROFILES, TIERS
from genios_engine.capture.structural.tokens import RouterCounts

T1, T2, T3 = TIERS

#: Score band lower bounds, from doc 04's table: `T1 if < 40`, `T2 if 40 <= s < 75`, `T3 if >=
#: 75`. Expressed as bounds rather than as three comparisons so that the bands provably tile the
#: number line — `_check_bands` asserts they are ascending and start below any reachable score,
#: which is the property a hand-written chain of `elif`s cannot state.
T2_THRESHOLD = 40
T3_THRESHOLD = 75

#: Profiles that may never run on the cheapest model. A forty-page agreement and a diarized
#: hour of speech are the two shapes where a T1 miss is not "thinner meaning" but a wrong
#: number in a card — doc 04's first override, and the reason the spec's own table test says
#: *"a PDF chunk -> never T1"*.
FLOOR_T2_PROFILES: frozenset[str] = frozenset({"document", "transcript"})

#: The profile the score penalises. A Slack line is short, low-stakes and arrives in volume;
#: -30 is what keeps a busy channel from being the largest line on the invoice.
CHEAP_PROFILE = "chat"

#: Doc 04's thresholds, named so the score rows and the tests read the same constants.
LONG_CONTENT_CHARS = 4_000
DATE_TOKENS_FOR_POINTS = 2
CURRENCY_TOKENS_FOR_POINTS = 1
DEEP_THREAD_MESSAGES = 3


@dataclass(frozen=True)
class TierRequest:
    """Everything the score is computed from — all of it deterministic, all of it already known.

    `counts` is the W2 structural parser's output for this exact text, not a re-scan and not an
    estimate: `router_counts(scan(clean_text))`. It is taken as `RouterCounts` rather than as two
    integers precisely so that this signature changes the day ALG-05 starts scoring identifier
    density, instead of the router growing a private opinion about which dictionary key means
    "dates" (L1.3.5-U2's docstring makes that the point of the type).

    `internal_kind` is the company canon marker from the envelope — an org deliberately asserting
    something about itself enters at canon authority (`capture/validate/authority.py` rank 5),
    and material that outranks a system of record is worth reading properly.
    """

    profile_id: str
    content_length: int
    counts: RouterCounts
    attachment_present: bool = False
    thread_depth: int = 0
    internal_kind: str | None = None

    def __post_init__(self) -> None:
        if self.profile_id not in PROFILES:
            raise ValueError(
                f"unknown extraction profile {self.profile_id!r}. Unlike `get_profile`, this "
                "does NOT degrade to the email profile: the only ids that are not registered "
                "are the model-free `structured` bypass lane (doc 03), which must make zero "
                "model calls, and a caller bug. Silently tiering either one buys a model call "
                f"nobody asked for. Registered: {sorted(PROFILES)}")
        if self.content_length < 0:
            raise ValueError(f"content_length is {self.content_length}; a negative length is a "
                             "caller arithmetic bug, and it would suppress the +30 row silently")
        if self.thread_depth < 0:
            raise ValueError(f"thread_depth is {self.thread_depth}; depth is a count of messages "
                             "held, and a negative count has no meaning")


@dataclass(frozen=True)
class ScoreRow:
    """One row of doc 04's scoring table: a name, its points, and the condition that earns them.

    A table rather than a run of `+=` statements because the ROWS are the audit: `decide_tier`
    reports which fired, so a tier can be re-derived by hand from the stored contributions
    without re-reading the content. A `+=` chain reports only the total, and a total is not an
    explanation.
    """

    name: str
    points: int
    applies: Callable[[TierRequest], bool]
    why: str


#: Doc 04, L1.4.10-U1's pseudocode, transcribed row for row and in its order.
SCORE_TABLE: tuple[ScoreRow, ...] = (
    ScoreRow("long_content", 30,
             lambda r: r.content_length > LONG_CONTENT_CHARS,
             f"content is longer than {LONG_CONTENT_CHARS} characters"),
    ScoreRow("attachment_present", 25,
             lambda r: r.attachment_present,
             "the message carries an attachment"),
    ScoreRow("currency_tokens", 25,
             lambda r: r.counts.currency_token_count >= CURRENCY_TOKENS_FOR_POINTS,
             f"the structural parser found >= {CURRENCY_TOKENS_FOR_POINTS} currency token"),
    ScoreRow("date_tokens", 20,
             lambda r: r.counts.date_token_count >= DATE_TOKENS_FOR_POINTS,
             f"the structural parser found >= {DATE_TOKENS_FOR_POINTS} date strings"),
    ScoreRow("heavy_profile", 20,
             lambda r: r.profile_id in FLOOR_T2_PROFILES,
             "the profile is a document or a transcript"),
    ScoreRow("deep_thread", 15,
             lambda r: r.thread_depth >= DEEP_THREAD_MESSAGES,
             f"the thread holds >= {DEEP_THREAD_MESSAGES} messages"),
    ScoreRow("company_canon", 15,
             lambda r: r.internal_kind is not None,
             "the event is company canon (internal_kind is set)"),
    ScoreRow("cheap_profile", -30,
             lambda r: r.profile_id == CHEAP_PROFILE,
             "the profile is chat, which is short and arrives in volume"),
)


def _check_table() -> None:
    """Row names are unique and no row is worth nothing — both are silent-failure shapes.

    A duplicated name makes two different reasons indistinguishable in the audit; a zero-point
    row is a condition somebody meant to weight and left at the default, and it would report
    itself as "applied" while changing no outcome.
    """
    names = [row.name for row in SCORE_TABLE]
    if len(set(names)) != len(names):
        raise ValueError(f"SCORE_TABLE has duplicate row names {names}")
    zeroed = [row.name for row in SCORE_TABLE if row.points == 0]
    if zeroed:
        raise ValueError(f"SCORE_TABLE rows {zeroed} are worth 0 points — a row that cannot "
                         "change the tier reports itself as applied and does nothing")
    if not T2_THRESHOLD < T3_THRESHOLD:
        raise ValueError(f"bands must ascend: T2 at {T2_THRESHOLD}, T3 at {T3_THRESHOLD}")


_check_table()


@dataclass(frozen=True)
class TierContribution:
    """One score row, evaluated. Carried whether or not it fired.

    Non-firing rows are kept deliberately: *"this stayed T1 because it had no currency tokens"*
    is the explanation somebody needs when a card is missing an amount, and a list of only the
    rows that fired cannot give it.
    """

    name: str
    points: int
    applied: bool
    why: str

    @property
    def awarded(self) -> int:
        return self.points if self.applied else 0


#: Why a tier is not simply the band the score landed in.
FLOOR_REASON = "profile floor: a document or transcript is never read by the cheapest model"
BUDGET_REASON = "the org's daily T3 budget is exhausted"


@dataclass(frozen=True)
class TierDecision:
    """The tier, the arithmetic behind it, and — when they differ — what was asked for.

    `requested_tier` is what the score and the profile floor entitled this extraction to;
    `tier` is what it got. They differ only under the budget override, and that difference is
    the whole of `tier_demoted`. Storing both is what makes the FAILURE MODES line checkable:
    an admin console counting demotions is counting rows where the two disagree, and a schema
    that kept only the delivered tier could not produce that count at any price.
    """

    tier: str
    tier_score: int
    requested_tier: str
    tier_demoted: bool
    demotion_reason: str | None
    floor_applied: bool
    contributions: tuple[TierContribution, ...]

    def __post_init__(self) -> None:
        if self.tier not in TIERS or self.requested_tier not in TIERS:
            raise ValueError(f"tier {self.tier!r}/{self.requested_tier!r} not in {TIERS}")
        if self.tier_demoted != (self.tier != self.requested_tier):
            raise ValueError(
                f"tier_demoted={self.tier_demoted} but tier={self.tier!r} and "
                f"requested_tier={self.requested_tier!r}. The flag IS the difference between "
                "the two; a demotion that does not set it is the silent downgrade this unit "
                "exists to make impossible, and a flag set without a difference is a false "
                "alarm in the counter the admin console watches")
        if self.tier_demoted != (self.demotion_reason is not None):
            raise ValueError("a demotion carries its reason and a non-demotion carries none; "
                             f"got tier_demoted={self.tier_demoted}, "
                             f"demotion_reason={self.demotion_reason!r}")

    @property
    def fired(self) -> tuple[TierContribution, ...]:
        """Only the rows that earned points — the short form for a log line."""
        return tuple(c for c in self.contributions if c.applied)


def band_for(tier_score: int) -> str:
    """The tier a bare score lands in, before any override. Total over every integer."""
    if tier_score >= T3_THRESHOLD:
        return T3
    if tier_score >= T2_THRESHOLD:
        return T2
    return T1


@dataclass(frozen=True)
class T3Budget:
    """L1.4.10-U2 — one org's daily T3 allowance, and what has happened to it today.

    Frozen and returned-not-mutated, so a budget is a VALUE a caller can persist, compare and
    replay rather than a counter two coroutines race on. `day` is carried but never computed
    here: this module has no clock (a tier decision that depends on when it ran is not
    replayable), so the caller stamps the day it means and a stale row is visible as a day that
    does not match rather than as a budget that silently never resets.
    """

    #: How many T3 extractions the org may issue per day. 0 means no T3 at all — a legitimate
    #: plan, not a misconfiguration, so it is not refused.
    t3_limit: int
    #: T3 extractions actually issued today.
    t3_granted: int = 0
    #: Requests that scored T3 and were served T2 instead.
    t3_demoted: int = 0
    #: The day these counters belong to, as the caller names it (e.g. "2026-09-05"). Opaque.
    day: str = ""

    def __post_init__(self) -> None:
        for name in ("t3_limit", "t3_granted", "t3_demoted"):
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"{name} is {value}; a negative count would make `exhausted` "
                                 "read False forever and the budget unenforceable")

    @property
    def exhausted(self) -> bool:
        """No T3 left today. `>=` rather than `==` so a limit lowered mid-day takes effect
        immediately instead of waiting for the counter to walk back down to it."""
        return self.t3_granted >= self.t3_limit

    @property
    def t3_requested(self) -> int:
        """Extractions that were entitled to T3, served or not — the demotion denominator."""
        return self.t3_granted + self.t3_demoted

    @property
    def demotion_rate_bp(self) -> int:
        """Share of T3-entitled extractions that were demoted, in integer basis points.

        Basis points and floor division, never a float: this number is compared against a
        threshold in an alert, and two processes that disagree at the sixth decimal about
        whether 1/3 exceeds 0.3333 produce an alert that flaps. 0 when nothing asked for T3 —
        no demotions out of no requests is a healthy day, not an undefined one.
        """
        requested = self.t3_requested
        return 0 if requested == 0 else self.t3_demoted * 10_000 // requested


#: A budget for an org that has no T3 allowance configured.
#:
#: Zero, not unlimited. The two defaults fail in opposite directions and only one of them is
#: recoverable: an org wrongly capped at zero produces T2 extractions and a demotion counter
#: climbing in the admin console, which is exactly the signal doc 04 asks be monitored; an org
#: wrongly uncapped produces a frontier-model bill discovered at the end of the month.
NO_T3_BUDGET = T3Budget(t3_limit=0)

#: A budget that never demotes — for tests, backfills and the single-document paths where the
#: allowance is enforced somewhere else. Named so a call site reads as a decision.
UNLIMITED_T3 = T3Budget(t3_limit=1_000_000_000)


def decide_tier(request: TierRequest, budget: T3Budget = NO_T3_BUDGET) -> TierDecision:
    """L1.4.10-U1 — T1 / T2 / T3 for this extraction, from counts alone.

    The three steps doc 04 states, in its order:

    1. **score** every row of `SCORE_TABLE`, keeping the non-firing rows too, and band it;
    2. **floor** — a `document` or `transcript` profile is never T1, however short the chunk.
       A one-paragraph excerpt of a contract is still contract language, and the +20 heavy-profile
       row alone does not clear the T2 threshold;
    3. **budget** — a T3 the org cannot afford comes back T2 with `tier_demoted` set. The
       demotion is applied last, so `requested_tier` records what the content deserved rather
       than what the wallet allowed, and the two are stored separately.

    The floor and the budget cannot fight: the floor raises to T2 and the budget lowers only to
    T2, so no ordering of the two can produce a T1 for a document.
    """
    contributions = tuple(
        TierContribution(name=row.name, points=row.points, applied=row.applies(request),
                         why=row.why)
        for row in SCORE_TABLE)
    tier_score = sum(c.awarded for c in contributions)

    requested = band_for(tier_score)
    floor_applied = request.profile_id in FLOOR_T2_PROFILES and requested == T1
    if floor_applied:
        requested = T2

    demoted = requested == T3 and budget.exhausted
    return TierDecision(
        tier=T2 if demoted else requested,
        tier_score=tier_score,
        requested_tier=requested,
        tier_demoted=demoted,
        demotion_reason=BUDGET_REASON if demoted else None,
        floor_applied=floor_applied,
        contributions=contributions,
    )


def record(budget: T3Budget, decision: TierDecision) -> T3Budget:
    """L1.4.10-U2 — the budget after this decision has been acted on.

    **Derived unit** (the component map promises an L1.4.10-U2 and doc 04 writes no block for
    it). It is the other half of the override in U1: `decide_tier` READS `budget.exhausted`, and
    something has to make that property become true, or the budget is a constant and the second
    override is dead code that every test passes by handing it a pre-exhausted value.

    Exactly one counter moves per decision, and which one is the point:

    * **granted** — a served T3 spends allowance. T1 and T2 spend none: the limit doc 04 names
      is a *daily T3 budget*, and metering cheap calls against it would demote frontier work to
      pay for newsletters;
    * **demoted** — a T3 that came back T2 spends no allowance (it was never issued) but is
      counted, because the counter is the FAILURE MODES signal: *persistent demotion means the
      budget is wrong, not the router*. Rows both `tier` and `requested_tier` agree on move
      nothing.

    Idempotency is the caller's: this returns the next value, it does not remember decisions.
    Apply it once per issued extraction — on a cache HIT no model ran, so no allowance was spent
    and `record` must not be called at all.
    """
    if decision.tier_demoted:
        return replace(budget, t3_demoted=budget.t3_demoted + 1)
    if decision.tier == T3:
        return replace(budget, t3_granted=budget.t3_granted + 1)
    return budget


#: Why a tier was lowered by the MONEY ceiling rather than by the T3 count allowance.
COST_REASON = "the org's daily extraction budget would be exceeded at the requested tier"


def demote_for_cost(decision: TierDecision, tier: str, reason: str = COST_REASON) -> TierDecision:
    """The same decision, served at a cheaper `tier` because the budget said so — U1's override,
    reached from the other ceiling.

    L1.4.8's cost governor and this module's T3 allowance bound different things: one counts
    frontier extractions, the other counts money. Both can lower a tier, and the FAILURE MODES
    line doc 04 writes — *"persistent demotion means the budget is wrong, not the router"* —
    only holds if both demotions are counted the same way. So the money governor does not carry
    a private flag; it comes back through here, and the demotion lands on `tier_demoted` with
    `requested_tier` preserved, which is the one field an admin console counts.

    `requested_tier` is what the CONTENT deserved, so a decision already demoted by the
    allowance keeps its original request rather than recording the T2 it was talked down to:
    two ceilings, one entitlement.
    """
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}, got {tier!r}")
    if TIERS.index(tier) > TIERS.index(decision.tier):
        raise ValueError(
            f"a budget may only lower a tier: asked to move {decision.tier!r} up to {tier!r}. "
            "Raising a tier here would let a money ceiling BUY a better model than the content "
            "scored for, which is the router's decision and not the wallet's")
    if not reason:
        raise ValueError("a demotion carries its reason; an empty one makes the counter unreadable")
    if tier == decision.tier:
        return decision
    return replace(decision, tier=tier, tier_demoted=True, demotion_reason=reason)


def route(request: TierRequest, budget: T3Budget = NO_T3_BUDGET) -> tuple[TierDecision, T3Budget]:
    """U1 then U2 — the decision and the budget it leaves behind, for the ordinary call site.

    A convenience with one job: making the pairing impossible to get wrong. A caller that ran
    `decide_tier` and forgot `record` gets a budget that never exhausts and an org that never
    demotes — the failure is invisible until the invoice, which is the same class of bug as the
    260 cached extractions that survived a prompt fix.
    """
    decision = decide_tier(request, budget)
    return decision, record(budget, decision)


__all__ = ["BUDGET_REASON", "COST_REASON", "CHEAP_PROFILE", "CURRENCY_TOKENS_FOR_POINTS",
           "DATE_TOKENS_FOR_POINTS", "DEEP_THREAD_MESSAGES", "FLOOR_REASON",
           "FLOOR_T2_PROFILES", "LONG_CONTENT_CHARS", "NO_T3_BUDGET", "SCORE_TABLE", "T1", "T2",
           "T2_THRESHOLD", "T3", "T3_THRESHOLD", "UNLIMITED_T3", "ScoreRow", "T3Budget",
           "TierContribution", "TierDecision", "TierRequest", "band_for", "decide_tier",
           "record", "route"]
