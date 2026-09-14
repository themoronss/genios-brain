"""Almost everything the evaluator does is a refusal, and each refusal has a number.

`lifecycle/gate.py` describes the shape one module over: "Everything this module does is decide
NOT to spend a call, and it is written as a cascade of named refusals rather than one boolean
because 'the sweep made 4000 calls' and 'the sweep made none' are both answerable only if the
reason each situation was skipped is a value."

The five laws are lifted from `reason/llm_interpretation.py`, which already does this correctly at
Layer 4. Each is tested here as behaviour rather than as a comment, because the cost of each one
being wrong is a bill rather than an error.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.angles.contract import Angle, GateSource, register
from genios_engine.context.angles.store import (AUDIT_SITE, evaluate_angle, evaluate_org,
                                                read_verdicts)
from genios_engine.context.graph_store import GraphStore

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "o"

_SCHEMA = (
    "create table graph_facts (org_id text, subject_node_id text, field text, value text, "
    "status text, valid_to text)",
    "create table context_residue (org_id text, residue_kind text, subject_ref text, "
    "detail text, first_seen_at timestamp, last_seen_at timestamp)",
    "create table context_angle_verdicts (org_id text, angle_id text, angle_version text, "
    "subject_ref text, verdict text, confidence_bp integer, refused boolean, saw_hash text, "
    "model_run_id text, first_seen_at timestamp, last_seen_at timestamp, "
    "primary key (org_id, angle_id, subject_ref))",
    "create table l2_model_runs (run_id text primary key, org_id text, site text, "
    "subject_ref text, prompt_version text, prompt_hash text, model_snapshot text, "
    "max_tokens integer, input_tokens integer, output_tokens integer, success boolean, "
    "error text, parsed_output text, raw_output text, response_hash text, latency_ms integer, "
    "called_at timestamp)",
    # `model_audit.record_model_run` files the cost row beside the audit envelope. Present here
    # because a fixture missing it does not fail the audit — it fails the CALL, which would let
    # this file pass while proving the opposite of what it claims.
    "create table llm_costs (org_id text, model text, purpose text, input_tokens integer, "
    "output_tokens integer, success boolean, error text, subject_ref text, created_at timestamp)",
)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for stmt in _SCHEMA:
            c.execute(text(stmt))
    s = object.__new__(GraphStore)
    s._engine = engine
    return s


def _angle(angle_id="condition_now_true", **over):
    spec = dict(angle_id=angle_id, version="1.0.0",
                gate=("derived.timeline.condition_review",), gate_source=GateSource.FACTS,
                sees=("condition.quote",),
                returns=("met", "not_met", "not_a_condition", "unknowable"),
                refusal="unknowable", confidence_band=(2_000, 8_000), max_per_sweep=40)
    spec.update(over)
    return Angle(**spec)


def _fact(store, node, field, value="x"):
    with store._engine.begin() as c:
        c.execute(text("insert into graph_facts values (:o,:n,:f,:v,'active',null)"),
                  {"o": ORG, "n": node, "f": field, "v": value})


def _queued(store, node, quote="once you have two references"):
    _fact(store, node, "derived.timeline.condition_review", "{}")
    _fact(store, node, "condition.quote", quote)


def _asker(word="met", confidence=7_000, calls=None):
    def ask(angle, subject_ref, seen):
        if calls is not None:
            calls.append((subject_ref, dict(seen)))
        return (word, confidence)
    return ask


# ── law 1 · a gate miss never pays ───────────────────────────────────────────────────────────

def test_a_subject_outside_the_gate_is_never_summarised_or_asked(store) -> None:
    """The common case is an empty queue, and it must cost one SELECT."""
    _fact(store, "n1", "condition.quote", "an ordinary fact on an ordinary node")
    calls: list = []
    run = evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker(calls=calls))
    assert run.gated == 0 and run.asked == 0
    assert calls == []


def test_a_subject_must_satisfy_every_gate_name_not_any(store) -> None:
    """An angle declaring two preconditions and firing on one is not a narrower angle — it is a
    looser one that still reads correctly in review."""
    two = _angle(gate=("derived.timeline.condition_review", "condition.actor"))
    _queued(store, "n1")                       # has only the first
    assert evaluate_angle(store, ORG, two, eval_time=NOW, asker=_asker()).gated == 0
    _fact(store, "n1", "condition.actor", "Theresa")
    assert evaluate_angle(store, ORG, two, eval_time=NOW, asker=_asker()).gated == 1


# ── law 2 · an unchanged slice is never re-asked ─────────────────────────────────────────────

def test_the_same_slice_is_never_paid_for_twice(store) -> None:
    """This is what makes an angle's steady-state cost the rate at which its queue CHANGES rather
    than the size of the queue."""
    _queued(store, "n1")
    calls: list = []
    first = evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker(calls=calls))
    second = evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker(calls=calls))
    assert (first.asked, second.asked) == (1, 0)
    assert second.unchanged == 1
    assert len(calls) == 1


def test_a_slice_that_moves_is_asked_again(store) -> None:
    _queued(store, "n1")
    evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        c.execute(text("update graph_facts set value='once you have THREE references' "
                       "where field='condition.quote'"))
    assert evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker()).asked == 1


def test_only_the_fields_sees_names_reach_the_model(store) -> None:
    """A reviewer reads one tuple to know what leaves the tenant. A field the caller would like
    and the declaration does not name is not fetched."""
    _queued(store, "n1")
    _fact(store, "n1", "condition.actor", "Theresa")
    _fact(store, "party.secret", "n1", "never asked for")
    calls: list = []
    evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker(calls=calls))
    [(_, seen)] = calls
    assert set(seen) == {"condition.quote"}


# ── law 3 · the one-hop law ──────────────────────────────────────────────────────────────────

def test_a_verdict_is_not_written_where_a_gate_or_a_slice_could_read_it(store) -> None:
    """Enforced by construction rather than a filter: verdicts land in
    `context_angle_verdicts`, which no gate and no slice reads, so a model cannot reach its own
    output without somebody editing `GateSource`."""
    _queued(store, "n1")
    evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker())
    with store._engine.connect() as c:
        facts = c.execute(text("select count(*) from graph_facts where field like '%verdict%' "
                               "or field like '%angle%'")).scalar()
        verdicts = c.execute(text("select count(*) from context_angle_verdicts")).scalar()
    assert facts == 0, "a verdict must never become a fact a later gate could match"
    assert verdicts == 1


# ── law 4 · the enum and the band belong to the contract ─────────────────────────────────────

def test_an_answer_outside_the_enum_costs_one_subject_not_the_sweep(store) -> None:
    _queued(store, "n1")
    _queued(store, "n2")
    run = evaluate_angle(store, ORG, _angle(), eval_time=NOW,
                         asker=lambda a, ref, seen: (("nonsense", 5_000) if ref == "n1"
                                                     else ("met", 5_000)))
    assert (run.failed, run.asked) == (1, 1)


def test_an_over_claiming_confidence_is_bounded_on_the_way_in(store) -> None:
    _queued(store, "n1")
    evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker(confidence=9_999))
    with store._engine.connect() as c:
        assert c.execute(text("select confidence_bp from context_angle_verdicts")).scalar() == 8_000


def test_a_refusal_is_counted_as_a_result(store) -> None:
    """An angle whose refusals dominate is asking the wrong question or reading the wrong queue,
    and that is only visible if refusals are counted rather than discarded."""
    _queued(store, "n1")
    run = evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker(word="unknowable"))
    assert (run.asked, run.refused) == (1, 1)
    with store._engine.connect() as c:
        assert c.execute(text("select refused from context_angle_verdicts")).scalar() in (1, True)


# ── law 5 · the model is injected, never constructed ─────────────────────────────────────────

def test_with_no_asker_the_pass_costs_one_query_and_says_so(store) -> None:
    """`no_asker` is reported for the reason the `budgets` ledger exists: a pass that made no
    calls because it COULD not must never read as a pass with nothing to do."""
    _queued(store, "n1")
    run = evaluate_angle(store, ORG, _angle(), eval_time=NOW)
    assert run.no_asker is True
    assert (run.gated, run.asked) == (1, 0)


def test_retirement_happens_even_with_no_asker(store) -> None:
    """A subject that left the queue must lose its verdict whether or not anybody is asking new
    questions, or a tenant who turns the angles off keeps the last opinions they received."""
    _queued(store, "n1")
    evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        c.execute(text("delete from graph_facts where field='derived.timeline.condition_review'"))
    run = evaluate_angle(store, ORG, _angle(), eval_time=NOW)
    assert run.retired == 1
    with store._engine.connect() as c:
        assert read_verdicts(c, ORG) == []


# ── the budget ───────────────────────────────────────────────────────────────────────────────

def test_one_sweep_stops_at_the_declared_ceiling(store) -> None:
    for i in range(5):
        _queued(store, f"n{i}")
    run = evaluate_angle(store, ORG, _angle(max_per_sweep=2), eval_time=NOW, asker=_asker())
    assert (run.asked, run.budget_exhausted) == (2, True)


def test_a_complete_pass_is_not_reported_as_exhausted(store) -> None:
    _queued(store, "n1")
    assert evaluate_angle(store, ORG, _angle(), eval_time=NOW,
                          asker=_asker()).budget_exhausted is False


def test_the_backlog_drains_across_sweeps(store) -> None:
    """A ceiling is only correct if repeating the pass finishes the work — the drain repeats."""
    for i in range(5):
        _queued(store, f"n{i}")
    angle = _angle(max_per_sweep=2)
    total = 0
    for _ in range(4):
        total += evaluate_angle(store, ORG, angle, eval_time=NOW, asker=_asker()).asked
    assert total == 5


# ── the audit receipt, and what a lost one costs ─────────────────────────────────────────────

def test_every_call_files_a_durable_receipt(store) -> None:
    _queued(store, "n1")
    evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker())
    with store._engine.connect() as c:
        row = c.execute(text("select site, subject_ref, prompt_version from l2_model_runs")).first()
        linked = c.execute(text("select model_run_id from context_angle_verdicts")).scalar()
    assert row.site == AUDIT_SITE
    assert row.subject_ref == "condition_now_true:n1"
    assert linked is not None, "a verdict must be traceable to the prompt bytes it came from"


def test_a_lost_receipt_does_not_cost_the_verdict(store) -> None:
    """The tenant has already paid for the answer. A failure to write the audit row is a lost
    audit row, not a reason to discard it."""
    with store._engine.begin() as c:
        c.execute(text("drop table l2_model_runs"))
    _queued(store, "n1")
    run = evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker())
    assert (run.asked, run.failed) == (1, 0)
    with store._engine.connect() as c:
        assert c.execute(text("select model_run_id from context_angle_verdicts")).scalar() is None


# ── containment ──────────────────────────────────────────────────────────────────────────────

def test_one_angles_failure_is_not_the_others(store) -> None:
    """The boundary every pass in `runner.py` carries, for the reason that file records: a single
    bad pass once skipped the six behind it while the sweep still reported a clean run."""
    register(_angle(angle_id="angle_that_breaks", gate=("no_such_table_field",)))
    register(_angle(angle_id="angle_that_works"))
    _queued(store, "n1")
    report = evaluate_org(store, ORG, eval_time=NOW, asker=_asker())
    by_id = {run.angle_id: run for run in report.runs}
    assert by_id["angle_that_works"].asked == 1


def test_another_tenants_queue_is_never_read(store) -> None:
    with store._engine.begin() as c:
        c.execute(text("insert into graph_facts values "
                       "('other','n1','derived.timeline.condition_review','{}','active',null)"))
    assert evaluate_angle(store, ORG, _angle(), eval_time=NOW, asker=_asker()).gated == 0
