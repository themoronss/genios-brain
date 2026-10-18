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


def _propose(engine, *, review=REVIEW, file=UNKINDED, at=AT, why="unset"):
    # ⛔ RESTATED by M35.C3.L-integration.V2.U05 (crosscheck X19): the line is written from the reason AS
    # CHECKED (`CardWords.kind`), passed in — here the review's own, as a check that let it stand would.
    why = (review.proposed_kind.why if review.proposed_kind is not None else None) if why == "unset" else why
    with engine.begin() as c:
        return K.propose_kind(c, org_id=ORG, review=review, file=file, fingerprint="ffp-1", at=at, why=why)


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


def test_the_experts_proposal_names_its_own_line_and_mints_nothing(engine, monkeypatch):
    """`03` F170: the line id comes from what is proposed — the file's counterparty and the kind — so a
    review that proposes never moves an id the rest of a run mints."""
    from genios_engine.platform import company_brief_store as store
    minted = []
    monkeypatch.setattr(store, "new_id", lambda prefix: minted.append(prefix) or "cbl_minted")
    proposal = _propose(engine)
    assert minted == [] and proposal.line_id.startswith("cbl_") and proposal.line_id != "cbl_minted"
    assert proposal.line_id == K.line_id_for(ORG, UNKINDED, "investor", "ffp-1")


def test_proposing_again_after_the_quiet_window_writes_a_new_line(engine):
    """The rejection's quiet window over, a later review's proposal is its own line — never a clash
    with the line the founder rejected."""
    from genios_engine.platform import company_brief_store as store
    first = _propose(engine)
    with engine.begin() as c:
        store.reject(c, org_id=ORG, line_id=first.line_id, decided_by="founder", at=AT)
    later = AT + timedelta(days=store.REJECTED_QUIET_DAYS + 1)
    with engine.begin() as c:
        again = K.propose_kind(c, org_id=ORG, review=REVIEW, file=UNKINDED, fingerprint="ffp-2", at=later,
                               why=REVIEW.proposed_kind.why)
    assert again.line_id and again.line_id != first.line_id


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


# ⛔ RESTATED by STEP-16 (`yc2_w27_s16` M46.C5.L-logic.V2.U03, `03` F157): this asserted that an accepted kind
# is never re-proposed as another — "F132 stays open". That was the defect F157 names, and it closes here: the
# review's kind is proposed as a line that REPLACES the accepted one, for the founder to accept.
def _filed_program(engine):
    with engine.begin() as c:
        return BS.add(c, org_id=ORG, section="in_motion", words="Program · Surge — the cohort",
                      decided_by="founder", at=AT, domain="larkspurvc.test", kind="program")


FILED = dataclasses.replace(UNKINDED, work_kind="program")


def test_an_accepted_kind_is_proposed_as_another_by_a_line_that_replaces_it_f157(engine):
    """F132: the programme is filed `program`; the expert reads it as the fund behind it — a proposal that
    replaces the accepted line, labelled, and nothing applied until the founder accepts it."""
    old = _filed_program(engine)
    proposal = _propose(engine, file=FILED)
    assert proposal.line_id and "replacing program" in proposal.says
    [line] = _pending(engine)
    assert (line["kind"], line["domain"], line["replaces"]["line_id"], line["replaces"]["kind"]) == (
        "investor", "larkspurvc.test", old, "program")
    assert line["text"].startswith("Investor · Larkspur Ventures — proposed by the expert, replacing program: ")
    assert len(line["text"]) <= MAX_LINE_CHARS
    with engine.connect() as c:
        assert [(ln.line_id, ln.kind) for ln in BS.accepted(c, ORG) if ln.section == "in_motion"] == [
            (old, "program")], "never applied"
    with engine.begin() as c:
        BS.accept(c, org_id=ORG, line_id=proposal.line_id, decided_by="founder", at=AT + timedelta(hours=1))
        now = [(ln.line_id, ln.kind) for ln in BS.accepted(c, ORG) if ln.section == "in_motion"]
    assert now == [(proposal.line_id, "investor")], "accepted in one act: the old line is gone"


def test_a_replacing_proposal_is_made_once_and_never_nags_after_a_rejection(engine):
    _filed_program(engine)
    first = _propose(engine, file=FILED)
    again = _propose(engine, file=FILED, at=AT + timedelta(days=1))
    assert first.line_id and again.line_id is None and "already holds a line" in again.says
    with engine.begin() as c:
        BS.reject(c, org_id=ORG, line_id=first.line_id, decided_by="founder", at=AT + timedelta(days=2))
    assert _propose(engine, file=FILED, at=AT + timedelta(days=30)).line_id is None
    assert _pending(engine) == []


def test_a_person_files_kind_is_corrected_on_the_line_that_names_them(engine):
    """The replacing line keeps the replaced line's counterparty — here the partner's address, not the anchor's."""
    with engine.begin() as c:
        old = BS.add(c, org_id=ORG, section="in_motion", words="Program · Ira at Surge", decided_by="founder",
                     at=AT, address="ira@larkspurvc.test", kind="program")
    person = dataclasses.replace(FILED, counterparty="Ira Sen", counterparty_key="ira@larkspurvc.test",
                                 counterparty_type="person")
    assert _propose(engine, file=person).line_id
    [line] = _pending(engine)
    assert (line["address"], line["domain"], line["replaces"]["line_id"]) == ("ira@larkspurvc.test", None, old)


def test_a_kind_no_accepted_line_gives_is_not_proposed_and_it_says_so(engine):
    proposal = _propose(engine, file=FILED)
    assert proposal.line_id is None and "no accepted line in force gives the file program" in proposal.says
    assert _pending(engine) == []


def test_the_line_giving_the_kind_is_the_first_accepted_that_names_the_file(engine):
    """`context/workstreams._work_kind`'s rule, read back as a line: the parent domain names the file, and the
    first line the founder accepted wins."""
    with engine.begin() as c:
        first = BS.add(c, org_id=ORG, section="in_motion", words="Program · Surge — the cohort",
                       decided_by="founder", at=AT, domain="larkspurvc.test", kind="program")
        BS.add(c, org_id=ORG, section="in_motion", words="Investor · Larkspur partners", decided_by="founder",
               at=AT + timedelta(hours=1), address="ira@larkspurvc.test", kind="investor")
        sub = dataclasses.replace(FILED, counterparty_key="surge.larkspurvc.test")
        assert K.line_giving_the_kind(c, org_id=ORG, file=sub).line_id == first
        assert K.line_giving_the_kind(c, org_id=ORG, file=dataclasses.replace(sub, work_kind=None)) is None
        assert K.line_giving_the_kind(c, org_id=ORG, file=dataclasses.replace(sub, work_kind="investor")) is None


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


def test_the_line_is_written_from_the_checked_reason_and_none_without_one(engine):
    """M35.C3.L-integration.V2.U05 (X19): a corrected reason is the one the brief's line says; a reason the
    check withheld proposes nothing."""
    corrected = _propose(engine, why="the fund wrote again after 6 days")
    [line] = _pending(engine)
    assert corrected.line_id and "after 6 days" in line["text"]
    assert _propose(engine, file=UNKINDED, why=None).line_id is None


def test_a_company_files_kind_given_by_a_partners_address_is_corrected_on_that_line(engine):
    """The file is the fund (its anchor a domain); the line that gives it its kind names the partner — one of
    the file's people — by address. The replacing proposal is on that line's counterparty."""
    with engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
                       "values ('node_ira_s16', :o, 'person', 'Ira Sen', 'ira@larkspurvc.test')"), {"o": ORG})
        old = BS.add(c, org_id=ORG, section="in_motion", words="Program · Ira's cohort", decided_by="founder",
                     at=AT, address="ira@larkspurvc.test", kind="program")
    company = dataclasses.replace(FILED, people=("node_ira_s16",))
    with engine.connect() as c:
        assert K.line_giving_the_kind(c, org_id=ORG, file=company).line_id == old
    assert _propose(engine, file=company).line_id
    [line] = _pending(engine)
    assert (line["address"], line["domain"], line["replaces"]["line_id"]) == ("ira@larkspurvc.test", None, old)


def test_a_file_named_by_its_parent_domain_is_corrected_on_the_parents_line(engine):
    with engine.begin() as c:
        old = BS.add(c, org_id=ORG, section="in_motion", words="Program · Larkspur's programmes",
                     decided_by="founder", at=AT, domain="larkspurvc.test", kind="program")
    sub = dataclasses.replace(FILED, counterparty_key="surge.larkspurvc.test")
    assert _propose(engine, file=sub).line_id
    [line] = _pending(engine)
    assert (line["domain"], line["replaces"]["line_id"]) == ("larkspurvc.test", old)


def test_a_line_naming_no_kind_is_passed_over_as_the_file_reads_it(engine):
    """`_work_kind` reads only lines that name a kind: an earlier in-motion line naming the counterparty with no
    kind gives the file none, and the kind comes from the next."""
    with engine.begin() as c:
        BS.add(c, org_id=ORG, section="in_motion", words="Larkspur — talking", decided_by="founder", at=AT,
               domain="larkspurvc.test")
        kinded = BS.add(c, org_id=ORG, section="in_motion", words="Program · Ira's cohort", decided_by="founder",
                        at=AT + timedelta(hours=1), address="ira@larkspurvc.test", kind="program")
        person = dataclasses.replace(FILED, counterparty_key="ira@larkspurvc.test")
        assert K.line_giving_the_kind(c, org_id=ORG, file=person).line_id == kinded
