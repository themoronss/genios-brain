"""L2.3/L2.7 · the ANGLE SCHEMA — a bounded model question as data, not as code.

WHAT AN ANGLE IS. A question put to a model about ONE subject drawn from a queue the deterministic
layer has already built, seeing a named list of fields and answering with one word from a closed
set. It is modelled on `reason/llm_interpretation.py`, which does this correctly one layer up and
describes itself in the sentence this whole file exists to make reusable: *"A deterministic gate
decides WHEN a model may look… the model sees ONE sentence and returns one of six stances with a
confidence of 2,000-8,000… A gate miss never pays for a reading."*

WHY A SCHEMA AND NOT FOUR PYTHON FUNCTIONS. The same argument `patterns/contract.py` already won
for detectable situations, and cohorts and expectation maps before it: a declared thing can be
diffed, reviewed and corrected by the person who noticed it was wrong, while a question written in
Python can only be corrected by whoever wrote it. It matters more here than anywhere else in the
layer, because a question is the one artefact whose cost is paid per tenant per sweep — a
reviewer has to be able to see what it asks, what it is shown, and what it may answer, without
reading the caller.

THE SIX RULES THIS FILE ENFORCES AT CONSTRUCTION, each because the alternative fails quietly and
expensively:

1. **A `gate` may not be empty.** The gate is the cost control, not a convenience: it is what
   turns "ask about every node, every sweep" into "ask about the eleven rows in a queue". An angle
   with no gate is not a cheap angle, it is an unbounded one, and the shape of that failure is a
   bill nobody predicted. Unconstructable rather than discouraged.

2. **`sees` may not be empty, and it is a LIST OF FIELD NAMES.** The model never receives "the
   graph" — it receives what this tuple names. A reviewer reads one line to know what leaves the
   tenant, and a field added to the prompt without being added here does not exist.

3. **`returns` must be a closed set, and it MUST CONTAIN A REFUSAL.** The first half is ordinary:
   free text never becomes a fact, which is what `framing/headline.py` enforces by giving an
   invented noun nowhere to go. The second half is the one this system keeps having to relearn.
   An enum of `met / not_met` forces a guess on every call, because "I cannot tell from this" has
   nowhere to land — and `quality/missing.py` spent a whole module establishing that conflating
   "no" with "unknowable" is how a false finding is born. An angle that cannot say `unknowable`
   is an angle that will say something else instead.

4. **`confidence_band` may not reach certainty.** `llm_interpretation` bands its readings at
   2,000-8,000 so a model reading "enters the snapshot as evidence and can LOWER a confidence and
   never raise one". An angle is an opinion about a queue the deterministic layer could not
   resolve; a band that touches 10,000 lets that opinion outrank a measured fact.

5. **`max_per_sweep` is required and bounded.** Every pass in `runner.py` that can grow with a
   tenant carries a ceiling, and the `budgets` ledger exists because those ceilings were once
   computed and thrown away — "an org above a budget therefore looked exactly like an org that
   had nothing to do". A model pass without one is the same failure with an invoice attached.

6. **There is no field that makes an angle REQUIRED.** Not a flag defaulting to false — the field
   does not exist, and cannot be added without editing this docstring. An angle may only ever ADD
   to what the deterministic layer produced; nothing downstream may withhold a situation because a
   model was unavailable, over budget, or unsure. That is the standing rule of this branch —
   *no gate may refuse on an absence, only on positive contrary evidence* — expressed as an
   absence in the schema rather than as a sentence in a comment, because a sentence is not
   enforcement.

WHAT IS DELIBERATELY NOT HERE. No prompt text, no model name, no temperature: an angle says what
is asked and what may come back, and `angles/store.py` decides how. No scoring — how much a
verdict is worth is `importance.py`'s question and composes from Layer 1's own signals. And no
schedule: an angle does not know when it runs, which is what lets the same declaration be
evaluated on a drain, in a backfill, or not at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{2,63}")

#: The widest a verdict's confidence may ever be, in basis points. The floor is not zero because a
#: model that answered at all has said something; the ceiling is not 10,000 because a fact
#: measured by the deterministic layer must always be able to outrank an opinion about a queue
#: that layer could not resolve. `llm_interpretation` bands its own readings at 2,000-8,000 and
#: this is the outer bound every angle must sit inside.
CONFIDENCE_FLOOR_BP = 1_000
CONFIDENCE_CEILING_BP = 9_000

#: The most calls one angle may make for one tenant in one sweep, whatever it declares. A per-angle
#: ceiling is the author's business; this is the one nobody can raise by editing a declaration.
MAX_CALLS_PER_SWEEP = 200


class CostTier(str, Enum):
    """Which class of model an angle is worth. Named rather than a model id: a model name in a
    declaration is a declaration that has to be re-reviewed every time a vendor renames one."""

    CHEAP = "cheap"        # a classification over a compact summary — the common case
    CAPABLE = "capable"    # a judgement needing prose, reserved and budgeted harder


class GateSource(str, Enum):
    """WHICH QUEUE the gate names, because the two are different tables and guessing is not an
    option this layer permits anywhere else.

    ADDED WHEN THE STORE WAS WRITTEN, not before. `gate` shipped as a tuple of names and the
    schema landed alone deliberately — "a schema reviewed on its own is a schema a reviewer can
    argue with". The first thing that had to EXECUTE a gate could not, because
    `derived.timeline.condition_review` is a `graph_facts` row and `ball_in_court_unreported` is a
    `context_residue` row, and nothing said which a given angle meant. A store that inferred it
    from the string's shape would be a store that silently reads the wrong table the day somebody
    names a fact after a residue kind.

    CLOSED, so `angles/store.py` matches over it exhaustively: a source the store does not
    implement cannot be declared, rather than being discovered as an angle that quietly never
    fires — which is exactly the failure `patterns/registry.py` refuses loudly for condition kinds.
    """

    #: Subjects carrying every named field as a live `graph_facts` row. The common case: a queue
    #: the deterministic layer built by publishing a fact it could not act on.
    FACTS = "facts"

    #: Rows of `context_residue` of the named kinds — what L2 measured it could not explain. The
    #: only queue in the layer that is defined by the absence of a reading rather than the
    #: presence of a fact.
    RESIDUE = "residue"


class UnavailableAngle(ValueError):
    """Raised at REGISTRATION, never at evaluation.

    `patterns/registry.py` says why this is a distinct error and not a generic one: "a pattern
    whose condition kind is not implemented does not fail loudly — it simply never matches", and
    the same is true here. An angle naming a field nothing writes, or a verdict nothing handles,
    is not a quiet no-op to be discovered in a month of empty output; it is a declaration error
    with a name.
    """


def _identifier(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not _IDENTIFIER.fullmatch(text):
        raise UnavailableAngle(
            f"{label} must be lowercase snake_case, 3-64 characters: {value!r}")
    return text


def _names(values: Iterable[Any], label: str) -> tuple[str, ...]:
    out: list[str] = []
    for value in values or ():
        text = str(value or "").strip()
        if not text:
            raise UnavailableAngle(f"{label} contains a blank entry")
        if text in out:
            raise UnavailableAngle(f"{label} repeats {text!r}")
        out.append(text)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class Angle:
    """One bounded question, declared."""

    angle_id: str
    version: str

    #: THE DETERMINISTIC PRECONDITION, and the whole cost control. Names the rows this angle may
    #: be asked about — a queue the layer already built, never "every node". Evaluated before any
    #: model is reached, so a gate miss costs nothing at all.
    gate: tuple[str, ...]

    #: Which queue `gate` names. See `GateSource` — the store matches over this exhaustively, so
    #: an angle cannot name a source nothing implements.
    gate_source: GateSource

    #: EXACTLY WHICH FIELDS REACH THE MODEL. A reviewer reads this tuple to know what leaves the
    #: tenant. A field the prompt uses and this does not name is a field that does not exist.
    sees: tuple[str, ...]

    #: THE CLOSED SET OF ANSWERS. Must contain `refusal` — see rule 3 in the module docstring.
    returns: tuple[str, ...]

    #: The one answer that means "I cannot tell from what I was shown". Not a failure and not a
    #: default: a recorded result, which is how an angle's budget can be judged at all.
    refusal: str

    confidence_band: tuple[int, int]
    max_per_sweep: int
    #: ONE GATE ROW, MANY SUBJECTS — for a queue whose fact value is a LIST.
    #:
    #: WHY THIS EXISTS, and it is a correction rather than a feature. Both fact-shaped refusal
    #: queues in this layer store one row per NODE whose value is a list:
    #: `derived.timeline.condition_review` holds `{"review": [...]}` and
    #: `derived.dependency.missing_prerequisite` holds `{"absences": [...]}`. Without a fan-out
    #: the gate admits one subject per node, so an angle can only ever answer for the whole list.
    #: `condition_queue_triage` absorbed that by asking a question that is TRUE at node level and
    #: naming its fields `queue`. A CLASSIFICATION cannot: "Finance" and "Ankit's team" on one
    #: node are different kinds of absence, and one verdict covering both is not approximate, it
    #: is wrong.
    #:
    #: `(list_key, item_key)` — the key holding the list inside the gate value, and the key inside
    #: each item that names it. The subject becomes `"<node>#<digest of the item key>"`, the slice
    #: carries THAT ITEM ALONE, and `store._seen` fetches node facts against the node half. Items
    #: with a blank key are skipped rather than merged: an unnamed item is not a subject.
    #:
    #: Requires exactly one gate name — with two, there is no answer to WHICH value gets fanned.
    fan_out: tuple[str, ...] = ()

    cost_tier: CostTier = CostTier.CHEAP

    #: Free-form notes for the reviewer. Never read by the engine.
    note: str = ""
    config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "angle_id", _identifier(self.angle_id, "angle_id"))
        object.__setattr__(self, "version", str(self.version or "").strip() or "1.0.0")

        gate = _names(self.gate, "gate")
        if not gate:
            raise UnavailableAngle(
                f"{self.angle_id}: an angle with no gate is asked about every subject on every "
                "sweep — the gate is the cost control, not a convenience")
        object.__setattr__(self, "gate", gate)
        if not isinstance(self.gate_source, GateSource):
            try:
                object.__setattr__(self, "gate_source", GateSource(str(self.gate_source)))
            except ValueError as exc:
                raise UnavailableAngle(
                    f"{self.angle_id}: {self.gate_source!r} is not a queue this engine can read — "
                    f"one of {[s.value for s in GateSource]}") from exc

        fan = _names(self.fan_out, "fan_out")
        if fan:
            if len(fan) != 2:
                raise UnavailableAngle(
                    f"{self.angle_id}: fan_out is (list_key, item_key) — the key holding the list "
                    "inside the gate value, and the key inside each item that names it")
            if len(self.gate) != 1:
                raise UnavailableAngle(
                    f"{self.angle_id}: fan_out needs exactly one gate name — with two there is no "
                    "answer to which value gets fanned out")
        object.__setattr__(self, "fan_out", fan)

        sees = _names(self.sees, "sees")
        if not sees:
            raise UnavailableAngle(
                f"{self.angle_id}: `sees` is empty, so the model is asked to answer from nothing")
        object.__setattr__(self, "sees", sees)

        returns = _names(self.returns, "returns")
        if len(returns) < 2:
            raise UnavailableAngle(
                f"{self.angle_id}: `returns` needs at least two answers — a question with one "
                "answer is not a question")
        refusal = str(self.refusal or "").strip()
        if refusal not in returns:
            raise UnavailableAngle(
                f"{self.angle_id}: `refusal` must be one of `returns`, and `returns` must have "
                "one. An enum with no way to say 'I cannot tell from this' forces a guess on "
                "every call — see `quality/missing.py` on conflating 'no' with 'unknowable'")
        object.__setattr__(self, "returns", returns)
        object.__setattr__(self, "refusal", refusal)

        band = tuple(int(value) for value in self.confidence_band)
        if len(band) != 2 or band[0] >= band[1]:
            raise UnavailableAngle(
                f"{self.angle_id}: confidence_band must be (low, high) with low < high")
        if band[0] < CONFIDENCE_FLOOR_BP or band[1] > CONFIDENCE_CEILING_BP:
            raise UnavailableAngle(
                f"{self.angle_id}: confidence_band must sit inside "
                f"{CONFIDENCE_FLOOR_BP}..{CONFIDENCE_CEILING_BP} — an angle answers about a queue "
                "the deterministic layer could not resolve, and must never outrank a measured "
                "fact")
        object.__setattr__(self, "confidence_band", band)

        budget = self.max_per_sweep
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            raise UnavailableAngle(f"{self.angle_id}: max_per_sweep must be a positive integer")
        if budget > MAX_CALLS_PER_SWEEP:
            raise UnavailableAngle(
                f"{self.angle_id}: max_per_sweep {budget} exceeds the engine ceiling "
                f"{MAX_CALLS_PER_SWEEP}")
        object.__setattr__(self, "max_per_sweep", budget)

        if not isinstance(self.cost_tier, CostTier):
            object.__setattr__(self, "cost_tier", CostTier(str(self.cost_tier)))

    def admits(self, verdict: str) -> bool:
        """Whether this angle may answer with that word at all."""
        return str(verdict or "").strip() in self.returns

    def clamp(self, confidence_bp: int) -> int:
        """A confidence inside the band. Clamped rather than rejected: a model returning 9,900 is
        over-claiming, which is a thing to bound, not a reason to lose the verdict."""
        low, high = self.confidence_band
        return max(low, min(high, int(confidence_bp)))


#: What separates a node from the item within it in a fanned subject ref. A digest follows it and
#: digests contain no `#`, so `rsplit` recovers the node exactly even if a node id ever carried one.
FAN_SEP = "#"


def fan_subject_ref(node_ref: str, item_key: str) -> str:
    """The subject ref for one item inside a fanned gate row.

    ONE SPELLING, SHARED. The evaluator builds these and a reader joining verdicts back onto cards
    has to build the same string; two independent implementations of "how we name an item" is the
    trap `condition_situations` records against its own field name — "two spellings of one name,
    and the reader's copy would have kept selecting nothing".

    HASHED, NOT INTERPOLATED, because the item key is free text out of somebody's sentence — "the
    security review", a name with a `#` or a colon in it — and this string is split on a delimiter
    by its own reader.
    """
    import hashlib

    normalised = " ".join(str(item_key).split()).lower()
    digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]
    return f"{node_ref}{FAN_SEP}{digest}"


def fan_node_ref(subject_ref: str) -> str:
    """The node half of a subject ref, or the whole thing when it was never fanned."""
    return subject_ref.rsplit(FAN_SEP, 1)[0]


@dataclass(frozen=True, slots=True)
class AngleVerdict:
    """What one angle said about one subject.

    THE CONSTRUCTOR IS THE ENFORCEMENT POINT, not a downstream reader's `if`. The same discipline
    `correlation_timeline.SatisfiedCondition` keeps — it refuses to exist without both evidence
    spans "because the card has to show the sentence from May, and a claim with no receipt is a
    guess". A verdict whose word is not in its angle's `returns`, or whose confidence is outside
    the band, cannot be constructed, so no consumer has to check and none can forget to.
    """

    angle_id: str
    angle_version: str
    subject_ref: str
    verdict: str
    confidence_bp: int

    #: WHAT THE MODEL WAS SHOWN, by name. The audit answer to "on what basis?", and the reason a
    #: verdict can be re-judged later without re-running it.
    saw: tuple[str, ...] = ()

    #: The model-run row `context/model_audit.py` filed for this call, so a verdict can be traced
    #: to the prompt bytes and the parsed artifact it came from.
    model_run_id: str | None = None

    #: WHETHER THE MODEL SAID IT COULD NOT TELL, carried rather than looked up.
    #:
    #: An earlier cut derived this from the registry at read time, which was wrong twice: it made
    #: a verdict depend on global state it had already been handed, and its fallback answered True
    #: for any angle the registry had since lost — so an unregistered angle's every verdict read
    #: as a refusal. `of()` has the angle in hand; the answer belongs there.
    #:
    #: A REAL RESULT, not a failure. An angle whose refusals dominate is asking the wrong question
    #: or looking at the wrong queue, and that is only visible if refusing is recorded rather than
    #: discarded — `lifecycle/gate.py` makes the same argument for writing down why a call was NOT
    #: made: "the sweep made 4000 calls" and "the sweep made none" are both answerable only if the
    #: reason each subject was skipped is a value.
    refused: bool = False

    @classmethod
    def of(cls, angle: Angle, *, subject_ref: str, verdict: str, confidence_bp: int,
           model_run_id: str | None = None) -> "AngleVerdict":
        word = str(verdict or "").strip()
        if not angle.admits(word):
            raise UnavailableAngle(
                f"{angle.angle_id} answered {word!r}, which is not in its declared returns "
                f"{angle.returns} — a verdict outside the enum is free text wearing a schema")
        subject = str(subject_ref or "").strip()
        if not subject:
            raise UnavailableAngle(f"{angle.angle_id}: a verdict needs a subject to be about")
        return cls(angle_id=angle.angle_id, angle_version=angle.version, subject_ref=subject,
                   verdict=word, confidence_bp=angle.clamp(confidence_bp), saw=angle.sees,
                   model_run_id=model_run_id, refused=(word == angle.refusal))


#: `angle_id -> Angle`, populated by `register`. A plain dict rather than a frozen constant for the
#: reason `domain_spec._SPECS` is one: the angles a build ships with are registered at import, and
#: a test may register its own without editing this module.
_REGISTRY: dict[str, Angle] = {}


def register(angle: Angle) -> Angle:
    """Declare an angle. Refuses a second declaration of one name.

    Loading is not the point; REFUSING is — `patterns/registry.py`'s sentence, and it applies for
    the same reason. Two angles sharing an id is two budgets sharing a ledger and two prompts
    sharing an audit trail, and the failure shows up as a cost nobody can attribute.
    """
    held = _REGISTRY.get(angle.angle_id)
    if held is not None and held != angle:
        raise UnavailableAngle(
            f"{angle.angle_id} is already registered with a different declaration — one id, one "
            "question, or the audit trail describes neither")
    _REGISTRY[angle.angle_id] = angle
    return angle


def resolve(angle_id: str) -> Angle:
    """The registered angle, or `UnavailableAngle` naming what is missing."""
    angle = _REGISTRY.get(str(angle_id or "").strip())
    if angle is None:
        raise UnavailableAngle(
            f"no angle registered as {angle_id!r} — a caller naming an unregistered angle would "
            "otherwise ask nothing and report success")
    return angle


def registered() -> tuple[Angle, ...]:
    """Every declared angle, ordered by id so a report is diffable."""
    return tuple(_REGISTRY[key] for key in sorted(_REGISTRY))


__all__ = [
    "FAN_SEP", "fan_node_ref", "fan_subject_ref","Angle", "AngleVerdict", "CONFIDENCE_CEILING_BP", "CONFIDENCE_FLOOR_BP",
           "CostTier", "GateSource",
           "MAX_CALLS_PER_SWEEP", "UnavailableAngle", "register", "registered", "resolve"]
