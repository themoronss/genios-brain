"""C-04..C-09 · what one message turned out to contain, and the receipt behind every part.

Five claim types and the aggregate that carries them. Each claim type answers one question
about a single message — who was named (C-04), who owes what to whom by when (C-05), where a
decision stands (C-06), what is waiting on what (C-07), and what the model noticed that our
vocabulary has no word for (C-08). `ExtractionResult` (C-09) is the complete answer for one
message: the S2 (L1.4) output, produced once and cached permanently.

Three properties run through all six types, and none of them is decoration:

* **A claim with no receipt is a guess.** Every claim-bearing type embeds a non-empty
  `evidence: list[EvidenceSpan]` and refuses to construct without one (universal rule 4).
  The alternative is a card that states a commitment in the same typography as a fact and
  cannot say where it came from — which is indistinguishable, to the reader, from a fluent
  invention.
* **Confidence is integer basis points.** `confidence_bp` is 0..10000, checked by the one
  shared `require_bp`. A 0.87-style ratio is not merely a different spelling: it composes
  irreproducibly across replays, and confidence is composed at ALG-13 (L1.5.7) precisely so
  that a downstream number can be traced back to the weakest source that produced it.
* **The vocabulary is described here, not enforced here.** `entity_type`, `state`,
  `dependency_type`, `intent`, `stance` and `extraction_profile` are typed `str` on purpose.
  The closed sets live in `genios_engine/capture/semantic/vocabulary.py` (doc 04, L1.4.4-U1)
  because that module is also what the prompt generator and the promotion path read; pinning
  a second copy into a contract other layers have already stored would guarantee the two
  drift, and a promotion (L1.4.5-U2) would then have to edit a boundary type to add a word.

**The result is internal to L1.** L2 never receives an `ExtractionResult`; it receives the
QualifiedEnterpriseSignal, which embeds one. That distinction is what lets the structured
bypass lane (L1.3.9, a registered field mapping and no model at all) emit this same shape
with `confidence_bp` stamped at 10000 — a typed CRM field is not a guess — while everything
from S3 onward stays unable to tell the two lanes apart.

Nothing here parses, resolves, verifies or scores. Span verification is ALG-08 (L1.5.1),
money is ALG-10, dates are ALG-09, importance is ALG-17 (L1.6.7). This module owns only what
a value must be true of once it exists, which is why it may be imported from anywhere and why
the seams above it are free to change their heuristics without rewriting a stored contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from numbers import Real
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.intent import MessageIntent
from genios_engine.contracts.units import Money, ResolvedDate
from genios_engine.contracts.validators import (require_bool, require_bp, require_non_negative,
                                                require_text)

#: The per-extraction ceiling on open-lane observations (doc 04, L1.4.5-U1). It is stated here
#: so the prompt builder, the weekly discovery report and the review query share one number —
#: and it is deliberately NOT enforced as a validator. The cap exists to stop the lane becoming
#: a dumping ground, and the doc's mechanism for that is instructing the model to pick the five
#: most significant. Raising here instead would mean an over-eager extractor destroys an entire
#: message's extraction, which is the precise failure the open lane was built to end.
MAX_UNCLASSIFIED_PER_EXTRACTION = 5

#: The two scores that may never appear on an ExtractionResult, with the reason each is
#: refused. Kept as data rather than prose so the check below and the class comment cannot
#: drift apart. See `ExtractionResult._refuse_scored_fields`.
FORBIDDEN_RESULT_FIELDS = {
    "importance_bp": ("importance is computed at L1.6.7 (ALG-17) from VALIDATED facts; a "
                      "model-produced score is not reproducible across replays"),
    "priority_bp": ("priority is a Layer 4 decision about what to do next, not a property of "
                    "what a message said"),
}


def _require_receipt(spans: list[EvidenceSpan], claim: str) -> list[EvidenceSpan]:
    """Universal rule 4, enforced at the seam that produced the claim (universal rule 5).

    An empty list is refused at construction rather than at the publishing gate because by the
    gate the claim has already been counted, ranked and composed with others; V-4 rejecting it
    there costs a whole signal, while refusing it here costs one malformed object. The doc's
    own wording is the test: a claim with no receipt is a guess.
    """
    if not spans:
        raise ValueError(f"{claim} requires at least one evidence span — "
                         "a claim with no receipt is a guess")
    return spans


def _claim_confidence(value: Any) -> int:
    """CV-BP for a claim's own confidence, through the single shared helper.

    `require_bp` already refuses a bool, refuses anything that is not an exact integer, and
    range-checks 0..10000; a second copy of that logic is a second place for the range to be
    wrong. Structured-lane claims arrive stamped 10000 — a mapped CRM field is not a guess —
    and that is a value, not a special case.
    """
    return require_bp(value, "confidence_bp")


def _reject_fractional(value: Any, path: str) -> Any:
    """Refuse a fractional number smuggled through one of the open `dict` lanes.

    `roles`, `relationships` and `scheduling_proposals` are untyped by design at W0, and an
    untyped lane is exactly where a 0.85 gets in. It matters because these dicts are embedded
    verbatim in the QualifiedEnterpriseSignal: a ratio here survives to the QES seam, where V-7
    scans the SERIALIZED object and rejects the entire signal. Catching it while the extraction
    is being built names the offending key instead of condemning the message.

    Integers pass, strings pass, `None` passes. Mapping keys are coerced to `str` so the JSON
    round-trip and any content address computed over the result are stable regardless of what
    the model emitted as a key.
    """
    if value is None or isinstance(value, (str, bytes, int)):    # bool is an int; both fine
        return value
    if isinstance(value, (Real, Decimal)):
        raise TypeError(f"{path} carries a fractional number ({value!r}); scores are integer "
                        "basis points and money is integer minor units")
    if isinstance(value, Mapping):
        return {str(key): _reject_fractional(item, f"{path}.{key}")
                for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_reject_fractional(item, f"{path}[{index}]")
                for index, item in enumerate(value)]
    return value


def _open_lane_dicts(values: Any, label: str) -> list[dict[str, Any]]:
    """Shape guard for the three untyped lanes: a list of string-keyed mappings, no fractions."""
    if values is None:
        return []
    if isinstance(values, Mapping) or not isinstance(values, (list, tuple)):
        raise TypeError(f"{label} must be a list of objects")
    cleaned: list[dict[str, Any]] = []
    for index, entry in enumerate(values):
        if not isinstance(entry, Mapping):
            raise TypeError(f"{label}[{index}] must be an object")
        cleaned.append(_reject_fractional(entry, f"{label}[{index}]"))
    return cleaned


#: What a legacy lane entry's confidence becomes when the stored row carried none. 5000 bp is
#: "somebody said it and nothing corroborates it" — the neutral standing an unscored claim takes
#: everywhere else in this layer, and deliberately BELOW anything the extractor states for itself
#: so a rehydrated legacy claim never outranks a graded one.
LEGACY_LANE_CONFIDENCE_BP = 5000


def _legacy_claim(entry: Any, lane: str) -> Any:
    """One entry of a promoted lane, in whichever shape it was stored. See
    `ExtractionResult._rehydrate_legacy_lanes` for why this exists and what it refuses to do.

    Returns the entry UNCHANGED unless it is recognisably the pre-2026-09-23 shape, so the new
    shape pays one `isinstance` and nothing else.
    """
    if isinstance(entry, str):
        # `questions` was `list[str]`. A bare string is the whole question and no receipt.
        return {"text": entry, "evidence": [], "confidence_bp": LEGACY_LANE_CONFIDENCE_BP}
    if not isinstance(entry, Mapping):
        return entry
    if "evidence" in entry and "confidence_bp" in entry:
        return entry                       # already the new shape; nothing to migrate
    data = {str(key): value for key, value in entry.items()}
    quote = data.pop("evidence_text", None)
    if "evidence" not in data:
        if isinstance(quote, str) and quote.strip():
            # A PROBE, not a positioned citation: the words are the model's own and the offsets
            # say "somewhere". ALG-08 relocates it; `verified` stays False, because the one thing
            # this may never do is stamp a receipt the validator has not checked.
            data["evidence"] = [{"source_ref": f"legacy_lane:{lane}", "quote": quote,
                                 "start_offset": 0, "end_offset": len(quote),
                                 "verified": False}]
        else:
            data["evidence"] = []
    data.setdefault("confidence_bp", LEGACY_LANE_CONFIDENCE_BP)
    return data


def _required_strings(values: Any, label: str) -> list[str]:
    """Non-empty, stripped strings. An empty topic or question is a list entry that renders as
    a blank line in a card and counts as one more item in every tally above."""
    if values is None:
        return []
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise TypeError(f"{label} must be a list of strings")
    return [require_text(entry, label) for entry in values]


class EntityMention(BaseModel):
    """One entity as the source actually wrote it, plus a hint about who it probably is.

    Two fields do two different jobs and conflating them is the failure this type prevents.
    `surface_form` is testimony — "AWS", "Amazon Web Services", "aws inc" — and is never
    rewritten, because the string a human typed is what a human can check. `canonical_hint` is
    a guess, filled by L1.5.4 (ALG-11) from deterministic alias and domain matching and never
    from embeddings (MAP B: L1 v2 ships none), and it is NOT authoritative. L2 owns identity;
    a hint that hardened into a decision here would merge two vendors on a shared substring and
    do it invisibly, three layers below the place that is supposed to resolve them.
    """

    #: Exactly as written: "AWS", "Amazon Web Services". Never normalised, never title-cased.
    surface_form: str

    #: person | organization | vendor | product | document | project (doc 04's ENTITY_TYPE).
    #: Typed `str` and not promoted to an Enum: the set is closed in `vocabulary.py`, where the
    #: promotion path can extend it behind a schema-version bump, and an Enum frozen into a
    #: contract would make adding a kind a boundary-type change with stored rows behind it.
    entity_type: str

    #: L1.5.4's proposal; L2 decides. DIVERGENCE FROM DOC 08: the doc declares the field with
    #: no default. `= None` is added because a mention arrives from the extractor without one —
    #: the hint is filled a whole subgroup later — so requiring it would force every extractor
    #: call site to type `canonical_hint=None` and would make forgetting to do so a crash rather
    #: than the absence it actually is.
    canonical_hint: str | None = None

    #: Universal rule 4. Non-empty, enforced below.
    evidence: list[EvidenceSpan]

    #: 0..10000. The structured lane stamps 10000: a typed field is not a guess.
    confidence_bp: int

    @field_validator("surface_form")
    @classmethod
    def _written_form(cls, value: str) -> str:
        return require_text(value, "surface_form")

    @field_validator("entity_type")
    @classmethod
    def _kind(cls, value: str) -> str:
        """Presence only. Membership is `vocabulary.py`'s to assert, at the extractor seam."""
        return require_text(value, "entity_type")

    @field_validator("confidence_bp", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> int:
        return _claim_confidence(value)

    @model_validator(mode="after")
    def _carries_receipt(self) -> EntityMention:
        _require_receipt(self.evidence, "an entity mention")
        return self


class Commitment(BaseModel):
    """Who owes what to whom, by when, and under what condition.

    The conditional pair is the whole point. *"I'll send the contract once legal confirms"* is
    not a promise with a date, and a system that stores it as one produces a false overdue —
    it chases a founder about a deliverable that was never due, and the second false chase is
    the last time that founder reads a nudge from us. So `is_conditional` has no default: the
    extractor must decide and say so, because a defaulted `False` is a silent assertion that
    an unconditional promise was made.

    `due is None` means no date was stated. It does not mean "due now", and nothing downstream
    may read it that way — an undated commitment is tracked as an open loop, never escalated as
    a missed one.
    """

    #: Who owes it.
    actor: str
    #: What they owe.
    action: str
    #: Who they owe it to, when the source says. `= None` is the house-style form of the doc's
    #: undefaulted `str | None`: plenty of commitments name no beneficiary ("I'll look into
    #: it"), and that absence is information rather than an omission to be filled in.
    beneficiary: str | None = None
    #: The resolved window, carrying its own certainty band. Absent means undated, above.
    due: ResolvedDate | None = None
    #: No default, deliberately — see the class docstring.
    is_conditional: bool
    #: The condition verbatim ("once legal confirms"), so the card can show the reader why we
    #: are not treating this as a deadline instead of just quietly not treating it as one.
    condition_text: str | None = None
    evidence: list[EvidenceSpan]
    confidence_bp: int

    @field_validator("actor", "action")
    @classmethod
    def _parties(cls, value: str) -> str:
        return require_text(value, "commitment field")

    @field_validator("is_conditional", mode="before")
    @classmethod
    def _conditional_flag(cls, value: Any) -> bool:
        """A literal bool. Truthiness coercion is how `""` or `0` becomes "unconditional"."""
        return require_bool(value, "is_conditional")

    @field_validator("confidence_bp", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> int:
        return _claim_confidence(value)

    @model_validator(mode="after")
    def _carries_receipt(self) -> Commitment:
        _require_receipt(self.evidence, "a commitment")
        return self


class DecisionState(BaseModel):
    """Where a decision stands, what it is blocked on, and who owns it.

    This is the type that turns a thread into a tracked decision rather than a pile of
    messages. `blocked_on` and `owner` are what make the state actionable: "blocked" with
    neither is a status nobody can move, and a decision nobody can move is the one that sits
    for three weeks while each side believes the other has it.
    """

    #: "AWS renewal", "pricing" — the thing being decided, not the message it appeared in.
    subject: str
    #: pending | made | blocked | deferred | abandoned (doc 04's DECISION_STATE). Typed `str`
    #: for the same reason as `EntityMention.entity_type`: the five values are documented and
    #: closed in `vocabulary.py`, not enum-enforced in a stored boundary type.
    state: str
    #: What is holding it up. `= None` (house-style form of the doc's undefaulted optional) —
    #: a decision that is merely pending is blocked on nothing, and saying so is not a gap.
    blocked_on: str | None = None
    #: Who it is waiting on. Absent when the source named nobody; never inferred here.
    owner: str | None = None
    evidence: list[EvidenceSpan]
    confidence_bp: int

    @field_validator("subject")
    @classmethod
    def _what_is_decided(cls, value: str) -> str:
        return require_text(value, "subject")

    @field_validator("state")
    @classmethod
    def _status(cls, value: str) -> str:
        return require_text(value, "state")

    @field_validator("confidence_bp", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> int:
        return _claim_confidence(value)

    @model_validator(mode="after")
    def _carries_receipt(self) -> DecisionState:
        _require_receipt(self.evidence, "a decision state")
        return self


class Dependency(BaseModel):
    """A blocks B. This is what makes a deadline more than a calendar entry.

    Without the blocker edge a due date is a reminder that fires at the person holding the
    deliverable, who is not the person who can unblock it. With the edge, the same date is a
    chain, and an escalation can be aimed at the node that is actually stuck — which is the
    difference between telling someone they are late and telling them why.
    """

    #: The thing in the way.
    blocker: str
    #: The thing waiting.
    blocked: str
    #: approval | information | delivery | decision (doc 04's DEPENDENCY_TYPE). Typed `str`;
    #: the kind decides who gets escalated to and how long the wait is allowed to run.
    dependency_type: str
    evidence: list[EvidenceSpan]
    confidence_bp: int

    @field_validator("blocker", "blocked")
    @classmethod
    def _ends(cls, value: str) -> str:
        return require_text(value, "dependency end")

    @field_validator("dependency_type")
    @classmethod
    def _kind(cls, value: str) -> str:
        return require_text(value, "dependency_type")

    @field_validator("confidence_bp", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> int:
        return _claim_confidence(value)

    @model_validator(mode="after")
    def _carries_receipt(self) -> Dependency:
        _require_receipt(self.evidence, "a dependency")
        return self


class UnclassifiedObservation(BaseModel):
    """THE OPEN LANE — something the model noticed that has no name in our vocabulary.

    It is stored, span-validated exactly like any other claim, never consumed by any rule, and
    reviewed weekly. This is the only mechanism by which GeniOS discovers a pattern nobody
    wrote a rule for. Everything else in the pipeline can only find what it was already told to
    look for; without this lane, every detail outside the current vocabulary dies at the sink
    rather than at the model, silently and with no record that it was ever seen.

    Two rules keep it from becoming either useless or dangerous:

    * **No rule may read this type or its table** (`unclassified_observations`, rolling 180
      days). Doc 04's L1.4.5-U1 backs it with an import-graph assertion — the G3 gate asserts
      nothing under `packs/` or `reason/` imports `capture/semantic/open_lane.py`. A rule that
      fired on a free-text label the model invented would be a rule whose behaviour changes
      when the model's phrasing does, which is not a rule at all.
    * **Promotion is human-only and carries a schema-version bump** (L1.4.5-U2). A recurring
      `proposed_kind` becomes a vocabulary member when a person decides it should; the bump
      invalidates the extraction cache key so new events extract with the new kind. A
      vocabulary that grows itself is a vocabulary nobody can write a rule against.
    """

    #: The model's own free-text label. Deliberately unconstrained — validating it against the
    #: closed vocabulary would mean the lane can only capture what the vocabulary already
    #: contains, which is the exact circularity the lane exists to break.
    proposed_kind: str
    #: What was noticed, in the model's words, so the weekly report reads as observations
    #: rather than as a column of unexplained labels.
    description: str
    #: Universal rule 4 applies here too. An unnamed observation with no quote behind it cannot
    #: be reviewed, cannot be promoted, and is the one thing this lane must not accumulate.
    evidence: list[EvidenceSpan]
    confidence_bp: int

    @field_validator("proposed_kind")
    @classmethod
    def _label(cls, value: str) -> str:
        return require_text(value, "proposed_kind")

    @field_validator("description")
    @classmethod
    def _what_was_seen(cls, value: str) -> str:
        return require_text(value, "description")

    @field_validator("confidence_bp", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> int:
        return _claim_confidence(value)

    @model_validator(mode="after")
    def _carries_receipt(self) -> UnclassifiedObservation:
        _require_receipt(self.evidence, "an unclassified observation")
        return self


BusinessField = Literal[
    "party.role", "relationship.nature", "deal.stage", "deal.value", "person.title",
    "company.industry", "thread.objective", "campaign.objective", "organization.relationship",
]


class BusinessFact(BaseModel):
    """A business noun, with testimony distinct from interpretation.

    Seven of the nine fields had zero live facts on 2026-09-10. A typed lane carries them
    through the existing extraction, without another model call or upgrading guesses to R2.
    """

    field: BusinessField
    subject: str
    value: str | Money
    standing: Literal["observed", "judgement"]
    evidence: list[EvidenceSpan]
    confidence_bp: int

    @field_validator("subject")
    @classmethod
    def _subject(cls, value: str) -> str:
        return require_text(value, "business subject")

    @field_validator("confidence_bp", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> int:
        return _claim_confidence(value)

    @model_validator(mode="after")
    def _typed_receipted_value(self) -> BusinessFact:
        _require_receipt(self.evidence, "a business fact")
        if self.field == "deal.value":
            if not isinstance(self.value, Money) or not self.value.currency_known:
                raise ValueError("deal.value requires Money with a known currency")
        else:
            if not isinstance(self.value, str):
                raise ValueError("only deal.value accepts Money")
            self.value = require_text(self.value, "business value")
            if self.value.casefold() in {"unknown", "none", "null", "n/a", "not known"}:
                raise ValueError("unknown business values remain missing")
        return self


class RoleAssertion(BaseModel):
    """Who somebody IS, as this message asserts it. *"Maya is now the CFO."*

    PROMOTED FROM `list[dict[str, Any]]` on 2026-09-23. The lane's own field note said it was
    *"untyped at W0 by design: typing roles is doc 04's work"* — a dated deferral, not a refusal,
    and this is that work coming due. `esqe/detector.py` fires RELATIONSHIP_CHANGE off it and
    said so in a comment: *"it carries no EvidenceSpan (the lane is `list[dict]` by contract),
    hence no receipt on that detection."* Doctrine 3 of this layer is *no claim without a
    receipt*, and a lane with nowhere to put one cannot obey it however carefully it is filled.

    THE KEYS ARE NOT NEW. `capture/semantic/vocabulary.UNTYPED_LANE_KEYS` already closed this
    lane to `party` / `role` / `evidence_text`, read off the shipping consumer rather than
    invented. What changes is that `evidence_text` — a free string nobody could resolve — becomes
    a real `EvidenceSpan` that ALG-08 grades against the source characters.

    **This does not change any score.** `normalize.DATE_POLICY[RELATIONSHIP_CHANGE]` is `none`
    and `AMOUNT_POLICY` is `claims_only` by design, so ALG-17 reads no date and no amount here
    either way. What it buys is a claim a reader can check.
    """

    #: Who the message is talking about.
    party: str
    #: What it says they are. Free text: a role vocabulary that closed here would cap discovery
    #: at the titles somebody already wrote down, which is `context/extract/vocab.py`'s recorded
    #: failure pointing the other way.
    role: str
    evidence: list[EvidenceSpan]
    confidence_bp: int

    @field_validator("party", "role")
    @classmethod
    def _parties(cls, value: str) -> str:
        return require_text(value, "role assertion field")


class AvailabilityWindow(BaseModel):
    """When somebody CANNOT act, as they stated it. *"On leave 15–22, Anisha covers."*

    PROMOTED on the same terms as `RoleAssertion`, and this is the lane with the most readers in
    the tree — `esqe/detector.py` fires AVAILABILITY_CHANGE off it, `esqe/lifecycle.py` and
    `esqe/qualification.py` both branch on that type, and Layer 2 writes `person.availability`
    from it.

    `from_text` AND `to_text` ARE THE MESSAGE'S OWN WORDS, verbatim — *"from 15th"*, *"kal se"*,
    *"back on Monday"*. Layer 2 (`context/extract/availability.py`) resolves them into dates
    against the message date. **No model ever does the arithmetic**, which is why they are strings
    here and not a `ResolvedDate`: a model that returned a date would be guessing at a timezone
    and a reference point it was never given.
    """

    #: Whose absence this is — **`None` means the message's own author**, which is by far the
    #: commonest case (an out-of-office auto-reply says "I am away" and names nobody). Optional
    #: because its one consumer already reads it that way: `context/extract/availability._person`
    #: returns `None` for a missing value and for a self-word, with the comment *"None when it
    #: names the author"*. Requiring a name here would refuse the ordinary OOO and force the
    #: extractor to invent an identity the message never stated.
    person: str | None = None
    #: leave · out_of_office · sick · travel · busy — the shape `vocabulary.py` closes.
    kind: str
    #: The start, in the message's own words. `None` when it stated only an end.
    from_text: str | None = Field(default=None, alias="from")
    #: The end, in the message's own words. `None` when it stated only a start — an open-ended
    #: absence is a real answer and must not be filled in with a guessed return date.
    to_text: str | None = Field(default=None, alias="to")
    #: Who is covering, when the message names somebody. This is the field that makes an absence
    #: actionable rather than merely known.
    coverage_person: str | None = None
    evidence: list[EvidenceSpan]
    confidence_bp: int

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("kind")
    @classmethod
    def _stated(cls, value: str) -> str:
        return require_text(value, "availability field")

    @field_validator("person", "coverage_person")
    @classmethod
    def _named_or_absent(cls, value: str | None) -> str | None:
        """Absent is a real answer; BLANK is not. `""` and `"   "` both mean the extractor
        emitted a field it had nothing to put in, and they render as an empty name beside a real
        one. `None` says "the author" and is unambiguous."""
        if value is None:
            return None
        return require_text(value, "availability field")


class OpenQuestion(BaseModel):
    """Something the message ASKED and nobody has answered.

    PROMOTED FROM `list[str]`. Its field note already argued for it: *"an unanswered question is
    an open loop even when nobody promised anything, which is why they are captured separately
    from commitments."* A loop the product cannot quote is a loop it cannot show, and benchmark
    P3 — *"the final unresolved question"* — is exactly this lane.

    A bare string could not say WHO asked, or point at the sentence. Both are needed before Layer
    2 can decide whose court the question sits in.
    """

    #: The question as asked.
    text: str
    #: Who asked, when the message makes it plain. `None` rather than the sender by default:
    #: a forwarded thread routinely carries somebody else's question, and attributing it to the
    #: forwarder puts the open loop on the wrong person's node.
    asked_by: str | None = None
    #: Who it was put to, when stated.
    asked_of: str | None = None
    evidence: list[EvidenceSpan]
    confidence_bp: int

    @field_validator("text")
    @classmethod
    def _asked(cls, value: str) -> str:
        return require_text(value, "open question text")


class ExtractionResult(BaseModel):
    """C-09 · the complete S2 (L1.4) output for one message. INTERNAL TO L1.

    L2 never sees this type. L2 sees the QualifiedEnterpriseSignal, which embeds one — and the
    structured bypass lane (L1.3.9's mapper, no model involved) produces this SAME shape from a
    registered field mapping with every mapped field's confidence at 10000. From S3 onward
    nothing may tell the two lanes apart, which is what makes a CRM-sourced fact and an
    email-sourced fact comparable instead of two parallel pipelines that drift.

    It is cached permanently in `l1_extraction_results`, keyed by content hash, prompt version,
    schema version, model snapshot and vocabulary fingerprint. Every replay reads the stored
    extraction and never re-runs the model: that is what makes a decision from March reproduce
    in September, and it is why every provenance field below is required rather than optional.
    Change the prompt, the vocabulary or the model and the key changes, so old rows stay valid
    for the code that wrote them instead of being reinterpreted by code that did not.

    **FORBIDDEN FIELDS — `importance_bp` and `priority_bp` may never appear on this type.**
    Importance is computed at L1.6.7 (ALG-17) from facts that have already been span-validated,
    money-normalised and date-resolved; a score the model emitted alongside its own claims is
    derived from unvalidated input and does not reproduce across replays, so caching it would
    freeze one run's guess into every future reading of the same message. Priority is a
    different question entirely — what to do next — and it belongs to Layer 4, which is the
    only place that can see the other things competing for the same attention. Both names are
    refused at construction below rather than merely omitted, because a field that is silently
    ignored is a field that reappears the first time a prompt is edited to emit it.
    """

    # --- what the message means ---
    #: The closed intent set from doc 04 (inform | request | commit | decide | escalate |
    #: schedule | negotiate | approve | reject | question | acknowledge | introduce). Typed
    #: `str`; the frozenset lives in `vocabulary.py`, which is deliberately independent of the
    #: rules' own vocabulary — deriving it from what rules consult would cap discovery at what
    #: somebody already wrote a rule for.
    intent: str
    #: What it is about. Free text by design; topics are for retrieval and grouping, not for
    #: rule matching, so a closed set would buy nothing and lose the specific words.
    topics: list[str] = Field(default_factory=list)
    #: positive | neutral | cautious | negative | mixed (doc 04's STANCE).
    stance: str

    # --- what it contains ---
    entity_mentions: list[EntityMention] = Field(default_factory=list)
    #: Integer minor units plus an ISO code, never a bare number — C-02 owns the reason.
    amounts: list[Money] = Field(default_factory=list)
    #: Every date the message referred to, as windows with certainty bands. `GatedEvent`'s
    #: single `deadline_at` datetime is absorbed here: one timestamp could not say whether it
    #: came from "October 15" or from "pretty soon", so the deadline-proximity term of ALG-17
    #: read a guessed window as a stated one.
    dates_mentioned: list[ResolvedDate] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)
    decision_states: list[DecisionState] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    business_facts: list[BusinessFact] = Field(default_factory=list)
    #: WHAT KIND OF EXCHANGE THIS IS, read with the whole message in hand rather than the
    #: subject line the junk gate saw. `None` when the model did not answer — which is not the
    #: same as "unknown", and `MessageIntent.merged_with` relies on the difference to avoid
    #: overwriting the gate's real answer with this reader's silence.
    #:
    #: NOT `intent`, which is taken and means something narrower: the SPEECH ACT of this one
    #: message (`inform | request | commit | decide | escalate`), which `esqe/detector` reads to
    #: fire ESCALATION. "I am escalating this" is a speech act; "this is a vendor pitch" is the
    #: kind of exchange it sits in. One message has both and the two must not share a name.
    #:
    #: NEVER NULLABLE. Schema rule S-1 refuses a null field on an extraction and says why: an
    #: empty collection is how "nothing was found" is said here. An EMPTY `MessageIntent` says
    #: exactly that — every axis `unknown`, every boolean `None` — and it merges as a no-op,
    #: because `merged_with` only takes a field the other reading actually answered. So silence
    #: needs no sentinel of its own.
    exchange_intent: MessageIntent = Field(default_factory=MessageIntent)
    #: What the message implies somebody should do, in the model's words. Not an instruction
    #: and not a task — Layer 4 decides whether anything is done.
    implied_actions: list[str] = Field(default_factory=list)
    #: Questions asked in the message. An unanswered question is an open loop even when nobody
    #: promised anything, which is why they are captured separately from commitments.
    questions: list[OpenQuestion] = Field(default_factory=list)
    #: Role candidates. Untyped at W0 by design: typing roles is doc 04's work and needs the
    #: extraction this envelope feeds, so freezing a shape here would pin a boundary type to a
    #: design that has not been made yet. DIVERGENCE FROM DOC 08: written `list[dict]` in the
    #: doc and `list[dict[str, Any]]` here — the contents stay untyped, the keys are pinned to
    #: `str` so the JSON round-trip and any content address over the result are stable.
    roles: list[RoleAssertion] = Field(default_factory=list)
    #: Where `GatedEvent.linkage_hints` lands. It was computed, persisted and then read by
    #: nothing — the hint reached the boundary and stopped there. Same untyped-by-design terms
    #: as `roles`.
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    #: Proposed times, places and attendees, as written. Same terms again.
    scheduling_proposals: list[dict[str, Any]] = Field(default_factory=list)
    #: Absence / reduced capacity someone STATED — leave, out of office, sick, travel, busy —
    #: with the start/end words quoted verbatim. Same untyped-lane terms as the three above; its
    #: key names are closed by `capture/semantic/vocabulary.UNTYPED_LANE_KEYS`, and Layer 2
    #: (`context/extract/availability.py`) resolves the quoted words into dates against the
    #: message date. The model never does date arithmetic.
    availability: list[AvailabilityWindow] = Field(default_factory=list)

    # --- the discovery lane ---
    #: C-08. Capped at MAX_UNCLASSIFIED_PER_EXTRACTION by prompt instruction, not by this
    #: contract — see that constant for why raising here would defeat the lane.
    unclassified_observations: list[UnclassifiedObservation] = Field(default_factory=list)

    # --- trust ---
    #: Per-field basis points, keyed by field name. Every value goes through `require_bp`, so a
    #: ratio cannot enter through the dict that the annotation alone would not catch. The
    #: structured lane sets every mapped field to 10000.
    field_confidence: dict[str, int] = Field(default_factory=dict)
    #: Every span the extraction produced, flat. L1.5.1 walks this to verify them in one pass;
    #: `evidence_from_claims()` below is what proves nothing was left out of it.
    all_evidence: list[EvidenceSpan] = Field(default_factory=list)

    # --- provenance (required for replay) ---
    #: The exact model id, not a family name. "claude-3-5-haiku" is not reproducible; a dated
    #: snapshot is, and the difference is whether a replay months later re-derives the same
    #: extraction or a differently-behaved successor's version of it.
    model_snapshot: str
    prompt_version: str
    #: NOTE THE TYPE MISMATCH, carried deliberately: `str` here, `int` on the
    #: QualifiedEnterpriseSignal. Doc 08 states both literally and they are not unified, because
    #: this value is already part of a cache key over stored rows — retyping it would change
    #: every key and orphan the cache it was meant to protect.
    schema_version: str
    #: email | chat | transcript | document | crm_note. Which profile ran decides what the
    #: extractor was even looking for, so a replay that does not know it is not a replay.
    extraction_profile: str
    #: Token counts, for cost attribution against `llm_costs`. Zero on the structured lane —
    #: that lane calls no model, and a mapping that reports tokens it never spent would make
    #: the bypass look as expensive as the thing it exists to avoid.
    input_tokens: int
    output_tokens: int

    @model_validator(mode="before")
    @classmethod
    def _refuse_scored_fields(cls, data: Any) -> Any:
        """The two forbidden names are rejected loudly, not ignored quietly.

        Pydantic's default is to drop an unknown key, which would mean a prompt edited to emit
        `importance_bp` would be accepted forever with the field vanishing at the boundary and
        nobody learning that the extractor is now producing a score nothing reads. Only these
        two names are refused; other unknown keys still pass, so a cached row written by an
        older schema version stays replayable.
        """
        if isinstance(data, Mapping):
            for name, reason in FORBIDDEN_RESULT_FIELDS.items():
                if name in data:
                    raise ValueError(f"{name} may never appear on an ExtractionResult: {reason}")
        return data

    @field_validator("intent", "stance", "model_snapshot", "prompt_version", "schema_version",
                     "extraction_profile")
    @classmethod
    def _required_provenance(cls, value: str) -> str:
        """Presence, not membership. Every one of these is either a vocabulary value asserted
        at the extractor seam or a provenance string a replay cannot proceed without."""
        return require_text(value, "extraction field")

    #: `questions` LEFT this validator on 2026-09-23 when it became `list[OpenQuestion]`; a
    #: string-list guard on a model list would refuse every valid entry.
    @field_validator("topics", "implied_actions", mode="before")
    @classmethod
    def _text_lists(cls, value: Any) -> list[str]:
        return _required_strings(value, "list entry")

    #: `roles` and `availability` left this one for the same reason — they are `RoleAssertion`
    #: and `AvailabilityWindow` now, and pydantic validates their shape from the model. The two
    #: lanes still here are the ones step 4 has not promoted yet.
    @field_validator("relationships", "scheduling_proposals", mode="before")
    @classmethod
    def _open_lanes(cls, value: Any) -> list[dict[str, Any]]:
        return _open_lane_dicts(value, "open lane")

    @model_validator(mode="before")
    @classmethod
    def _rehydrate_legacy_lanes(cls, data: Any) -> Any:
        """READ-SIDE MIGRATION, added 2026-09-23 with step 4. Not a leniency.

        `questions`, `roles` and `availability` were `list[str]` / `list[dict]` until this date.
        Every row already in `l1_extraction_results` carries the old shape, and
        `context/qes_adapter.adapt_qes_extraction` rehydrates those rows with
        `ExtractionResult.model_validate(...)` on the live L2 path. Without this the promotion
        would not merely change the wire — **it would make every cached extraction in every
        tenant unreadable**, and Layer 2 would stop receiving anything from the cache on the day
        it shipped. The cache is keyed on content version and only turns over when a message
        changes, so "it will age out" is not an answer for a corpus nobody re-sends.

        WHAT IT DOES, and the one thing it refuses to do:

        * a bare string in `questions` becomes `{"text": <the string>}` — that lane genuinely
          was a list of strings;
        * `evidence_text`, the free receipt string the old shape carried, becomes a PROBE span:
          the model's own words at offsets `0..len`, `verified=False`. That is the same
          convention `extractor._spans_from_payload` already uses for a model that quoted
          correctly and counted in the wrong frame, and ALG-08 relocates it against the source.
          The alternative — dropping it — would silently delete the only receipt a legacy claim
          ever had;
        * a missing `confidence_bp` becomes `LEGACY_LANE_CONFIDENCE_BP`.

        IT NEVER INVENTS A QUOTE. An entry with no `evidence_text` gets `evidence=[]`, which is
        the honest "this claim was stored without a receipt" — and V-5 downgrades it, exactly as
        it downgrades a claim whose quote failed to resolve.

        A payload already in the NEW shape is untouched: every branch is keyed on a field the new
        shape does not have (a bare string, `evidence_text`, an absent `evidence`).
        """
        if not isinstance(data, Mapping):
            return data
        upgraded: dict[str, Any] | None = None
        for lane in ("questions", "roles", "availability"):
            entries = data.get(lane)
            if not isinstance(entries, (list, tuple)) or not entries:
                continue
            rebuilt = [_legacy_claim(entry, lane) for entry in entries]
            if rebuilt == list(entries):
                continue
            if upgraded is None:
                upgraded = dict(data)
            upgraded[lane] = rebuilt
        return upgraded if upgraded is not None else data

    @field_validator("field_confidence", mode="before")
    @classmethod
    def _per_field_confidence(cls, value: Any) -> dict[str, int]:
        """CV-BP applied inside the dict, where the `dict[str, int]` annotation would let lax
        coercion round a ratio to an integer and call it a confidence."""
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise TypeError("field_confidence must be a mapping of field name to basis points")
        return {require_text(name, "field_confidence key"): require_bp(score, f"{name} confidence")
                for name, score in value.items()}

    @field_validator("input_tokens", "output_tokens", mode="before")
    @classmethod
    def _token_count(cls, value: Any) -> int:
        """A count of things that happened. Negative is not a small error, it is a different
        kind of value, and it propagates straight into cost attribution."""
        return require_non_negative(value, "token count")

    def evidence_from_claims(self) -> list[EvidenceSpan]:
        """Every span carried by an embedded claim, in declaration order, deduplicated.

        `EvidenceSpan` is frozen and therefore hashable, so the many claims extracted from one
        sentence share a single receipt instead of each carrying a near-identical copy. L1.5.1
        (ALG-08) verifies spans once per distinct span; open-lane observations are included
        because doc 04 requires them span-validated exactly like any other claim.

        Derived, never stored: a stored copy drifts out of agreement with the claims the moment
        ALG-08 rewrites a corrected span, and there is nothing this method could know that the
        claims themselves do not already say. Compare it against `all_evidence` to find spans
        an extractor asserted but attached to no claim.
        """
        seen: dict[EvidenceSpan, None] = {}
        claim_lists: tuple[list[Any], ...] = (
            self.entity_mentions, self.dates_mentioned, self.commitments,
            self.decision_states, self.dependencies, self.business_facts,
            self.unclassified_observations,
            # PROMOTED 2026-09-23 (step 4). These three were `list[dict]`/`list[str]` and could
            # not appear here — a lane with no `evidence` field has no span to contribute. They
            # are not an afterthought on this list: `esqe/detector.py` fires RELATIONSHIP_CHANGE,
            # AVAILABILITY_CHANGE and a decision predicate off exactly these three, so until
            # today the only three signal types derived from unverifiable claims were also the
            # only three whose receipts ALG-08 never saw.
            self.questions, self.roles, self.availability,
        )
        for claims in claim_lists:
            for claim in claims:
                for span in claim.evidence:
                    seen.setdefault(span, None)
        for commitment in self.commitments:
            if commitment.due is not None:
                for span in commitment.due.evidence:
                    seen.setdefault(span, None)
        return list(seen)

    @property
    def is_structured_lane(self) -> bool:
        """True when no model produced this — the L1.3.9 mapping lane spent no tokens.

        Read it for cost attribution and for explaining a decision's provenance to a human,
        never to branch behaviour: everything from S3 onward is required to treat the two lanes
        identically, and a caller that special-cases one of them reintroduces the split this
        shared shape exists to remove.
        """
        return self.input_tokens == 0 and self.output_tokens == 0


__all__ = ["FORBIDDEN_RESULT_FIELDS", "MAX_UNCLASSIFIED_PER_EXTRACTION", "Commitment",
           "RoleAssertion", "AvailabilityWindow", "OpenQuestion",
           "MessageIntent",
           "BusinessFact", "BusinessField", "DecisionState", "Dependency", "EntityMention", "ExtractionResult",
           "UnclassifiedObservation"]
