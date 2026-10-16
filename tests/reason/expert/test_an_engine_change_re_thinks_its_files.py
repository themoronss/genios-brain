"""STEP-13b · a file is thought about again when the engine it reads moved, or when the company has spoken since it asked.

    .venv/bin/python -m pytest -q tests/reason/expert/test_an_engine_change_re_thinks_its_files.py

Tree `yc2_w27_s13b` M37.C5.L-logic.V5.U02 (`reason/expert/triggers`). `engine_moved`: the file's route key or the learned
brains' snapshot is not what its last review saw (`06` D48 as Rohit answered it — the dossier changed, so the file is
thought again — only the files whose engine lines moved). A review stored before the engine was named saw none: a file
that reads one now has moved. `self_moved`: a file whose last review asked a question (held, or find out) and the
company's record has a line since it was asked (F52). The prompt's and the check's versions alone re-think nothing.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from genios_engine.context.company_record import CompanyRecord, SelfLine
from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert import fingerprint as F
from genios_engine.reason.expert import triggers as T
from tests.reason.expert.test_the_dossier import NOW, _parts

pytestmark = pytest.mark.unit

PROMPT = "expert-review.v5"


def _engine(parts, route="route-aaaa", learned="learned-1"):
    return dataclasses.replace(parts, route_key=route, learned_snapshot=learned)


def _said(parts, *events):
    lines = tuple(SelfLine(event_id=e, at=NOW - timedelta(days=i), said="We have customers.")
                  for i, e in enumerate(events))
    return dataclasses.replace(parts, company=CompanyRecord(org_id="o", as_of=NOW, lines=lines))


def _inputs(parts):
    return F.fingerprint_inputs(parts, prompt_version=PROMPT)


def _last(parts, *, asked: bool = False, mode: str = "act", fate: str = C.SHOWN):
    """The last standing review as the store reads it back — JSON inputs, and whether it asked a question."""
    checked = SimpleNamespace(fate=fate, question="Whom?" if asked else None)
    return SimpleNamespace(inputs=json.loads(json.dumps(_inputs(parts))), reviewed_at=NOW - timedelta(hours=1),
                           review=SimpleNamespace(mode=mode), checked=checked)


def _kinds(found):
    return [t.kind for t in found]


def test_the_kinds_name_both_and_nothing_else_is_new():
    assert T.ENGINE_MOVED == "engine_moved" and T.SELF_MOVED == "self_moved"
    assert {T.ENGINE_MOVED, T.SELF_MOVED} <= set(T.KINDS)


def test_a_file_whose_engine_did_not_move_is_not_looked_at():
    base = _engine(_parts())
    assert T.triggers_for(_engine(_parts()), _inputs(_engine(_parts())), last=_last(base)) == ()


@pytest.mark.parametrize("route, learned, says", [
    ("route-bbbb", "learned-1", "route-aaaa → route-bbbb"),
    ("route-aaaa", "learned-2", "learned-1 → learned-2"),
    ("route-aaaa", "none", "learned-1 → none")])
def test_a_route_or_a_learned_snapshot_that_moved_re_thinks_the_file(route, learned, says):
    found = T.triggers_for(_engine(_parts(), route, learned), _inputs(_engine(_parts(), route, learned)),
                           last=_last(_engine(_parts())))
    assert _kinds(found) == [T.ENGINE_MOVED] and says in found[0].says


def test_a_review_that_saw_no_engine_is_moved_by_one_it_reads_now():
    then = _parts()                                  # route_key None: its engine was `none`
    found = T.triggers_for(_engine(_parts()), _inputs(_engine(_parts())), last=_last(then))
    assert _kinds(found) == [T.ENGINE_MOVED] and "none → " in found[0].says
    stored_before = _last(then)
    stored_before.inputs.pop("engine"); stored_before.inputs.pop("self")      # a row from before this version
    assert T.triggers_for(_parts(), _inputs(_parts()), last=stored_before) == (), "none and none are the same file"
    assert _kinds(T.triggers_for(_engine(_parts()), _inputs(_engine(_parts())), last=stored_before)) == [T.ENGINE_MOVED]


def test_a_version_alone_re_thinks_nothing():
    base = _engine(_parts())
    last = _last(base)
    last.inputs["who_decides"] = {"ladder": "ladder.v0", "prompt_version": "expert-review.v4",
                                  "dossier_version": "dossier.v1"}
    assert T.triggers_for(base, _inputs(base), last=last) == ()


def test_the_company_speaking_since_a_question_was_asked_brings_the_file_back():
    base = _parts()
    asked = _last(_said(base, "evt_a"), asked=True, fate=C.HELD)
    found = T.triggers_for(_said(base, "evt_b", "evt_a"), _inputs(_said(base, "evt_b", "evt_a")), last=asked)
    assert _kinds(found) == [T.SELF_MOVED] and "evt_b" in found[0].says


def test_a_find_out_review_that_asked_is_brought_back_too():
    base = _parts()
    asked = _last(_said(base, "evt_a"), asked=True, mode="find_out")
    assert _kinds(T.triggers_for(_said(base, "evt_b", "evt_a"), _inputs(_said(base, "evt_b", "evt_a")),
                                 last=asked)) == [T.SELF_MOVED]


def test_a_review_that_asked_nothing_is_not_brought_back_by_the_company_speaking():
    base = _parts()
    shown = _last(_said(base, "evt_a"))
    assert T.triggers_for(_said(base, "evt_b", "evt_a"), _inputs(_said(base, "evt_b", "evt_a")), last=shown) == ()


def test_the_company_having_said_nothing_new_is_no_trigger():
    base = _parts()
    asked = _last(_said(base, "evt_a"), asked=True, fate=C.HELD)
    assert T.triggers_for(_said(base, "evt_a"), _inputs(_said(base, "evt_a")), last=asked) == ()


def test_a_review_that_saw_no_record_asked_and_the_company_has_spoken_since():
    base = _parts()
    asked = _last(base, asked=True, fate=C.HELD)
    assert _kinds(T.triggers_for(_said(base, "evt_a"), _inputs(_said(base, "evt_a")), last=asked)) == [T.SELF_MOVED]


def test_both_can_fire_and_a_first_look_fires_neither():
    base = _engine(_parts())
    asked = _last(_said(base, "evt_a"), asked=True, fate=C.HELD)
    now = _said(_engine(_parts(), "route-bbbb"), "evt_b", "evt_a")
    assert _kinds(T.triggers_for(now, _inputs(now), last=asked)) == [T.ENGINE_MOVED, T.SELF_MOVED]
    assert _kinds(T.triggers_for(now, _inputs(now))) == [T.FIRST_LOOK]


def test_a_row_whose_inputs_were_not_kept_is_a_first_look_only():
    base = _engine(_parts())
    last = _last(base)
    last.inputs = None
    assert _kinds(T.triggers_for(base, _inputs(base), last=last)) == [T.FIRST_LOOK]


def test_the_units_roster_alone_moves_the_engine():
    base = _engine(_parts())
    last = _last(base)
    last.inputs["engine"]["units"] = "units-old"
    found = T.triggers_for(base, _inputs(base), last=last)
    assert _kinds(found) == [T.ENGINE_MOVED] and "units units-old → " in found[0].says


def test_a_find_out_review_that_asked_nothing_is_not_asking():
    base = _parts()
    quiet = _last(_said(base, "evt_a"), mode="find_out")
    assert quiet.checked.question is None
    assert T.triggers_for(_said(base, "evt_b", "evt_a"), _inputs(_said(base, "evt_b", "evt_a")), last=quiet) == ()


def test_a_record_that_has_gone_quiet_is_not_the_company_speaking():
    base = _parts()
    asked = _last(_said(base, "evt_a"), asked=True, fate=C.HELD)
    assert T.triggers_for(base, _inputs(base), last=asked) == ()
