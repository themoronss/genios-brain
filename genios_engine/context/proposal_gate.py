"""L2-6 · the deterministic validator that makes a cheap model safe.

⛔ **THE GATE EXISTS; LAYER 2 OWED THE VALIDATOR.** `RSiteGate.consult` step 6 is *"validate the
output — the caller's validator"* and step 7 is *"on any failure: deterministic fallback,
recorded — never a retry storm, never silence."* When a model may be consulted, what it costs and
what happens when it fails are already solved and property-tested. This module is the contents of
`validate`, and nothing else.

**IT IS THE COST STRATEGY, NOT TIDYING-UP.** The reasoner is Haiku. Haiku is affordable precisely
because a deterministic pass catches it being wrong. Without this, you need Sonnet everywhere —
because nothing would notice.

⛔ **THE STEP'S FOUR CHECKS HAD TO BE RE-AIMED, AND L2-2 IS WHY.** They read
`inferred_state → must cite ≥1 observed_fact`. Those fields do not exist: L2-2 measured that v2
is **already full of interpretation** — `visibility` *"a DERIVED claim"*, `missing_facts` *"the
entries are FINDINGS"*, V-4…V-7 existing because trends can be wrong — and classified the 28
fields it has rather than minting six more, deferring the genuinely absent ones to L2-5 with their
writer. So a PROPOSAL is `{field: value}` over `claim_state.model_writable_fields()`, which L2-2
built for this exact caller: *"L2-5's gate needs this list, and deriving it by hand at the call
site is how the list and the rule stop agreeing."*

**EVERY RULE IS READ, NEVER RE-IMPLEMENTED.**

    authority      claim_state.model_may_write          who may write what          (L2-2)
    receipt        contracts.situation.RECEIPT_REQUIRED who owes a citation         (L2-2, V-9)
    schema         validators.require_no_float          V-8, integer basis points
    contradiction  graph_store.fact_write_action        "lower authority disagrees" (pure already)
    completeness   the V-10 reading                     None coverage lands with False

A second copy of any of them is a second answer to one question, and this repository has caught
that drift five times.

⛔ **THE REASON CODE CARRIES THE CHECK AND THE SUBJECT, BECAUSE THE TRACE IS NOT STORED.**
`BundleStore.record_call` persists `reason_codes` as jsonb and **not** `trace`. So
`l2_authority:evidence` survives to a ledger somebody reads days later and
`{"check": …, "claim": …}` does not — the same `<rule>:<subject>` shape L2-2 chose for
`observed:V-9:anomalies[0]`.

**PURE. NO CLOCK, NO CLIENT, NO CONNECTION.** The one thing that must touch storage — does a
citation resolve — arrives as a `resolve_refs` callable, HANDED IN, for the reason L2-3 spent a
step on: *"a fetched slice cannot be replayed."* It is called **once, with every ref**, and not at
all when nothing cites.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Outcome(str, Enum):
    """Four, not two.

    L1 learned this the hard way: a binary gate held 367 candidates and admitted 18, because
    everything that was not obviously right was refused and nothing said which kind of wrong it
    was.
    """

    #: Every check held. Commit it.
    ACCEPT = "accept"
    #: Worth a better model, once. **The validator never escalates itself** — it has no client and
    #: no budget, and *"no R-site may call a model directly"*. This is a code the CALLER acts on.
    ESCALATE = "escalate"
    #: A check failed. Recorded with its reason, never silently dropped.
    REFUSE = "refuse"
    #: The model declined to conclude, and that is a REAL ANSWER. Committed as unknown.
    UNKNOWN = "unknown"


#: ⛔ Every check, and the prefix its refusals are recorded under. A table with a row per member —
#: the same idiom as `PRECEDENCE`, `ANCHOR_FAMILIES`, `SITUATION_STAGES` and `ADMISSION_REASONS` —
#: so a check whose code nobody declared cannot exist, because a refusal nobody can count is the
#: defect L2-0 spent a whole step on.
CHECKS: dict[str, str] = {
    "schema": "l2_schema",
    "authority": "l2_authority",
    "receipt": "l2_receipt",
    "unresolved": "l2_unresolved",
    "contradiction": "l2_contradiction",
    "completeness": "l2_completeness",
}


@dataclass(frozen=True, slots=True)
class ProposalVerdict:
    """What the gate may do with this proposal, and why."""

    outcome: Outcome
    reason_codes: tuple[str, ...] = ()

    @property
    def commits(self) -> bool:
        """⛔ `UNKNOWN` COMMITS. `RSiteGate.consult` returns RAN only when the validator's value is
        not `None`; a `None` is retried and recorded as FAILED_VALIDATION. So an UNKNOWN returned
        as `None` would be indistinguishable from a model that produced garbage — a correct
        refusal that looks like nothing happened, which is exactly what L2-0 exists to end."""
        return self.outcome in (Outcome.ACCEPT, Outcome.UNKNOWN)


def _refs_in(value: Any) -> tuple[str, ...]:
    """A claim's citations. `Trend` spells it `evidence_points`, the rest `evidence_refs`; both are
    read, because renaming a shipped field to make one rule simpler is churn the rule does not
    need."""
    cited = getattr(value, "evidence_refs", None) or getattr(value, "evidence_points", None) or ()
    return tuple(str(ref) for ref in cited)


def validate_proposal(proposal: Mapping[str, Any], *,
                      resolve_refs: Callable[[Sequence[str]], Iterable[str]],
                      held_facts: Mapping[str, Mapping[str, Any]] | None = None,
                      coverage_ready: bool | None = True,
                      expected_facts: Sequence[str] = ()) -> ProposalVerdict:
    """Run every check over one proposal and return a typed verdict. Never raises.

    `resolve_refs` is given EVERY citation at once and returns the subset that exists. Handed in,
    never fetched — the module cannot open a connection, which is what lets the whole validator be
    tested without a database, the property that made L1's `validate/` its strongest package.

    `held_facts` and `expected_facts` are likewise computed by the caller. A contract may not read
    a registry (the import ratchet caught L2-2 doing exactly that), and a validator that queries is
    a validator whose verdict cannot be replayed.
    """
    from genios_engine.contracts.claim_state import FIELD_CLAIMS, model_may_write
    from genios_engine.contracts.situation import RECEIPT_REQUIRED
    from genios_engine.contracts.conflict import require_no_float

    codes: list[str] = []
    held = dict(held_facts or {})

    # ── Check 1 · schema ─────────────────────────────────────────────────────────────────────
    for field in proposal:
        if field not in FIELD_CLAIMS:
            codes.append(f"{CHECKS['schema']}:{field}")
    try:
        require_no_float(dict(proposal), "proposal")
    except (TypeError, ValueError):
        # V-8. The law already owns the rule and already explains it: "a ratio stored as jsonb
        # comes back out as a number nobody can trace to a source".
        codes.append(f"{CHECKS['schema']}:float")

    # ── Check 2 · authority ──────────────────────────────────────────────────────────────────
    # ⛔ THE CHECK THE STEP COULD NOT WRITE AND L2-2 MADE POSSIBLE. "A model that can write an
    # observation is a model that can invent a fact." `visibility` is refused for its own reason:
    # a model that may set it may WIDEN an audience.
    for field in proposal:
        claim = FIELD_CLAIMS.get(field)
        if claim is not None and not model_may_write(claim.state):
            codes.append(f"{CHECKS['authority']}:{field}")

    # ── Check 3 · the receipt, and whether it resolves ───────────────────────────────────────
    cited: dict[str, tuple[str, ...]] = {}
    for field in RECEIPT_REQUIRED:
        for index, entry in enumerate(proposal.get(field) or ()):
            subject = f"{field}[{index}]"
            refs = _refs_in(entry)
            if not refs:
                codes.append(f"{CHECKS['receipt']}:{subject}")
            else:
                cited[subject] = refs

    # ONE READ, WITH EVERY REF — and none at all when nothing cites, because a round trip bought
    # for an empty set is a round trip bought for nothing.
    if cited:
        wanted = sorted({ref for refs in cited.values() for ref in refs})
        known = frozenset(str(ref) for ref in resolve_refs(wanted))
        for subject, refs in cited.items():
            if not all(ref in known for ref in refs):
                # ⛔ A ref the Evidence Graph has never heard of is WORSE than no ref: it looks
                # like proof. L1: "an unanchorable claim is kept and flagged, never invented."
                codes.append(f"{CHECKS['unresolved']}:{subject}")

    # ── Check 4 · contradiction ──────────────────────────────────────────────────────────────
    if held:
        from genios_engine.context.graph_store import fact_write_action

        for field, value in proposal.items():
            current = held.get(field)
            if not current:
                continue
            action = fact_write_action(
                held_value_json=str(current.get("value")),
                held_rank=int(current.get("authority_rank") or 1),
                held_occurred_at=current.get("occurred_at"),
                new_value_json=str(value),
                # A PROPOSAL IS THE LOWEST AUTHORITY THERE IS. It has not been observed; it has
                # been guessed at from things that were. Ranking it above a held fact would let a
                # model supersede an observation, which is Check 2 defeated by the back door.
                new_rank=0, new_occurred_at=current.get("occurred_at"))
            if action == "discrepancy":
                codes.append(f"{CHECKS['contradiction']}:{field}")

    # ── Check 5 · uncertainty survives ───────────────────────────────────────────────────────
    # V-10's reading, one layer earlier: `None` coverage lands with `False`, and a type whose
    # domain expects nothing cannot be accused of hiding it.
    if "missing_facts" in proposal and not proposal.get("missing_facts") \
            and not bool(coverage_ready) and tuple(expected_facts):
        codes.append(f"{CHECKS['completeness']}:missing_facts")

    if codes:
        return ProposalVerdict(outcome=Outcome.REFUSE, reason_codes=tuple(codes))
    # NOTHING PROPOSED IS NOT THE SAME AS NOTHING CONCLUDED — and neither is a proposal whose every
    # value is absent. The model looked and declined to say, which is an answer worth committing.
    if all(value in (None, (), [], {}, "") for value in proposal.values()):
        return ProposalVerdict(outcome=Outcome.UNKNOWN)
    return ProposalVerdict(outcome=Outcome.ACCEPT)


def as_gate_validator(**kwargs: Any) -> Callable[[Mapping[str, Any]],
                                                 tuple[Any, tuple[str, ...], Mapping[str, Any]]]:
    """Adapt the verdict to `RSiteGate.consult`'s `(value, reason_codes, trace_record)` contract.

    The gate's protocol is binary — `value is not None` means RAN — so the four outcomes ride
    inside it: ACCEPT and UNKNOWN return a value, REFUSE and ESCALATE return `None` with codes.
    The outcome is put in the trace record AND encoded in the codes, because only the codes are
    persisted.
    """
    def _validate(parsed: Mapping[str, Any]):
        verdict = validate_proposal(parsed, **kwargs)
        record = {"outcome": verdict.outcome.value, "codes": list(verdict.reason_codes)}
        if not verdict.commits:
            return None, verdict.reason_codes, record
        return (dict(parsed) if verdict.outcome is Outcome.ACCEPT else {}), (), record

    return _validate


def _check() -> None:
    for name, prefix in CHECKS.items():
        assert name and prefix.startswith("l2_"), f"{name}: a check code must be namespaced"


_check()

__all__ = ["CHECKS", "Outcome", "ProposalVerdict", "as_gate_validator", "validate_proposal"]
