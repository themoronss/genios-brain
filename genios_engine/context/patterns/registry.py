"""L2.6.1-U1 · the pattern REGISTRY — declaration, registration-time validation, and the two
guards that make a bad pattern visible.

WHAT REGISTRATION IS FOR. Loading a pattern is not the point; REFUSING one is. Doc 06 names four
ways a pattern goes wrong and three of them are silent:

    too loose      it fires on everything and becomes noise          → the fire-rate guard, below
    too tight      it never fires at all                             → the silence report, below
    overlapping    three cards for one reality                       → L2.7.3 clusters by entity
    unavailable    a condition kind nobody implemented               → REFUSED here, loudly

The fourth is the one this file exists for. A pattern whose condition kind is not implemented does
not error at evaluation — it simply never holds, and *"never held"* is indistinguishable from
*"correctly found nothing"* in every metric anybody looks at. Layer 1 shipped fifteen of
twenty-one deep sales rules in exactly that state, gated on a field 9% of records carried, and the
suite was green the whole time. So: every condition is checked against `matcher.IMPLEMENTED_KINDS`
at registration, every `@`-reference against the closed set of references, and a pattern that
fails either does not enter the registry.

THE FIRE-RATE GUARD IS THE INTERESTING HALF. Every pattern declares `expected_fire_rate`, and a
pattern observed firing more than `FIRE_RATE_CAP_MULTIPLIER` times that rate MAY NOT ACTIVATE.
This is the loose-pattern failure caught before a tenant sees it, and it is stated as integer
arithmetic with no division (`observed_fires * 100 > expected * cap * anchors`) so a small
population cannot round a breach away to zero.

BOTH FAILURES ARE VISIBLE, WHICH IS THE POINT. `silent_patterns` reports the patterns that fired
zero times in the window, and `breaching_patterns` reports the ones that fired on everything. A
registry that only reported one of the two would be a registry that made the other one worse.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from genios_engine.context.patterns.contract import (AUTHORITY_THRESHOLD_REF, ANCHOR_REF,
                                                     Condition, ConditionKind, EdgeCondition,
                                                     FactCondition, NUMERIC_FACT_OPS,
                                                     Pattern, PatternError, no_float)
from genios_engine.context.patterns.matcher import IMPLEMENTED_KINDS

#: Doc 06: *"exceeding it 10x blocks activation"*. Named rather than inlined because the report
#: script prints the ceiling it used and an operator comparing two runs needs them to be the same
#: number.
FIRE_RATE_CAP_MULTIPLIER = 10

#: Where the shipped patterns live. Data, in files, so adding a detectable situation is a file and
#: a review rather than a deploy of new logic.
SEED_DIR = Path(__file__).resolve().parent / "seed"


class _NoFloatLoader(yaml.SafeLoader):
    """A YAML loader that refuses floats outright.

    `yaml.safe_load("weight_bp: 0.3")` produces a Python float without comment, and a float in a
    pattern is a threshold that compares differently on two machines. `packs/compiler/authoring`
    solved the same problem by mapping floats to `Decimal`; patterns have no legitimate use for a
    fraction at all — every ratio is basis points and every amount is minor units — so the honest
    answer here is a refusal rather than a conversion.
    """


def _refuse_float(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    raise PatternError(
        f"{node.start_mark} — a pattern may not contain the float {node.value!r}. Ratios are "
        "integer basis points and money is minor units.")


_NoFloatLoader.add_constructor("tag:yaml.org,2002:float", _refuse_float)


class RegistrationError(PatternError):
    """A pattern that was refused. Carries the pattern id so a load of twelve files names the
    one that is wrong."""


# =================================================================================================
# Registration
# =================================================================================================

def validate_pattern(pattern: Pattern, *,
                     implemented: frozenset[ConditionKind] = IMPLEMENTED_KINDS) -> None:
    """Every check that can be made without a graph. Raises `RegistrationError`, or returns.

    `implemented` is a parameter rather than a module read so a test can prove the refusal by
    taking a kind away — a guard nobody can demonstrate failing is a guard nobody can trust.
    """
    seen: set[tuple[str, str, str]] = set()
    for index, condition in enumerate((*pattern.conditions,
                                       *(s.condition for s in pattern.optional_signals))):
        where = f"{pattern.pattern_id} condition {index}"
        if condition.kind not in implemented:
            raise RegistrationError(
                f"{where} uses condition kind {condition.kind.value!r}, which no evaluator "
                f"implements ({sorted(k.value for k in implemented)}). A pattern with an "
                "unevaluable condition never fires, and never-fires is indistinguishable from "
                "found-nothing.")
        _validate_references(condition, where)
        key = _condition_key(condition)
        if key in seen:
            raise RegistrationError(
                f"{where} repeats {key[1]!r} — a duplicated condition cannot make a pattern "
                "tighter, and reads in review as though it does")
        seen.add(key)

    if pattern.optional_signals:
        total = sum(s.weight_bp for s in pattern.optional_signals)
        if total <= 0:                                   # pragma: no cover — weights are > 0
            raise RegistrationError(f"{pattern.pattern_id}: optional weights must be positive")


def _condition_key(condition: Condition) -> tuple[str, str, str]:
    path = getattr(condition, "field_path", None) or getattr(condition, "metric", "")
    return (condition.kind.value, str(path), str(getattr(condition, "op", "")))


def _validate_references(condition: Condition, where: str) -> None:
    """`@`-references: closed set, and each one legal only where it means something.

    An unknown `@name` would otherwise be compared as the literal string `"@name"`, which never
    equals anything and makes the condition permanently false — the silent non-fire again.
    """
    if isinstance(condition, FactCondition):
        value = condition.value
        if isinstance(value, str) and value.startswith("@"):
            if value != AUTHORITY_THRESHOLD_REF:
                raise RegistrationError(
                    f"{where}: unknown reference {value!r}; the only value reference is "
                    f"{AUTHORITY_THRESHOLD_REF}")
            if condition.op not in NUMERIC_FACT_OPS:
                raise RegistrationError(
                    f"{where}: {AUTHORITY_THRESHOLD_REF} is an approval THRESHOLD and is only "
                    f"meaningful with a magnitude operator, not {condition.op.value!r}")
    if isinstance(condition, EdgeCondition):
        for label, ref in (("from", condition.from_node), ("to", condition.to_node)):
            if isinstance(ref, str) and ref.startswith("@") and ref != ANCHOR_REF:
                raise RegistrationError(
                    f"{where}: unknown node reference {ref!r} in `{label}`; the only node "
                    f"reference is {ANCHOR_REF}")


class PatternRegistry:
    """The registered patterns, keyed by id, deterministic in every read.

    Registration is the only way in and it validates; there is no `patterns.append`. A registry
    whose contents could be added to without validation would make the registration-time checks
    advisory, which is the same as not having them.
    """

    def __init__(self, patterns: Iterable[Pattern] = (), *,
                 implemented: frozenset[ConditionKind] = IMPLEMENTED_KINDS) -> None:
        self._implemented = implemented
        self._by_id: dict[str, Pattern] = {}
        for pattern in patterns:
            self.register(pattern)

    def register(self, pattern: Pattern) -> Pattern:
        held = self._by_id.get(pattern.pattern_id)
        if held is not None and held.version == pattern.version and held != pattern:
            raise RegistrationError(
                f"pattern {pattern.pattern_id!r} version {pattern.version} is already registered "
                "with different conditions — a changed pattern needs a new version, or the "
                "situations it produced cannot be traced to what produced them")
        if held is not None and held.version > pattern.version:
            raise RegistrationError(
                f"pattern {pattern.pattern_id!r} is registered at version {held.version}; "
                f"refusing to go back to {pattern.version}")
        validate_pattern(pattern, implemented=self._implemented)
        self._by_id[pattern.pattern_id] = pattern
        return pattern

    def get(self, pattern_id: str) -> Pattern | None:
        return self._by_id.get(pattern_id)

    def all(self) -> tuple[Pattern, ...]:
        """Every registered pattern, sorted by id — the order the report prints and the drain
        evaluates in, so two runs produce comparable output."""
        return tuple(self._by_id[k] for k in sorted(self._by_id))

    def for_anchor(self, node_type: str) -> tuple[Pattern, ...]:
        """The patterns that could possibly match an anchor of this type. Step 1's cheap
        rejection, hoisted so the drain does not build slices nothing can match."""
        return tuple(p for p in self.all() if p.anchor_node_type == node_type)

    def anchor_types(self) -> tuple[str, ...]:
        return tuple(sorted({p.anchor_node_type for p in self._by_id.values()}))

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, pattern_id: object) -> bool:
        return pattern_id in self._by_id


# =================================================================================================
# Loading — a pattern is a file
# =================================================================================================

def load_pattern(data: Mapping[str, Any]) -> Pattern:
    """One pattern from the doc-06 mapping shape, with `optional_signals` flattened as the doc
    writes them: `{kind: observation, kind_name: x, weight_bp: 1500}`.

    `weight_bp` is popped OUT of the condition before the condition is built, so an optional
    signal and a required condition are the same type evaluated by the same code. A parallel
    "optional condition" type would be a second grammar to keep in step with the first.
    """
    no_float(data, "pattern")
    body = dict(data)
    emits = body.pop("emits", None)
    if isinstance(emits, Mapping) and "situation_type" in emits:
        body["situation_type"] = emits["situation_type"]
    anchor = body.pop("anchor", None)
    if isinstance(anchor, Mapping) and "node_type" in anchor:
        body["anchor_node_type"] = anchor["node_type"]

    signals: list[dict[str, Any]] = []
    for raw in body.pop("optional_signals", ()) or ():
        entry = dict(raw)
        weight = entry.pop("weight_bp", None)
        if weight is None:
            raise RegistrationError(
                f"{data.get('pattern_id')!r}: an optional signal without `weight_bp` contributes "
                "nothing and reads as though it does")
        signals.append({"condition": entry, "weight_bp": weight})
    body["optional_signals"] = signals

    try:
        return Pattern(**body)
    except PatternError:
        raise
    except Exception as exc:                       # pydantic ValidationError, KeyError, TypeError
        raise RegistrationError(
            f"{data.get('pattern_id', '<unnamed>')!r} is not a valid pattern: {exc}") from exc


def load_pattern_file(path: Path) -> Pattern:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_NoFloatLoader)
    except PatternError:
        raise
    except (OSError, yaml.YAMLError) as exc:
        raise RegistrationError(f"{path.name} could not be read as YAML: {exc}") from exc
    if not isinstance(data, Mapping):
        raise RegistrationError(f"{path.name} is not a pattern mapping")
    return load_pattern(data)


def load_directory(directory: Path) -> tuple[Pattern, ...]:
    """Every `*.yaml` in a directory, in filename order. Sorted, so two machines load the same
    registry and a diff of two fire reports is a diff of behaviour rather than of `readdir`."""
    return tuple(load_pattern_file(path) for path in sorted(directory.glob("*.yaml")))


@functools.lru_cache(maxsize=1)
def seed_registry() -> PatternRegistry:
    """The shipped registry — doc 06's six V1-reachable patterns.

    Cached because it is pure file IO over immutable data and the drain would otherwise re-parse
    six files per org per sweep. `cache_clear()` is available to a test that writes a seventh.
    """
    return PatternRegistry(load_directory(SEED_DIR))


# =================================================================================================
# The two guards — a pattern that fires on everything, and one that fires on nothing
# =================================================================================================

@dataclass(frozen=True, slots=True)
class FireObservation:
    """What one pattern actually did on one tenant over one window. Counted, never estimated."""

    pattern_id: str
    #: Fires in the window. A fire is one (pattern, anchor) match, deduplicated per evaluation.
    fires: int
    #: How many anchors of the pattern's type were CONSIDERED. The denominator, and the reason
    #: this is a rate rather than a count: 12 fires means nothing until you know whether the org
    #: has 20 contracts or 20,000.
    anchors: int
    window_days: int


@dataclass(frozen=True, slots=True)
class ActivationDecision:
    """May this pattern activate for this tenant, and on what evidence."""

    pattern_id: str
    allowed: bool
    reason: str
    #: Fires per 100 anchors per 30 days, integer, normalised to the declared window so two
    #: reports over different windows are comparable.
    observed_rate: int
    expected_rate: int
    ceiling_rate: int
    fires: int
    anchors: int

    def as_record(self) -> dict[str, Any]:
        return {"pattern_id": self.pattern_id, "allowed": self.allowed, "reason": self.reason,
                "observed_rate_per_100_anchors_30d": self.observed_rate,
                "expected_rate_per_100_anchors_30d": self.expected_rate,
                "ceiling_rate_per_100_anchors_30d": self.ceiling_rate,
                "fires": self.fires, "anchors": self.anchors}


def observed_rate_per_100_anchors_30d(observation: FireObservation) -> int:
    """The observed rate, normalised to 30 days and 100 anchors. Integer division, floor.

    Reported for a human; NEVER used to decide a breach — see `exceeds_expected`, which compares
    without dividing so a 3-anchor tenant cannot round its own breach away.
    """
    if observation.anchors <= 0 or observation.window_days <= 0:
        return 0
    return observation.fires * 100 * 30 // (observation.anchors * observation.window_days)


def exceeds_expected(pattern: Pattern, observation: FireObservation, *,
                     multiplier: int = FIRE_RATE_CAP_MULTIPLIER) -> bool:
    """Did this pattern fire more than `multiplier` times its declared rate? EXACT arithmetic.

    Written as a cross-multiplication rather than as `observed_rate > ceiling` on purpose. The
    rate is a floor division, and on a small population it floors a genuine breach to zero: two
    fires over three anchors in a week is 950 per 100 per 30 days against an expected 4, and an
    intermediate `//` at the wrong step reports 0. The comparison below never divides.
    """
    if observation.anchors <= 0 or observation.window_days <= 0:
        return False
    ceiling = pattern.expected_fire_rate.per_100_anchors_per_30d * multiplier
    # fires / (anchors * window/30) > ceiling / 100   ⟺   fires * 100 * 30 > ceiling * anchors * window
    return (observation.fires * 100 * 30
            > ceiling * observation.anchors * observation.window_days)


def activation_decision(pattern: Pattern, observation: FireObservation, *,
                        multiplier: int = FIRE_RATE_CAP_MULTIPLIER) -> ActivationDecision:
    """Doc 06's guard, as a decision an operator and a route can both read.

    A pattern with NO observation yet is allowed: a pattern must be able to run in shadow before
    anybody can know its rate, and refusing activation for want of evidence nobody could have
    collected would make the guard unfalsifiable. What is refused is activating a pattern that has
    ALREADY been shown to fire on everything.
    """
    expected = pattern.expected_fire_rate.per_100_anchors_per_30d
    ceiling = expected * multiplier
    rate = observed_rate_per_100_anchors_30d(observation)
    if observation.anchors <= 0:
        return ActivationDecision(pattern.pattern_id, True,
                                  "no anchors of this type observed yet — nothing to measure",
                                  rate, expected, ceiling, observation.fires, observation.anchors)
    if exceeds_expected(pattern, observation, multiplier=multiplier):
        return ActivationDecision(
            pattern.pattern_id, False,
            f"fired {observation.fires} times over {observation.anchors} anchors in "
            f"{observation.window_days}d — {rate} per 100 anchors per 30d against a declared "
            f"{expected} and a ceiling of {ceiling}. A pattern that matches everything is noise, "
            "not intelligence.",
            rate, expected, ceiling, observation.fires, observation.anchors)
    return ActivationDecision(pattern.pattern_id, True,
                              f"{rate} per 100 anchors per 30d, within the {ceiling} ceiling",
                              rate, expected, ceiling, observation.fires, observation.anchors)


def breaching_patterns(registry: PatternRegistry, observations: Sequence[FireObservation], *,
                       multiplier: int = FIRE_RATE_CAP_MULTIPLIER) -> tuple[ActivationDecision, ...]:
    """Every registered pattern whose observed rate breaches its ceiling. The loose half."""
    out = []
    for observation in sorted(observations, key=lambda o: o.pattern_id):
        pattern = registry.get(observation.pattern_id)
        if pattern is None:
            continue
        decision = activation_decision(pattern, observation, multiplier=multiplier)
        if not decision.allowed:
            out.append(decision)
    return tuple(out)


def silent_patterns(registry: PatternRegistry,
                    observations: Sequence[FireObservation]) -> tuple[str, ...]:
    """Registered patterns that fired ZERO times in the window — doc 06's *"reported for review"*.

    A pattern with no observation row at all counts as silent, which is the whole point: the
    dangerous state is a pattern nobody has heard from, and "no row" is exactly what that looks
    like in the fire log.
    """
    fired = {o.pattern_id for o in observations if o.fires > 0}
    return tuple(p.pattern_id for p in registry.all() if p.pattern_id not in fired)


__all__ = ["FIRE_RATE_CAP_MULTIPLIER", "SEED_DIR", "ActivationDecision", "FireObservation",
           "PatternRegistry", "RegistrationError", "activation_decision", "breaching_patterns",
           "exceeds_expected", "load_directory", "load_pattern", "load_pattern_file",
           "observed_rate_per_100_anchors_30d", "seed_registry", "silent_patterns",
           "validate_pattern"]
