r"""Plane D `U05` · a route refusal says which of four kinds it is, structurally.

⛔ WHAT WAS WRONG. `NoExpertiseRoute` was `class NoExpertiseRoute(DomainCompilerError): pass`, so the
only way to tell its causes apart was to read the sentence it was built with — and
`scripts/corpus_route_probe.py` did precisely that, with three string tests over FOUR causes and an
`else` catch-all. Measured on the four real messages: `domain_not_activated` came back as
`no_route_type`. An operations fact reported as missing content, in the one tool routing coverage is
read from.

⛔ AND THE RIGHT PATTERN WAS FOURTEEN LINES UP IN THE SAME FILE. `UnsupportedCoverage` validates its
reason against a closed set at construction, with a docstring saying why. The argument was never
applied one class down.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from genios_engine.packs.compiler import capability_resolver as CR
from genios_engine.packs.compiler.errors import (AuthoringIntegrityError, NoExpertiseRoute,
                                                 UnsupportedCoverage)

REPO = pathlib.Path(__file__).resolve().parents[3]


# ── the vocabulary ────────────────────────────────────────────────────────────────────────────

def test_there_are_exactly_four_reasons():
    """Four, because there are four raise sites with four different owners. A fifth cause is a
    fifth entry here — visible in a diff rather than absorbed by an `else`."""
    assert NoExpertiseRoute.REASONS == frozenset({
        "unknown_domain_hint", "domain_not_activated",
        "predicate_rejected", "no_situation_binds_type"})


@pytest.mark.parametrize("reason", sorted(NoExpertiseRoute.REASONS))
def test_every_reason_is_documented_in_the_class_itself(reason):
    """⛔ SCOPED TO THIS CLASS'S OWN DOCSTRING, not the module's. A previous test in this session
    searched a whole module for an enum value and matched an unrelated class's member."""
    assert reason in (NoExpertiseRoute.__doc__ or "")


def test_a_reason_nobody_declared_is_refused_at_construction():
    with pytest.raises(ValueError, match="unknown NoExpertiseRoute reason"):
        NoExpertiseRoute("x", reason="not_a_reason")


def test_the_refusal_lists_the_four_so_the_caller_need_not_go_looking():
    with pytest.raises(ValueError) as caught:
        NoExpertiseRoute("x", reason="typo")
    for reason in NoExpertiseRoute.REASONS:
        assert reason in str(caught.value)


def test_the_reason_is_required_and_has_no_default():
    """⛔ A default would let a new raise site mint an unlabelled refusal that READS as one of the
    four, and not guessing which is the entire point of the field."""
    with pytest.raises(TypeError):
        NoExpertiseRoute("x")                                          # type: ignore[call-arg]
    sig = inspect.signature(NoExpertiseRoute.__init__)
    assert sig.parameters["reason"].default is inspect.Parameter.empty
    assert sig.parameters["reason"].kind is inspect.Parameter.KEYWORD_ONLY


def test_the_situation_type_rides_on_the_exception():
    """`domain_shadow` catches this inside a loop that still holds the row, so it COULD supply the
    type — and then two places would decide what the pair means."""
    exc = NoExpertiseRoute("x", reason="predicate_rejected", situation_type="reply_owed")
    assert exc.situation_type == "reply_owed"
    assert NoExpertiseRoute("x", reason="predicate_rejected").situation_type is None


def test_the_message_still_reaches_a_human_unchanged():
    """The structured field is additive. An operator reading a log loses nothing."""
    assert str(NoExpertiseRoute("situation 'x' names unknown domains ['fundraising']",
                                reason="unknown_domain_hint")) == \
        "situation 'x' names unknown domains ['fundraising']"


def test_it_is_still_a_domain_compiler_error():
    """Every existing `except NoExpertiseRoute` and `except DomainCompilerError` keeps working."""
    from genios_engine.packs.compiler.errors import DomainCompilerError

    assert issubclass(NoExpertiseRoute, DomainCompilerError)


def test_unsupported_coverage_is_deliberately_not_in_that_hierarchy():
    """Its own docstring: inheriting *"would put it one bare `except DomainCompilerError` away from
    being silently swallowed again."* Asserted so a tidy-up cannot undo the reasoning."""
    from genios_engine.packs.compiler.errors import DomainCompilerError

    assert not issubclass(UnsupportedCoverage, DomainCompilerError)


# ── every raise site is labelled, and correctly ───────────────────────────────────────────────

def _raise_sites() -> list[ast.Call]:
    """⛔ AST, NOT A GREP. The family rule, and this session broke it four times before writing it
    into its own tests: assert on structure, never on text that happens to sit near a thing."""
    tree = ast.parse(pathlib.Path(CR.__file__).read_text())
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "NoExpertiseRoute"]


def test_the_resolver_raises_it_in_exactly_four_places():
    assert len(_raise_sites()) == 4


def test_every_raise_site_names_a_reason_and_the_situation_type():
    """A single unlabelled site is a hole the `else` used to be."""
    for call in _raise_sites():
        kwargs = {k.arg for k in call.keywords}
        assert "reason" in kwargs, f"line {call.lineno} raises without a reason"
        assert "situation_type" in kwargs, f"line {call.lineno} raises without its type"


def test_the_four_sites_use_four_different_reasons():
    """⛔ TOTALITY, BOTH DIRECTIONS. Every reason is reachable from the resolver, and no two sites
    share one — a reason two causes share is a reason that tells nobody which team to send."""
    used = []
    for call in _raise_sites():
        for kw in call.keywords:
            if kw.arg == "reason" and isinstance(kw.value, ast.Constant):
                used.append(kw.value.value)
    assert sorted(used) == sorted(NoExpertiseRoute.REASONS)


def test_every_reason_is_reachable_from_the_resolver_and_none_is_dead():
    """The other half: a reason the resolver can never raise is dead vocabulary, and dead
    vocabulary gets "fixed" later by somebody widening a condition until it is reachable."""
    used = {kw.value.value for call in _raise_sites() for kw in call.keywords
            if kw.arg == "reason" and isinstance(kw.value, ast.Constant)}
    assert used == NoExpertiseRoute.REASONS


# ── and the string diagnosis it replaces ──────────────────────────────────────────────────────

def test_the_four_real_messages_were_genuinely_indistinguishable_to_three_tests():
    """⛔ THE MEASUREMENT THAT JUSTIFIED THE UNIT, KEPT AS A TEST. Replays the old classifier over
    the resolver's four actual messages and shows two of them collapsing into one bucket — so the
    finding cannot later be dismissed as theoretical."""
    def old_classifier(text: str) -> str:
        if "unknown domains" in text:
            return "unknown_domain_hint"
        if "no authored" in text:
            return "no_route_predicate"
        return "no_route_type"

    messages = {
        "unknown_domain_hint": "situation 'x' names unknown domains ['fundraising']",
        "domain_not_activated": ("situation 'x' routes to ['sales'], none of which this tenant "
                                 "has activated (['admin']). See platform/l3_activation."),
        "predicate_rejected": "situation 'x' matched the type index but no authored situation "
                              "predicate",
        "no_situation_binds_type": "no expertise route for situation type 'vendor_renewal' in "
                                   "domains ['admin']",
    }
    verdicts = {reason: old_classifier(text) for reason, text in messages.items()}
    assert verdicts["domain_not_activated"] == verdicts["no_situation_binds_type"], (
        "the premise of this unit was that these two collapsed; if they no longer do, re-measure "
        "before trusting anything else here")
    assert len(set(verdicts.values())) == 3, "three buckets over four causes"


def test_nothing_in_packs_diagnoses_a_refusal_from_its_message():
    """⛔ AST over every `packs/` module: no comparison against `str(exc)`. A grep for `str(exc)`
    would match the comments explaining why it is forbidden — which is the exact mistake this
    rule exists to stop."""
    offenders: list[str] = []
    for py in sorted((REPO / "genios_engine/packs").rglob("*.py")):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for side in (node.left, *node.comparators):
                if (isinstance(side, ast.Call) and isinstance(side.func, ast.Name)
                        and side.func.id == "str"
                        and any(isinstance(a, ast.Name) and a.id in ("exc", "e", "err")
                                for a in side.args)):
                    offenders.append(f"{py.name}:{node.lineno}")
    assert not offenders, offenders


def test_an_authoring_defect_is_still_a_different_exception():
    """A route that resolved no required objects is a corpus BUG, not a coverage gap. Keeping them
    as different types is what lets `no_route` mean one thing."""
    assert not issubclass(AuthoringIntegrityError, NoExpertiseRoute)
    assert not issubclass(NoExpertiseRoute, AuthoringIntegrityError)
