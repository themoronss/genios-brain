"""A small shared world for the GeniOS-008 L2 tests: one file (the STEP-12 fixture's Meridian file), its
bundle's signals, a snapshot, a history, the tools, and an answer the model could give."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.capture.esqe.bundle_store import StoredBundle
from genios_engine.contracts.reasoning_result import CONFIDENCE_DIMENSIONS, HistoricalCase, HistoricalContext
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.l2.dossier import build_l2_dossier
from genios_engine.reason.l2.inputs import L2Signal, subjects_for
from genios_engine.reason.l2.plan import compile_plan
from genios_engine.reason.l2.prompt import depth_note
from genios_engine.reason.l2.snapshot import Snapshot, SnapshotNode
from genios_engine.reason.l2.tools import measured_inputs, run_tools
from tests.reason.expert.test_the_dossier import FILE, NOW, _parts, _review

ORG = "org_x"
T0 = NOW - timedelta(hours=30)


def signal(sid, event="evt_005", *, thread="th_1", direction="inbound", ball="us", due=None, quotes=(),
           at=T0, importance=6000):
    return L2Signal(signal_id=sid, event_id=event, signal_type="commitment_due", subject_key="meridian",
                    occurred_at=at, due_at=due, thread_key=thread, direction=direction, ball_in_court=ball,
                    importance_bp=importance, state="active", quotes=tuple(quotes))


def bundle(bid, sids, *, at=None, subject="meridian", coverage=None, unresolved=()):
    return StoredBundle(bundle_id=bid, org_id=ORG, trace_id="tr", signal_ids=tuple(sids), subject_key=subject,
                        coverage=coverage if coverage is not None else
                        {"sources": [{"source": "gmail", "completeness_bp": 9000}]},
                        unresolved=tuple(unresolved), created_at=at or NOW - timedelta(hours=1))


def file_subject():
    sigs = {"s1": signal("s1", quotes=("Thanks Kunal, I will book it again tonight",)),
            "s2": signal("s2", event="evt_003", direction="inbound", at=T0 - timedelta(hours=40))}
    return subjects_for([bundle("b1", ["s1", "s2"])], sigs, {"evt_005": FILE, "evt_003": FILE})[0]


SNAP = Snapshot(seeds=(FILE,), nodes=(SnapshotNode(FILE, "company", "Meridian Ventures"),
                                      SnapshotNode("node_kunal", "person", "Kunal")),
                edges=(("works_at", "node_kunal", FILE),), revision=41, truncated=False)
HISTORY = HistoricalContext(cases=(HistoricalCase(case_id="case:node_other", subject="Other Fund",
                                                  work_kind="investor", outcome="investor_followup resolved",
                                                  last_touch=NOW - timedelta(days=20),
                                                  summary="the move was theirs"),))


def file_world():
    parts = _parts()
    subject = file_subject()
    tools = run_tools(subject.signals, eval_time=NOW, file=parts.file)
    plan = compile_plan(tools=measured_inputs(tools), file_id=FILE, unresolved=(), truncated=False, situations=1,
                        importance_bp=6000)
    dossier = build_l2_dossier(org_id=ORG, subject=subject, as_of=NOW, snapshot=SNAP, history=HISTORY, tools=tools,
                               file_dossier=D.build_dossier(parts), depth_note=depth_note(plan))
    return parts, subject, tools, plan, dossier


def answer(**over):
    """A whole answer: the STEP-12 fixture review, plus its judgment half."""
    raw = _review("evt_005", "Hi Kunal, booking it now.").as_mapping()
    raw.update({
        "intervention_mode": "prepare_decision",
        "confidence": {d: {"level": "high", "reason": "the mail says so", "evidence": ["evt_005"]}
                       for d in CONFIDENCE_DIMENSIONS},
        "options": [{"option": "book the call tonight", "benefit": "keeps it warm", "downside": "none",
                     "reversibility": "reversible", "affects": "Kunal", "would_change": "a decline"}],
        "history_used": [{"case": "Other Fund", "applies": False, "why": "the move was theirs there",
                          "based_on": ["case:node_other"]}],
        "second_order": ["the fund reads the delay as interest cooling"],
        "decision_need": {"needed": False},
        "proposed_mutations": [{"op": "create", "situation": "first call with Meridian", "why": "booking is open",
                                "evidence": ["sig:s1"]}],
        "evidence_needs": [{"question": "did we already send a calendar invite from another address?",
                            "why_it_matters": "if we did, the move is theirs", "decision_changing": True,
                            "subject_ref": "thread:th_1", "acceptable_sources": ["gmail"],
                            "unacceptable_sources": []}],
        "coverage_limitations": ["the calendar was not read"],
        "open_conflict": None, "deeper": None})
    raw.update(over)
    return raw


def aware(at: datetime) -> datetime:
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)
