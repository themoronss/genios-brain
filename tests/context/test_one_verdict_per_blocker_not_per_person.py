"""A classification cannot be shared, and the gate had no way to say so until now.

Both fact-shaped refusal queues in this layer store ONE row per node whose value is a LIST.
The condition angle shipped without a fan-out and absorbed that by asking a question true at node
level, naming its fields `queue`; it has since been fanned out too. A classification could never
have absorbed it: "Finance" and "Ankit's team" on one person are different kinds of absence, and
one verdict covering both is not approximate — it is wrong.

So `Angle.fan_out` makes each item its own subject. Half this file tests that machinery, because
it is new and the ways it fails are silent: a slice carrying the whole list instead of one item
asks a model about the group under a subject's name; a `_seen` that selects on `n_rohit#f938…`
finds no facts at all and bills for a prompt full of blanks; two unnamed items sharing a blank key
overwrite each other's verdicts in a table keyed on it.

The other half tests what the angle is not allowed to do. It classifies a card that already
exists: it cannot drop one, cannot touch `blocker.we_searched` — the computed flag that is the
only warrant for saying nobody is there — and a tenant with no angle layer gets exactly the cards
U4.1 produced.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.angles.contract import (Angle, GateSource, UnavailableAngle,
                                                   fan_node_ref, fan_subject_ref)
from genios_engine.context.angles.library import BLOCKER_ABSENCE
from genios_engine.context.angles.queues import BLOCKER_KIND_FIELD, blocker_absence_verdicts
from genios_engine.context.angles.store import evaluate_angle
from genios_engine.context.blocker_situations import BLOCKER_FIELD, read_unnamed_blockers
from genios_engine.context.graph_store import GraphStore
from tests.context._model_audit_schema import MODEL_AUDIT_SCHEMA

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "o"
PERSON = "n_rohit"

_SCHEMA = (
    "create table graph_facts (org_id text, subject_node_id text, field text, value text, "
    "status text, valid_to text)",
    "create table context_angle_verdicts (org_id text, angle_id text, angle_version text, "
    "subject_ref text, verdict text, confidence_bp integer, refused boolean, saw_hash text, "
    "model_run_id text, first_seen_at timestamp, last_seen_at timestamp, "
    "primary key (org_id, angle_id, subject_ref))",
    # Both tables `model_audit.record_model_run` writes, shared rather than copied — see
    # `_model_audit_schema` for the migration this file's own copy had not heard of.
    *MODEL_AUDIT_SCHEMA,
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


def _absence(named, quote=None, absence_type="unknowable") -> dict:
    quote = quote if quote is not None else f"we're blocked on {named}"
    return {"blocker_named": named,
            "absence": {"subject_node_id": PERSON, "expected_fact": "dependency.blocker",
                        "absence_type": absence_type},
            "evidence": [{"quote": quote, "start_offset": 0, "end_offset": len(quote),
                          "verified": False, "source_ref": "prepared_content:pc_x"}]}


def _fact(store, field, value, node=PERSON):
    with store._engine.begin() as c:
        c.execute(text("insert into graph_facts values (:o,:n,:f,:v,'active',null)"),
                  {"o": ORG, "n": node, "f": field, "v": value})


def _blocked_on(store, *names, node=PERSON):
    import json
    _fact(store, BLOCKER_FIELD,
          json.dumps({"absences": [_absence(n) for n in names]}), node=node)
    _fact(store, "party.role", "investor", node=node)
    _fact(store, "relationship.nature", "prospective_investor", node=node)


def _asker(word="named_function", confidence=6_000, seen=None, by_name=None):
    def ask(angle, subject_ref, slice_):
        if seen is not None:
            seen.append((subject_ref, dict(slice_)))
        if by_name is not None:
            item = slice_[BLOCKER_FIELD]
            return (by_name[item["blocker_named"]], confidence)
        return (word, confidence)
    return ask


def _cards(store, verdicts=None):
    import json
    with store._engine.begin() as c:
        rows = {r[0]: r[1] for r in c.execute(text(
            "select subject_node_id, value from graph_facts where field = :f"),
            {"f": BLOCKER_FIELD})}
    return read_unnamed_blockers({k: json.loads(v) for k, v in rows.items()}, NOW, None, verdicts)


def _facts(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


# ── the fan-out, which is the new machinery ──────────────────────────────────────────────────

def test_three_absences_on_one_person_are_three_subjects(store) -> None:
    """THE WHOLE REASON THIS UNIT EXISTS. One gate row, one fact, one node — three questions."""
    _blocked_on(store, "Finance", "the security review", "Ankit's team")
    seen: list = []
    run = evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker(seen=seen))

    assert (run.gated, run.asked) == (3, 3)
    assert len({ref for ref, _ in seen}) == 3
    assert all(fan_node_ref(ref) == PERSON for ref, _ in seen)


def test_each_slice_carries_one_absence_and_not_the_list(store) -> None:
    """Showing a model the siblings invites an answer about the group wearing a subject's name."""
    _blocked_on(store, "Finance", "legal")
    seen: list = []
    evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker(seen=seen))

    for _ref, slice_ in seen:
        item = slice_[BLOCKER_FIELD]
        assert isinstance(item, dict) and "absences" not in item
        assert item["blocker_named"] in {"Finance", "legal"}
    assert {s[BLOCKER_FIELD]["blocker_named"] for _r, s in seen} == {"Finance", "legal"}


def test_the_node_facts_still_reach_a_fanned_subject(store) -> None:
    """THE SILENT, BILLABLE FAILURE. `_seen` selects `subject_node_id = :s`, and a fanned ref is
    `n_rohit#f938…` — not a node id. Selecting on it returns nothing, with no error: a prompt full
    of blanks, on every sweep, paid for. `fan_node_ref` is what keeps the node half addressable."""
    _blocked_on(store, "Finance")
    seen: list = []
    evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker(seen=seen))

    [(ref, slice_)] = seen
    assert "#" in ref
    assert set(slice_) == set(BLOCKER_ABSENCE.sees)
    assert slice_["party.role"] and slice_["relationship.nature"]


def test_an_item_with_no_name_is_skipped_and_never_merged(store) -> None:
    """Two blank keys would produce one subject ref and overwrite each other in a table keyed on
    it — the second verdict silently winning. An unnamed item is not a subject."""
    import json
    _fact(store, BLOCKER_FIELD, json.dumps({"absences": [
        _absence("Finance"), {"blocker_named": "  "}, {"blocker_named": ""}]}))
    run = evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker())
    assert (run.gated, run.asked) == (1, 1)


@pytest.mark.parametrize("payload", ['not json', '{"absences": "Finance"}', '{}', '[]'])
def test_a_malformed_payload_yields_no_subjects_and_no_exception(store, payload) -> None:
    _fact(store, BLOCKER_FIELD, payload)
    run = evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker())
    assert (run.gated, run.asked, run.failed) == (0, 0, 0)


def test_an_absence_that_goes_away_retires_its_verdict(store) -> None:
    """Retirement works per ITEM now, which it could not before: resolving "Finance" must not
    retire the opinion about "the security review"."""
    import json
    _blocked_on(store, "Finance", "legal")
    evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        assert c.execute(text("select count(*) from context_angle_verdicts")).scalar() == 2
        c.execute(text("update graph_facts set value = :v where field = :f"),
                  {"v": json.dumps({"absences": [_absence("legal")]}), "f": BLOCKER_FIELD})

    run = evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker())
    assert run.retired == 1
    with store._engine.begin() as c:
        [(kept,)] = c.execute(text("select subject_ref from context_angle_verdicts")).all()
    assert kept == fan_subject_ref(PERSON, "legal")


# ── the contract refuses a fan-out it cannot honour ──────────────────────────────────────────

def _angle(**over):
    spec = dict(angle_id="probe", version="1.0.0", gate=("a",), gate_source=GateSource.FACTS,
                sees=("a",), returns=("x", "unknowable"), refusal="unknowable",
                confidence_band=(2_000, 8_000), max_per_sweep=10)
    spec.update(over)
    return Angle(**spec)


def test_a_fan_out_needs_exactly_one_gate_name() -> None:
    """With two gate names there is no answer to WHICH value gets fanned, and picking the first
    would be a rule nobody declared."""
    with pytest.raises(UnavailableAngle, match="exactly one gate name"):
        _angle(gate=("a", "b"), fan_out=("absences", "blocker_named"))


def test_a_fan_out_is_a_pair_or_nothing() -> None:
    with pytest.raises(UnavailableAngle, match="list_key, item_key"):
        _angle(fan_out=("absences",))


def test_an_angle_without_a_fan_out_is_unchanged() -> None:
    """The default is empty and every angle shipped before this one keeps node-level subjects."""
    assert _angle().fan_out == ()
    assert fan_node_ref("n_plain") == "n_plain"


# ── the verdict lands on the card it is about ────────────────────────────────────────────────

def test_two_blockers_on_one_person_get_different_verdicts(store) -> None:
    """THE POINT OF THE WHOLE UNIT. Before the fan-out, one verdict covered both of these and
    whichever word it carried was wrong about one of them."""
    _blocked_on(store, "Finance", "Ankit's team")
    evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW,
                   asker=_asker(by_name={"Finance": "named_function",
                                         "Ankit's team": "named_party"}))
    with store._engine.begin() as c:
        verdicts = blocker_absence_verdicts(c, ORG)

    by_name = {_facts(f)["blocker.named"]: _facts(f).get(BLOCKER_KIND_FIELD)
               for f in _cards(store, verdicts)}
    assert by_name == {"Finance": "named_function", "Ankit's team": "named_party"}


def test_the_reader_and_the_evaluator_name_a_subject_the_same_way(store) -> None:
    """Rebuilding the fanned ref by hand in the reader is the two-spellings failure: the join
    matches nothing, silently, and every card simply lacks a classification."""
    _blocked_on(store, "the security review")
    evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker("named_function"))
    with store._engine.begin() as c:
        [ref] = list(blocker_absence_verdicts(c, ORG))
    assert ref == fan_subject_ref(PERSON, "the security review")


def test_a_refusal_never_reaches_a_card(store) -> None:
    _blocked_on(store, "Finance")
    run = evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW,
                         asker=_asker("unknowable", 3_000))
    assert run.refused == 1
    with store._engine.begin() as c:
        assert blocker_absence_verdicts(c, ORG) == {}
    assert BLOCKER_KIND_FIELD not in _facts(_cards(store, {})[0])


# ── the three ways it is forbidden to matter ─────────────────────────────────────────────────

def test_a_card_is_identical_without_the_angle(store) -> None:
    _blocked_on(store, "Finance")
    before = _facts(_cards(store, None)[0])
    evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        verdicts = blocker_absence_verdicts(c, ORG)
    after = _facts(_cards(store, verdicts)[0])

    assert all(before[k] == after[k] for k in before)
    assert set(after) - set(before) == {BLOCKER_KIND_FIELD}


def test_not_a_dependency_marks_a_card_and_removes_nothing(store) -> None:
    """The claim came from an extractor that cannot always tell a blocking relation from a turn of
    phrase, so the model may disagree. Disagreeing is not deletion."""
    _blocked_on(store, "Finance")
    evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker("not_a_dependency"))
    with store._engine.begin() as c:
        verdicts = blocker_absence_verdicts(c, ORG)
    cards = _cards(store, verdicts)
    assert len(cards) == 1
    assert _facts(cards[0])[BLOCKER_KIND_FIELD] == "not_a_dependency"


def test_the_classification_cannot_touch_the_warrant(store) -> None:
    """`blocker.we_searched` is COMPUTED from the typed absence and is the only licence for saying
    nobody is there. A model verdict may sit beside it and must never move it."""
    _blocked_on(store, "Finance")
    evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker("named_party", 8_000))
    with store._engine.begin() as c:
        verdicts = blocker_absence_verdicts(c, ORG)
    facts = _facts(_cards(store, verdicts)[0])
    assert facts["blocker.we_searched"] is False
    assert "could not find" in _cards(store, verdicts)[0].display_name


# ── the one-hop law, and the field that would break it ───────────────────────────────────────

def test_the_angle_cannot_read_its_own_verdict(store) -> None:
    _blocked_on(store, "Finance", "legal")
    first = evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker())
    assert first.asked == 2
    second = evaluate_angle(store, ORG, BLOCKER_ABSENCE, eval_time=NOW, asker=_asker())
    assert (second.asked, second.unchanged) == (0, 2)


def test_no_angle_gates_or_sees_the_classification_it_produces() -> None:
    from genios_engine.context.angles.contract import registered

    for angle in registered():
        assert BLOCKER_KIND_FIELD not in angle.gate + angle.sees


def test_the_angle_does_not_ask_for_a_field_that_is_blank_here() -> None:
    """`derived.dependency.blocked_count` is built from resolved CHAINS. A node whose only
    dependency claim went unresolved has no edge, so no chain and no count — it would be blank in
    exactly the common case and billed for on every sweep. The same discipline that keeps
    `thread.days_waiting` out of `reply_owed_triage`."""
    from genios_engine.context.correlation_dependency import FIELD_BLOCKED_COUNT

    assert FIELD_BLOCKED_COUNT not in BLOCKER_ABSENCE.sees
