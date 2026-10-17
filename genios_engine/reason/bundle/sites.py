"""MAP A's R-series, as a closed vocabulary — which model sites exist, at which tier, and what a
consult of one may end as.

**Why the ids live in code and not in a docstring.** Doc 11's tier discipline ("T2 only for
R-2/R-1/R-5; narration of already-decided alternatives is T1") is a spend decision, and a spend
decision expressed as a comment is a spend decision nobody enforces. `tier_for` is the one place a
site's tier is chosen, and `require_site` refuses a name nobody budgeted for — a typo must be a
refusal rather than a ledger row under `R-6` that reads as an activated site right up until the
month's bill.

**Why `OUTCOMES` includes five kinds of NOT-RUNNING.** Doc 01 C5 asks for the gate outcome on
every consult; a vocabulary that only distinguished success from failure would record "the
narrative was quiet" identically for a tenant who is not on the pilot, a tenant whose budget ran
out, a deployment with no API key, and a generation that failed its gauntlet twice. Those are four
different things to do about it.
"""

from __future__ import annotations

#: `context/llm/client.THINKING_OFF`, as its literal: no module of the bundle package but the gate
#: may import a model client (`tests/reason/test_bundle_doctrine`), and
#: `tests/reason/test_every_site_says_whether_it_thinks` holds the two words equal.
_THINKING_OFF = "off"

#: R-1 · the ambiguity interpreter. Returns a typed classification with a confidence, consumed as
#: EVIDENCE by units; never a verdict. Owned by the R-sites wave; the gate is shared.
SITE_INTERPRET = "R-1"
#: R-2 · the reasoning bundle narrative — this group's centrepiece. Runs after the decision is
#: fixed, once per published decision.
SITE_NARRATE = "R-2"
#: R-3 · alternatives narration, on card expand.
SITE_ALTERNATIVES = "R-3"
#: R-4 · expected-effect framing. Doc 11 folds it into R-2's call and doc 05 §3 says so twice, so
#: it has an id and no separate call: `expected_effect` is one of R-2's five prose fields. The id
#: exists so a future wave that unfolds it does not have to invent one.
SITE_EFFECT = "R-4"
#: R-5 · the low-confidence consult, after DEFER is chosen. Recorded non-authoritative.
SITE_CONSULT = "R-5"
#: ⛔ R-6 · L2-5's Context Reasoner — ⛔ RETIRED 2026-10-11 (`06` D51, STEP-12): the sweep no longer
#: consults it (it ran ahead of the change gate, `03` F141) and its feature is refused; the id stays so
#: the rows it wrote still name a site. **One call per SITUATION, never per event** — the pilot
#: carries 159 active situations against 465 events. T1 because the deterministic validator
#: (`context/proposal_gate`) is what makes a cheap model safe: without it you need Sonnet
#: everywhere, because nothing would catch the error. Sonnet is the ESCALATION, on two numbers,
#: not the tier.
SITE_SITUATION = "R-6"
#: ⛔ R-7 · the expert (STEP-12). One strong judgment of a FILE — the whole piece of work — each time
#: its fingerprint moves, never one per situation per sweep: the dossier in, an `ExpertReview`
#: (`contracts/expert_review`) out, validated against what the dossier holds. T2, and only T2:
#: `06` D7 (answered 10 Oct) is Sonnet-class only: the SITE is T2. STEP-13b's ladder (`EXPERT_LADDER`) climbs to it
#: from T1, and may reach an Opus-class third rung (`TIER_T3`, `06` D74) only where a tenant allows it — off for all.
SITE_EXPERT = "R-7"
#: R-8 · the morning brief's writer (STEP-15). The day's checked material in, one line per item
#: out — written once a day, never per event and never per situation. Haiku-class: the same
#: pattern as R-6's own note, a deterministic check (`executive/morning_check`) is what makes a
#: cheap model safe here, not that the brief is unimportant.
SITE_BRIEF = "R-8"
#: R-8E · the same brief asked once more, on the Sonnet-class tier, after the Haiku draft fails
#: its check twice or comes back malformed past its one repair (STEP-15 §8.3 point 3; s15-D1).
#: Never escalated again and never Opus: failing twice more, the template stands and the brief
#: says so.
SITE_BRIEF_ESCALATE = "R-8E"

R_SITES = (SITE_INTERPRET, SITE_NARRATE, SITE_ALTERNATIVES, SITE_EFFECT, SITE_CONSULT,
           SITE_SITUATION, SITE_EXPERT, SITE_BRIEF, SITE_BRIEF_ESCALATE)

#: Tier per site, exactly as doc 11 §1 prints it. T1 = Haiku-class, T2 = Sonnet-class, the same
#: two names `capture.semantic.batch.DEFAULT_TIER_PRICES` prices — reused rather than re-declared,
#: because a second tier vocabulary is a second place a price can be wrong.
TIER_T1 = "T1"
TIER_T2 = "T2"
#: ⛔ STEP-13b · the Opus-class tier (`06` D74, s13b-D1): the THIRD RUNG of the expert's ladder only — no site's
#: tier is T3 — built SWITCHED OFF for every tenant: `expert_ladder` refuses it unless the tenant allows it,
#: and switching it on waits for the lead's Opus pass on the residual cases. `llm_sites.tier_model` names it.
TIER_T3 = "T3"
SITE_TIERS = {
    SITE_INTERPRET: TIER_T2,
    SITE_NARRATE: TIER_T2,
    SITE_ALTERNATIVES: TIER_T1,
    SITE_EFFECT: TIER_T1,
    SITE_CONSULT: TIER_T2,
    SITE_SITUATION: TIER_T1,
    SITE_EXPERT: TIER_T2,
    SITE_BRIEF: TIER_T1,
    SITE_BRIEF_ESCALATE: TIER_T2,
}

#: ⛔ THE EXPERT'S RUNGS (`yc2_w27_s13b` M38.C1.L-contract.V0.U02; `speedrun008/YC-II W27/` STEP-13b §8.4 item 5): a
#: file's review is asked on the cheapest rung first and climbs only when the check shows a writer's own fault
#: (`contracts/model_ladder`). The ladder is CONFIGURATION — its order and length per tenant — and the prompt names
#: no model. The default is Haiku-class then Sonnet-class; a tenant may start at Sonnet (`("T2",)`, s13b-D2).
EXPERT_LADDER = (TIER_T1, TIER_T2)
#: Every rung there can be, cheapest first — `expert_ladder` picks among them.
EXPERT_RUNGS = (TIER_T1, TIER_T2, TIER_T3)
_RUNG_ORDER = EXPERT_RUNGS


def expert_ladder(rungs=None, *, allow_opus: bool = False) -> tuple[str, ...]:
    """The rungs a tenant's expert climbs, cheapest first. `None` is the default (`EXPERT_LADDER`). A ladder
    climbs one way — each rung once, in `T1 < T2 < T3` order — and T3 (Opus-class) is on it only when the tenant
    allows it (s13b-D1, off for every tenant): naming it without the allowance is refused loudly, never dropped
    silently, so a configuration that expects an Opus rung does not run without one."""
    ladder = tuple(EXPERT_LADDER if rungs is None else rungs)
    if not ladder:
        raise ValueError("a ladder has at least one rung")
    if any(r not in _RUNG_ORDER for r in ladder):
        raise ValueError(f"a rung is one of {_RUNG_ORDER}, not {ladder}")
    if len(set(ladder)) != len(ladder) or list(ladder) != sorted(ladder, key=_RUNG_ORDER.index):
        raise ValueError(f"a ladder climbs one way, each rung once, cheapest first, not {ladder}")
    if TIER_T3 in ladder and not allow_opus:
        raise ValueError("an Opus rung is off for every tenant until the tenant allows it (s13b-D1)")
    return ladder


#: The output ceiling per site, in tokens. A cap rather than a hope: doc 11 sizes R-2 at ~450
#: output tokens, and a model that decides to write an essay is a cost incident and a V-7 failure
#: at the same time.
#:
#: ⛔ "GENEROUS ENOUGH THAT A REAL NARRATIVE IS NEVER TRUNCATED" IS WHAT THIS COMMENT USED TO SAY,
#: AND IT WAS FALSE. Measured on the design partner's org 2026-10-04, over 24 hours of
#: `llm_costs`: `l4_bundle` ran 12 calls and EIGHT failed, every one of them at exactly 1400
#: output tokens — the ceiling, to the token. The successes ranged 737–1400 and averaged 1053, so
#: the real distribution runs past this cap and the narrative site was being cut mid-JSON two
#: times in three. The stored error said "unparseable JSON", which sent every reader to the
#: prompt; the budget was the answer the whole time.
#:
#: 2400 IS A MEASURED STEP, NOT A FREE HAND. It is ~1.7x the old cap — above every success we
#: have observed, still a hard bound on the essay this comment is right to fear. It is tuned from
#: the next measurement rather than guessed again: `LLMClient` reads `stop_reason` now, so a call
#: that still truncates says so in its own words instead of being filed as bad JSON, and
#: `scripts/pipeline_health.py` fails the moment a lane's failures cluster on one output size.
#:
#: ⛔ AND THAT MEASUREMENT WAS NOT OF PROSE (the 13 Oct audit, s5t-F4; `yc2_w27_s18`
#: M50.C2.L-contract.V1.U02). R-2 ran on `claude-sonnet-5`, which THINKS BY DEFAULT and spends its
#: thinking from the same `max_tokens`: the 737–1,400 above were thinking plus answer, read as answer.
#: The answer itself is ~450 tokens (doc 11), at most ~1,000 by its field caps
#: (`contracts/reasoning`). Every site now asks with thinking OFF (`SITE_THINKING`, `06` D71), which is
#: what these ceilings were sized for; a site that thinks sizes its ceiling for thinking plus answer.
SITE_MAX_OUTPUT_TOKENS = {
    SITE_INTERPRET: 400,
    SITE_NARRATE: 2400,
    SITE_ALTERNATIVES: 600,
    SITE_EFFECT: 400,
    SITE_CONSULT: 600,
    # Structured output, not prose: a proposal is a mapping of at most fourteen fields, and a
    # model that decides to explain itself is a cost incident and a V-8 failure at once.
    SITE_SITUATION: 500,
    # ⛔ MEASURED, AND THE OLD SIZING WAS WRONG (s5t-F2, F4). The 4,000 here was sized from "a full
    # review runs about 800-1,600 tokens". The golden live passes of 12 Oct measured it: on Haiku 4.5,
    # which does not think, a review ran p50 2,737, p90 3,509, max 3,990 output tokens and six more
    # were cut at 4,000; on Sonnet 5, which thinks by default, all 203 calls stopped at 4,000 (thinking
    # ~2,600-3,500 of it). Asked with thinking OFF (`06` D71), 6,000 is 1.7x Haiku's p90 — ~$0.06 of
    # output at the T2 price, $0.09 with a 60,000-character dossier, under the expert's own $0.10 per
    # call. A cut answer is still a RECORDED refusal (`truncated`, `03` F140). `06` D72 measures
    # whether thinking (adaptive at 12,000) earns its cost.
    SITE_EXPERT: 6000,
    # ⛔ NOT YET MEASURED (`[MODELLED]`) — unlike every number above. The plan caps a brief at 600
    # words and models its output at ~800 tokens (`reason/bundle/budget.OWN_BUDGETS`'s own comment:
    # "a brief is about 6,000 tokens in and 800 out"). R-2's history (this dict's own lesson) is
    # that a ceiling equal to the estimate truncates a real answer two times in three, so this is
    # 2x the modelled figure rather than the figure itself — headroom, not a hope. The live look
    # (s15-D1, M45.C5) measures the real distribution before any tenant reads a written brief; this
    # number is revisited then, the way R-2's was.
    SITE_BRIEF: 1600,
    SITE_BRIEF_ESCALATE: 1600,
}

#: ⛔ WHETHER A SITE MAY THINK (`yc2_w27_s18` M50.C2.L-contract.V1.U02). Claude 5 models think unless
#: told not to, and the thinking is spent from the site's ceiling above. `06` D71 (13 Oct): every site
#: asks with thinking OFF until a measurement says otherwise — the ceilings were sized for a model that
#: does not think, so this restores what they were sized for and costs nothing that works today. The
#: gate sends it (`RSiteGate.consult`) to a client that takes it; `context/llm/client` turns it into
#: what each model family honours (Opus 5.5 cannot turn thinking off: lowest effort, its own headroom).
SITE_THINKING = {
    SITE_INTERPRET: _THINKING_OFF,
    SITE_NARRATE: _THINKING_OFF,
    SITE_ALTERNATIVES: _THINKING_OFF,
    SITE_EFFECT: _THINKING_OFF,
    SITE_CONSULT: _THINKING_OFF,
    SITE_SITUATION: _THINKING_OFF,
    SITE_EXPERT: _THINKING_OFF,
    SITE_BRIEF: _THINKING_OFF,
    SITE_BRIEF_ESCALATE: _THINKING_OFF,
}

#: How long one call of a site may take, in seconds, where the client's own 60 s is too short. None
#: is the client's. MEASURED (s5t-F10): on 12 Oct a 4,000-token Sonnet 5 answer took 37–45 s (the
#: gaps between calls, p50 45.3 s), so R-7's 6,000 needs ~56–68 s — past 60 s, where the SDK retries
#: a call whose answer may already be paid for. 120 s is 1.8x the slow end.
SITE_TIMEOUT_S = {
    SITE_EXPERT: 120.0,
}

# ── what a consult may END as ────────────────────────────────────────────────────────────────

#: A model ran and its output survived the validator.
OUTCOME_RAN = "ran"
#: The answer was already on the record for this cache key. No model ran; no money moved.
OUTCOME_CACHED = "cached"
#: `l4_activation(org, feature)` is not live for this tenant. The commonest outcome, by design.
OUTCOME_NOT_ACTIVATED = "skipped_not_activated"
#: The site's own precondition was absent — R-1 has no UNRESOLVED flag on a fact the plan reads,
#: R-2 has no published decision. Doc 11 guard 7: never "just in case".
OUTCOME_NO_PRECONDITION = "skipped_precondition"
#: The tenant's daily narrative budget is spent, or this one call would exceed the per-decision
#: ceiling. Doc 11 guard 1: degrade to template, never stop deciding.
OUTCOME_NO_BUDGET = "skipped_budget"
#: No model is configured at all (no API key). Distinct from a budget skip: one is a deployment
#: fact and the other is a spend fact, and the fix for each is in a different place.
OUTCOME_NO_CLIENT = "skipped_no_client"
#: The model was called and did not come back with something parseable, twice.
OUTCOME_FAILED_GENERATION = "failed_generation"
#: The model came back and the gauntlet refused it, twice. The generation is recorded with the
#: checks that refused it, so "the model is bad at this" is answerable from the ledger.
OUTCOME_FAILED_VALIDATION = "failed_validation"
#: The doctrine switch is on: every R-site is refused so a replay can prove the decisions do not
#: move. Its own outcome rather than a reused skip, because a force-failed run appearing in the
#: ledger as an ordinary budget skip would make the doctrine test invisible after the fact.
OUTCOME_FORCE_FAILED = "force_failed"
#: ⛔ `03` F140 · the answer was cut at the token ceiling (`LLMResult.truncated`). Never validated,
#: never parsed into anything — a leniently closed JSON is a shorter answer than the model meant —
#: and never retried at the same ceiling, which would only cut it again. Recorded with its cost.
OUTCOME_TRUNCATED = "truncated"

OUTCOMES = (OUTCOME_RAN, OUTCOME_CACHED, OUTCOME_NOT_ACTIVATED, OUTCOME_NO_PRECONDITION,
            OUTCOME_NO_BUDGET, OUTCOME_NO_CLIENT, OUTCOME_FAILED_GENERATION,
            OUTCOME_FAILED_VALIDATION, OUTCOME_FORCE_FAILED, OUTCOME_TRUNCATED)

#: The outcomes on which the caller must use its deterministic fallback. Everything that is not a
#: model answer this run — a cache hit is an answer, so it is not here.
FALLBACK_OUTCOMES = frozenset(OUTCOMES) - {OUTCOME_RAN, OUTCOME_CACHED}


def require_site(site: str) -> str:
    """The one place an R-site id is validated. See the module docstring."""
    if site not in R_SITES:
        raise ValueError(f"unknown R-site {site!r}; expected one of {R_SITES}")
    return site


def require_outcome(outcome: str) -> str:
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown gate outcome {outcome!r}; expected one of {OUTCOMES}")
    return outcome


def tier_for(site: str) -> str:
    """Doc 11 §1's tier discipline, as a function. Never inline a tier at a call site."""
    return SITE_TIERS[require_site(site)]


def max_output_tokens(site: str) -> int:
    return SITE_MAX_OUTPUT_TOKENS[require_site(site)]


def thinking_mode(site: str) -> str:
    """`SITE_THINKING`'s word for the site — `context/llm/client.THINKING_MODES`."""
    return SITE_THINKING[require_site(site)]


def timeout_s(site: str) -> float | None:
    """The site's own per-call timeout, or None for the client's."""
    return SITE_TIMEOUT_S.get(require_site(site))


__all__ = ["FALLBACK_OUTCOMES", "OUTCOMES", "OUTCOME_CACHED", "OUTCOME_FAILED_GENERATION",
           "OUTCOME_FAILED_VALIDATION", "OUTCOME_FORCE_FAILED", "OUTCOME_NOT_ACTIVATED",
           "OUTCOME_NO_BUDGET", "OUTCOME_NO_CLIENT", "OUTCOME_NO_PRECONDITION", "OUTCOME_RAN",
           "OUTCOME_TRUNCATED",
           "R_SITES", "SITE_ALTERNATIVES", "SITE_BRIEF", "SITE_BRIEF_ESCALATE", "SITE_CONSULT",
           "SITE_EFFECT", "SITE_EXPERT", "SITE_INTERPRET", "SITE_SITUATION",
           "SITE_MAX_OUTPUT_TOKENS", "SITE_NARRATE", "SITE_THINKING", "SITE_TIERS", "SITE_TIMEOUT_S",
           "EXPERT_LADDER", "EXPERT_RUNGS", "TIER_T1", "TIER_T2", "TIER_T3", "expert_ladder",
           "max_output_tokens", "require_outcome", "require_site", "thinking_mode", "tier_for",
           "timeout_s"]
