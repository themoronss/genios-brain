"""Eleven investors on a To line are eleven relationships, not a newsletter.

`_BULK_RECIPIENTS = 10` discarded EVERY recipient of any email addressed to more than ten people
— not the eleventh onward, all of them — so a fundraise update produced no person nodes, no
presence receipts, no `corresponded_with` edges and nothing for the outbound-evidence mirror to
write against. The counterparties the founder most wanted followed up were the ones the graph
never recorded having been written to.

The replacement refuses on what the message SAYS about itself. These tests pin both halves: a wide
human thread keeps everyone, and a genuine list keeps nobody.
"""
import pytest
from sqlalchemy import create_engine, text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from genios_engine.context.graph_store import GraphStore
from .test_event_presence_store import presence_schema
from .test_support_derived_provenance import NOW

OWNER = "owner@gmail.com"


@pytest.fixture
def run(monkeypatch):
    """Drive `process_event` and hand back the recipient nodes it established."""
    def _run(recipients, *, canon_meta=None, sender=OWNER):
        engine = create_engine("sqlite://")
        store = object.__new__(GraphStore)
        store._engine = engine
        with engine.begin() as c:
            presence_schema(c)
        for method in ("write_fact", "write_edge", "write_change"):
            monkeypatch.setattr(store, method, lambda *a, **kw: None)
        monkeypatch.setattr(store, "bump_version", lambda *a: 1)
        monkeypatch.setattr(store, "find_or_create_node", lambda *a, **kw: kw["canonical_key"])
        monkeypatch.setattr(pipeline, "correlate_event", lambda *a, **kw: [])
        monkeypatch.setattr(pipeline, "close_loops_for_reply", lambda *a, **kw: None)
        monkeypatch.setattr(pipeline, "record_ask", lambda *a, **kw: "loop")
        monkeypatch.setattr(pipeline, "resolve_canon_mention", lambda *a, **kw: None)
        body = "Sharing our Q3 update ahead of the round."
        pipeline.process_event(
            org_id="o", event_id="e", source="gmail", content=body,
            sender_email=sender, recipient_emails=list(recipients),
            internal_emails=frozenset({OWNER}), occurred_at=NOW,
            llm=None, store=store, is_inbound=False, canon_meta=canon_meta,
            qualified_extraction=Extraction(
                ok=True, relevance=0.9, noise_type="none", domains=[], entity_mentions=[],
                fact_candidates=[], commitments=[], questions=[], observations=[]))
        with engine.connect() as c:
            # The SENDER's own node is excluded, not a hardcoded owner: a message from
            # `noreply@…` still establishes its sender, correctly, and counting that as a
            # recipient would have this test pass for the wrong reason.
            return {r[0] for r in c.execute(text(
                "select distinct subject_node_id from graph_observations "
                "where subject_node_id != :sender"), {"sender": sender}).all()}
    return _run


def _investors(n: int) -> list[str]:
    return [f"partner{i}@fund{i}.com" for i in range(n)]


# ── the defect ───────────────────────────────────────────────────────────────────────────────

def test_eleven_investors_all_reach_the_graph(run) -> None:
    """The exact shape that produced nothing: one more recipient than the old cap allowed."""
    assert run(_investors(11)) == set(_investors(11))


@pytest.mark.parametrize("n", [1, 9, 10, 11, 25])
def test_a_human_thread_keeps_everyone_at_any_width(run, n: int) -> None:
    """There is no cliff any more. Width is not evidence of anything."""
    assert run(_investors(n)) == set(_investors(n))


def test_the_old_cliff_is_gone(run) -> None:
    """Ten worked and eleven produced nothing. The two must now agree."""
    assert len(run(_investors(10))) == 10
    assert len(run(_investors(11))) == 11


# ── the judgement that replaced it ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("headers", [
    {"List-Unsubscribe": "<https://esp.example/u/abc>"},
    {"List-Id": "<announce.example.com>"},
    {"Precedence": "bulk"},
    {"Auto-Submitted": "auto-generated"},
])
def test_a_genuine_mailing_list_establishes_nobody(run, headers) -> None:
    """A list's subscribers are not this tenant's relationships, at any size."""
    assert run(_investors(11), canon_meta={"headers": headers}) == set()


def test_a_machine_sender_establishes_nobody(run) -> None:
    assert run(_investors(11), sender="noreply@esp.example") == set()


def test_a_small_list_is_still_a_list(run) -> None:
    """Symmetry with the test above it: the judgement does not consult the count in EITHER
    direction, so three subscribers are skipped exactly as eleven are."""
    assert run(_investors(3), canon_meta={"headers": {"List-Id": "<x.example>"}}) == set()


def test_a_payload_with_no_headers_keeps_its_recipients(run) -> None:
    """The anti-over-gating law at the call site: a missing header set is not evidence of a
    list, so the recipients survive. Only a positive marker discards them."""
    assert len(run(_investors(11), canon_meta=None)) == 11
    assert len(run(_investors(11), canon_meta={})) == 11
    assert len(run(_investors(11), canon_meta={"headers": {}})) == 11
