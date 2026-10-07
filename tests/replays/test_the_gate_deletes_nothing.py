"""STEP-03 · the acceptance: on every founder case the gate deletes nothing, and the board does not move.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_the_gate_deletes_nothing.py -q

Tree `yc2_w27_s03/M21.C5.L-integration.V5.U03`. Every founder case is replayed from its cassette
through the REAL chain (`engine_runner.run_case`, the recorded model — no spend), and the tenant's
rows are read before it is removed. Measured BEFORE STEP-03 on the same replay (a worktree at
`4d1ad2fe`, the gate as it was): of 86 mail objects, 51 emitted, 2 parked, and 33 DROPPED with their
content gone — N-02 16, N-03 8, N-06 4, llm_junk 4, N-07 1 (`speedrun008/YC-II W27/` STEP-03 §8.1;
`DROPPED_BEFORE` below, object by object). After it, per case:

  * no object is dropped;
  * every object the gate dropped before is ARCHIVED, with the same code — and nothing else is;
  * every archived object carries `attention = archive` and its code and its encrypted payload —
    and NO prepared text: every reader of a message's words selects by correlation membership, and
    on F37 the resolution model read an archived introduction the first time this ran;
  * the case is marked exactly as before — verdict, where it was lost, and how many cards it
    showed (`BOARD_BEFORE`): STEP-03 changes what the gate keeps, not what the founder sees. So no
    must-abstain case gains a card, and an archived must-detect mail is still lost at the gate.

`scripts/golden_score.py --assert-recorded` is the board-level half, run beside this file.

RESTATED BY STEP-04 (`yc2_w27_s04 · M22.C5.L-integration.V3.U04`). The runner now creates the tenant
as signup does — with its owner seat — and declares the case's own addresses and domains; re-run
2026-10-06 under it, with every STEP-04 change, no case moved: `BOARD_BEFORE` stands as measured. The
four cases STEP-04 added (`ADDED_AFTER`) have no "before STEP-03" — the gate's promise is held on
them too (nothing dropped, an archive carries no prepared text), and their marking is the board's.

RESTATED BY STEP-05 (`yc2_w27_s05 · M23.C5.L-integration.V4.U02`). STEP-05 gives every kept event a
road into memory, so thirteen cases moved — every one of them from "lost before memory" or "not
exercised" — and each is held to its new marking in `MOVED_AFTER`, by the step that moved it.
`BOARD_BEFORE` stays the measurement it was. The gate's own promise did not move on any case: nothing
dropped, every archive the same, and no archive with prepared text.

RESTATED BY STEP-07 (`yc2_w27_s07 · M25.C7.L-integration.V5.U02`). The golden founder now holds the
company brief STEP-07 §4 would draft, and a sender it names — the intro agent's address, a watchlist
domain — is KEPT and read (W-07). 21 of the 33 objects the gate archived are such mail
(`KEPT_BY_THE_BRIEF`): StartupSetu's and DigiVault's notices (F01, F02), every Introly mail (F03–F09,
F37), the State Startup Mission's four (F23) and Lakshya's community mail (F32). Each is now emitted,
and the other twelve are archived exactly as before. Four cases moved — F01, F02, F03 and F09, from
lost at the gate to lost in REASONING (`MOVED_AFTER`): their mail is read now, and no situation it
forms reaches a card yet (STEP-09's workstreams, STEP-12's expert pass).
"""
from __future__ import annotations

import collections
import os

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.marking import judge

CASES = load_cases()

#: Measured 2026-10-06 at `4d1ad2fe`, the gate before STEP-03: each object it DROPPED, by provider
#: id, and the code that dropped it. 33 objects in 18 cases.
DROPPED_BEFORE: dict[str, dict[str, str]] = {
    "F01": {"f01-status": "N-06"},
    "F02": {"f02-ask": "N-06", "f02-granted": "N-03", "f02-locker": "N-03", "f02-received": "llm_junk"},
    "F03": {"f03-intro": "N-02", "f03-nudge1": "N-02", "f03-nudge2": "N-02"},
    "F04": {"f04-intro": "N-02"},
    "F05": {"f05-intro": "N-02"},
    "F06": {"f06-intro": "N-02"},
    "F07": {"f07-intro": "N-02"},
    "F08": {"f08-omar": "N-02", "f08-simon": "N-02"},
    "F09": {"f09-ask": "N-02"},
    "F16": {"f16-bounce": "N-03"},
    "F18": {"f18-round": "llm_junk"},
    "F21": {"f21-one": "llm_junk", "f21-two": "llm_junk"},
    "F22": {"f22-grant": "N-02"},
    "F23": {"f23-a": "N-03", "f23-b": "N-03", "f23-c": "N-03", "f23-d": "N-03"},
    "F32": {"f32-forum": "N-06", "f32-nirmaan": "N-02", "f32-social": "N-02"},
    "F33": {"f33-promo": "N-06", "f33-receipt": "N-03", "f33-update": "N-02"},
    "F34": {"f34-fellows": "N-02", "f34-match": "N-07"},
    "F37": {"f37-intro": "N-02"},
}

#: STEP-07: the objects above that a sender the golden founder's company brief names now KEEPS —
#: emitted, attention `deep`, reason W-07 (`test_the_company_brief_is_in_every_prompt` holds the tier).
KEPT_BY_THE_BRIEF: dict[str, tuple[str, ...]] = {
    "F01": ("f01-status",),
    "F02": ("f02-ask", "f02-granted", "f02-locker", "f02-received"),
    "F03": ("f03-intro", "f03-nudge1", "f03-nudge2"),
    "F04": ("f04-intro",),
    "F05": ("f05-intro",),
    "F06": ("f06-intro",),
    "F07": ("f07-intro",),
    "F08": ("f08-omar", "f08-simon"),
    "F09": ("f09-ask",),
    "F23": ("f23-a", "f23-b", "f23-c", "f23-d"),
    "F32": ("f32-social",),
    "F37": ("f37-intro",),
}

#: Cases added after STEP-03 measured the set, each by the step that added it.
ADDED_AFTER: dict[str, str] = {"F41": "STEP-04", "F42": "STEP-04", "F43": "STEP-04",
                               "F44": "STEP-04"}

#: Cases a later step moved, with their marking after it — (step, (kind, verdict, lost_at, cards)).
#: STEP-05: a mail below the floor, the founder's own sent mail and an archive now enter memory.
MOVED_AFTER: dict[str, tuple[str, tuple[str, str, str | None, int]]] = {
    "F04": ("STEP-05", ("must_detect", "pass", None, 1)),
    "F05": ("STEP-05", ("must_detect", "pass", None, 1)),
    "F06": ("STEP-05", ("must_detect", "pass", None, 1)),
    "F07": ("STEP-05", ("must_detect", "fail", "reasoning", 2)),
    "F10": ("STEP-05", ("must_detect", "pass", None, 1)),
    "F11": ("STEP-05", ("must_detect", "fail", "reasoning", 0)),
    "F19": ("STEP-05", ("must_detect", "fail", "reasoning", 2)),
    "F24": ("STEP-05", ("must_detect", "fail", "reasoning", 1)),
    "F26": ("STEP-05", ("must_detect", "pass", None, 1)),
    "F31": ("STEP-05", ("must_abstain", "pass", None, 1)),
    "F36": ("STEP-05", ("must_abstain", "pass", None, 0)),
    "F38": ("STEP-05", ("must_abstain", "pass", None, 0)),
    "F39": ("STEP-05", ("must_abstain", "pass", None, 0)),
    # STEP-07: the brief keeps the portal's, the locker's and the intro agent's mail, and it is
    # read — but no situation it forms reaches a card yet.
    "F01": ("STEP-07", ("must_detect", "fail", "reasoning", 0)),
    "F02": ("STEP-07", ("must_detect", "fail", "reasoning", 0)),
    "F03": ("STEP-07", ("must_detect", "fail", "reasoning", 0)),
    "F09": ("STEP-07", ("must_detect", "fail", "reasoning", 0)),
}

#: The same measurement: (kind, verdict, lost_at, cards over every sweep) per case.
BOARD_BEFORE: dict[str, tuple[str, str, str | None, int]] = {
    "F01": ("must_detect", "fail", "gate", 0),
    "F02": ("must_detect", "fail", "gate", 0),
    "F03": ("must_detect", "fail", "gate", 0),
    "F04": ("must_detect", "fail", "memory", 0),
    "F05": ("must_detect", "fail", "memory", 0),
    "F06": ("must_detect", "fail", "memory", 0),
    "F07": ("must_detect", "fail", "memory", 2),
    "F08": ("must_detect", "not_expressible", None, 0),
    "F09": ("must_detect", "fail", "gate", 0),
    "F10": ("must_detect", "fail", "memory", 0),
    "F11": ("must_detect", "fail", "memory", 0),
    "F12": ("must_detect", "pass", None, 1),
    "F13": ("must_detect", "pass", None, 1),
    "F14": ("must_detect", "not_expressible", None, 0),
    "F15": ("must_detect", "fail", None, 0),
    "F16": ("must_detect", "fail", "gate", 0),
    "F17": ("must_detect", "fail", "reasoning", 0),
    "F18": ("must_detect", "not_expressible", None, 0),
    "F19": ("must_detect", "fail", "memory", 1),
    "F20": ("must_detect", "not_expressible", None, 0),
    "F21": ("must_detect", "not_expressible", None, 0),
    "F22": ("must_detect", "not_expressible", None, 0),
    "F23": ("must_detect", "not_expressible", None, 0),
    "F24": ("must_detect", "fail", "memory", 2),
    "F25": ("must_detect", "pass", None, 1),
    "F26": ("must_detect", "fail", "memory", 0),
    "F27": ("must_detect", "fail", "reasoning", 2),
    "F28": ("must_detect", "pass", None, 1),
    "F29": ("must_detect", "fail", "reasoning", 3),
    "F30": ("must_detect", "not_expressible", None, 0),
    "F31": ("must_abstain", "fail", None, 0),
    "F32": ("must_abstain", "pass", None, 0),
    "F33": ("must_abstain", "pass", None, 0),
    "F34": ("must_abstain", "pass", None, 0),
    "F35": ("must_abstain", "pass", None, 0),
    "F36": ("must_abstain", "not_exercised", None, 0),
    "F37": ("must_abstain", "pass", None, 1),
    "F38": ("must_abstain", "fail", None, 1),
    "F39": ("must_abstain", "not_exercised", None, 0),
    "F40": ("must_abstain", "fail", None, 2),
}


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def test_the_measurement_is_the_one_section_8_recorded():
    """The pinned tables are data; this holds them to the numbers STEP-03 §8.1 published."""
    codes = collections.Counter(code for objs in DROPPED_BEFORE.values() for code in objs.values())
    assert codes == {"N-02": 16, "N-03": 8, "N-06": 4, "llm_junk": 4, "N-07": 1}
    assert sum(codes.values()) == 33
    assert set(BOARD_BEFORE) | set(ADDED_AFTER) == {c.case_id for c in CASES}
    assert not set(BOARD_BEFORE) & set(ADDED_AFTER)
    assert set(DROPPED_BEFORE) <= set(BOARD_BEFORE)
    assert set(MOVED_AFTER) <= set(BOARD_BEFORE), "a moved case needs a before to move from"
    assert all(after != BOARD_BEFORE[c] for c, (_step, after) in MOVED_AFTER.items()), (
        "a case listed as moved did not move")
    assert all(set(objs) <= set(DROPPED_BEFORE[c]) for c, objs in KEPT_BY_THE_BRIEF.items()), (
        "the brief can only keep what the gate archived")
    assert sum(len(objs) for objs in KEPT_BY_THE_BRIEF.values()) == 21


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_the_gate_deletes_nothing_and_the_case_is_marked_as_before(case):
    _scratch_db()
    from sqlalchemy import text

    from genios_engine.api import routes
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM

    run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    engine = routes._graph.engine
    try:
        with engine.connect() as c:
            rows = c.execute(text(
                "select se.source_object_id, se.attention, se.attention_reason, "
                "       exists (select 1 from raw_payloads rp where rp.org_id = se.org_id "
                "               and rp.event_id = se.event_id) as has_payload, "
                "       exists (select 1 from prepared_content pc where pc.org_id = se.org_id "
                "               and pc.event_id = se.event_id) as has_prepared "
                "  from source_events se where se.org_id = :o and se.outcome = 'archived'"),
                {"o": run.org_id}).fetchall()
    finally:
        remove_tenant(engine, run.org_id)

    assert not run.misses, f"{case.case_id}: the replay missed its cassette at {run.misses[:3]}"
    dropped = [(x.source_object_id, x.reason) for x in run.landed if x.outcome == "dropped"]
    assert not dropped, f"{case.case_id}: the gate still deleted {dropped}"

    kept = set(KEPT_BY_THE_BRIEF.get(case.case_id, ()))
    expected = {oid: code for oid, code in DROPPED_BEFORE.get(case.case_id, {}).items()
                if oid not in kept}
    archived = {x.source_object_id: x.reason for x in run.landed if x.outcome == "archived"}
    assert archived == expected, (
        f"{case.case_id}: archived {archived}, but the gate dropped {expected} before STEP-03 "
        f"(less what the company brief keeps: {sorted(kept)})")
    landed = {x.source_object_id: x.outcome for x in run.landed}
    assert {oid: landed.get(oid) for oid in kept} == {oid: "emitted" for oid in kept}, (
        f"{case.case_id}: the brief's senders did not land kept")

    stored = {r.source_object_id: r for r in rows}
    assert set(stored) == set(expected), f"{case.case_id}: archived rows {sorted(stored)}"
    for oid, code in expected.items():
        r = stored[oid]
        assert (r.attention, r.attention_reason) == ("archive", code), (case.case_id, oid, r)
        assert r.has_payload, f"{case.case_id}: {oid} is archived with no body"
        assert not r.has_prepared, f"{case.case_id}: {oid} is archived WITH prepared text — a reader of words can reach it"

    if case.case_id in ADDED_AFTER:
        return                 # no "before STEP-03" to compare with — the board records it
    mark = judge(case, run)
    after = (case.kind, mark.verdict, mark.lost_at, len(run.cards))
    if case.case_id in MOVED_AFTER:
        step, moved = MOVED_AFTER[case.case_id]
        assert after == moved, f"{case.case_id}: marked {after}, after {step} {moved}"
        return
    assert after == BOARD_BEFORE[case.case_id], (
        f"{case.case_id}: marked {after}, before STEP-03 {BOARD_BEFORE[case.case_id]}")
