"""M-6 is finished, correct, and unreachable — and the reason is a design constraint, not neglect.

`context/framing` is 629 lines with no caller in any layer. That looks like the dead code this
branch has been removing, and it is not. Two things prevent it running, and only one of them is a
wiring job:

  1. **IT IS PER-READER.** `FramingInput.for_viewer(..., viewer_email=...)` drops every fact the
     reader may not see BEFORE the prompt is built — "barrier one of two", and the reason a leak
     would require the model to INVENT a fact rather than repeat one. A sweep has no reader. So
     framing cannot run in `process_pending` at all; it belongs where a card is rendered for
     somebody, one viewer at a time.
  2. **IT HAS NOTHING TO FRAME.** Its input is a pattern's `matched_conditions`, and
     `is_patterns_activated` is false for every tenant — fail-closed, deliberately, because
     activation is an operator's decision about an unbudgeted graph read.

So this file does not wire it. It locks in the two properties that decide whether wiring it later
is a one-line change or a debugging session, and pins the invariant that must survive either way.

THE COUPLING IS THE PART THAT ALREADY BIT. A template is selected by `situation_type`, and U5.2
found the `condition_met` template keyed on `condition_now_satisfied` — a name no domain binds —
so the one pattern whose inputs exist on a mail-only tenant would have framed into nothing.
Nothing checked it. `test_framing.py` checks patterns → templates; this checks the direction that
failed, templates → a type the corpus can actually route.
"""
import pathlib

import pytest
import yaml

from genios_engine.context.framing.headline import (TEMPLATES, FramingFact, FramingInput, frame,
                                                    template_headline)
from genios_engine.context.patterns.routing import UNROUTED_PATTERN_TYPES

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "Domain Expertise"


def _census() -> set[str]:
    voc = yaml.safe_load((_CORPUS / "_schema" / "vocabulary.yaml").read_text())
    return set((voc.get("substrate") or {}).get("l2_situation_types") or ())


def _bound() -> set[str]:
    found: set[str] = set()
    for path in _CORPUS.glob("*/registry/situation-capability-map.yaml"):
        found |= set((yaml.safe_load(path.read_text()) or {}).get("map") or {})
    return found


def _template_types() -> list[tuple[str, str]]:
    return [(t.template_id, st) for t in TEMPLATES for st in t.situation_types]


# ── the coupling that already failed once ────────────────────────────────────────────────────

@pytest.mark.parametrize("template_id,situation_type", _template_types())
def test_every_template_names_a_type_layer_two_can_emit(template_id: str,
                                                        situation_type: str) -> None:
    """A template keyed on a type nothing emits can never be selected, and nothing would say so.
    This is the half `test_framing.py` does not check — it asks whether every SEED PATTERN has a
    template, never whether every TEMPLATE has a reachable situation."""
    assert situation_type in _census(), (
        f"template `{template_id}` frames `{situation_type}`, which is not in the closed census "
        f"of types Layer 2 emits — it can never be selected.")


@pytest.mark.parametrize("template_id,situation_type", _template_types())
def test_every_template_reaches_a_card_or_says_why_not(template_id: str,
                                                       situation_type: str) -> None:
    """THE DEFECT U5.2 FOUND, held here. The `condition_met` template framed
    `condition_now_satisfied` while the corpus bound `condition_satisfied` — two names for one
    concept, so the only pattern whose inputs exist on a mail-only tenant framed into nothing.

    Unbound is permitted where the pattern that emits the type is itself declared unroutable:
    five of the six templates are for patterns that cannot fire on a mail-only tenant, and a
    template waiting for its pattern is not the same defect as a template waiting for nothing.
    """
    if situation_type in _bound():
        return
    assert situation_type in UNROUTED_PATTERN_TYPES, (
        f"template `{template_id}` frames `{situation_type}`, which no domain binds and no "
        f"deferral declares. Either bind the type or declare it in "
        f"`patterns/routing.UNROUTED_PATTERN_TYPES`.")


def test_the_one_routable_template_is_the_one_whose_pattern_can_fire() -> None:
    """`condition_now_satisfied` is the only seed pattern whose inputs exist on a mail-only tenant
    — `correlation_timeline` writes its two-span fact every sweep — so its template is the only
    one that must be fully routable today."""
    routable = {st for _tid, st in _template_types() if st in _bound()}
    assert routable == {"condition_satisfied"}, routable


# ── wiring it later must not need a model, a budget, or a decision ───────────────────────────

def _input(situation_type: str = "condition_satisfied") -> FramingInput:
    facts = (FramingFact(fact_id="f1", label="days left", value="12",
                         field_path="derived.timeline.condition_satisfied"),
             FramingFact(fact_id="f2", label="counterparty", value="Theresa",
                         field_path="thread.ball_in_court"))
    return FramingInput.for_viewer(
        situation_type, facts, matched_conditions=("derived.timeline.condition_satisfied",),
        viewer_email="rohit@example.com", subject_label="Theresa")


def test_a_headline_exists_with_no_model_at_all() -> None:
    """`ask=None` IS THE DEFAULT, the same shape `angles/store` keeps: "a test drives the same
    code path with a stub and no network, and the sweep path cannot reach a model even by
    accident because it never receives one". So wiring framing costs no budget and no model
    decision — it produces the deterministic sentence until somebody injects an asker."""
    unasked = frame(_input())
    assert unasked.headline
    assert unasked.fallback_reason == "no_model"
    assert unasked.headline == template_headline(_input()).headline


def test_the_fallback_names_which_fallback_it_was() -> None:
    """"A plainer card always beats a wrong one" — and every one of the five fallback paths is
    LOGGED with which it was, so a tenant whose cards are all deterministic is a visible fact
    rather than a silent one."""
    assert frame(_input()).fallback_reason == "no_model"


# ── the invariant that must survive whoever wires it ─────────────────────────────────────────

def test_a_reader_who_may_see_nothing_is_not_even_told_the_subject() -> None:
    """Barrier one, and it degrades rather than leaks: when the filter empties the input the
    subject becomes the situation TYPE, "which names a category and nobody". An anchor's name is
    itself a fact about the world."""
    from genios_engine.contracts.visibility import Visibility

    secret = FramingFact(fact_id="f1", label="counterparty", value="Theresa",
                         field_path="thread.ball_in_court",
                         visibility=Visibility(scope="participants",
                                               principals=["someone@else.com"],
                                               derived_from="test:thread"))
    inp = FramingInput.for_viewer("condition_satisfied", (secret,),
                                  matched_conditions=(), viewer_email="outsider@example.com",
                                  subject_label="Theresa", org_member=False)
    assert inp.facts == ()
    assert "Theresa" not in inp.subject_label
    assert "Theresa" not in template_headline(inp).headline


def test_no_sweep_can_reach_the_framing_site() -> None:
    """THE PERMANENT INVARIANT, and the reason this unit does not wire framing into
    `process_pending`. Framing is filtered FOR ONE READER before the prompt is built; a sweep has
    no reader, so a sweep that framed anything would be framing for nobody — and the only honest
    `viewer_email` it could pass is None, which is the value that empties the filter.

    Guarded the way `test_m9_never_fires_inside_a_sweep` guards its own site: a raw scan of the
    runner, prose included, so the import cannot appear even in a comment that a later edit
    uncomments.
    """
    runner = (_ROOT / "genios_engine" / "context" / "runner.py").read_text()
    assert "framing" not in runner, (
        "runner.py names the framing site. Framing is per-reader and a sweep has no reader; it "
        "belongs where a card is rendered for somebody.")
