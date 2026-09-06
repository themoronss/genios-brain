"""L1.4.8 · the batch planner and cost governor — what the drain is about to spend, before it does.

Doc 04 gives this component a row in the map ("3 units, W4, exists, port") and then never
writes it. What "exists" refers to is two controls that were built at different times for
different doors and have never met:

* commit `7e17a6d` — a per-org DAILY ceiling on `llm_costs` rows, checked in `api/routes.py`
  before a sync is allowed to START. Pre-flight only, fail-open on a broken check, and set far
  above a real day's work so only a runaway trips it. It is on the "must not regress" list
  (item 7) and its three properties are preserved here verbatim: **pre-flight, never
  mid-flight**; **a per-call ceiling as well as a per-money one**; **a refusal that names
  itself** rather than an exception nobody can attribute;
* doc 04's own L1.4.10 line — *"org daily T3 budget exhausted -> demote to T2 and record
  `tier_demoted`"* — which no code has ever implemented.

The gap between them is the reason this module exists. A breaker is all-or-nothing: it stops
the sync or it does not, and on the day a tenant's inbox doubles the honest answer is neither
"spend whatever it takes" nor "read nothing today". It is *read everything, more cheaply* —
and read the forty-page agreement properly or not at all, because a contract read by the
cheapest model produces a confident wrong renewal date, which costs more than not reading it.

    L1.4.8-U1 · `plan_batch` — the calls one drain will make, chunked, ordered and estimated
    L1.4.8-U2 · `govern`     — admit, DEMOTE or refuse each call against a budget
    L1.4.8-U3 · `breaker`    — the pre-flight hard stop, ported from 7e17a6d

**DEMOTION IS NEVER SILENT.** `GovernedCall.tier_demoted` is the flag doc 04's L1.4.10 names,
and it is set by this module because this module is what decides it — L1.4.10 scores content to
pick a tier and has no idea what the day has cost. The router stamps the flag onto its own
decision from here, the extractor writes it to `l1_extraction_results.tier`, and the admin
console counts it: *"persistent demotion means the budget is wrong, not the router."* A
demotion nobody can count is a quality regression that presents as a mystery.

**EVERY FIGURE IS AN INTEGER IN MINOR UNITS.** Money is cents; rates are minor units per
million tokens; the breaker threshold is basis points of the daily budget. Rounding on cost is
always UP (`_ceil_div`), because a governor that under-estimates by a rounding error on each of
forty thousand calls has authorised a spend nobody approved. `platform/metrics.py` prices
history in floats against a stale table (`opus` at $15/MTok); it is deliberately not imported —
see `DEFAULT_TIER_PRICES`.

PURITY. No clock, no DB, no model, no float. "Today" is not read here: `Ledger` is what the day
has cost so far and the caller reads it from `llm_costs`, exactly as `_llm_over_daily_cap`
already does, which keeps this module replayable against a stored ledger.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from functools import lru_cache

from genios_engine.capture.documents.chunking import chunk_document
from genios_engine.capture.semantic.injection import fence
from genios_engine.capture.semantic.profiles import TIERS, get_profile
from genios_engine.capture.semantic.schema_gen import generate_schema_block
from genios_engine.capture.semantic.vocabulary import vocabulary_block

#: Characters per token, for estimation only. Four is the long-standing English-prose ratio and
#: it is deliberately not a tokenizer call: the planner runs over every event in a drain before
#: any of them is sent, so an exact count would cost a network round trip per call to decide
#: whether to make the call. The estimate feeds a BUDGET, and a budget wants a cheap number
#: that errs high, which `_ceil_div` guarantees.
CHARS_PER_TOKEN = 4

#: What the nonce fence adds around the body: two markers, their nonces and the newlines that
#: separate them from the content. MEASURED, once, off `injection.fence` itself rather than
#: typed — the fence is fixed-length by construction (`NONCE_CHARS` hex digits in each of two
#: markers), so probing it with a one-character body gives the exact constant and a rename of
#: `OPEN_LABEL` re-derives it instead of silently invalidating a literal.
FENCE_OVERHEAD_CHARS = len(fence("x").text) - 1

#: The envelope allowance for a request that does not declare its own. The envelope is per-call
#: content — direction, sender, recipients, subject, thread position — so `ExtractionRequest`
#: carries `envelope_chars` and a caller that has built one passes its real length. This default
#: is what an undeclared envelope is CHARGED, and it deliberately sits well above a real five-key
#: envelope (~110 characters): an estimator that guesses low on the one term it cannot see is the
#: defect this module was fixing, and 512 characters is 128 tokens against a ~2,800-token spine.
DEFAULT_ENVELOPE_CHARS = 512

#: Output estimate: a floor, a proportion of the input, and a ceiling. Extraction output is the
#: claims plus their quotes, so it scales with the input but far below it — and it is bounded,
#: because `MAX_UNCLASSIFIED_PER_EXTRACTION` and the per-claim quote cap bound how much a
#: single extraction can say. A flat per-call constant would over-price a chat line by an order
#: of magnitude and under-price a contract section.
OUTPUT_FLOOR_TOKENS = 200
OUTPUT_SHARE_BP = 1500
OUTPUT_CAP_TOKENS = 4000

#: One basis point ceiling, shared with every other bp figure in Layer 1.
BP_FULL = 10000

#: The lowest tier each profile may be demoted to. Doc 04's L1.4.10 override — *"profile in
#: {document, transcript} always >= T2"* — restated as a floor the GOVERNOR respects, because a
#: floor only the router enforces is a floor the budget walks straight through. A document that
#: cannot be afforded at T2 is REFUSED, not demoted to T1: an unread contract is a gap somebody
#: notices, and a contract read badly is a wrong renewal date nobody notices until it renews.
TIER_FLOORS = {"email": "T1", "chat": "T1", "crm_note": "T1", "document": "T2", "transcript": "T2"}

#: The default floor for a profile id this table does not name. `get_profile` degrades an
#: unknown id to `email`, so this is reached only if the registry grows a profile and this table
#: is not updated — T1 is the wrong answer to guess for an unknown content type, so the
#: conservative default floors it at T2 and the demotion simply stops one step earlier.
FALLBACK_TIER_FLOOR = "T2"


@dataclass(frozen=True)
class TierPrice:
    """List price for one tier, in minor units per MILLION tokens.

    Per million rather than per token because per-token prices are fractions of a cent, and the
    only integer representation of a fraction is a rounding rule somebody forgets. Per million
    keeps every rate a whole number and pushes the single rounding to `_ceil_div`, where it is
    named and always rounds against us.
    """

    tier: str
    input_per_mtok: int
    output_per_mtok: int
    priced_against: str

    def __post_init__(self) -> None:
        if self.tier not in TIERS:
            raise ValueError(f"unknown tier {self.tier!r}; expected one of {TIERS}")
        if self.input_per_mtok < 0 or self.output_per_mtok < 0:
            raise ValueError(f"{self.tier}: a negative rate would make a call earn money")


#: US cents per million tokens, at list. `priced_against` records WHICH model each tier was
#: priced from and is documentation, not a routing decision — L1.4.10 owns the tier-to-snapshot
#: mapping, and `govern` takes a `prices` argument so that when the router lands it can supply
#: the table for the snapshots it actually calls.
#:
#: NOT read from `platform/metrics.LLM_PRICE`: that table is float USD per token, is keyed by
#: family substring, and still carries $15/$75 for opus. It prices HISTORY, where a stale rate
#: mis-reports a past bill; this prices a call about to be made, where a stale rate authorises
#: a spend. Two different jobs, and merging them would make the analytics table load-bearing
#: for the breaker.
DEFAULT_TIER_PRICES: dict[str, TierPrice] = {
    "T1": TierPrice("T1", 100, 500, "claude-haiku-4-5"),
    "T2": TierPrice("T2", 200, 1000, "claude-sonnet-5"),
    "T3": TierPrice("T3", 500, 2500, "claude-opus-5"),
}

#: How many calls one planned batch may hold. A backfill can produce tens of thousands of
#: chunks, and a plan that held all of them would be a governor decision made over a ledger that
#: is minutes stale by the time the last call runs. Planning in waves keeps each governed batch
#: decided against a ledger the caller just read.
DEFAULT_MAX_CALLS = 500

#: Refusal and demotion reasons. Constants because callers branch on them, they land in a
#: progress row a customer reads, and a reason typed twice is a reason that stops matching.
ADMITTED = ""
REASON_BREAKER_TRIPPED = "breaker_tripped"
REASON_DAILY_BUDGET = "daily_budget_exhausted"
REASON_T3_BUDGET = "t3_budget_exhausted"
REASON_CALL_CAP = "daily_call_cap_reached"
REASON_OVERSIZED = "chunk_oversized"


def _ceil_div(numerator: int, denominator: int) -> int:
    """Integer division that rounds UP, for every cost in this module.

    A cost estimate that rounds down is a cost estimate that authorises slightly more than the
    budget, once per call, forever. `int(x * 0.9)`-style arithmetic is refused across
    `capture/` for the same reason; here the direction of the error is the whole point.
    """
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return -(-numerator // denominator)


@dataclass(frozen=True)
class ExtractionRequest:
    """One message the drain wants extracted, before anyone has decided how.

    `requested_tier` arrives from L1.4.10, which scored the content. It is what the router
    asked for, never what will run — `govern` may return something cheaper, and the difference
    between the two is exactly what `tier_demoted` reports.

    `envelope_chars` is the ONE part of the assembled prompt this module cannot measure for
    itself: the envelope is built per event by the extractor from that event's headers, so the
    caller declares its length and the planner charges for it. It defaults to
    `DEFAULT_ENVELOPE_CHARS` rather than to zero because an undeclared envelope is still an
    envelope that gets sent, and a default of zero would reintroduce, in miniature, exactly the
    under-count `fixed_prompt_tokens` exists to remove. Zero is a legitimate DECLARED value —
    an uploaded document has no sender — but it has to be said.
    """

    event_id: str
    profile_id: str
    content: str
    requested_tier: str
    envelope_chars: int = DEFAULT_ENVELOPE_CHARS

    def __post_init__(self) -> None:
        if not isinstance(self.envelope_chars, int) or isinstance(self.envelope_chars, bool):
            raise TypeError(f"envelope_chars must be an integer count of characters, got "
                            f"{self.envelope_chars!r}; a fractional character is not a thing a "
                            "prompt can contain")
        if self.envelope_chars < 0:
            raise ValueError(f"envelope_chars must not be negative, got {self.envelope_chars}; a "
                             "negative envelope would BUY back budget the call still spends")
        if not self.event_id.strip():
            raise ValueError("event_id is required — a call nothing can attribute cannot be "
                             "billed, cached or replayed")
        if self.requested_tier not in TIERS:
            raise ValueError(f"{self.event_id}: unknown tier {self.requested_tier!r}; expected "
                             f"one of {TIERS}")
        if not self.content.strip():
            raise ValueError(f"{self.event_id}: content is empty — planning a call over nothing "
                             "spends tokens and returns invention")


@dataclass(frozen=True)
class PlannedCall:
    """One model call the drain will make, sized and priced but not yet authorised.

    `chunk_start` is carried because L1.4.6 needs it: every offset the model returns for this
    chunk is a VIEW offset, and `prepared = view + chunk_start` is the rule that turns it into
    a span the store can resolve. A plan that dropped it would produce calls whose evidence
    cannot be aligned, which is not visible until a quote fails to verify.
    """

    event_id: str
    profile_id: str
    chunk_index: int
    chunk_count: int
    chunk_start: int
    content_chars: int
    requested_tier: str
    floor_tier: str
    input_tokens: int
    output_tokens: int
    oversized: bool

    def __post_init__(self) -> None:
        if self.chunk_index < 0 or self.chunk_index >= self.chunk_count:
            raise ValueError(f"{self.event_id}: chunk {self.chunk_index} of {self.chunk_count} "
                             "is not a chunk that exists")
        if self.input_tokens <= 0 or self.output_tokens <= 0:
            raise ValueError(f"{self.event_id}: a call with no estimated tokens cannot be priced")

    def cost_minor(self, tier: str, prices: dict[str, TierPrice]) -> int:
        """What this call costs at `tier`, in minor units, rounded up.

        Priced per part rather than on a summed token count, because input and output are
        charged at different rates and a single blended rate would be wrong in whichever
        direction the ratio happened to fall.
        """
        price = prices.get(tier)
        if price is None:
            raise ValueError(f"no price for tier {tier!r}; priced tiers: {sorted(prices)}")
        return (_ceil_div(self.input_tokens * price.input_per_mtok, 1_000_000)
                + _ceil_div(self.output_tokens * price.output_per_mtok, 1_000_000))


@dataclass(frozen=True)
class ExtractionPlan:
    """L1.4.8-U1's output: every call this wave will make, in arrival order.

    ORDER IS THE CALLER'S, and that is a decision. Under a budget that runs out mid-batch, the
    order decides who goes unread, and this module will not rank messages — ranking is
    importance, importance is ALG-17 over VALIDATED facts, and a batch planner that sorted by
    its own guess at what matters would be scoring content before anything had read it. Arrival
    order is defensible and explicable; a heuristic here would be neither.
    """

    calls: tuple[PlannedCall, ...]
    deferred: tuple[ExtractionRequest, ...]
    planned_chars: int

    def groups(self) -> tuple[tuple[PlannedCall, ...], ...]:
        """The calls of one event, together, in chunk order.

        The unit `govern` admits or refuses. A document whose chunk 1 ran and whose chunk 7 was
        refused for budget is not a cheaper extraction of that document, it is a contract with
        its termination clause missing and no marker saying so — the same harm
        `capture/documents/chunking.py` refuses to cause by splitting a clause.
        """
        out: list[tuple[PlannedCall, ...]] = []
        current: list[PlannedCall] = []
        for call in self.calls:
            if current and call.event_id != current[-1].event_id:
                out.append(tuple(current))
                current = []
            current.append(call)
        if current:
            out.append(tuple(current))
        return tuple(out)


def _spine_chars(profile_id: str) -> int:
    """The template's own characters, with all four substitutions emptied.

    Rendered rather than arithmetic on placeholder lengths, because `str.format` is what the
    extractor runs and a second model of the same substitution is a second thing to get wrong.
    """
    template = get_profile(profile_id).prompt_template
    return len(template.format(schema="", vocab="", envelope="", content=""))


@lru_cache(maxsize=None)
def fixed_prompt_tokens(profile_id: str) -> int:
    """Every token an assembled call pays before a single character of the body — MEASURED.

    The four things `render_prompt` puts in a prompt, all of them counted here because all four
    are billed:

    * the **spine** — the profile's own six blocks. Per profile, not flat: the `transcript` role
      paragraph and the `chat` one differ, and every call in a backfill pays the difference;
    * the **schema block** — `generate_schema_block()` over `ExtractionResult`, ~7,000
      characters of JSON shape. This is the term that was missing;
    * the **vocabulary block** — the five closed sets;
    * the **fence** — L1.4.7's nonce delimiters around the body.

    It is generated, not assumed, and that is the whole point of the unit. The estimator it
    replaces charged `len(template)/4 + 900` and an assembled call is ~1,090 tokens more than
    that, on EVERY call. A governor short by 1,090 tokens a call authorises spend nobody
    approved and trips its daily breaker after the money is gone — the demotion path is not the
    broken part, the accounting feeding it was. Adding a field to `ExtractionResult` or a word
    to a closed set now re-prices the call by itself.

    Cached because the two generators walk a pydantic model and five frozensets and the planner
    asks once per request in a wave of hundreds. Both are pure functions of imported constants,
    so the cache can never go stale within a process.
    """
    fixed = (_spine_chars(profile_id) + len(generate_schema_block()) + len(vocabulary_block())
             + FENCE_OVERHEAD_CHARS)
    return _ceil_div(fixed, CHARS_PER_TOKEN)


def _output_tokens(body_tokens: int) -> int:
    """Estimated completion size for an input of `body_tokens`: floor, share, cap."""
    share = body_tokens * OUTPUT_SHARE_BP // BP_FULL
    return min(OUTPUT_CAP_TOKENS, OUTPUT_FLOOR_TOKENS + share)


def plan_batch(requests: tuple[ExtractionRequest, ...] | list[ExtractionRequest], *,
               max_calls: int = DEFAULT_MAX_CALLS) -> ExtractionPlan:
    """L1.4.8-U1 · turn a drain's worth of messages into the calls it would take to read them.

    Each request is chunked with ITS OWN profile's strategy and cap — `chunk_document` is the
    one splitter, so the extractor and the planner cannot disagree about where a document
    divides — and each chunk becomes one `PlannedCall` carrying its own offset, token estimate
    and tier floor.

    Two things this deliberately does not do:

    * **it does not truncate.** A section longer than the profile's `max_input_chars` comes back
      from the chunker `oversized`, is planned as an oversized call, and is REFUSED by `govern`
      with `chunk_oversized`. `render_prompt` would raise on it, and the alternative — cutting
      it to fit — produces a complete-looking extraction with the paragraph the number was in
      removed;
    * **it does not exceed `max_calls`.** Requests past the cap are returned in `deferred`,
      whole, so the caller re-plans them in the next wave against a ledger it has re-read. A
      request is never split across waves: a half-planned document is the partial read
      `groups()` exists to prevent.

    `max_calls` counts CALLS, not requests, because one attachment can be forty of them.
    """
    if max_calls < 1:
        raise ValueError(f"max_calls must be positive, got {max_calls}")
    calls: list[PlannedCall] = []
    deferred: list[ExtractionRequest] = []
    planned_chars = 0
    for request in requests:
        if deferred:
            deferred.append(request)
            continue
        profile = get_profile(request.profile_id)
        chunks = chunk_document(request.content, max_chars=profile.max_input_chars,
                                strategy=profile.chunk_strategy)
        if not chunks:
            raise ValueError(f"{request.event_id}: the chunker returned nothing for non-empty "
                             "content; the request and the profile disagree about what text is")
        if len(calls) + len(chunks) > max_calls:
            deferred.append(request)
            continue
        floor = TIER_FLOORS.get(profile.profile_id, FALLBACK_TIER_FLOOR)
        overhead = (fixed_prompt_tokens(profile.profile_id)
                    + _ceil_div(request.envelope_chars, CHARS_PER_TOKEN))
        for index, chunk in enumerate(chunks):
            body_tokens = _ceil_div(len(chunk.text), CHARS_PER_TOKEN)
            calls.append(PlannedCall(
                event_id=request.event_id, profile_id=profile.profile_id, chunk_index=index,
                chunk_count=len(chunks), chunk_start=chunk.start_offset,
                content_chars=len(chunk.text), requested_tier=request.requested_tier,
                floor_tier=floor, input_tokens=body_tokens + overhead,
                output_tokens=_output_tokens(body_tokens), oversized=chunk.oversized))
            planned_chars += len(chunk.text)
    return ExtractionPlan(calls=tuple(calls), deferred=tuple(deferred),
                          planned_chars=planned_chars)


@dataclass(frozen=True)
class Budget:
    """What one org may spend on extraction in one day, in minor units.

    Three ceilings, because the two that already existed bound different things and neither
    bounds the third:

    * `daily_minor` — the money ceiling. Reaching it stops NEW spend, and demotion is what the
      governor tries first;
    * `t3_daily_minor` — the sub-ceiling doc 04's L1.4.10 names. T3 is five times T1 and is
      where a runaway becomes expensive fastest, so it is capped separately: the day's frontier
      budget can run out while ordinary extraction continues at T2;
    * `daily_call_cap` — the CALL ceiling from 7e17a6d. It catches the failure money cannot: a
      loop re-extracting the same cheap message forever stays under a dollar ceiling for a long
      time while doing nothing but burning rate limit.

    `breaker_bp` is the hard stop as basis points of `daily_minor` — 15000 is the 1.5x the old
    `CostGuard` used. It may not be below `BP_FULL`, because a breaker that trips before the
    budget is spent means the budget was never the number.
    """

    daily_minor: int
    t3_daily_minor: int
    daily_call_cap: int
    breaker_bp: int = 15000
    currency: str = "USD"

    def __post_init__(self) -> None:
        for name in ("daily_minor", "t3_daily_minor", "daily_call_cap", "breaker_bp"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer in minor units, got {value!r}. A "
                                "float budget re-rounds differently on every worker")
            if value < 0:
                raise ValueError(f"{name} must not be negative, got {value}")
        if self.breaker_bp < BP_FULL:
            raise ValueError(
                f"breaker_bp is {self.breaker_bp}, below {BP_FULL} (1x the daily budget). A "
                "breaker that trips before the budget is spent makes daily_minor unreachable, "
                "so the number a human approved is not the number the system enforces")
        if self.t3_daily_minor > self.daily_minor:
            raise ValueError(
                f"t3_daily_minor ({self.t3_daily_minor}) exceeds daily_minor "
                f"({self.daily_minor}); a sub-budget larger than its parent never binds")

    @property
    def breaker_threshold_minor(self) -> int:
        """The hard stop, in minor units. Integer bp arithmetic, rounded down: the threshold is
        a ceiling on spend, so rounding it down keeps the enforced number at or below the
        authored one."""
        return self.daily_minor * self.breaker_bp // BP_FULL


@dataclass(frozen=True)
class Ledger:
    """What the day has cost so far. Read from `llm_costs` by the caller, never by this module.

    Passing it in is what keeps the governor replayable: the same plan and the same ledger
    produce the same decisions in September as they did in March, which a module that read the
    clock and the database could not promise.
    """

    spent_minor: int
    t3_spent_minor: int
    calls: int

    def __post_init__(self) -> None:
        for name in ("spent_minor", "t3_spent_minor", "calls"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer, got {value!r}")
            if value < 0:
                raise ValueError(f"{name} must not be negative, got {value}")
        if self.t3_spent_minor > self.spent_minor:
            raise ValueError(f"t3_spent_minor ({self.t3_spent_minor}) exceeds total spend "
                             f"({self.spent_minor}); the T3 sub-ledger is part of the total")


@dataclass(frozen=True)
class BreakerVerdict:
    """L1.4.8-U3's answer: may this org start extracting at all?

    `tripped` is the decision and `reason` names which ceiling did it. Both are carried into
    the progress row a customer reads — 7e17a6d's own lesson was that the job must show *"paused
    for today, resumes tomorrow"* rather than crash, and a verdict with no reason cannot say
    which of three ceilings to raise.
    """

    tripped: bool
    reason: str
    spent_minor: int
    budget_minor: int
    threshold_minor: int
    calls: int
    call_cap: int


def breaker(budget: Budget, ledger: Ledger) -> BreakerVerdict:
    """L1.4.8-U3 · the pre-flight hard stop, ported from commit `7e17a6d`.

    THREE ceilings trip it, and the money one is stated twice on purpose:

    * spend at or above `daily_minor` — `daily_budget_exhausted`. This is the ceiling the
      DEPLOYED control already enforces: `api/routes._llm_over_daily_cap` refuses to start a
      sync at `usd >= settings.daily_llm_usd_cap`, at 1x, not at 1.5x. A pre-flight here that
      admitted a batch at 1.2x the budget would be a second, laxer ceiling for the same money —
      the caller would get "may start" from this function and "refused" from the deployed one,
      and which answer applied would depend on which door the work came through;
    * spend at or above `breaker_threshold_minor` — `breaker_tripped`. The RUNAWAY stop, above
      the budget, kept separate so a reader can tell "today is spent" from "something is
      looping". Both refuse; only one is a bug report;
    * call count at or above `daily_call_cap` — `daily_call_cap_reached`. A zero cap means "no
      ceiling", which is how `_llm_over_daily_cap` already reads `GENIOS_LLM_DAILY_CAP=0`, and
      changing the meaning of a configured zero silently disables a control somewhere.

    The runaway is tested BEFORE the budget so the more serious of the two money reasons is the
    one reported when both hold.

    **PRE-FLIGHT ONLY.** This decides whether a batch may START. It has no way to interrupt a
    call already in flight and must never grow one: the original commit is explicit that the
    breaker never stops a run in progress, because a sync killed halfway leaves an org's graph
    in a state no drain reconciles.

    Unlike the original it does NOT fail open, and the difference is deliberate. That check
    swallowed exceptions and allowed the sync, because it read a database that could be down
    and blocking every tenant on a broken query would be worse than one uncapped day. This
    function reads two integers it was handed and cannot fail; the fail-open belongs at the
    call site that fetches the ledger, where it can distinguish "the DB is down" from "the
    budget is spent".
    """
    threshold = budget.breaker_threshold_minor
    if ledger.spent_minor >= threshold:
        reason = REASON_BREAKER_TRIPPED
    elif ledger.spent_minor >= budget.daily_minor:
        reason = REASON_DAILY_BUDGET
    elif budget.daily_call_cap > 0 and ledger.calls >= budget.daily_call_cap:
        reason = REASON_CALL_CAP
    else:
        reason = ADMITTED
    return BreakerVerdict(tripped=bool(reason), reason=reason, spent_minor=ledger.spent_minor,
                          budget_minor=budget.daily_minor, threshold_minor=threshold,
                          calls=ledger.calls, call_cap=budget.daily_call_cap)


@dataclass(frozen=True)
class GovernedCall:
    """One planned call, decided. The tier here is the tier that will actually run.

    `tier_demoted` is doc 04's flag and the reason this type exists rather than a filtered list
    of calls: a caller handed only the survivors could not tell a T3 extraction from a T3
    request served at T2, and the difference is the whole quality story of a constrained day.
    """

    call: PlannedCall
    admitted: bool
    tier: str
    tier_demoted: bool
    estimated_cost_minor: int
    reason: str

    def __post_init__(self) -> None:
        if self.admitted and self.reason not in (ADMITTED, REASON_T3_BUDGET, REASON_DAILY_BUDGET):
            raise ValueError(f"an admitted call may not carry the refusal reason "
                             f"{self.reason!r}")
        if not self.admitted and self.estimated_cost_minor:
            raise ValueError("a refused call must cost nothing; a non-zero estimate here would "
                             "be counted against a budget by a call that never ran")
        if self.tier_demoted and not self.admitted:
            raise ValueError("a refused call was not demoted, it was refused; recording both "
                             "would double-count the demotion the admin console monitors")


@dataclass(frozen=True)
class GovernedBatch:
    """L1.4.8-U2's output: every planned call with its decision, plus the totals that explain it.

    `estimated_cost_minor` is the sum over ADMITTED calls only, so it is the number the caller
    may add to the ledger after the batch runs — and it is an estimate, so the caller reconciles
    against real token counts afterwards rather than trusting it.
    """

    calls: tuple[GovernedCall, ...]
    breaker_verdict: BreakerVerdict
    estimated_cost_minor: int
    estimated_t3_cost_minor: int
    admitted: int
    demoted: int
    refused: int
    currency: str

    def admitted_calls(self) -> tuple[GovernedCall, ...]:
        """The calls the extractor may actually make, in plan order."""
        return tuple(call for call in self.calls if call.admitted)


def _demote(tier: str, steps: int, floor: str) -> str:
    """`tier` lowered by `steps`, never below `floor`. TIERS is ascending, so index is rank."""
    lowered = max(TIERS.index(floor), TIERS.index(tier) - steps)
    return TIERS[lowered]


def govern(plan: ExtractionPlan, *, budget: Budget, ledger: Ledger,
           prices: dict[str, TierPrice] | None = None) -> GovernedBatch:
    """L1.4.8-U2 · decide every call in `plan`: admit, demote, or refuse. Never silently.

    The algorithm, and why each step is where it is:

    1. **the breaker first.** If `breaker` has tripped, every call is refused with
       `breaker_tripped` and nothing is priced. There is no partial answer to a hard stop;
    2. **oversized chunks are refused before anything is budgeted.** `render_prompt` raises on
       content over the profile's cap, so an oversized chunk cannot run at any tier or price.
       Refusing it here means it never displaces a call that could have run;
    3. **each event group is decided whole**, at one tier vector. Demotion is applied to the
       group and re-priced, one step at a time, until it fits the remaining budget or every
       call in it sits on its `floor_tier`. A group still unaffordable at the floor is refused
       — `document` and `transcript` floor at T2 for the reason `TIER_FLOORS` states;
    4. **the running ledger advances with each admitted group**, so a batch cannot authorise
       forty calls that each fit the remaining budget individually and blow it together. This
       is the failure a per-call check has: it is correct on every call and wrong on the batch.

    Reasons survive onto ADMITTED calls when they were demoted, which is why `GovernedCall`
    permits a budget reason on an admitted call: `tier_demoted=True, reason="t3_budget_exhausted"`
    is the complete sentence — *this ran, more cheaply, because that ceiling was reached*.
    """
    table = DEFAULT_TIER_PRICES if prices is None else prices
    verdict = breaker(budget, ledger)
    decided: list[GovernedCall] = []
    spent, t3_spent, made = ledger.spent_minor, ledger.t3_spent_minor, ledger.calls
    batch_cost = batch_t3 = 0

    for group in plan.groups():
        runnable: list[PlannedCall] = []
        for call in group:
            if verdict.tripped:
                decided.append(_refuse(call, verdict.reason))
            elif call.oversized:
                decided.append(_refuse(call, REASON_OVERSIZED))
            else:
                runnable.append(call)
        if not runnable:
            continue
        if budget.daily_call_cap > 0 and made + len(runnable) > budget.daily_call_cap:
            decided.extend(_refuse(call, REASON_CALL_CAP) for call in runnable)
            continue

        steps = 0
        previous: tuple[str, ...] | None = None
        while True:
            tiers = tuple(_demote(call.requested_tier, steps, call.floor_tier)
                          for call in runnable)
            costs = [call.cost_minor(tier, table) for call, tier in zip(runnable, tiers)]
            total = sum(costs)
            t3_total = sum(cost for cost, tier in zip(costs, tiers) if tier == "T3")
            if t3_total and t3_spent + t3_total > budget.t3_daily_minor:
                blocked = REASON_T3_BUDGET
            elif spent + total > budget.daily_minor:
                blocked = REASON_DAILY_BUDGET
            else:
                blocked = ADMITTED
            if not blocked:
                break
            if tiers == previous:
                decided.extend(_refuse(call, blocked) for call in runnable)
                break
            previous, steps = tiers, steps + 1

        if blocked:
            continue
        for call, tier, cost in zip(runnable, tiers, costs):
            demoted = tier != call.requested_tier
            decided.append(GovernedCall(
                call=call, admitted=True, tier=tier, tier_demoted=demoted,
                estimated_cost_minor=cost,
                reason=(REASON_T3_BUDGET if demoted and call.requested_tier == "T3"
                        else REASON_DAILY_BUDGET if demoted else ADMITTED)))
        spent += total
        t3_spent += t3_total
        made += len(runnable)
        batch_cost += total
        batch_t3 += t3_total

    ordered = _in_plan_order(plan, decided)
    return GovernedBatch(
        calls=ordered, breaker_verdict=verdict, estimated_cost_minor=batch_cost,
        estimated_t3_cost_minor=batch_t3,
        admitted=sum(1 for call in ordered if call.admitted),
        demoted=sum(1 for call in ordered if call.tier_demoted),
        refused=sum(1 for call in ordered if not call.admitted), currency=budget.currency)


def _refuse(call: PlannedCall, reason: str) -> GovernedCall:
    """A refusal keeps the call's REQUESTED tier and costs nothing.

    Keeping the requested tier rather than blanking it is what lets a caller re-plan tomorrow
    without re-running L1.4.10 over content nothing has read.
    """
    return GovernedCall(call=call, admitted=False, tier=call.requested_tier, tier_demoted=False,
                        estimated_cost_minor=0, reason=reason)


def _in_plan_order(plan: ExtractionPlan,
                   decided: list[GovernedCall]) -> tuple[GovernedCall, ...]:
    """Restore the plan's own order after per-group decisions reshuffled it.

    Refused-in-group and admitted-in-group calls are appended at different moments, so without
    this the output order would encode the governor's control flow rather than the drain's. A
    caller zipping `plan.calls` against `batch.calls` — the obvious thing to do — would then
    pair a decision with the wrong call and never see an error.
    """
    by_key = {(governed.call.event_id, governed.call.chunk_index): governed
              for governed in decided}
    if len(by_key) != len(decided):
        raise ValueError("two decisions for one call; (event_id, chunk_index) is not unique in "
                         "this plan and a caller keying on it would silently drop one")
    return tuple(by_key[(call.event_id, call.chunk_index)] for call in plan.calls)


@dataclass(frozen=True)
class SpendVerdict:
    """L1.4.8-U4 · what the money ceiling says about ONE extraction, before it is made.

    A single typed answer rather than a `GovernedBatch` the caller has to reduce, because the
    reduction is a decision and it belongs here: an event is one extraction, its chunks are
    priced together, and a caller that admitted "the chunks that fit" would produce the partial
    read `ExtractionPlan.groups()` exists to prevent.

    `tier` is what will actually run and `requested_tier` is what the router asked for. They
    differ only under a ceiling, and `tier_demoted` IS that difference — the same contract
    `model_router.TierDecision` keeps, so the two cannot disagree about what a demotion is.
    """

    admitted: bool
    tier: str
    requested_tier: str
    tier_demoted: bool
    reason: str
    estimated_cost_minor: int
    breaker: BreakerVerdict

    def __post_init__(self) -> None:
        if self.tier_demoted != (self.tier != self.requested_tier):
            raise ValueError(
                f"tier_demoted={self.tier_demoted} but tier={self.tier!r} and requested_tier="
                f"{self.requested_tier!r}; the flag IS the difference between the two, and a "
                "demotion that does not set it is the silent downgrade this module exists to "
                "make impossible")
        if not self.admitted and self.estimated_cost_minor:
            raise ValueError("a refused extraction must cost nothing")


class CostGovernor:
    """One org's daily money ceiling, held across a drain and safe to share between threads.

    `govern` is a pure function — a plan and a ledger in, decisions out — which is the right
    shape for a unit and the wrong shape for `sync_runner`'s capture pool: ten workers each
    reading the same immutable ledger would each be told the budget is free, and the day's spend
    would be exceeded by roughly the worker count. Serialising read-decide-write is the whole
    job of this class, exactly as `pipeline.T3Allowance` does for the T3 COUNT allowance, and it
    is cheap: pricing a call is integer arithmetic over a fixed table, not I/O.

    **It does not read the database and it does not read the clock.** The opening ledger is
    handed in by the wiring that queried `llm_costs`, so the same plan and the same ledger decide
    the same way on any machine and in any month — the property that lets a disputed demotion be
    replayed. What it DOES do is advance that ledger with every admitted extraction, so the
    ceiling binds within a sweep and not only between sweeps.

    **It is the same ceiling as the deployed one, not a second one.** `api/routes`'
    `_llm_over_daily_cap` refuses to START a sync for an org already at
    `settings.daily_llm_usd_cap`; this refuses or demotes each CALL against that same number and
    the same `llm_costs` day. Pre-flight and in-flight halves of one budget — which is why
    `platform/wiring.make_cost_governor` builds the budget from that setting rather than from a
    number of its own, and why a zero cap means "no governor" here just as it means "no ceiling"
    there.
    """

    def __init__(self, budget: Budget, ledger: Ledger | None = None,
                 prices: dict[str, TierPrice] | None = None) -> None:
        self._budget = budget
        self._ledger = ledger if ledger is not None else Ledger(0, 0, 0)
        self._prices = prices
        self._lock = threading.Lock()

    @property
    def budget(self) -> Budget:
        return self._budget

    @property
    def ledger(self) -> Ledger:
        """What this process believes the day has cost so far, opening balance included."""
        with self._lock:
            return self._ledger

    def decide(self, request: ExtractionRequest) -> SpendVerdict:
        """Admit, demote or refuse ONE extraction, and spend what it costs — atomically."""
        with self._lock:
            plan = plan_batch((request,))
            batch = govern(plan, budget=self._budget, ledger=self._ledger, prices=self._prices)
            if not batch.calls:                     # the planner deferred it; nothing to decide
                raise ValueError(f"{request.event_id}: the planner produced no call for a "
                                 "request it was handed alone; a wave of one cannot defer")
            admitted = all(call.admitted for call in batch.calls)
            refusal = next((call.reason for call in batch.calls if not call.admitted), ADMITTED)
            decided = batch.calls[0]
            if not admitted:
                return SpendVerdict(
                    admitted=False, tier=request.requested_tier,
                    requested_tier=request.requested_tier, tier_demoted=False, reason=refusal,
                    estimated_cost_minor=0, breaker=batch.breaker_verdict)
            self._ledger = Ledger(
                spent_minor=self._ledger.spent_minor + batch.estimated_cost_minor,
                t3_spent_minor=self._ledger.t3_spent_minor + batch.estimated_t3_cost_minor,
                calls=self._ledger.calls + len(batch.calls))
            return SpendVerdict(
                admitted=True, tier=decided.tier, requested_tier=request.requested_tier,
                tier_demoted=decided.tier != request.requested_tier, reason=decided.reason,
                estimated_cost_minor=batch.estimated_cost_minor,
                breaker=batch.breaker_verdict)


__all__ = ["ADMITTED", "BP_FULL", "CHARS_PER_TOKEN", "DEFAULT_ENVELOPE_CHARS",
           "DEFAULT_MAX_CALLS", "DEFAULT_TIER_PRICES", "FALLBACK_TIER_FLOOR",
           "FENCE_OVERHEAD_CHARS", "OUTPUT_CAP_TOKENS", "OUTPUT_FLOOR_TOKENS", "OUTPUT_SHARE_BP",
           "REASON_BREAKER_TRIPPED", "REASON_CALL_CAP", "REASON_DAILY_BUDGET", "REASON_OVERSIZED",
           "REASON_T3_BUDGET", "TIER_FLOORS", "Budget", "BreakerVerdict",
           "CostGovernor", "ExtractionPlan", "ExtractionRequest", "GovernedBatch",
           "GovernedCall", "Ledger", "PlannedCall", "SpendVerdict", "TierPrice", "breaker",
           "fixed_prompt_tokens", "govern", "plan_batch"]
