"""M-3, the model site the spec named and nothing filled until now.

`correlation_dependency`'s header states the census: *"Correlation's two model sites are M-3
(ambiguous conversation matching) and M-5 (condition parsing)"*. M-5 became `condition_now_true`.
M-3 could not be declared at all until U4.3 built it a queue, because `find_campaigns` groups by
the exact sentence and persists nothing.

THE ENUM IS THE UNIT. A binary — one campaign or not — would have been the obvious shape and would
have been wrong for this tenant's actual mail. An introducer makes five introductions; the founder
answers each personally the same morning; every reply mentions the raise. Those share distinctive
wording, land in one window and reach enough people, so they arrive in this queue EVERY TIME. They
are not a campaign. Forced into `one_campaign` they produce a card telling a founder to follow up
on an outreach they never sent; forced into `unrelated` they lose the one true thing about them.
`same_topic_not_one_message` is that answer, and `test_five_personal_replies_are_not_a_blast` is
the test that would fail if somebody collapsed the enum.

The rest of the file is about what a verdict may not do. It merges nothing: `find_campaigns`
remains the only thing that mints a campaign and it still requires the exact sentence.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.angles.contract import fan_node_ref, fan_subject_ref
from genios_engine.context.angles.library import SAME_SITUATION_TWO_THREADS as M3
from genios_engine.context.angles.queues import VERDICT_KEY, adjudicated_candidates
from genios_engine.context.angles.store import evaluate_angle
from genios_engine.context.campaign_candidates import FIELD_CANDIDATE
from genios_engine.context.graph_store import GraphStore

NOW = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)
ORG = "o"
TENANT = "n_tenant"

_SCHEMA = (
    "create table graph_facts (org_id text, subject_node_id text, field text, value text, "
    "status text, valid_to text)",
    "create table graph_nodes (org_id text, node_id text, canonical_key text, node_type text, "
    "valid_to text)",
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
        c.execute(text("insert into graph_nodes values (:o,:n,:k,'tenant',null)"),
                  {"o": ORG, "n": TENANT, "k": f"tenant:{ORG}"})
    s = object.__new__(GraphStore)
    s._engine = engine
    return s


def _candidate(cid, sentences, *, tokens=("preseed", "traction", "mrr"), recipients=None,
               hours=2):
    n = len(sentences)
    return {"candidate_id": cid,
            "shared_tokens": list(tokens),
            "sentences": list(sentences),
            "recipients": list(recipients or [f"n_{cid}_{i}" for i in range(n)]),
            "event_ids": [f"e_{cid}_{i}" for i in range(n)],
            "sends": n,
            "first_sent": NOW.isoformat(),
            "last_sent": (NOW + timedelta(hours=hours)).isoformat()}


def _queued(store, *candidates):
    with store._engine.begin() as c:
        c.execute(text("insert into graph_facts values (:o,:n,:f,:v,'active',null)"),
                  {"o": ORG, "n": TENANT, "f": FIELD_CANDIDATE,
                   "v": json.dumps({"candidates": list(candidates)})})


def _asker(word="one_campaign", confidence=6_000, seen=None, by_id=None):
    def ask(angle, subject_ref, slice_):
        item = slice_[FIELD_CANDIDATE]
        if seen is not None:
            seen.append((subject_ref, item))
        if by_id is not None:
            return (by_id[item["candidate_id"]], confidence)
        return (word, confidence)
    return ask


#: THE BLAST — one raise, retyped, sent out by the founder.
_BLAST = ("We are raising a preseed round with traction at 3k MRR",
          "Quick note on our preseed, traction is now about 3k MRR",
          "Sharing that we opened a preseed; MRR traction sits near 3k")

#: THE BOARDY SHAPE — five introductions answered individually, all mentioning the raise.
_REPLIES = ("Thanks so much for the intro Ankit — we're mid-preseed, traction around 3k MRR",
            "Lovely to meet you Priya, happy to share more; preseed is open, 3k MRR traction",
            "Good to connect Sam — as context we're raising a preseed off 3k MRR traction")


# ── the reason the enum has four answers ─────────────────────────────────────────────────────

def test_five_personal_replies_are_not_a_blast(store) -> None:
    """THE CASE THE BINARY WOULD HAVE LOST, and the one this tenant actually has. Five intros
    answered personally in one morning share the raise vocabulary and reach this queue every time.
    Calling them a campaign produces a card about an outreach nobody sent."""
    _queued(store, _candidate("c_blast", _BLAST), _candidate("c_replies", _REPLIES))
    evaluate_angle(store, ORG, M3, eval_time=NOW,
                   asker=_asker(by_id={"c_blast": "one_campaign",
                                       "c_replies": "same_topic_not_one_message"}))

    with store._engine.begin() as c:
        by_id = {e["candidate_id"]: e.get(VERDICT_KEY) for e in adjudicated_candidates(c, ORG)}
    assert by_id == {"c_blast": "one_campaign", "c_replies": "same_topic_not_one_message"}


def test_the_enum_keeps_the_answer_that_is_neither(store) -> None:
    """Collapsing this to a binary is the change this test exists to stop."""
    assert "same_topic_not_one_message" in M3.returns
    assert {"one_campaign", "unrelated", "unknowable"} <= set(M3.returns)


# ── the queue it reads, and how it is addressed ──────────────────────────────────────────────

def test_each_candidate_is_its_own_question(store) -> None:
    """One fact on the tenant node holds the whole queue; `fan_out` makes each candidate a
    subject, so two near-misses can be adjudicated differently."""
    _queued(store, _candidate("c1", _BLAST), _candidate("c2", _REPLIES))
    seen: list = []
    run = evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker(seen=seen))

    assert (run.gated, run.asked) == (2, 2)
    assert {fan_node_ref(ref) for ref, _item in seen} == {TENANT}
    assert {item["candidate_id"] for _ref, item in seen} == {"c1", "c2"}


def test_the_model_is_shown_one_candidate_and_the_whole_question(store) -> None:
    """`sees` names one field and it is reused from the gate, so this angle costs one SELECT per
    tenant however many candidates it adjudicates — and the slice is ONE candidate, not the list."""
    _queued(store, _candidate("c1", _BLAST), _candidate("c2", _REPLIES))
    seen: list = []
    evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker(seen=seen))

    for _ref, item in seen:
        assert "candidates" not in item
        assert item["sentences"] and item["shared_tokens"]
    assert M3.sees == (FIELD_CANDIDATE,)


def test_the_reader_and_the_evaluator_name_a_candidate_the_same_way(store) -> None:
    _queued(store, _candidate("c1", _BLAST))
    evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        [ref] = [r[0] for r in c.execute(text("select subject_ref from context_angle_verdicts"))]
    assert ref == fan_subject_ref(TENANT, "c1")


# ── what a verdict is forbidden to do ────────────────────────────────────────────────────────

def test_a_verdict_merges_nothing(store) -> None:
    """`one_campaign` is an OPINION about mail the exact-sentence rule declined to group, and the
    ANGLE writes nothing: no fact, no node, no edge. `find_campaigns` remains the only thing that
    mints a `Campaign`, and it still requires the sentence to match.

    NARROWED DELIBERATELY IN U5.7, and the assertion below is untouched. This docstring also said
    "no card", and a downstream reading now produces one — `reworded_outreach` turns a
    `one_campaign` verdict into `outreach_reworded`, its own type, which declares
    `outreach.exact_sentence` ABSENT precisely because that absence is why the deterministic
    grouping did not fire. The rule that mattered was never "no card"; it was that a model verdict
    must not be dressed as a campaign it cannot evidence. That rule still holds, and this test
    still holds the half it always checked: evaluating the angle mutates no graph."""
    _queued(store, _candidate("c1", _BLAST))
    evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker("one_campaign", 8_000))

    with store._engine.begin() as c:
        fields = [r[0] for r in c.execute(text("select distinct field from graph_facts"))]
        nodes = [r[0] for r in c.execute(text("select node_type from graph_nodes"))]
    assert fields == [FIELD_CANDIDATE]
    assert nodes == ["tenant"]


def test_the_queue_reads_the_same_without_any_angle(store) -> None:
    """A build with no angle layer and a sweep that made no calls both return the queue U4.3
    published — unannotated, which is worse than adjudicated and is still reviewable."""
    _queued(store, _candidate("c1", _BLAST))
    with store._engine.begin() as c:
        before = adjudicated_candidates(c, ORG)
    assert len(before) == 1 and VERDICT_KEY not in before[0]

    evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        after = adjudicated_candidates(c, ORG)
    assert set(after[0]) - set(before[0]) == {VERDICT_KEY}
    assert all(before[0][k] == after[0][k] for k in before[0])


def test_a_refusal_leaves_the_candidate_unannotated(store) -> None:
    """An unanswered candidate is returned rather than hidden: a queue showing only what a model
    reached is a queue nobody can review."""
    _queued(store, _candidate("c1", _BLAST))
    run = evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker("unknowable", 3_000))
    assert run.refused == 1
    with store._engine.begin() as c:
        [entry] = adjudicated_candidates(c, ORG)
    assert VERDICT_KEY not in entry


def test_a_database_without_the_verdict_table_still_answers(store) -> None:
    _queued(store, _candidate("c1", _BLAST))
    with store._engine.begin() as c:
        c.execute(text("drop table context_angle_verdicts"))
        [entry] = adjudicated_candidates(c, ORG)
    assert entry["candidate_id"] == "c1" and VERDICT_KEY not in entry


# ── budget, identity and the one-hop law ─────────────────────────────────────────────────────

def test_a_candidate_whose_membership_changed_is_a_new_question(store) -> None:
    """`candidate_id` is content-addressed on the SET of sends, so a group that gained a member is
    a different candidate — and last sweep's opinion must not silently cover it."""
    _queued(store, _candidate("c1", _BLAST))
    evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        c.execute(text("update graph_facts set value = :v"),
                  {"v": json.dumps({"candidates": [_candidate("c1_plus", _BLAST + (
                      "Also raising a preseed, traction near 3k MRR",))]})})

    run = evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker())
    assert (run.asked, run.retired) == (1, 1)


def test_the_angle_cannot_read_its_own_verdict(store) -> None:
    _queued(store, _candidate("c1", _BLAST))
    first = evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker())
    assert first.asked == 1
    second = evaluate_angle(store, ORG, M3, eval_time=NOW, asker=_asker())
    assert (second.asked, second.unchanged) == (0, 1)


def test_this_is_the_judgement_a_better_model_is_reserved_for(store) -> None:
    """Every other angle classifies a short field. This reads up to six sentences of real prose
    and decides whether they are one voice."""
    from genios_engine.context.angles.contract import CostTier

    assert M3.cost_tier is CostTier.CAPABLE
    assert M3.max_per_sweep == 40
