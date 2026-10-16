"""STEP-13b · the fingerprint names the engine a file reads and the ladder that decides — never a model.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_fingerprint_names_the_engine.py

Tree `yc2_w27_s13b` M37.C5.L-logic.V4.U01 (`reason/expert/fingerprint`). `who_decides` is the model LADDER's version, the
prompt's and the dossier's — a climb from one rung to another never re-keys a file, and no model is named. `engine` is
the file's route key, the learned brains' snapshot for its subjects and the units' roster version; `self` the newest line
of the company's record that is not the file's own. A file with no engine line and no record names `none`, and is
fingerprinted as a file with neither.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.company_record import CompanyRecord, SelfLine
from genios_engine.contracts.model_ladder import LADDER_VERSION
from genios_engine.reason.expert import fingerprint as F
from genios_engine.reason.expert.file_units import UNITS_ROSTER_VERSION
from tests.reason.expert.test_the_dossier import _parts

pytestmark = pytest.mark.unit

PROMPT = "expert-review.v5"


def _inputs(parts, **kw):
    return F.fingerprint_inputs(parts, prompt_version=PROMPT, **kw)


def _fp(parts, **kw):
    return F.file_fingerprint(parts, prompt_version=PROMPT, **kw)


def _engine(parts, route="route-aaaa", learned="learned-1"):
    return dataclasses.replace(parts, route_key=route, learned_snapshot=learned)


def _line(event, day=1):
    return SelfLine(event_id=event, at=datetime(2026, 10, 2, tzinfo=timezone.utc) + timedelta(days=day), said="We have customers.")


def _record(*lines):
    return CompanyRecord(org_id="org_x", as_of=datetime(2026, 10, 10, tzinfo=timezone.utc), lines=tuple(lines))


def test_who_decides_is_the_ladder_the_prompt_and_the_dossier_and_names_no_model():
    who = _inputs(_parts())["who_decides"]
    assert who == {"ladder": LADDER_VERSION, "prompt_version": PROMPT, "dossier_version": "dossier.v2"}
    assert "model" not in who
    with pytest.raises(TypeError):
        _inputs(_parts(), model="claude-haiku-5")


def test_a_climb_never_re_keys_a_file_but_a_ladder_version_does():
    base = _parts()
    assert _fp(base) == _fp(base, ladder_version=LADDER_VERSION)
    assert _fp(base, ladder_version="ladder.v2") != _fp(base)
    assert _fp(base) != F.file_fingerprint(base, prompt_version="expert-review.v6")


def test_a_file_with_no_engine_and_no_record_names_none():
    inputs = _inputs(_parts())
    assert inputs["engine"] == "none" and inputs["self"] == "none"
    assert _fp(_engine(_parts(), route="none", learned="none")) == _fp(_parts())


def test_the_engine_is_the_route_the_learned_snapshot_and_the_units_roster():
    inputs = _inputs(_engine(_parts()))
    assert inputs["engine"] == {"route": "route-aaaa", "learned": "learned-1", "units": UNITS_ROSTER_VERSION}


def test_the_route_the_learned_snapshot_and_the_roster_each_move_the_file():
    base = _engine(_parts())
    assert _fp(_engine(_parts(), route="route-bbbb")) != _fp(base)
    assert _fp(_engine(_parts(), learned="learned-2")) != _fp(base)
    assert _fp(_engine(_parts(), learned="none")) != _fp(base)
    assert _fp(base) == _fp(_engine(_parts()))
    assert _fp(_engine(_parts(), route="none", learned="learned-1")) != _fp(_parts()), "a learned line alone is an engine"


def test_a_file_whose_engine_was_never_read_cannot_be_told_from_one_that_reads_nothing():
    assert _inputs(dataclasses.replace(_parts(), route_key=None, learned_snapshot=None))["engine"] == "none"


def test_the_company_record_moves_the_file_by_its_newest_line_that_is_not_the_files_own():
    base = _parts()
    one = dataclasses.replace(base, company=_record(_line("evt_a")))
    assert _inputs(one)["self"] == "evt_a" and _fp(one) != _fp(base)
    two = dataclasses.replace(base, company=_record(_line("evt_b", 5), _line("evt_a")))
    assert _inputs(two)["self"] == "evt_b" and _fp(two) != _fp(one)
    own_event = base.timeline.touches[0].event_id
    mine = dataclasses.replace(base, company=_record(_line(own_event)))
    assert _inputs(mine)["self"] == "none" and _fp(mine) == _fp(base), "the file's own mail is its timeline"
    older = dataclasses.replace(base, company=_record(_line("evt_b", 5), _line("evt_a"), _line("evt_0", 0)))
    assert _fp(older) == _fp(two), "only the newest line is named"


def test_the_same_inputs_are_the_same_file_in_any_order_and_a_later_read():
    a = _engine(_parts())
    assert _inputs(a) == _inputs(_engine(_parts()))


def test_a_meeting_booked_ahead_is_the_files_own_too():
    from genios_engine.context.workstream_timeline import Touch
    base = _parts()
    meeting = Touch(at=base.as_of + timedelta(days=3), kind="meeting", direction="meeting", who=None, who_name=None,
                    event_id="evt_call", thread=None)
    booked = dataclasses.replace(base, timeline=dataclasses.replace(base.timeline, upcoming=(meeting,)))
    mine = dataclasses.replace(booked, company=_record(_line("evt_call")))
    assert _inputs(mine)["self"] == "none"
