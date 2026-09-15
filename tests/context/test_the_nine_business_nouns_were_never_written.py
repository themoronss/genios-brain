"""The extractor published 1,211 business facts. The graph held five.

    pytest tests/context/test_the_nine_business_nouns_were_never_written.py -q

MEASURED READ-ONLY ON THE PILOT, 2026-09-15, by running the layer's own code over its own stored
extractions rather than by reading rows:

    field                      emitted by L1   in the graph
    party.role                           393              5
    thread.objective                     316              0
    person.title                         267              0
    organization.relationship            117              0
    deal.stage                            56              0
    deal.value                            23              0
    company.industry                      21              0
    relationship.nature                   15              0
    campaign.objective                     3              0

THE MECHANISM, and it is not the one it looks like. L1 files the extractor's UNVERIFIED output in
the permanent cache on purpose — an audit and a replay need the original — and grades spans on the
way OUT of the lane. Layer 2 is a reader too and read `l1_extraction_results.output` raw, so every
span arrived `verified: false`, and `_business_claim` keeps a fact only with a verified receipt.
`runner.graded_extraction` closed that. It closed it for events that arrive AFTERWARDS, and an
event already processed is never processed again — so a tenant onboarded before the fix keeps a
graph with none of these nouns in it, permanently, while the code that would write them is correct.

WHAT THAT COST, specifically. `cohort_outreach_gap` groups on `thread.objective`. Its corpus card
is authored, reviewer-approved and content-hashed, and it was structurally unfireable on a tenant
holding zero of them — which looked exactly like a broken reading and was a graph built one fix
too early.

THIS IS THE LIVE PATH, REPLAYED — NOT A LOOSER ONE. The claim, its value and its receipt are the
ones L1 already published; re-grading is integer work over a string and costs no model call. A
span that still does not resolve is dropped where the live path drops it, and a subject that does
not resolve to a node of the right type is dropped where `_business_subject` drops it. A backfill
that admitted what the live path refuses would put facts in the graph that no future event could
ever have produced, and nothing downstream could tell the two apart.
"""
from __future__ import annotations

import ast
import inspect

import pytest

from genios_engine.context import backfill

pytestmark = pytest.mark.unit


def _source() -> ast.Module:
    return ast.parse(inspect.getsource(backfill.backfill_business_facts))


def _calls() -> set[str]:
    return {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            for n in ast.walk(_source()) if isinstance(n, ast.Call)}


def test_the_backfill_regrades_rather_than_re_extracting() -> None:
    """NO MODEL CALL. The claims are the ones L1 already published; only the grading and the
    resolution are re-run, and both are deterministic. Re-extracting would spend the tenant's
    budget to recover facts we already have, and could return different claims than the ones the
    audit trail records."""
    called = _calls()
    assert "graded_extraction" in called
    assert not {"extract", "complete", "create"} & called, "the backfill is calling a model"


def test_it_refuses_exactly_where_the_live_path_refuses() -> None:
    """A backfill looser than the live path writes facts no future event could produce, and
    nothing downstream can tell those apart from real ones."""
    called = _calls()
    assert "_business_claim" in called, "the verified-receipt seam is being skipped"
    assert "_business_subject" in called, "subject resolution is being skipped"
    assert "_thread_node" in called, "the conversation subject is being skipped"


def test_every_claim_read_is_written_or_named() -> None:
    """The census discipline the correlators hold to: a claim that vanishes without a reason is
    the state this whole unit exists to end."""
    tree = _source()
    reasons = {n.args[0].value for n in ast.walk(tree)
               if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "refuse"
               and n.args and isinstance(n.args[0], ast.Constant)}
    assert reasons == {"extraction_unreadable", "no_verified_span", "subject_unresolved",
                       "no_thread_node", "objective_not_about_the_thread", "already_current"}, \
        f"the refusal vocabulary changed: {reasons}"


def test_an_unchanged_value_is_not_counted_as_a_loss() -> None:
    """A second pass over a backfilled org writes nothing, and that is not 800 failures. It is
    counted apart from the refusals so a re-run does not read as a regression."""
    src = inspect.getsource(backfill.backfill_business_facts)
    assert "already_current" in src
    assert src.index("already_current") > src.index("write_fact"), \
        "the no-op count must come from the writer's own answer, not be guessed beforehand"


def test_the_objective_is_written_on_the_thread_and_never_on_a_person() -> None:
    """`graph_facts` keys on (org, subject, field). One person spans 254 threads in the pilot's
    graph, so a conversation's objective written on them is overwritten by whichever message
    landed last — the exact collision `_thread_node` was built to end. A backfill that took the
    convenient subject would reintroduce it at scale."""
    tree = _source()
    branches = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                and any(isinstance(c, ast.Constant) and c.value == "thread.objective"
                        for c in ast.walk(n.test))]
    assert branches, "nothing special-cases the thread objective's subject"
    assert any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_thread_node"
               for b in branches for c in ast.walk(b))


def test_it_is_batched_so_one_transaction_never_spans_a_tenants_history() -> None:
    """The module's own rule, restated where it could be broken: a long backfill that holds one
    transaction open is a backfill that cannot be interrupted."""
    assert isinstance(backfill._FACT_BATCH, int) and 0 < backfill._FACT_BATCH <= 500
    tree = _source()
    assert any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "range"
               for n in ast.walk(tree)), "the whole tenant is being read into one transaction"


def test_the_backfill_declares_no_threshold_about_which_nouns_are_worth_writing() -> None:
    """Nine fields, no favourites. A rule here — "only write `thread.objective`, that is the one
    we noticed" — would be tuned on the tenant we happened to look at."""
    tree = _source()
    fields = {n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and n.value.count(".") == 1 and n.value.split(".")[0] in
              {"party", "person", "company", "deal", "organization", "relationship", "campaign"}}
    assert fields <= {"deal.value"}, (
        f"the backfill names business fields it favours: {fields} — `deal.value` is allowed "
        f"because its VALUE TYPE differs (Money, not a string), which the live path also "
        f"special-cases")
