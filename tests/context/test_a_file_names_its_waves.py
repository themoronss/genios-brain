"""STEP-10 · a file names the waves its people were sent, and what came of each there.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_file_names_its_waves.py -q

`context/workstream_numbers.numbers_for` (tree `yc2_w27_s10 · M29.C2.L-logic.V2.U05`). Found holding the build
against STEP-10's vision — *"a wave as one object … GET /v1/workstreams/{file} serves it"*: the wave existed
(`correlation_conversation.find_waves`) and nothing read it, so a fund's file never said it was one of five
funds that got the same pitch. Now a file's numbers carry every wave one of its people was sent — its line,
when it went, how many it went to and what came of it, each a `Measured` — and, for this file's own people,
who replied, whose address bounced and whom we wrote to again. Read only.
"""
from __future__ import annotations

import pytest

from genios_engine.context.workstream_numbers import as_dict, numbers_for
from genios_engine.context.workstream_timeline import timeline_for
from genios_engine.context.workstreams import files_for

from .test_a_wave_is_one_object import (COBALT, JUNIPER, LATTICE, NOW, ORG, f15,  # noqa: F401
                                        store)
from .workstream_world import node, process

pytestmark = pytest.mark.pg


def _numbers(store, person: str):
    who = node(store, ORG, person).node_id
    with store.engine.connect() as c:
        [file] = [f for f in files_for(c, ORG, now=NOW).files if who in f.people]
        return numbers_for(c, ORG, file, timeline_for(c, ORG, file.file_id, now=NOW), now=NOW)


def test_a_funds_file_names_the_wave_it_was_one_of(store):
    f15(store)
    [wave] = _numbers(store, COBALT).waves
    assert (wave.sent.says(), wave.reply_rate.says(), wave.bounce_rate.says(),
            wave.follow_up_rate.says()) == ("5", "1 of 5", "1 of 5", "1 of 5")


@pytest.mark.parametrize("fund, replied, bounced, followed_up", [
    (COBALT, True, False, False), (LATTICE, False, True, False), (JUNIPER, False, False, True)])
def test_each_file_says_what_came_of_the_wave_for_its_own_people(store, fund, replied, bounced,
                                                                   followed_up):
    f15(store)
    [mine] = as_dict(_numbers(store, fund))["waves"][0]["this_file"]
    assert mine == {"key": fund, "replied": replied, "bounced": bounced,
                    "followed_up": followed_up}


def test_a_file_outside_every_wave_names_none(store):
    f15(store)
    process(store, ORG, event_id="evt_elsewhere", sender="ana@southwind.test", thread="t-ana",
            at=NOW)
    assert _numbers(store, "ana@southwind.test").waves == ()


def test_the_waves_read_as_json(store):
    """Meridian Seed answers too, and Northstar hears from us again: three replies would be wrong,
    so the counts differ — two replies, one bounce, two follow-ups — each in its own place."""
    f15(store)
    from datetime import timedelta
    from .test_a_wave_is_one_object import MERIDIAN, NORTHSTAR, SUBJECT, WAVE, reply, send
    reply(store, "evt_meridian", sender=MERIDIAN, thread="t-to-4", at=WAVE + timedelta(days=3))
    send(store, "evt_nudge_ns", to=(NORTHSTAR,), subject=f"Re: {SUBJECT}", thread="t-to-5",
         at=WAVE + timedelta(days=10), body="Following up on the note below.")
    [wave] = as_dict(_numbers(store, COBALT))["waves"]
    assert (wave["sent"]["says"], wave["replied"]["says"], wave["bounced"]["says"],
            wave["followed_up"]["says"]) == ("5", "2 of 5", "1 of 5", "2 of 5")
    assert wave["recognised_by"] and wave["line"] and wave["first_sent"] < wave["last_sent"]
    assert round(wave["days_since_last_send"], 1) == 56.3, "a follow-up is not a send of the wave"
