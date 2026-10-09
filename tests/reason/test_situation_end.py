"""STEP-06 · every active situation names exactly one end — one reader, from the ledgers that made it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_situation_end.py -q

Tree `yc2_w27_s06 · M24.C2.L-logic.V2.U02`. 126 of the golden set's 227 active situations had no
record anywhere of how they ended (`speedrun008/YC-II W27/` STEP-06 §8.1, 03 F77): every shadow and
unroutable one. `reason/situation_end` names one end for every situation — from the tenant's
activation, the admission ledger, `situation_outcomes`, the change gate's rows and the open cards —
and `unrecorded` for a live one nothing explains, which is what must be zero.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

ORG = "sit_end_org"
AT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)

#: situation id → (domain, type)
SITUATIONS = {
    "s_fund": ("fundraising", "investor_relationship"),
    # STEP-11 (2026-10-09): `fundraising` maps to the Founder Office now, so `general` carries the
    # no-corpus end — a domain no corpus claims.
    "s_general": ("general", "relationship"),
    "s_sales": ("sales", "pipeline_period_review"),
    "s_held": ("admin", "awaiting_response"),
    "s_rejected": ("admin", "account_admin"),
    "s_stopped": ("admin", "meeting_follow_through"),
    "s_decided": ("admin", "reply_owed"),
    "s_old_decided": ("admin", "admin_contact"),
    "s_carded": ("admin", "account_admin"),
    "s_never": ("admin", "condition_in_review"),
    "s_admit_only": ("admin", "dependency_stated"),
}


def _reset(eng):
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        for table in ("context_situations", "reasoning_fingerprints"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from genios_engine.platform.l3_activation import activate
    eng = create_engine(url)
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'se@example.test')"),
                  {"o": ORG})
        for sid, (domain, kind) in SITUATIONS.items():
            c.execute(text("insert into context_situations (situation_id, org_id, correlation_id, "
                           "anchor_node_id, situation_type, domain) "
                           "values (:s, :o, :c, 'n1', :t, :d)"),
                      {"s": sid, "o": ORG, "c": f"corr_{sid}", "t": kind, "d": domain})

        def admission(sid, outcome, reasons=(), *, decision=None, at=AT):
            c.execute(text(
                "insert into situation_admission_decisions (decision_id, org_id, situation_id, "
                "candidate_hash, outcome, reasons, candidate, schema_version, decided_at, "
                "reevaluate_after) values (:d, :o, :s, :h, :out, cast(:r as jsonb), "
                "cast('{}' as jsonb), 'v1', :at, :retry)"),
                {"d": decision or f"dec_{sid}", "o": ORG, "s": sid, "h": f"h_{sid}_{outcome}",
                 "out": outcome, "r": __import__("json").dumps(list(reasons)), "at": at,
                 "retry": at + timedelta(hours=1) if outcome == "hold" else None})

        admission("s_held", "hold", ["verified_evidence_required"])
        admission("s_rejected", "reject", ["identity_review_required"])
        for sid in ("s_stopped", "s_decided", "s_old_decided", "s_carded", "s_admit_only"):
            admission(sid, "admit")
        # an older admission that was then held must not hide the latest one
        admission("s_decided", "hold", ["qes_required"], decision="dec_s_decided_old",
                  at=AT - timedelta(days=1))
        for sid, outcome, reason in [("s_stopped", "no_route", "predicate_rejected"),
                                     ("s_decided", "decided", "emitted")]:
            c.execute(text("insert into situation_outcomes (org_id, decision_id, situation_id, "
                           "outcome, reason, recorded_at, last_seen_at) "
                           "values (:o, :d, :s, :out, :r, :at, :at)"),
                      {"o": ORG, "d": f"dec_{sid}", "s": sid, "out": outcome, "r": reason,
                       "at": AT})
        c.execute(text("insert into reasoning_fingerprints (org_id, subject_key, lane, fingerprint, "
                       "outcome, decided_at, last_checked_at) values "
                       "(:o, 's_old_decided|expertise.admin_contact', 'compiled', 'fp', 'standing', "
                       " :at, :at)"), {"o": ORG, "at": AT})
        c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
                       "reason_code, eval_time, situation_id) "
                       "values ('sig_carded', :o, 'r1', 'n1', 50, 'rc', :at, 's_carded')"),
                  {"o": ORG, "at": AT})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, why, actions, artifact, state, expires_at) values "
            "('card_1', 'sig_carded', :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), "
            "cast('[]' as jsonb), cast('{}' as jsonb), 'queued', :exp)"),
            {"o": ORG, "exp": AT + timedelta(days=3)})
    activate(eng, ORG, domain="admin", by="test_situation_end")
    yield eng
    _reset(eng)


def test_every_active_situation_names_exactly_one_end(engine):
    from genios_engine.reason import situation_end as se
    with engine.connect() as c:
        ends = {e.situation_id: (e.end, e.detail) for e in se.situation_ends(c, ORG)}
    assert ends == {
        # a tenant with Admin alone: the Founder Office exists and is not switched on (STEP-11, D2)
        "s_fund": (se.NOT_LIVE, ("founder_office",)),
        "s_general": (se.NO_CORPUS, ("general",)),
        "s_sales": (se.NOT_LIVE, ("sales",)),
        "s_held": (se.HELD, ("verified_evidence_required",)),
        "s_rejected": (se.REJECTED, ("identity_review_required",)),
        "s_stopped": (se.STOPPED, ("no_route", "predicate_rejected")),
        "s_decided": (se.DECIDED, ("emitted",)),
        "s_old_decided": (se.DECIDED, ("standing",)),
        "s_carded": (se.CARDED, ("card_1",)),
        "s_never": (se.UNRECORDED, ()),
        "s_admit_only": (se.UNRECORDED, ()),
    }


def test_a_situation_that_is_no_longer_active_is_not_asked(engine):
    from genios_engine.reason import situation_end as se
    with engine.begin() as c:
        c.execute(text("update context_situations set status = 'resolved' "
                       "where org_id = :o and situation_id = 's_never'"), {"o": ORG})
    with engine.connect() as c:
        assert "s_never" not in {e.situation_id for e in se.situation_ends(c, ORG)}


def test_the_vocabulary_is_closed():
    from genios_engine.reason import situation_end as se
    assert se.ENDS == {se.NO_CORPUS, se.NOT_LIVE, se.HELD, se.REJECTED, se.CARDED, se.DECIDED,
                       se.STOPPED, se.UNRECORDED}
