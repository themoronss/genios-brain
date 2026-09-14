"""A pattern that fires into a type no domain binds produces nothing, and produces it silently.

The chain is: pattern → `pattern_fires.situation_type` → a situation of that type → an L3
capability keyed on it → a card. When no authored situation binds the type the chain ends at step
three. The corpus tooling does report it — *"emitted by Layer 2, bound by no domain — no
capability will ever compile for it"* — but that is a line in a tool nobody runs on a normal day,
and nothing in the engine or the suite said a word.

THE DEFECT THIS FILE WAS WRITTEN AFTER. `condition_now_satisfied` is the one seed pattern whose
inputs exist on a mail-only tenant: `correlation_timeline` writes
`derived.timeline.condition_satisfied` with both evidence spans, and U2.4 gave that a card. The
pattern emitted `condition_now_satisfied` while `domain_spec` maps the `condition_met` anchor to
`condition_satisfied` and the authored document `admin.sit.condition_now_satisfied` binds THAT.
Two names for one concept, so the only pattern that could have reached a card could not. Nothing
failed; the type simply never routed.

Both directions are checked, because a one-way check rots. A type that has since been bound must
be removed from the deferral list, or the list becomes a record of things that used to be true.
"""
from pathlib import Path

import pytest
import yaml

from genios_engine.context.patterns.routing import UNROUTED_PATTERN_TYPES

_ROOT = Path(__file__).resolve().parents[3]
_SEED = _ROOT / "genios_engine" / "context" / "patterns" / "seed"
_CORPUS = _ROOT / "Domain Expertise"


def _emitted() -> dict[str, str]:
    """`{situation_type: pattern_id}` for every shipped seed pattern."""
    out: dict[str, str] = {}
    for path in sorted(_SEED.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        emits = (doc.get("emits") or {}).get("situation_type")
        if emits:
            out[str(emits)] = str(doc.get("pattern_id") or path.stem)
    return out


def _bound() -> set[str]:
    """Every L2 situation type some domain's GENERATED registry claims.

    Read from `registry/situation-capability-map.yaml` rather than by walking situation files,
    because the registry is what the compile actually consults — and `authoring.py` is explicit
    that it "is never hand-edited", so it is the honest source for what is really routed.
    """
    found: set[str] = set()
    for path in _CORPUS.glob("*/registry/situation-capability-map.yaml"):
        doc = yaml.safe_load(path.read_text()) or {}
        found.update(str(k) for k in (doc.get("map") or {}))
    return found


def test_the_seed_patterns_are_readable_at_all() -> None:
    emitted = _emitted()
    assert len(emitted) == len(list(_SEED.glob("*.yaml"))), "a seed pattern emits no situation type"
    assert _bound(), "no domain registry was found — has _tools/index.py ever run?"


@pytest.mark.parametrize("situation_type,pattern_id", sorted(_emitted().items()))
def test_every_pattern_type_is_bound_or_declared(situation_type: str, pattern_id: str) -> None:
    """The guard. A pattern may fire into a type nobody claims only if somebody wrote down why."""
    if situation_type in _bound():
        return
    assert situation_type in UNROUTED_PATTERN_TYPES, (
        f"pattern `{pattern_id}` emits `{situation_type}`, which no domain binds. A candidate it "
        f"produces can never compile into a card and nothing will say so. Either author a "
        f"situation that binds it, or declare it in `patterns/routing.UNROUTED_PATTERN_TYPES` "
        f"with the condition that would change it.")


def test_the_pattern_with_live_inputs_actually_routes() -> None:
    """`condition_now_satisfied` is the one whose inputs exist on a mail-only tenant —
    `correlation_timeline` writes the two-span fact it reads, every sweep. It is the regression
    this file exists to hold: it emitted a name the corpus did not bind, so the only seed pattern
    that could reach a card did not."""
    emitted = _emitted()
    assert emitted.get("condition_satisfied") == "condition_now_satisfied"
    assert "condition_satisfied" in _bound()
    assert "condition_now_satisfied" not in emitted


def test_no_declared_deferral_has_quietly_been_bound() -> None:
    """THE OTHER DIRECTION, and the one that makes the list trustworthy. An entry that has since
    been bound is a stale exception, and a list of stale exceptions is how a deferral register
    becomes a record of things that used to be true."""
    stale = sorted(set(UNROUTED_PATTERN_TYPES) & _bound())
    assert stale == [], (
        f"{stale} are bound by a domain now and still listed as unrouted — delete the entries.")


def test_no_declared_deferral_names_a_type_no_pattern_emits() -> None:
    """A deferral for a type nothing emits is a reason nobody needs, kept forever."""
    orphans = sorted(set(UNROUTED_PATTERN_TYPES) - set(_emitted()))
    assert orphans == [], f"{orphans} are declared unrouted but no seed pattern emits them."


@pytest.mark.parametrize("situation_type", sorted(UNROUTED_PATTERN_TYPES))
def test_every_deferral_says_what_would_change_it(situation_type: str) -> None:
    """`KNOWN_UNREAD`'s rule, applied here: a permanent exception list is a way to never fix
    anything, so each entry names the condition under which it stops being an exception."""
    reason = UNROUTED_PATTERN_TYPES[situation_type]
    assert "MOVES WHEN:" in reason, situation_type
    assert len(reason.split()) >= 30, situation_type
