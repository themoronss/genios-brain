"""P4 group A — hermetic unit tests: the post-pass hook, person resolution, cover copy, readiness
helpers, the open_card action, and the Linear connector against a FAKE Composio executor."""
from __future__ import annotations

import importlib.machinery
import sys
import types
from datetime import date

import pytest

from genios_engine.context.correlation_people import (COUNTERPARTY_WORDS, CommitmentLink,
                                                      PeopleDirectory, Person, scope_pairs_for)
from genios_engine.reason.team import postpass
from genios_engine.reason.team.common import span
from genios_engine.reason.team.cover import Cover
from genios_engine.reason.team.readiness import normalize_task_filter, task_matches, task_state


# ── post-pass hook ─────────────────────────────────────────────────────────────────────────────
def _module(name: str, run) -> None:
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None)
    mod.run = run
    sys.modules[name] = mod


def test_post_passes_skip_missing_log_failures_and_keep_going(monkeypatch, caplog):
    seen = []
    _module("_p4_fake_ok", lambda e, cs, o, *, now: seen.append(("ok", o, now)) or 3)

    def boom(e, cs, o, *, now):
        raise RuntimeError("pass exploded")
    _module("_p4_fake_boom", boom)
    monkeypatch.setattr(postpass, "PASSES", (("boom", "_p4_fake_boom"),
                                             ("missing", "genios_engine.reason.nope.passes"),
                                             ("ok", "_p4_fake_ok")))
    out = postpass.run_post_passes(None, None, "org_1", now="T")
    assert out == {"ok": 3}
    assert seen == [("ok", "org_1", "T")]
    assert "post-pass boom failed" in caplog.text


def test_queue_situation_door_matches_what_emit_writes():
    from genios_engine.deliver.store import SITUATION_CARD_BUILDER
    from genios_engine.reason.team.emit import BUILDER_VERSION
    assert SITUATION_CARD_BUILDER == BUILDER_VERSION


def test_registered_passes_are_team_then_verify():
    # P5 group B appends the meetings pass (prep precompute + follow-ups) after verify.
    assert [n for n, _ in postpass.PASSES] == ["team", "verify", "meetings"]
    assert postpass._present("genios_engine.reason.team.passes")


# ── person resolution ──────────────────────────────────────────────────────────────────────────
def _dir() -> PeopleDirectory:
    persons = [("n_emru", "emru@voltex.test", "Emru"), ("n_ani", "anisha@voltex.test", "Anisha Rao"),
               ("n_sha", "shalini@voltex.test", "Shalini Iyer"),
               ("n_ext", "priya@acme.test", "Priya Shah"), ("n_ext2", "anita@acme.test", "Anita"),
               ("n_dup1", "raj1@acme.test", "Raj"), ("n_dup2", "raj2@acme.test", "Raj")]
    seats = [("s_emru", "emru@voltex.test"), ("s_ani", "anisha@voltex.test"),
             ("s_sha", "shalini@voltex.test")]
    return PeopleDirectory(persons, [("ani", "n_ani")], seats)


def test_resolution_is_exact_or_nothing():
    d = _dir()
    assert d.resolve("Emru").seat_id == "s_emru"                      # exact display name
    assert d.resolve("ANISHA@voltex.test").seat_id == "s_ani"         # email, any case
    assert d.resolve("ani").seat_id == "s_ani"                        # person_name alias
    assert d.resolve("Shalini").seat_id == "s_sha"                    # unique seat first name
    assert d.resolve("s_sha").node_id == "n_sha"                      # seat id
    assert d.resolve("Raj") is None                                   # ambiguous → no link
    assert d.resolve("Priya") is None                                 # first name, not a seat
    assert d.resolve("Priya Shah").seat_id is None                    # external person, no seat
    assert d.resolve("") is None and d.resolve(None) is None


def test_counterparty_words_mirror_assignment_aliases():
    from genios_engine.executive.assignment import SCOPE_ALIASES
    expected = {w for w, paths in SCOPE_ALIASES.items() if "commitment.owed_to" in paths}
    assert set(COUNTERPARTY_WORDS) == expected


def test_scope_pairs_name_the_owner_so_a_cover_can_be_declared_on_a_person():
    link = CommitmentLink("c1", "send the pack", date(2026, 9, 18), "open",
                          Person("n_ani", "anisha@voltex.test", "Anisha Rao", "s_ani"), None,
                          "Emru", {"commitment.owed_to": "Emru", "commitment.text": "send the pack"})
    pairs = set(scope_pairs_for(link))
    assert {("seat", "s_ani"), ("person", "anisha@voltex.test"), ("client", "emru"),
            ("commitment.owed_to", "emru")} <= pairs


# ── copy ───────────────────────────────────────────────────────────────────────────────────────
def test_cover_sentences():
    assert Cover("s", "Shalini", "covers", "covers for Anisha").sentence() == \
        "Proposed cover: Shalini (covers for Anisha)."
    assert Cover(blocked=("Shalini",)).sentence() == "No cover available: Shalini is also away."
    assert Cover(blocked=("A", "B")).sentence() == "No cover available: A, B are also away."
    assert Cover().sentence() == "No cover on record."


def test_span_formats():
    from genios_engine.context.availability import AvailabilityWindow
    w = lambda s, e: AvailabilityWindow("n", None, None, "leave", s, e, None, 2, 0.8, None, "f")
    assert span(w(date(2026, 9, 15), date(2026, 9, 22))) == "15–22 Sep"
    assert span(w(date(2026, 9, 28), date(2026, 10, 3))) == "28 Sep–3 Oct"
    assert span(w(date(2026, 9, 15), None)) == "from 15 Sep"


def test_open_card_action_carries_the_dashboard_url(monkeypatch):
    from genios_engine.platform.config import get_settings
    from genios_engine.reason.team import emit
    monkeypatch.setattr(get_settings(), "dashboard_url", "https://app.genios.test/")
    out = emit._with_open_card([{"id": "assign_cover", "payload": {}},
                                {"id": "open_card", "payload": {"card_id": "stale"}}], "card_1")
    assert out[0]["id"] == "assign_cover"
    assert out[-1] == {"id": "open_card", "payload": {
        "card_id": "card_1", "url": "https://app.genios.test/dashboard/cards?card=card_1"}}
    assert sum(a["id"] == "open_card" for a in out) == 1


# ── readiness helpers ──────────────────────────────────────────────────────────────────────────
def test_task_filter_is_the_pinned_shape():
    assert normalize_task_filter(None) is None and normalize_task_filter({}) is None
    assert normalize_task_filter({"query": "  ISO "}) == {"query": "ISO"}
    assert normalize_task_filter({"query": ""}) is None
    for bad in ({"label": "x"}, {"query": 3}, {"query": "x" * 201}, "ISO"):
        with pytest.raises(ValueError):
            normalize_task_filter(bad)


def test_task_state_and_match():
    assert task_state({"task.state_type": "completed"}) == "done"
    assert task_state({"task.state_type": "canceled", "task.status": "Done"}) == "dropped"
    assert task_state({"task.status": "In Progress"}) == "pending"
    t = {"task.title": "Collect evidence", "task.labels": "ISO-27001, audit", "name": "x"}
    assert task_matches(t, "iso") and not task_matches(t, "soc2")


# ── Linear connector (fake Composio) ───────────────────────────────────────────────────────────
class FakeComposio:
    def __init__(self, pages: list[dict], issue: dict | None = None):
        self.pages, self.issue, self.calls = pages, issue, []

    def execute(self, slug, args):
        self.calls.append((slug, dict(args)))
        if slug.endswith("GET_LINEAR_ISSUE"):
            return {"issue": self.issue} if self.issue else {}
        return self.pages[1] if args.get("after") else self.pages[0]


ISSUE = {"id": "iss_1", "identifier": "OPS-12", "title": "Collect ISO evidence",
         "state": {"name": "Done", "type": "completed"},
         "assignee": {"email": "Anisha@Voltex.test", "name": "Anisha"},
         "project": {"name": "ISO audit"}, "team": {"key": "OPS", "name": "Ops"},
         "labels": {"nodes": [{"name": "iso"}, {"name": "audit"}]},
         "dueDate": "2026-09-18", "completedAt": "2026-09-12T10:00:00Z",
         "updatedAt": "2026-09-12T10:00:00Z"}


def test_linear_poll_flattens_issues_and_pages():
    from genios_engine.capture.connectors.linear import LINEAR_TOOL_SLUGS, ComposioLinearConnector
    fake = FakeComposio([
        {"issues": {"nodes": [ISSUE, {"title": "no id"}],
                    "pageInfo": {"hasNextPage": True, "endCursor": "c2"}}},
        {"issues": {"nodes": [{**ISSUE, "id": "iss_2", "state": {"name": "Todo",
                                                                  "type": "unstarted"}}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None}}}])
    conn = ComposioLinearConnector(api_key="", user_id="", executor=fake)
    first = conn.initial_snapshot(limit=10)
    assert first.next_cursor == "c2" and len(first.objects) == 1
    obj = first.objects[0]
    assert (obj.source, obj.object_type, obj.source_object_id) == ("linear", "issue", "iss_1")
    assert obj.content_version == "2026-09-12T10:00:00Z"
    assert obj.raw["state_type"] == "completed" and obj.raw["state_name"] == "Done"
    assert obj.raw["assignee_email"] == "anisha@voltex.test"
    assert obj.raw["labels"] == "audit, iso" and obj.raw["project"] == "ISO audit"
    second = conn.incremental_changes(cursor=first.next_cursor)
    assert second.next_cursor is None and second.objects[0].raw["state_type"] == "unstarted"
    assert fake.calls[0] == (LINEAR_TOOL_SLUGS["list_issues"], {"first": 10})
    assert fake.calls[1][1]["after"] == "c2"


def test_linear_structured_mapping_writes_task_facts():
    from genios_engine.capture.connectors.linear import ComposioLinearConnector
    from genios_engine.capture.structured.apply import apply_mapping
    from genios_engine.capture.structured.registry import all_mappings
    mapping = next(m for m in all_mappings() if m.mapping_id == "linear.issue.v1")
    obj = ComposioLinearConnector(api_key="", user_id="",
                                  executor=FakeComposio([{}]))._to_raw(ISSUE)
    fields = apply_mapping(mapping, obj.raw)
    assert fields["task.status"] == "Done" and fields["task.state_type"] == "completed"
    assert fields["task.project"] == "ISO audit" and fields["task.labels"] == "audit, iso"
    assert fields["task.assignee"] == "anisha@voltex.test" and "task.title" in fields
    assert mapping.node_type == "task"


def test_linear_webhook_door_matches_the_poll_and_refuses_non_issues():
    from genios_engine.capture.connectors import dispatch
    from genios_engine.capture.connectors.linear import ComposioLinearConnector
    assert dispatch.can_dispatch("linear")
    pushed = dispatch.webhook_to_raw_objects("linear", {"action": "update", "type": "Issue",
                                                        "data": ISSUE})
    polled = ComposioLinearConnector(api_key="", user_id="", executor=FakeComposio([{}]))._to_raw(
        ISSUE)
    assert pushed == (polled,)
    assert dispatch.webhook_to_raw_objects("linear", {"type": "Comment", "data": {"id": "c"}}) == ()
    # id-only push: fetched through the connector, or nothing without credentials
    assert dispatch.webhook_to_raw_objects("linear", {"type": "Issue", "data": {"id": "iss_1"}}) == ()
    fake = FakeComposio([{}], issue=ISSUE)
    got = dispatch.webhook_to_raw_objects(
        "linear", {"type": "Issue", "data": {"id": "iss_1"}},
        connector_factory=lambda: ComposioLinearConnector(api_key="", user_id="", executor=fake))
    assert got == (polled,)
