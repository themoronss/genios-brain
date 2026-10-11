"""STEP-12 · a review may propose the file's kind of work — a line of the brief the founder accepts or rejects.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_review_may_propose_a_kind.py -q

`reason/expert/kind_proposal.py` (tree `yc2_w27_s12` M32.C3.L-logic.V2.U08, `03` F132, F151). A valid review's
proposed kind becomes a PENDING in-motion line of the brief — the counterparty's domain or address, the
kind, labelled the expert's (its words, `proposed_by`, its evidence) — and nothing else: the file's kind
does not change until the founder accepts it. Not proposed: no proposal, the kind the brief already gives,
a counterparty the brief already holds a line for, or one the founder rejected lately — said each time.
"""
from __future__ import annotations

import dataclasses
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.contracts.company_brief import MAX_LINE_CHARS
from genios_engine.contracts.expert_review import ProposedKind
from genios_engine.platform import company_brief_store as BS
from genios_engine.reason.expert import kind_proposal as K
from tests.reason.expert.test_the_dossier import _file, _review

pytestmark = pytest.mark.pg

ORG = "org_s12_kind_proposal"
AT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
WHY = "Ira's signature names Larkspur Ventures, and she asks about the round"
REVIEW = dataclasses.replace(_review("evt_005", "Hi Kunal, booking it now."),
                             proposed_kind=ProposedKind(kind="investor", why=WHY, evidence=("evt_005",)))
UNKINDED = dataclasses.replace(_file(), work_kind=None, counterparty="Larkspur Ventures",
                               counterparty_key="larkspurvc.test")


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'kind@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from company_brief_lines where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _propose(engine, *, review=REVIEW, file=UNKINDED, at=AT):
    with engine.begin() as c:
        return K.propose_kind(c, org_id=ORG, review=review, file=file, fingerprint="ffp-1", at=at)


def _pending(engine):
    with engine.connect() as c:
        return BS.pending(c, ORG)


def test_a_fund_filed_as_a_sales_opportunity_is_proposed_as_an_investor(engine):
    """F151, case F53: a file with no kind of work, which the expert reads as a fund."""
    proposal = _propose(engine)
    assert proposal.kind == "investor" and proposal.line_id
    [line] = _pending(engine)
    assert (line["line_id"], line["section"], line["kind"], line["domain"], line["address"]) == (
        proposal.line_id, "in_motion", "investor", "larkspurvc.test", None)
    assert line["proposed_by"] == K.PROPOSED_BY == "expert_review"
    assert line["text"].startswith("Investor · Larkspur Ventures — proposed by the expert: ")
    assert line["evidence"] == [{"review": "ffp-1", "file": UNKINDED.file_id, "cites": ["evt_005"]}]


def test_a_proposal_changes_no_kind_until_the_founder_accepts_it(engine):
    _propose(engine)
    with engine.connect() as c:
        assert [ln for ln in BS.accepted(c, ORG) if ln.section == "in_motion"] == []
    with engine.begin() as c:
        BS.accept(c, org_id=ORG, line_id=_pending(engine)[0]["line_id"], decided_by="founder", at=AT)
        [line] = [ln for ln in BS.accepted(c, ORG) if ln.section == "in_motion"]
    assert (line.kind, line.domain) == ("investor", "larkspurvc.test")


def test_a_person_file_is_proposed_by_their_address(engine):
    person = dataclasses.replace(UNKINDED, counterparty="Ira Sen", counterparty_key="ira@larkspurvc.test",
                                 counterparty_type="person")
    assert _propose(engine, file=person).line_id
    [line] = _pending(engine)
    assert (line["address"], line["domain"]) == ("ira@larkspurvc.test", None)


def test_it_is_proposed_once_and_never_nags_after_a_rejection(engine):
    first = _propose(engine)
    again = _propose(engine, at=AT + timedelta(days=1))
    assert again.line_id is None and "already holds a line" in again.says
    with engine.begin() as c:
        BS.reject(c, org_id=ORG, line_id=first.line_id, decided_by="founder", at=AT + timedelta(days=2))
    assert _propose(engine, at=AT + timedelta(days=30)).line_id is None
    assert len(_pending(engine)) == 0


def test_an_accepted_kind_is_not_re_proposed_as_another_f132_stays_open(engine):
    """F132: the programme is filed `program`; the expert reads it as the fund — the founder's edit."""
    with engine.begin() as c:
        BS.add(c, org_id=ORG, section="in_motion", words="Program · Surge — the cohort",
               decided_by="founder", at=AT, domain="larkspurvc.test", kind="program")
    filed = dataclasses.replace(UNKINDED, work_kind="program")
    proposal = _propose(engine, file=filed)
    assert proposal.line_id is None and "already holds a line" in proposal.says
    assert _pending(engine) == []


@pytest.mark.parametrize("review, file, says", [
    (_review("evt_005", "Hi Kunal, booking it now."), UNKINDED, "proposes no kind"),
    (REVIEW, dataclasses.replace(UNKINDED, work_kind="investor"), "already names it investor"),
])
def test_nothing_is_proposed_without_a_new_kind_and_it_says_so(engine, review, file, says):
    proposal = _propose(engine, review=review, file=file)
    assert proposal.line_id is None and says in proposal.says and _pending(engine) == []


def test_a_long_reason_is_cut_at_a_word_to_the_brief_line():
    words = K.words_for("investor", "Larkspur Ventures", "because " + "the fund wrote again " * 20)
    assert len(words) <= MAX_LINE_CHARS and words.endswith("…")
    assert words[:-1].endswith(("again", "fund", "wrote", "the", "because"))
    assert K.words_for("investor", "Larkspur Ventures", "short") == (
        "Investor · Larkspur Ventures — proposed by the expert: short")
