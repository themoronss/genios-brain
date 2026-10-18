"""STEP-13 · the dossier read back by id — each place an id is printed, and whom the file's mail shows.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_dossier_lines.py

Tree `yc2_w27_s13` M35.C2.L-logic.V0.U01 (`reason/expert/dossier.lines_by_id`, `people_of`). The check holds a
claim to the lines it cites, so every id the dossier prints maps to each place it is printed: the line, the
item it belongs to (a head line with the lines indented under it — a touch's words, a person's numbers) and,
on a touch's head line, the touch's words. `people_of` says who the file's mail shows, and which connector
introduced the counterparty — never on the connector's own file. Built on a REAL dossier (`check_world`).
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from genios_engine.reason.expert import dossier as D
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit


def test_every_id_the_dossier_prints_is_found_and_nothing_else():
    dossier, _ = W.world()
    lines = D.lines_by_id(dossier.text)
    assert set(lines) == set(dossier.catalogue.evidence_ids)
    restricted = D.lines_by_id(dossier.text + "\n- [not_an_id] a stray bracket", dossier.catalogue.evidence_ids)
    assert "not_an_id" not in restricted and set(restricted) == set(lines)


def test_a_touch_is_read_back_with_its_words():
    dossier, _ = W.world()
    [head] = [dl for dl in D.lines_by_id(dossier.text)[W.ASK] if dl.words]
    assert head.line.startswith(f"- [{W.ASK}] 2026-08-11 09:20 UTC · they wrote · Marco Ruiz")
    assert head.words == ("Thanks Arjun — could you send a short deck before we set up a call? "
                          "I read everything within a week.")
    assert head.words in head.item and head.line in head.item


def test_a_touch_printed_elsewhere_carries_no_words_there():
    dossier, _ = W.world()
    places = D.lines_by_id(dossier.text)[W.ASK]
    assert len(places) >= 2, "the coverage line names the touch that answered our last mail"
    assert [dl.words is not None for dl in places].count(True) == 1


def test_only_a_touchs_own_line_carries_its_words():
    """An id printed on a line indented under a touch belongs to that touch's item — never to its words,
    or a quote would be checked against words its own id never said."""
    text = ("- [evt_a] 2026-08-11 09:20 UTC · they wrote · Marco\n  “send the deck”\n"
            "  [loop:aside] an ask noted under it")
    lines = D.lines_by_id(text)
    assert lines["evt_a"][0].words == "send the deck"
    assert lines["loop:aside"][0].words is None and "send the deck" in lines["loop:aside"][0].item


def test_a_calculator_is_read_back_inside_its_persons_item():
    dossier, _ = W.world()
    [place] = D.lines_by_id(dossier.text)[W.REPLY_TIME]
    assert place.line.startswith("their reply time: once: 6 days")
    assert place.item.startswith(f"- Marco Ruiz <{W.MARCO}>") and place.words is None


def test_cut_words_are_read_back_without_the_cut_note():
    p = W.parts(ask_words="could you send a short deck")
    cut = replace(p.timeline.touches[-1], words_cut=120)
    p = replace(p, timeline=replace(p.timeline, touches=(*p.timeline.touches[:-1], cut)))
    text = D.build_dossier(p).text
    assert "… (120 characters cut)" in text
    [head] = [dl for dl in D.lines_by_id(text)[W.ASK] if dl.words]
    assert head.words == "could you send a short deck"


def test_the_files_people_are_who_its_mail_shows():
    _, people = W.world()
    assert people.counterparty == D.Person(name="Marco Ruiz", key=W.MARCO)
    assert D.Person(name="Introly", key=W.INTROLY) in people.people, "a connector who wrote in it"
    assert all(p.key != "arjun@nimbuslabs.test" for p in people.people), "we wrote; we are not its people"
    # ⛔ RESTATED by M35.C2.L-logic.V0.U13 (`03` X07): the connector was named by its domain's label
    # ("introly") — which named a person at a company domain after the company. It is named as its own mail
    # in the file signs it: Introly.
    assert people.connector == D.Person(name="Introly", key=W.INTROLY)
    assert people.our_names == W.OUR_NAMES and people.us is W.US
    assert people.head.startswith("Counterparty: Marco Ruiz <marco@altavia.test> (person)")
    assert "Introduced by: hello@introly.test" in people.head


@pytest.mark.parametrize("kw", [{"kind": "connector"}, {"introduced_by": None}])
def test_no_connector_stands_between_a_file_and_its_own_counterparty(kw):
    _, people = W.world(**kw)
    assert people.connector is None


@pytest.mark.parametrize("key, label", [("hello@introly.test", "introly"), ("boardy.ai", "boardy"),
                                        ("rahul@gmail.com", None), ("", None), (None, None)])
def test_a_keys_own_name_is_its_hosts_first_label_never_a_public_hosts(key, label):
    assert D.label_of(key) == label
