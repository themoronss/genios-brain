"""STEP-03 · a sync counts what it archived, beside what it emitted, dropped and parked.

    pytest tests/capture/test_a_sync_counts_what_it_archived.py -q

`capture/acquire/sync_runner.SyncSummary.archived` (tree `yc2_w27_s03/M21.C4.L-interface.V4.U01`).
`run_sync` counts each result under the field its outcome names — `setattr(summary, outcome, …)` —
so an outcome with no field RAISES and takes the sweep with it. The gate now archives what it used
to drop, so the summary needs the field, the backfill totals must carry it, and the
`sync_completed` analytics event must say it: a sync that archived 33 mails and reported 0 dropped
would read as a mailbox with no noise.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire import sync_runner as S
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

T = datetime(2026, 10, 6, tzinfo=timezone.utc)


class _Junk:
    """The AI filter: confident junk for Boardy's automated nudge, keep for everything else."""

    def classify(self, ctx, prepared):
        if "boardy" in (ctx.event.actor.email or ""):
            return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated matchmaking")
        return RelevanceVerdict(True, 0.9, disposition="keep")


class _Inbox:
    source = "gmail"

    def _objs(self):
        return [
            RawObject("gmail", "email_message", "m1", T, actor_email="priya@realvc.test",
                      raw={"subject": "Term sheet", "snippet": "Can we talk Friday?"}),
            RawObject("gmail", "email_message", "m2", T, actor_email="arjun@customer.test",
                      raw={"subject": "Pricing", "snippet": "Following up on pricing."}),
            RawObject("gmail", "email_message", "m3", T, actor_email="intros@boardy.test",
                      raw={"subject": "Intro: Pankaj", "snippet": "Pankaj asked to meet you.",
                           "headers": {"List-Unsubscribe": "<mailto:u@boardy.test>"}}),
            RawObject("gmail", "email_message", "m4", T, actor_email="hello@boardy.test",
                      raw={"subject": "Boardy here", "snippet": "Want more investor intros?"}),
        ]

    def incremental_changes(self, cursor=None, limit=100, since=None):
        return SourceBatch(objects=self._objs(), next_cursor=None)

    def initial_snapshot(self, cursor=None, limit=100):
        return SourceBatch(objects=self._objs(), next_cursor=None)


def test_every_outcome_the_pipeline_can_produce_has_a_field():
    """The seam that raises: one field per outcome, or a sweep dies on its first archived mail."""
    fields = {f.name for f in dataclasses.fields(S.SyncSummary)}
    outcomes = set(P._OUTCOME_OF_VERB.values()) | {"duplicate"}
    assert outcomes <= fields, outcomes - fields


def test_a_sync_counts_the_archived_apart_from_the_dropped():
    s = S.run_sync(_Inbox(), org_id="o", connection_id="c",
                   repo=InMemorySourceEventRepository(), relevance=_Junk())
    assert (s.scanned, s.emitted, s.archived, s.dropped, s.parked) == (4, 2, 2, 0, 0)
    assert sorted(r.outcome for r in s.results) == ["archived", "archived", "emitted", "emitted"]


def test_a_backfill_carries_the_archived_into_its_totals():
    s = S.backfill_drain(_Inbox(), org_id="o", connection_id="c",
                         repo=InMemorySourceEventRepository(), source="gmail", relevance=_Junk())
    assert (s.emitted, s.archived, s.dropped) == (2, 2, 0)


def test_the_sync_completed_event_says_what_was_archived(monkeypatch):
    from genios_engine.platform import analytics

    sent: list[tuple[str, dict]] = []
    monkeypatch.setattr(analytics, "capture", lambda org, name, props: sent.append((name, props)))
    S.run_sync(_Inbox(), org_id="o", connection_id="c", repo=InMemorySourceEventRepository(),
               relevance=_Junk())
    props = dict(sent)["sync_completed"]
    assert (props["archived"], props["dropped"], props["emitted"]) == (2, 0, 2)
