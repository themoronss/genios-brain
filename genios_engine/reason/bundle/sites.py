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

R_SITES = (SITE_INTERPRET, SITE_NARRATE, SITE_ALTERNATIVES, SITE_EFFECT, SITE_CONSULT)

#: Tier per site, exactly as doc 11 §1 prints it. T1 = Haiku-class, T2 = Sonnet-class, the same
#: two names `capture.semantic.batch.DEFAULT_TIER_PRICES` prices — reused rather than re-declared,
#: because a second tier vocabulary is a second place a price can be wrong.
TIER_T1 = "T1"
TIER_T2 = "T2"
SITE_TIERS = {
    SITE_INTERPRET: TIER_T2,
    SITE_NARRATE: TIER_T2,
    SITE_ALTERNATIVES: TIER_T1,
    SITE_EFFECT: TIER_T1,
    SITE_CONSULT: TIER_T2,
}

#: The output ceiling per site, in tokens. A cap rather than a hope: doc 11 sizes R-2 at ~450
#: output tokens, and a model that decides to write an essay is a cost incident and a V-7 failure
#: at the same time. Generous enough that a real narrative is never truncated.
SITE_MAX_OUTPUT_TOKENS = {
    SITE_INTERPRET: 400,
    SITE_NARRATE: 1400,
    SITE_ALTERNATIVES: 600,
    SITE_EFFECT: 400,
    SITE_CONSULT: 600,
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

OUTCOMES = (OUTCOME_RAN, OUTCOME_CACHED, OUTCOME_NOT_ACTIVATED, OUTCOME_NO_PRECONDITION,
            OUTCOME_NO_BUDGET, OUTCOME_NO_CLIENT, OUTCOME_FAILED_GENERATION,
            OUTCOME_FAILED_VALIDATION, OUTCOME_FORCE_FAILED)

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


__all__ = ["FALLBACK_OUTCOMES", "OUTCOMES", "OUTCOME_CACHED", "OUTCOME_FAILED_GENERATION",
           "OUTCOME_FAILED_VALIDATION", "OUTCOME_FORCE_FAILED", "OUTCOME_NOT_ACTIVATED",
           "OUTCOME_NO_BUDGET", "OUTCOME_NO_CLIENT", "OUTCOME_NO_PRECONDITION", "OUTCOME_RAN",
           "R_SITES", "SITE_ALTERNATIVES", "SITE_CONSULT", "SITE_EFFECT", "SITE_INTERPRET",
           "SITE_MAX_OUTPUT_TOKENS", "SITE_NARRATE", "SITE_TIERS", "TIER_T1", "TIER_T2",
           "max_output_tokens", "require_outcome", "require_site", "tier_for"]
