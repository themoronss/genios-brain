"""They replied, we went quiet — and now the queue of those says which ones matter.

`reply_owed_triage` is the second declared angle and the first to read `context_residue`. The kind
it gates on is the one migration 0170 describes in the founder's own words: *"a node whose
`thread.ball_in_court` fact says the turn is OURS, with no live situation. This is the shape the
founder named directly: they replied, we went quiet, and nothing said so."*

A residue row has no live situation BY DEFINITION, so there is no card here to rank and this
angle mints none. It orders the work queue `read_residue` returns, and the tests below spend most
of their effort proving the things it must not do: it must not reorder the queue, must not remove
a row it calls `noise`, must not let a refusal through, and must leave a database without
migration 0171 reading exactly as it reads today.

The sharpest test in the file is `test_the_field_a_reader_would_reach_for_first_is_forbidden`.
`thread.days_waiting` is the obvious field for a queue about waiting, and it is guaranteed ABSENT
for this population: `waiting.py` retires it the moment a counterparty answers, and
`ball_in_court = us` means they answered last. Naming it would not error — it would put a
permanent blank in front of a model and bill for it every sweep.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.angles.library import REPLY_OWED_TRIAGE
from genios_engine.context.angles.store import evaluate_angle
from genios_engine.context.graph_store import GraphStore
from genios_engine.context.angles.queues import TRIAGE_KEY, triaged_residue
from genios_engine.context.residue import RESIDUE_BALL_IN_COURT, RESIDUE_SIGNAL
from genios_engine.context.waiting import WAITING_ONLY_FIELDS

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "o"
PERSON = "n_theresa"

_SCHEMA = (
    "create table graph_facts (org_id text, subject_node_id text, field text, value text, "
    "status text, valid_to text)",
    "create table context_residue (org_id text, residue_kind text, subject_ref text, "
    "detail text, first_seen_at timestamp, last_seen_at timestamp, "
    "primary key (org_id, residue_kind, subject_ref))",
    "create table context_angle_verdicts (org_id text, angle_id text, angle_version text, "
    "subject_ref text, verdict text, confidence_bp integer, refused boolean, saw_hash text, "
    "model_run_id text, first_seen_at timestamp, last_seen_at timestamp, "
    "primary key (org_id, angle_id, subject_ref))",
    "create table l2_model_runs (run_id text primary key, org_id text, site text, "
    "subject_ref text, prompt_version text, prompt_hash text, model_snapshot text, "
    "max_tokens integer, input_tokens integer, output_tokens integer, success boolean, "
    "error text, parsed_output text, raw_output text, response_hash text, latency_ms integer, "
    "called_at timestamp)",
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


def _fact(store, field, value, node=PERSON):
    with store._engine.begin() as c:
        c.execute(text("insert into graph_facts values (:o,:n,:f,:v,'active',null)"),
                  {"o": ORG, "n": node, "f": field, "v": value})


def _residue(store, node=PERSON, kind=RESIDUE_BALL_IN_COURT, detail="{}", days_old=30):
    with store._engine.begin() as c:
        c.execute(text("insert into context_residue values (:o,:k,:r,:d,:f,:l)"),
                  {"o": ORG, "k": kind, "r": node, "d": detail,
                   "f": NOW - timedelta(days=days_old), "l": NOW})


def _replied_and_we_went_quiet(store, node=PERSON):
    """The founder's case, as facts: they wrote last, the turn is ours, and they have a rhythm."""
    _fact(store, "thread.ball_in_court", "us", node=node)
    _fact(store, "thread.last_inbound", "2026-09-01T00:00:00+00:00", node=node)
    _fact(store, "thread.last_outbound", "2026-08-20T00:00:00+00:00", node=node)
    _fact(store, "thread.last_heard_days", "19", node=node)
    _fact(store, "party.reply_cadence_days", "2.5", node=node)
    _fact(store, "party.role", "investor", node=node)
    _fact(store, "relationship.nature", "introduced_by_boardy", node=node)
    _residue(store, node=node)


def _asker(word="important", confidence=6_000, seen=None):
    def ask(angle, subject_ref, slice_):
        if seen is not None:
            seen.append((subject_ref, dict(slice_)))
        return (word, confidence)
    return ask


def _queue(store, **kw):
    with store._engine.begin() as c:
        return triaged_residue(c, ORG, **kw)


# ── the field that must never be asked for ───────────────────────────────────────────────────

def test_the_field_a_reader_would_reach_for_first_is_forbidden() -> None:
    """`thread.days_waiting` is retired the instant a counterparty answers — `waiting.py` lists it
    in `WAITING_ONLY_FIELDS` and `retire_facts` closes it — and this angle gates on nodes where
    they answered LAST. Every waiting-only field is therefore a guaranteed blank here.

    Pinned against the real list rather than the literal, so the day somebody moves
    `thread.last_heard_days` into it, this fails instead of the angle quietly going blind.
    """
    assert not set(REPLY_OWED_TRIAGE.sees) & set(WAITING_ONLY_FIELDS)
    # …and the two that are here are exactly the ones that module says outlive a reply.
    assert "thread.last_heard_days" in REPLY_OWED_TRIAGE.sees
    assert "party.reply_cadence_days" in REPLY_OWED_TRIAGE.sees


def test_every_field_the_angle_declares_reaches_the_model(store) -> None:
    """`store._seen` fetches `sees` with `subject_node_id = :s`, so a field on another node comes
    back absent with no error. This angle's subject is a residue `subject_ref`, which for THIS
    kind is `f.subject_node_id` off a `thread.ball_in_court` fact — a node id. Two of the four
    residue kinds are not node-keyed at all (`open_loop_unreported` is a loop id,
    `signal_unreached` a type string), which is why the gate names exactly one kind.
    """
    _replied_and_we_went_quiet(store)
    seen: list = []
    evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=_asker(seen=seen))

    [(subject, slice_)] = seen
    assert subject == PERSON
    assert set(slice_) == set(REPLY_OWED_TRIAGE.sees)
    assert all(slice_[name] for name in REPLY_OWED_TRIAGE.sees), slice_


def test_the_gate_reads_residue_and_not_facts(store) -> None:
    """A node carrying every `sees` fact but NO residue row is not a subject: the queue is what
    the layer could not explain, not everyone we owe a reply."""
    _replied_and_we_went_quiet(store)
    with store._engine.begin() as c:
        c.execute(text("delete from context_residue"))
    run = evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=_asker())
    assert (run.gated, run.asked) == (0, 0)


# ── the verdict reaches the queue, and changes nothing else about it ─────────────────────────

def test_a_verdict_reaches_the_work_queue(store) -> None:
    _replied_and_we_went_quiet(store)
    evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=_asker("important", 7_000))
    [row] = _queue(store)
    assert row[TRIAGE_KEY] == "important"
    assert row["subject_ref"] == PERSON


def test_the_queue_is_still_ordered_by_age_and_not_by_the_model(store) -> None:
    """SORTING BY A MODEL'S WORD WOULD BE THE RANKING THE AGREED LAW FORBIDS — "a model may
    propose a situation; it may never rank one". The verdict rides beside each row so a reader can
    order by it; the engine keeps answering "longest unexplained first"."""
    _replied_and_we_went_quiet(store, node="n_old")
    _replied_and_we_went_quiet(store, node="n_new")
    with store._engine.begin() as c:
        c.execute(text("update context_residue set first_seen_at = :t where subject_ref = 'n_new'"),
                  {"t": NOW - timedelta(days=1)})

    # CHOSEN SO THE TWO ORDERS CONTRADICT. Age puts `n_old` first; the verdict words put
    # `n_new` first under any ordering that reads them (alphabetical, or severity with
    # `important` ranked highest and placed last). An earlier version of this test paired the
    # words the other way round, and a mutation that sorted the queue by verdict PASSED it —
    # "ambient" sorts before "important", which happened to reproduce age order by accident.
    def ask(angle, subject_ref, slice_):
        return ("important", 7_000) if subject_ref == "n_old" else ("ambient", 3_000)

    evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=ask)
    rows = _queue(store)
    assert [r["subject_ref"] for r in rows] == ["n_old", "n_new"]
    assert [r[TRIAGE_KEY] for r in rows] == ["important", "ambient"]


def test_noise_sinks_a_subject_and_removes_nothing(store) -> None:
    """`thread.ball_in_court` cannot tell a personal note from a no-reply blast, so the model is
    allowed to disagree. Disagreeing is not deletion: an angle cannot drop a residue row, retire a
    fact or suppress a reading, and the row stays in the queue wearing the word."""
    _replied_and_we_went_quiet(store)
    evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=_asker("noise", 6_000))
    [row] = _queue(store)
    assert row[TRIAGE_KEY] == "noise"
    with store._engine.begin() as c:
        assert c.execute(text("select count(*) from context_residue")).scalar() == 1
        assert c.execute(text(
            "select count(*) from graph_facts where field = 'thread.ball_in_court' "
            "and status = 'active'")).scalar() == 1


def test_a_refusal_never_reaches_the_queue(store) -> None:
    """`unknowable` is a fact about the ANGLE, not about this counterparty. `AngleRun.refused`
    counts it, and that is where an angle asking the wrong question becomes visible."""
    _replied_and_we_went_quiet(store)
    run = evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW,
                         asker=_asker("unknowable", 3_000))
    assert run.refused == 1
    assert TRIAGE_KEY not in _queue(store)[0]


# ── the three ways it is forbidden to matter ─────────────────────────────────────────────────

def test_the_queue_is_identical_without_the_angle(store) -> None:
    """THE STANDING LAW AT THE PLACE IT IS EASIEST TO BREAK: a build with no angle layer and a
    sweep that made no calls must both return today's queue."""
    _replied_and_we_went_quiet(store)
    before = _queue(store)
    assert TRIAGE_KEY not in before[0]

    evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=_asker())
    after = _queue(store)
    assert all(before[0][k] == after[0][k] for k in before[0])
    assert set(after[0]) - set(before[0]) == {TRIAGE_KEY}


def test_a_missing_verdict_table_raises_so_the_seam_can_undo_it(store) -> None:
    """THE PROPERTY MOVED TO THE SEAM THAT CAN ACTUALLY HONOUR IT, and this is the test that
    moved with it.

    This used to assert that the gather itself swallowed a missing table and returned an empty
    default. It did — and that WAS the bug. Postgres aborts the whole transaction on a failed
    statement, so the caught exception left the connection unusable and every LATER gather on it
    returned nothing. Measured on the live tenant: `context_angle_verdicts` did not exist, this
    guard behaved exactly as written, and eleven other gathers silently emptied. Twelve readings
    dead, no error naming the cause.

    So the gather now RAISES, and `outreach_situations._optional` is the single guard — it wraps
    each call in a SAVEPOINT, which is the only thing that can undo a failed statement. The
    degradation is unchanged from a reader's point of view; what changed is that it is now true.
    """
    from genios_engine.context.outreach_situations import _optional

    _replied_and_we_went_quiet(store)
    with store._engine.begin() as c:
        c.execute(text("drop table context_angle_verdicts"))
        with pytest.raises(Exception):
            triaged_residue(c, ORG)

    with store._engine.begin() as c:
        assert _optional(c, "triaged residue", lambda: triaged_residue(c, ORG), []) == []
        assert c.execute(text("select count(*) from context_residue")).scalar() >= 1


def test_a_kind_no_angle_looks_at_is_never_triaged(store) -> None:
    """`signal_unreached` is keyed by SIGNAL TYPE and `open_loop_unreported` by LOOP ID — neither
    is a node id, so neither can carry a `sees` slice and no angle gates on them. A triage key
    appearing on one would mean a verdict had been matched to the wrong subject entirely."""
    _residue(store, node="deadline", kind=RESIDUE_SIGNAL, detail='{"signals": 131}')
    _replied_and_we_went_quiet(store)
    evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=_asker())

    by_kind = {r["residue_kind"]: r for r in _queue(store)}
    assert TRIAGE_KEY in by_kind[RESIDUE_BALL_IN_COURT]
    assert TRIAGE_KEY not in by_kind[RESIDUE_SIGNAL]


def test_the_join_lives_where_it_cannot_close_a_cycle() -> None:
    """THE DAG CHECK CAUGHT THIS AND WAS RIGHT. The join belongs, by instinct, inside
    `residue.read_residue`. Put there it produced

        context_angle_verdicts -> context_residue -> context_angle_verdicts

    because `residue.py` WRITES `context_residue` while the angle store reads it and writes
    verdicts. Benign at runtime — only the reader joined, and `detect_residue` never looks at a
    verdict — but "benign because of which function you happened to call" stops being true the
    first time somebody filters the detector, and it stops being true silently.

    `scripts/derivation_dag_check.py` is what enforces this in CI; this says WHY in the one place
    a person moving the function back would read first.
    """
    import genios_engine.context.residue as residue_module

    assert "context_angle_verdicts" not in open(residue_module.__file__).read(), (
        "residue.py writes context_residue; reading verdicts there closes a derivation cycle — "
        "the join belongs in angles/queues.py, which writes nothing")


# ── the one-hop law ──────────────────────────────────────────────────────────────────────────

def test_the_angle_cannot_read_its_own_verdict(store) -> None:
    """The verdict lands in `context_angle_verdicts`; the slice is built from `graph_facts` and a
    residue row. They never meet, so the second sweep asks nothing — not because an answer was
    filtered out, but because the slice never moved."""
    _replied_and_we_went_quiet(store)
    first = evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=_asker())
    assert first.asked == 1

    seen: list = []
    second = evaluate_angle(store, ORG, REPLY_OWED_TRIAGE, eval_time=NOW, asker=_asker(seen=seen))
    assert (second.asked, second.unchanged) == (0, 1)
    assert seen == []


def test_a_backlog_drains_rather_than_being_paid_for_twice(store) -> None:
    """The budget is charged per CALL, and an unchanged slice is free forever. So a queue larger
    than `max_per_sweep` covers itself across sweeps and then costs one SELECT — which is why a
    ceiling well below the size of this queue is not a truncation."""
    for i in range(3):
        _replied_and_we_went_quiet(store, node=f"n_{i}")
    small = REPLY_OWED_TRIAGE.__class__(**{
        **{f.name: getattr(REPLY_OWED_TRIAGE, f.name)
           for f in REPLY_OWED_TRIAGE.__dataclass_fields__.values()},
        "angle_id": "reply_owed_budget_probe", "max_per_sweep": 2})

    first = evaluate_angle(store, ORG, small, eval_time=NOW, asker=_asker())
    assert (first.asked, first.budget_exhausted) == (2, True)
    second = evaluate_angle(store, ORG, small, eval_time=NOW, asker=_asker())
    assert (second.asked, second.unchanged, second.budget_exhausted) == (1, 2, False)
    third = evaluate_angle(store, ORG, small, eval_time=NOW, asker=_asker())
    assert (third.asked, third.unchanged) == (0, 3)
