"""A fundraise between four people in one mailbox is not one source of evidence.

`evidence_score` gained `voice_count` for a stated reason: `source_count` is
`count(distinct se.source)`, so a raise that lives entirely in Gmail scores 1 for ever, however
many people are in it, corroboration stops at 25 of its available 60, evidence caps at 65 — and
`compute_confidence` takes the MINIMUM, so 65 becomes the ceiling on the whole situation.

The argument reached `situations.py` and stopped there. The six readings dispatched from
`READINGS`, which produce most of the situations on a correspondence-only tenant, went on calling
`evidence_score(event_count=..., source_count=...)` with no third argument — so every card they
produce was capped at 65 no matter how many parties were in the thread.

Three stats builders feed that call and only one is exercised in the common case: `_refined_stats`
tries `_event_counts_sql` FIRST and falls back to `_direct_event_counts` only when it returns None.
Fixing the fallback alone would have left the fix almost never firing, which is why both are here.
"""
import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import _direct_event_counts, _event_counts_sql
from genios_engine.context.situations import evidence_score

ORG = "o"
WHEN = "2026-08-11T12:00:00+00:00"


def _graph(parties):
    """One node, one Gmail source, one event per party."""
    e = create_engine("sqlite://")
    with e.begin() as c:
        c.execute(text("create table graph_nodes (org_id text, node_id text, node_type text, "
                       "display_name text, canonical_key text, valid_to text)"))
        c.execute(text("create table graph_edges (org_id text, edge_type text, "
                       "from_node_id text, to_node_id text, valid_to text)"))
        c.execute(text("create table graph_facts (org_id text, subject_node_id text, "
                       "fact_version_id text, field text, value text, status text, "
                       "valid_to text)"))
        c.execute(text("create table graph_observations (org_id text, observation_id text, "
                       "subject_node_id text, status text, occurred_at timestamp)"))
        c.execute(text("create table graph_source_refs (org_id text, observation_id text, "
                       "fact_version_id text, event_id text, source text)"))
        c.execute(text("create table source_events (org_id text, event_id text, source text, "
                       "occurred_at timestamp, actor text)"))
        c.execute(text("insert into graph_nodes values (:o,'n1','person','Harshita','h@x.com',"
                       "null)"), {"o": ORG})
        for i, party in enumerate(parties):
            c.execute(text("insert into graph_observations values (:o,:ob,'n1','active',:at)"),
                      {"o": ORG, "ob": f"obs{i}", "at": WHEN})
            c.execute(text("insert into graph_source_refs values (:o,:ob,null,:e,'gmail')"),
                      {"o": ORG, "ob": f"obs{i}", "e": f"e{i}"})
            c.execute(text("insert into source_events (org_id,event_id,source,occurred_at,actor) "
                           "values (:o,:e,'gmail',:at,:a)"),
                      {"o": ORG, "e": f"e{i}", "at": WHEN,
                       "a": '{"email": "%s"}' % party})
    return e


def _counts(e, sql):
    with e.connect() as c:
        rows = c.execute(text(sql), {"o": ORG, "now": "2099-01-01T00:00:00+00:00"}).all()
    return {r.node_id: r for r in rows}


# ── both stats paths count parties ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("build", [_event_counts_sql, _direct_event_counts],
                         ids=["primary", "fallback"])
def test_distinct_parties_are_counted_on_both_paths(build) -> None:
    """`_refined_stats` tries the primary first; the fallback only runs when it returns None.
    A fix to one of them alone is a fix that mostly does not run."""
    e = _graph(["harshita@peakxv.com", "vidushi@peakxv.com", "owner@gmail.com"])
    assert _counts(e, build("sqlite"))["n1"].voices == 3


@pytest.mark.parametrize("build", [_event_counts_sql, _direct_event_counts],
                         ids=["primary", "fallback"])
def test_twenty_messages_from_one_person_are_still_one_party(build) -> None:
    """The principle the whole axis rests on: repetition within one account is not
    corroboration, and the party count must not become a second volume count."""
    e = _graph(["harshita@peakxv.com"] * 20)
    counts = _counts(e, build("sqlite"))["n1"]
    assert counts.voices == 1
    assert counts.events == 20


@pytest.mark.parametrize("build", [_event_counts_sql, _direct_event_counts],
                         ids=["primary", "fallback"])
def test_the_party_is_matched_on_the_email_not_the_whole_actor(build) -> None:
    """Comparing the actor blob is what once produced a "gmail and calendar share nobody"
    reading: two records of one person differ in every key except the address."""
    e = create_engine("sqlite://")
    with e.begin() as c:
        for stmt in (
            "create table graph_nodes (org_id text, node_id text, node_type text, "
            "display_name text, canonical_key text, valid_to text)",
            "create table graph_edges (org_id text, edge_type text, from_node_id text, "
            "to_node_id text, valid_to text)",
            "create table graph_facts (org_id text, subject_node_id text, fact_version_id text, "
            "field text, value text, status text, valid_to text)",
            "create table graph_observations (org_id text, observation_id text, "
            "subject_node_id text, status text, occurred_at timestamp)",
            "create table graph_source_refs (org_id text, observation_id text, "
            "fact_version_id text, event_id text, source text)",
            "create table source_events (org_id text, event_id text, source text, "
            "occurred_at timestamp, actor text)",
            "insert into graph_nodes values ('o','n1','person','H','h@x.com',null)",
        ):
            c.execute(text(stmt))
        for i, actor in enumerate((
                '{"email": "harshita@peakxv.com", "name": "Harshita"}',
                '{"email": "HARSHITA@peakxv.com", "name": "Harshita Kaul", "id": "9"}')):
            c.execute(text("insert into graph_observations values ('o',:ob,'n1','active',:at)"),
                      {"ob": f"obs{i}", "at": WHEN})
            c.execute(text("insert into graph_source_refs values ('o',:ob,null,:e,'gmail')"),
                      {"ob": f"obs{i}", "e": f"e{i}"})
            c.execute(text("insert into source_events (org_id,event_id,source,occurred_at,actor) "
                           "values ('o',:e,'gmail',:at,:a)"),
                      {"e": f"e{i}", "at": WHEN, "a": actor})
    assert _counts(e, build("sqlite"))["n1"].voices == 1, "one person, two records"


# ── and what that does to the ceiling ────────────────────────────────────────────────────────

def test_the_single_source_ceiling_lifts_once_parties_are_counted() -> None:
    """The whole point, in arithmetic. One connected tool, five events, four people."""
    capped = evidence_score(event_count=5, source_count=1, voice_count=0)
    counted = evidence_score(event_count=5, source_count=1, voice_count=4)
    assert capped == 65, "what every state reading scored before this"
    assert counted > capped
    assert counted == 100


def test_one_party_scores_exactly_what_zero_did() -> None:
    """`max(0, voices - 1)` — a lone voice corroborates nothing, so a reading that cannot count
    parties is not penalised against one that counts a single party."""
    assert (evidence_score(event_count=5, source_count=1, voice_count=1)
            == evidence_score(event_count=5, source_count=1, voice_count=0))
