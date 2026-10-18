"""Atlas Layer 7 #5 — permitted use, measured end to end instead of assumed.

The Atlas's acceptance evidence is *"prohibited evidence never reaches active brain or rendered
rationale"*, and it marks the cross-layer half UNMEASURED. Measured 2026-10-02:

  ✅ THE DECISION PATH ENFORCES IT. `packs/compiler/runtime_brains._visibility_allows_package` is
     called, and requires scope narrowness AND `set(package.principals) <= set(entry.principals)`
     — the whole audience, not one viewer. `contracts/learned_state._visible` is fail-closed on
     every axis, including an UNKNOWN scope.
  ⛔ THE RENDERED PATH DOES NOT. `api/brain_routes` selects the VALUE from both sinks with no
     visibility predicate, behind an org-only dependency that admits a `member` seat.

⛔ AND IT IS SAFE ONLY BECAUSE NOTHING CONSTRAINED CAN ARRIVE: every producer that writes a durable
sink declares an open scope. **Those two facts are only safe together**, so they are declared
together and this file fails the day either moves.

⛔⛔ AND ONE FRAGILITY UNDERNEATH BOTH. The enforcement runs only after
`Visibility.model_validate` succeeds, and that is kept alive by a TWO-ENTRY alias table
(`_L6_SCOPE_ALIASES`) that no test guarded. `runtime_brains`'s own docstring records what the last
failure of that exact shape cost: *"A SILENT TOTAL LOSS … the situation was counted as `error` and
its package — the whole package, not just the brain slice — was never built"*, and *"two defects in
series, the second hidden behind the first."*
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from genios_engine.contracts import visibility as V
from genios_engine.contracts.learned_state import _visible
from genios_engine.contracts.learning import VisibilityScope
from genios_engine.feedback import target_policy as TP
from genios_engine.packs.compiler.runtime_brains import (_L6_SCOPE_ALIASES,
                                                         _normalize_l6_visibility,
                                                         _visibility_allows_package)

_ENGINE = Path(__file__).resolve().parents[2] / "genios_engine"


# ── the resolver answers for everything, or says so ────────────────────────────────────────────

def test_every_proposal_site_resolves_or_is_declared_as_coming_from_storage():
    """⛔ COVERAGE BEFORE VERDICT. A resolver that answers for one call site and reports
    "nothing constrained" has reported nothing — it has reported its own blind spot."""
    unresolved = {f for f, _, _ in TP.unresolved_proposal_visibilities()}
    assert unresolved == set(TP.VISIBILITY_FROM_STORAGE), (
        f"measured unresolved={sorted(unresolved)} "
        f"declared={sorted(TP.VISIBILITY_FROM_STORAGE)}")


def test_the_resolver_actually_covers_most_of_the_engine():
    rows = TP.durable_proposal_visibilities()
    resolved = [r for r in rows if r[3] is not None]
    assert len(rows) >= 10, "no LearningObject call sites found — the resolver is broken, not clean"
    assert len(resolved) >= len(rows) - len(TP.VISIBILITY_FROM_STORAGE)


def test_the_resolver_follows_one_level_of_indirection():
    """`units.py` passes `_org_visibility()`, not `Visibility(...)`. Reading only the direct form
    resolved 1 of 11 sites."""
    scopes = {u: s for _, u, _, s in TP.durable_proposal_visibilities()}
    assert scopes.get("pattern_learning") == "ORGANIZATION"


# ── nothing constrained can reach a durable sink ───────────────────────────────────────────────

def test_no_durable_proposal_is_constrained():
    measured = TP.constrained_durable_proposals()
    assert set(f"{f}:{u}" for f, u, _ in measured) == set(TP.CONSTRAINED_DURABLE_PROPOSALS), (
        "a producer now proposes a CONSTRAINED durable brain value. ⛔ Before declaring it, read "
        "`target_policy.UNFILTERED_BRAIN_READERS`: `api/brain_routes.py` renders both sinks "
        f"org-wide with no principal check. Measured: {measured}")


@pytest.mark.parametrize("producer,unit", [
    ("packs/brains/behavior_distill.py", "<computed>"),
    ("packs/brains/adaptive_lease.py", "<computed>"),
    ("packs/brains/org_discovery.py", "<computed>"),
])
def test_each_delegated_producer_declares_an_open_scope(producer, unit):
    rows = [s for f, u, _, s in TP.durable_proposal_visibilities()
            if f == producer and u == unit]
    assert rows, f"{producer} no longer builds a LearningObject — re-read DELEGATED"
    assert all(s in TP.OPEN_SCOPES for s in rows), f"{producer} -> {rows}"


def test_the_one_constrained_proposal_targets_a_sink_no_brain_reader_selects():
    """`actor_outcome_analysis` is PRIVATE to the assignee — correct, and it goes to
    `learning_metrics`, which is why it is absent from the constrained-durable table."""
    rows = [(t, s) for _, u, t, s in TP.durable_proposal_visibilities()
            if u == "actor_outcome_analysis"]
    assert rows == [("METRICS", "PRIVATE")]
    assert "METRICS" not in TP.DURABLE_BRAIN_TARGETS


def test_open_scopes_is_exactly_the_two_that_need_no_principal_check():
    """⛔ The receipt's accepted set is built from this frozenset. Widening it would widen what
    `_CONSTRAINED_BRAIN_VALUE_SQL` calls healthy — silently, because the receipt would still be
    green. So the partition is pinned against the enum itself, not against a copy of it."""
    assert TP.OPEN_SCOPES == {"ORGANIZATION", "PUBLIC"}
    constrained = {m.name for m in VisibilityScope} - TP.OPEN_SCOPES
    assert constrained == {"PRIVATE", "PARTICIPANTS"}, (
        f"a new VisibilityScope member is neither declared open nor known constrained: "
        f"{sorted(constrained)}")
    for name in TP.OPEN_SCOPES:
        assert not _visible(VisibilityScope[name].value, None, set()) is False, name
    for name in constrained:
        assert _visible(VisibilityScope[name].value, None, set()) is False, (
            f"{name} passes the consumption contract with no viewer — it is not constrained")


# ── the readers, both directions ───────────────────────────────────────────────────────────────

def test_no_reader_drops_visibility_undeclared():
    assert TP.undeclared_unfiltered_readers() == (), (
        "a new reader selects a brain VALUE without its visibility and is undeclared")


def test_no_declared_reader_has_quietly_started_filtering():
    assert TP.stale_unfiltered_readers() == (), (
        "a declared reader now carries visibility on every value read — remove the declaration "
        "deliberately rather than leaving a lie in the table")


def test_the_rendered_reader_is_still_the_one_that_drops_it():
    assert "api/brain_routes.py" in TP.UNFILTERED_BRAIN_READERS
    dropped = {f for f, vis in TP.brain_sink_value_readers() if not vis}
    assert "api/brain_routes.py" in dropped


def test_the_rendered_reader_is_admitted_by_an_org_only_dependency():
    """The declaration claims a `member` seat can call it. That rests on the route depending on an
    ORG, not a seat — so the claim is checked rather than asserted in prose."""
    src = (_ENGINE / "api" / "brain_routes.py").read_text(encoding="utf-8")
    assert "get_current_org" in src
    assert "require_seat" not in src and "require_org_admin" not in src, (
        "the route now names a seat-level dependency; the declaration's reasoning must be re-read")


@pytest.mark.parametrize("reader", sorted(TP.UNFILTERED_BRAIN_READERS))
def test_every_declared_reader_says_why_and_what_moves_it(reader):
    omits, why, mover = TP.UNFILTERED_BRAIN_READERS[reader]
    assert len(omits) > 40 and len(why) > 80
    assert mover.startswith(("MOVES WHEN", "MOVES WITH"))


def test_the_rendered_readers_mover_names_the_fact_that_makes_it_safe():
    _, _, mover = TP.UNFILTERED_BRAIN_READERS["api/brain_routes.py"]
    assert mover.startswith("MOVES WITH")
    assert "CONSTRAINED_DURABLE_PROPOSALS" in mover


# ── the enforcement is real: behaviour, not a call-site grep ───────────────────────────────────

def test_the_package_gate_is_wired_into_a_LIVE_exclusion():
    """⛔ THE CALL BEING PRESENT IS NOT THE CALL BEING MADE.

    This test used to assert `"_visibility_allows_package" in called_names`, and a mutation
    rewriting the guard as `if False and not _visibility_allows_package(...)` **SURVIVED** — the
    call is still syntactically there. *A call site that looks wired is not a wired call site*, and
    a guard that passes while the feature is dead reads as coverage.

    ⛔ THE BEHAVIOURAL PROOF IS ELSEWHERE AND IS REAL:
    `tests/test_domain_expertise_compiler.py::test_runtime_brains_are_relevant_tenant_scoped_and_visibility_safe`
    builds a `private_preference` entry on production fixtures and asserts it lands in
    `package.metadata["excluded_runtime_entry_ids"]`. That test DOES catch the mutation. This one
    guards the shape that test depends on: the call must sit alone in the `if`, and the branch must
    exclude the entry rather than merely note it.
    """
    tree = ast.parse((_ENGINE / "packs" / "compiler" / "runtime_brains.py")
                     .read_text(encoding="utf-8"))
    live = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        # exactly `not _visibility_allows_package(...)` — no conjunction that can fold it away
        if not (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)):
            continue
        call = test.operand
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "_visibility_allows_package"):
            continue
        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        live.append(("Continue" in body or "Return" in body))
    assert live, (
        "the gate is no longer the whole condition of an `if` — a conjunction can constant-fold "
        "it away while leaving the call in place, which is exactly the mutation that survived")
    assert all(live), "the gate's branch no longer excludes the entry, it only records it"


@pytest.mark.parametrize("entry,package,allowed", [
    # ⛔ `V.ORG`, not `V.ORGANIZATION`. This test was written with the LEARNING vocabulary and
    # failed at collection: `contracts/learning.VisibilityScope.ORGANIZATION` is `"organization"`
    # while this compiler's model names the same scope `"org"`. Two vocabularies for one field,
    # which is the whole reason the alias table below is guarded.
    ({"scope": V.ORG}, {"scope": V.ORG}, True),
    # ⛔ the AUDIENCE must be covered, not merely overlap
    ({"scope": V.PRIVATE, "principals": ["a@x.com"]},
     {"scope": V.PRIVATE, "principals": ["a@x.com"]}, True),
    ({"scope": V.PRIVATE, "principals": ["a@x.com"]},
     {"scope": V.PRIVATE, "principals": ["a@x.com", "b@x.com"]}, False),
    ({"scope": V.PARTICIPANTS, "principals": ["a@x.com"]},
     {"scope": V.PARTICIPANTS, "principals": ["b@x.com"]}, False),
    # narrow evidence may not widen into a broader package
    ({"scope": V.PRIVATE, "principals": ["a@x.com"]}, {"scope": V.ORG}, False),
])
def test_the_package_gate_enforces_audience_containment(entry, package, allowed):
    assert _visibility_allows_package(entry, package) is allowed


@pytest.mark.parametrize("scope,principals,viewer,visible", [
    ("organization", None, set(), True),
    ("public", None, set(), True),
    ("private", ["a@x.com"], {"a@x.com"}, True),
    ("private", ["a@x.com"], {"b@x.com"}, False),
    ("private", ["a@x.com"], set(), False),
    ("participants", ["a@x.com"], {"a@x.com"}, True),
    ("participants", [], {"a@x.com"}, False),
    # ⛔ fail-closed on anything unrecognised — a scope nobody mapped is not an open one
    ("team", ["a@x.com"], {"a@x.com"}, False),
    (None, None, {"a@x.com"}, False),
    ("", None, {"a@x.com"}, False),
])
def test_the_consumption_contract_is_fail_closed_on_every_axis(scope, principals, viewer, visible):
    assert _visible(scope, principals, viewer) is visible


# ── ⛔⛔ and the alias table the whole enforcement stands on ──────────────────────────────────

def test_every_learning_scope_is_representable_after_normalisation():
    """⛔ A new `VisibilityScope` member with no alias makes `Visibility.model_validate` raise for
    EVERY entry of that scope. `shadow_compile` catches per situation, so the symptom is *"a
    compiled brain that produced nothing"* — which `runtime_brains`'s own docstring records as a
    SILENT TOTAL LOSS that stayed invisible behind a second defect."""
    for member in VisibilityScope:
        normalised = _normalize_l6_visibility({"scope": member.value})["scope"]
        assert normalised in V.SCOPES, (
            f"VisibilityScope.{member.name} = {member.value!r} normalises to {normalised!r}, "
            f"which is not in contracts/visibility.SCOPES {V.SCOPES}. Add the alias in "
            f"`_L6_SCOPE_ALIASES` or the brain slice of every package silently stops building")


def test_no_alias_names_a_scope_that_no_longer_exists():
    live = {m.value for m in VisibilityScope}
    stale = sorted(set(_L6_SCOPE_ALIASES) - live)
    assert not stale, f"stale aliases translate a scope nothing produces: {stale}"


def test_the_normaliser_output_validates_against_the_compilers_model():
    """Behaviour, not shape: the thing the enforcement actually needs is that the model accepts it."""
    for member in VisibilityScope:
        payload = _normalize_l6_visibility({"scope": member.value, "principals": ["a@x.com"],
                                            "derived_from": []})
        model = V.Visibility.model_validate(payload)
        assert model.scope in V.SCOPES
