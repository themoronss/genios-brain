"""STEP-05 · the acceptance: on every founder case, every kept item has entered memory.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_every_kept_item_enters_memory.py -q

Tree `yc2_w27_s05 · M23.C5.L-integration.V5.U03`. Every founder case is replayed from its cassette
through the REAL chain (`engine_runner.run_case`, the recorded model — no spend), and the tenant's rows
are read before it is removed:

  * every kept event — emitted or archived — has a settled L2 run (a screen item without a signal is
    not owed one, `06` D22);
  * every calendar event is a meeting node, whatever its signal;
  * no archived mail's words are readable: not in a fact, an evidence reference, a node, a card, a
    prepared text or an extraction — the sentences of its body that no kept mail of the case shares,
    and that are not its own ledger metadata (a signature that is the sender's name is the sender's
    name, which an archive enters memory with);
  * no screen contact became a person. ⛔ No founder case carries a screen item (F30, the screen door,
    is not expressible), so on the golden set this holds over nothing; the drain test holds it
    (`tests/context/test_every_kept_event_enters_memory.py`), and the control below proves the check
    can fail.

The controls plant one miss of each kind into a real run and require the check to name it.
"""
from __future__ import annotations

import json
import os
import re

import pytest
from sqlalchemy import text

from tests.replays import cassettes
from tests.replays.founder_case import load_cases

CASES = load_cases()
_SENTENCE = re.compile(r"(?<=[.?!])\s+|\n+")
_SCREEN = "screen_session"


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _sentences(body: str) -> set[str]:
    return {" ".join(s.split()) for s in _SENTENCE.split(body or "") if len(s.strip()) >= 24}


def _words(obj) -> set[str]:
    """An archived mail's own words: its sentences less what its ledger row already says — the
    sender as named on the From line, and the addresses it went to."""
    metadata = " ".join([obj.sender, *obj.to, *obj.cc]).lower()
    return {s for s in _sentences(obj.body) if s.lower() not in metadata}


def violations(engine, org: str, case, run) -> dict[str, list]:
    """The four promises, read off the tenant's rows. Every list empty is a pass."""
    by_object = {o.object_id: o for o in case.objects}
    archived = [ld for ld in run.landed if ld.outcome == "archived" and ld.event_id]
    kept_text = set().union(*[_sentences(o.body) for o in case.objects
                              if o.source == "gmail" and not any(
                                  ld.object_id == o.object_id for ld in archived)] or [set()])
    with engine.connect() as c:
        outside = [tuple(r) for r in c.execute(text(
            "select se.event_id, se.outcome from source_events se "
            " where se.org_id = :o and se.outcome in ('emitted', 'archived') "
            "   and not (se.source = :screen and not exists (select 1 from qualified_signals q "
            "            where q.org_id = se.org_id and q.event_id = se.event_id "
            "              and q.state = 'active')) "
            "   and not exists (select 1 from l2_processing_runs r where r.org_id = se.org_id "
            "                   and r.event_id = se.event_id and r.status = 'done')"),
            {"o": org, "screen": _SCREEN})]
        meetings = [r[0] for r in c.execute(text(
            "select distinct se.source_object_id from source_events se "
            " where se.org_id = :o and se.source = 'gcal' and se.object_type = 'calendar_event' "
            "   and se.outcome = 'emitted' "
            "   and not exists (select 1 from graph_nodes n where n.org_id = se.org_id "
            "                   and n.node_type = 'meeting' and n.valid_to is null "
            "                   and n.canonical_key = 'gcal:' || se.source_object_id)"),
            {"o": org})]
        readable = []
        for ld in archived:
            for sentence in sorted(_words(by_object[ld.object_id]) - kept_text):
                hits = c.execute(text(
                    "select 'fact' from graph_facts where org_id = :o and value::text ilike :w "
                    "union all select 'evidence' from graph_source_refs where org_id = :o "
                    "  and evidence::text ilike :w "
                    "union all select 'node' from graph_nodes where org_id = :o "
                    "  and (display_name ilike :w or attributes::text ilike :w) "
                    "union all select 'card' from cards where org_id = :o "
                    "  and concat_ws(' ', headline, situation, why::text, actions::text, "
                    "                artifact::text) ilike :w "
                    "union all select 'prepared' from prepared_content where org_id = :o "
                    "  and event_id = :e "
                    "union all select 'extraction' from l1_extraction_results where org_id = :o "
                    "  and event_id = :e"),
                    {"o": org, "e": ld.event_id, "w": f"%{sentence[:60]}%"}).fetchall()
                readable += [(ld.object_id, h[0], sentence[:60]) for h in hits]
        people = [r[0] for r in c.execute(text(
            "select distinct n.canonical_key from source_events se "
            "  join graph_nodes n on n.org_id = se.org_id and n.node_type = 'person' "
            "       and n.valid_to is null and n.canonical_key = lower(se.actor ->> 'email') "
            " where se.org_id = :o and se.source = :screen "
            "   and not exists (select 1 from source_events m where m.org_id = se.org_id "
            "                   and m.source <> :screen "
            "                   and lower(m.actor ->> 'email') = lower(se.actor ->> 'email'))"),
            {"o": org, "screen": _SCREEN})]
    return {"outside memory": outside, "calendar with no meeting": meetings,
            "archived words readable": readable, "screen contact made a person": people}


def _run(case):
    from genios_engine.api import routes
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import RecordedLLM

    return routes._graph.engine, run_case(case, RecordedLLM(cassettes.load(case)), keep=True)


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_every_kept_item_enters_memory(case):
    _scratch_db()
    from tests.replays.engine_runner import remove_tenant

    engine, run = _run(case)
    try:
        found = violations(engine, run.org_id, case, run)
    finally:
        remove_tenant(engine, run.org_id)
    assert not run.misses, f"{case.case_id}: the replay missed its cassette at {run.misses[:3]}"
    assert not any(found.values()), f"{case.case_id}: {found}"


def _plant(engine, org: str, case, run, kind: str) -> None:
    """One miss of `kind`, planted into a real run's rows."""
    with engine.begin() as c:
        if kind == "outside memory":
            kept = next(ld for ld in run.landed if ld.outcome == "emitted" and ld.event_id)
            c.execute(text("delete from l2_processing_runs where org_id = :o and event_id = :e"),
                      {"o": org, "e": kept.event_id})
        elif kind == "calendar with no meeting":
            c.execute(text("update graph_nodes set valid_to = now() where org_id = :o "
                           "and node_type = 'meeting' and valid_to is null"), {"o": org})
        elif kind == "archived words readable":
            archived = next(ld.object_id for ld in run.landed if ld.outcome == "archived")
            obj = next(o for o in case.objects if o.object_id == archived)
            node = c.execute(text("select node_id from graph_nodes where org_id = :o "
                                  "and valid_to is null order by node_id limit 1"),
                             {"o": org}).scalar()
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value) values ('fv_plant', 'f_plant', :o, :n, 'planted.note', "
                "cast(:v as jsonb))"),
                {"o": org, "n": node, "v": json.dumps(sorted(_words(obj))[0])})
        elif kind == "screen contact made a person":
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "source_object_id, dedup_key, actor, occurred_at, outcome) values ('evt_plant', "
                ":o, 'con_screen', :s, 'screen_chat_thread', 'scr_plant', 'scr_plant', "
                "cast('{\"email\": \"lena@screen.test\"}' as jsonb), now(), 'emitted')"),
                {"o": org, "s": _SCREEN})
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key) "
                           "values ('n_plant', :o, 'person', 'lena@screen.test')"), {"o": org})


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id, kind", [
    # STEP-07 · F04's introduction is no longer archived — the company brief names Introly, so it
    # is kept and read (W-07); the archive this control plants into is F32's program newsletters.
    ("F04", "outside memory"), ("F32", "archived words readable"),
    ("F12", "calendar with no meeting"), ("F12", "screen contact made a person")])
def test_a_planted_miss_of_each_kind_is_named(case_id, kind):
    """The negative control: each check, handed a real run with one miss planted, names it."""
    _scratch_db()
    from tests.replays.engine_runner import remove_tenant

    case = next(c for c in CASES if c.case_id == case_id)
    engine, run = _run(case)
    try:
        assert not violations(engine, run.org_id, case, run)[kind], "dirty before the plant"
        _plant(engine, run.org_id, case, run, kind)
        found = violations(engine, run.org_id, case, run)
    finally:
        remove_tenant(engine, run.org_id)
    assert found[kind], f"{case_id}: a planted '{kind}' was not named"
