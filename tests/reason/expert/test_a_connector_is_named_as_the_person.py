"""STEP-13 · the connector is named as the person — so a draft never goes to whoever made the introduction.

    .venv/bin/python -m pytest -q tests/reason/expert/test_a_connector_is_named_as_the_person.py

Tree `yc2_w27_s13` M35.C2.L-logic.V0.U13 (`reason/expert/dossier.connector_of`, read by `people_of`; `03` X07). A
connector who is a person at a company's domain — Pankaj at saka.vc — was named by the domain's label, "saka":
the check (`reason/expert/verify`, unedited, its own `matches`) then found "Pankaj Mehta" no connector, and
"Send Pankaj the short deck to forward to Marco" went out to the very person who introduced Marco. A connector
is named as the person: by the name its own mail in the file signs, else by its address's own words. Run on
the check itself, over a real dossier (`tests/reason/expert/check_world`).
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

PANKAJ = "pankaj@saka.vc"


def _parts(*, introduced_by: str = PANKAJ, signs: str | None = None):
    """Marco's file, introduced by `introduced_by`. `signs`: the name the introducer's own mail in the file
    signs (the intro is theirs), else the file holds no mail of theirs."""
    p = W.parts(introduced_by=introduced_by)
    if signs is not None:
        intro = replace(p.timeline.touches[0], who=introduced_by, who_name=signs)
        p = replace(p, timeline=replace(p.timeline, touches=(intro, *p.timeline.touches[1:])))
    return p


def _world(**kw):
    p = _parts(**kw)
    return D.build_dossier(p), D.people_of(p, us=W.US, our_names=W.OUR_NAMES)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


@pytest.mark.parametrize("introduced_by, signs, named", [
    (PANKAJ, None, "Pankaj"),                                  # his address's own words
    ("pankaj.mehta@saka.vc", None, "Pankaj Mehta"),
    (PANKAJ, "Pankaj Mehta", "Pankaj Mehta"),                  # the name his own mail signs
    (PANKAJ, PANKAJ, "Pankaj"),                                # …never an address printed as a name
    ("pankaj@gmail.com", None, "Pankaj"),                      # a public host was never a name
    (W.INTROLY, "Introly", "Introly"),                         # check_world's own: the intro signs it
    ("boardy.ai", None, "boardy")])                            # a company's domain: its label, as before
def test_a_connector_is_named_as_the_person_it_is(introduced_by, signs, named):
    assert D.connector_of(_parts(introduced_by=introduced_by, signs=signs)) == D.Person(name=named,
                                                                                      key=introduced_by)


@pytest.mark.parametrize("signs", [None, "Pankaj Mehta"], ids=["his-address-alone", "the-name-his-mail-signs"])
@pytest.mark.parametrize("to", ["Pankaj Mehta", "Pankaj", PANKAJ])
def test_a_draft_to_the_person_who_introduced_them_never_goes(signs, to):
    """⛔ `03` X07's run: "Send Pankaj the short deck to forward to Marco", to "Pankaj Mehta", was SHOWN with its
    draft. It is the connector — the review's own alternative is the move, and the draft for Pankaj goes nowhere."""
    dossier, people = _world(signs=signs)
    checked = check_review(W.review(move={"to": to, "what": "Send Pankaj the short deck to forward to Marco"}),
                           dossier.text, people)
    assert _verdict(checked, "to") == C.LineVerdict("to", C.DROPPED, C.RECIPIENT_IS_CONNECTOR, to)
    assert checked.words.draft is None and "Pankaj" not in str(checked.words.headline)


def test_the_counterparty_still_gets_the_draft_on_a_file_a_person_introduced():
    """⛔ THE NEGATIVE CONTROL: Marco is no connector — the faithful review's draft to Marco goes."""
    dossier, people = _world(signs="Pankaj Mehta")
    checked = check_review(W.review(), dossier.text, people)
    assert _verdict(checked, "to").verdict == C.KEPT and checked.words.draft and checked.fate == C.SHOWN


@pytest.mark.parametrize("kw", [{"kind": "connector"}, {"introduced_by": None}])
def test_no_connector_stands_between_a_file_and_its_own_counterparty(kw):
    assert D.connector_of(W.parts(**kw)) is None


def test_the_name_is_the_one_his_latest_mail_signs():
    """Two mails of his in the file, signed two ways: the latest is the name he goes by."""
    p = _parts(signs="P. Mehta")
    later = replace(p.timeline.touches[1], who=PANKAJ, who_name="Pankaj Mehta", direction="in")
    p = replace(p, timeline=replace(p.timeline, touches=(p.timeline.touches[0], later, *p.timeline.touches[2:])))
    assert D.connector_of(p) == D.Person(name="Pankaj Mehta", key=PANKAJ)
