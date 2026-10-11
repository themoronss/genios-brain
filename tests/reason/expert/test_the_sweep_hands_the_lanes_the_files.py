"""STEP-12 M33 · the sweep hands each lane what it needs — the pass's people to the compiled lane, and
what the files decided on the live lane explain to every pack's rules.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_the_sweep_hands_the_lanes_the_files.py -q

Tree `yc2_w27_s12` M33.C1.L-integration.V3.U15 (`reason/runner.run_all`), `03` F173. The expert pass names
each covered file and its people; the compiled lane decides each covered file and reports the ones it
decided on the LIVE lane (`decided`); the sweep reads each of those files' reviews once into a
`reason/expert/cover.Covers` and hands it to every pack's `run` (`explained`), so a pack rule its file's
review decided stands down (M33.C1.L-integration.V0.U14). A file decided in shadow, or not at all, stands
nothing down; a read that fails explains nothing and the sweep goes on.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason import runner
from genios_engine.reason.expert import store as R

pytestmark = pytest.mark.pg

ORG = "m33u15_sweep"
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
FILE, PERSON = "m33u15_acme", "m33u15_ada"


def _review_payload() -> dict:
    return {
        "facts": [{"claim": "Ada asked for the pricing sheet", "evidence": ["evt_m33u15_ask"]}],
        "frames": {"primary": "a buyer before a pricing call", "rivals": ["a polite check-in"]},
        "expected_vs_actual": {"stage": None, "expected": "the sheet", "actual": "nothing sent"},
        "scenarios": {"do_nothing": "the call goes ahead blind", "act": "the call starts informed",
                      "best": "a pilot", "worst": "a pass", "signals_to_watch": ["a reply"]},
        "appraisal": {"stakes": "medium", "urgency": "high", "reversibility": "reversible",
                      "reasons": ["the call is tomorrow"]},
        "mode": "act",
        "next_move": {"who": "the founder", "what": "Send Ada the pricing sheet", "for_whom": "Ada",
                      "by_when": None},
        "alternative": "walk her through it on the call", "wait_or_stop": "ask once more",
        "done_when": "Ada has the sheet", "draft": "Hi Ada, the pricing sheet is attached."}


def _seed_org(store) -> None:
    from sqlalchemy import text
    with store.engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": ORG}
        for r in reqd:
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else f"{ORG}@x.test" if "email" in r.column_name else ORG)
        conn.execute(text(f"insert into orgs ({','.join(cols)}) values ({','.join(ph)}) "
                          "on conflict do nothing"), vals)


@pytest.fixture
def stored(pg_store):
    from sqlalchemy import text

    from genios_engine.api.account_routes import _wipe
    _seed_org(pg_store)
    with pg_store.engine.begin() as c:
        _wipe(c, ORG)
        c.execute(text("delete from expert_reviews where org_id = :o"), {"o": ORG})
        assert R.write_review(c, org_id=ORG, file_id=FILE, fingerprint="ffp-m33u15-acme",
                              model="claude-sonnet-5", prompt_version="expert-review.v2",
                              dossier_digest="d" * 64, status=R.VALID, reason=None,
                              review=ExpertReview.from_mapping(_review_payload()), input_tokens=1,
                              output_tokens=1, cost_micro_usd=1, at=NOW,
                              inputs={"events": ["evt_m33u15_ask"], "booked": ["evt_m33u15_call"]},
                              triggers=[{"kind": "first_look", "says": "never judged"}])
    try:
        yield pg_store
    finally:
        with pg_store.engine.begin() as c:
            _wipe(c, ORG)
            c.execute(text("delete from expert_reviews where org_id = :o"), {"o": ORG})


def _sweep(store, monkeypatch, *, receipt, decided, compile_raises=False, read_raises=False):
    """`run_all` with the three lanes recorded: what the compiled lane and each pack's run were handed."""
    from genios_engine.reason import domain_shadow
    from genios_engine.reason.expert import cover, sweep
    handed: dict = {"runs": []}

    def _pass(**kw):
        return receipt

    def _compile(**kw):
        handed["compiled"] = kw
        if compile_raises:
            raise RuntimeError("the compiled lane broke")
        return {"decided": decided}

    def _run(**kw):
        handed["runs"].append(kw)
        return {"nodes": 0, "outcomes": {}}
    monkeypatch.setattr(sweep, "expert_pass", _pass)
    monkeypatch.setattr(domain_shadow, "shadow_compile", _compile)
    monkeypatch.setattr(runner, "run", _run)
    monkeypatch.setattr(runner, "l1_seam_enabled", lambda engine, org_id: True)
    if read_raises:
        monkeypatch.setattr(cover, "covers_for", lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("the review store is down")))
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    registry = make_registry(store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, ORG)
    runner.run_all(org_id=ORG, store=store, eval_time=NOW, registry=registry)
    return handed


RECEIPT = {"covered": {FILE: "ffp-m33u15-acme"}, "people": {FILE: [PERSON]}}


def test_the_compiled_lane_is_handed_the_files_and_their_people(stored, monkeypatch):
    handed = _sweep(stored, monkeypatch, receipt=RECEIPT, decided={})
    assert handed["compiled"]["covered"] == RECEIPT["covered"]
    assert handed["compiled"]["people"] == RECEIPT["people"]


def test_every_packs_run_is_handed_what_the_live_decisions_explain(stored, monkeypatch):
    handed = _sweep(stored, monkeypatch, receipt=RECEIPT, decided={FILE: "ffp-m33u15-acme"})
    assert handed["runs"], "no pack ran"
    for kw in handed["runs"]:
        [cover] = list(kw["explained"])
        assert (cover.file_id, cover.fingerprint) == (FILE, "ffp-m33u15-acme")
        assert cover.members == frozenset({FILE, PERSON})
        assert cover.seen == frozenset({"evt_m33u15_ask", "evt_m33u15_call"})


def test_a_file_decided_in_shadow_or_not_at_all_stands_nothing_down(stored, monkeypatch):
    handed = _sweep(stored, monkeypatch, receipt=RECEIPT, decided={})
    assert handed["runs"] and all(kw["explained"] is None for kw in handed["runs"])


def test_a_compiled_lane_that_failed_stands_nothing_down(stored, monkeypatch):
    handed = _sweep(stored, monkeypatch, receipt=RECEIPT, decided={FILE: "ffp-m33u15-acme"},
                    compile_raises=True)
    assert handed["runs"] and all(kw["explained"] is None for kw in handed["runs"])


def test_a_read_that_failed_explains_nothing_and_the_sweep_goes_on(stored, monkeypatch):
    handed = _sweep(stored, monkeypatch, receipt=RECEIPT, decided={FILE: "ffp-m33u15-acme"},
                    read_raises=True)
    assert handed["runs"] and all(kw["explained"] is None for kw in handed["runs"])


def test_a_decided_file_whose_review_is_gone_explains_nothing(stored, monkeypatch):
    handed = _sweep(stored, monkeypatch, receipt=RECEIPT, decided={FILE: "ffp-m33u15-other"})
    assert handed["runs"] and all(kw["explained"] is None for kw in handed["runs"])


def test_a_pass_that_failed_hands_no_one(stored, monkeypatch):
    handed = _sweep(stored, monkeypatch, receipt={"error": True}, decided={})
    assert handed["compiled"]["covered"] == {} and handed["compiled"]["people"] == {}
