"""STEP-11 · the operator names an in-motion line's kind of work — on add and on accept.

    pytest tests/scripts/test_company_brief_script_takes_a_kind.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_company_brief_script_takes_a_kind.py -q

`scripts/company_brief.py` (tree `yc2_w27_s11 · M30.C4.L-interface.V2.U08`, `06` D31). Until the dashboard
has the confirm screen, Harsh applies Rohit's answers with this script — and it could not say what kind
of work a line is. Now `--kind` (one of `WORK_KINDS`) goes with `add` and with `accept`, where it sets or
corrects the drafter's kind and `--kind none` clears it; on `accept`, `--address` and `--domain` correct
the counterparty, as the screen's route does. Each edit is for ONE line, and a `--kind` with nothing to
name is refused before any database. `show` prints each line's and each proposal's kind.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "company_brief.py"
FUND = "Banyan Seed — first call held, data room asked"


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("company_brief_script_kind", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("argv, why", [
    (["--org", "o", "reject", "cbl_1", "--kind", "investor"], "a line being added or accepted"),
    (["--org", "o", "remove", "cbl_1", "--kind", "investor"], "a line being added or accepted"),
    (["--org", "o", "show", "--kind", "investor"], "a line being added or accepted"),
    (["--org", "o", "accept", "cbl_1", "cbl_2", "--kind", "investor"], "ONE accepted line"),
    (["--org", "o", "accept", "cbl_1", "cbl_2", "--domain", "banyanseed.test"], "ONE accepted line"),
    (["--org", "o", "accept", "cbl_1", "cbl_2", "--address", "kiran@banyanseed.test"],
     "ONE accepted line"),
])
def test_a_kind_with_nothing_to_name_is_refused_before_any_database(argv, why):
    with pytest.raises(SystemExit, match=why):
        _module().main(argv)                                   # no --database-url given


def test_a_kind_off_the_list_never_reaches_the_writer(capsys):
    with pytest.raises(SystemExit) as refused:
        _module().main(["--org", "o", "add", "in_motion", FUND, "--kind", "fundraising"])
    assert refused.value.code == 2 and "invalid choice" in capsys.readouterr().err


@pytest.fixture
def tenant():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text

    from genios_engine.platform import company_brief_store as store

    org = f"org_s11_brief_cli_{uuid.uuid4().hex[:8]}"
    eng = create_engine(url)
    at = datetime.now(timezone.utc) - timedelta(days=1)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, company) values (:o, 'Arjun Rao', 'Nimbus Labs')"),
                  {"o": org})
        proposals = {
            "unnamed": store.propose(c, org_id=org, section="in_motion", proposed_by="drafter", at=at,
                                     words="Lakshya — the accelerator application"),
            "named": store.propose(c, org_id=org, section="in_motion", proposed_by="drafter", at=at,
                                   words="DigiVault — documents for the application",
                                   kind="compliance"),
            "fund": store.propose(c, org_id=org, section="in_motion", proposed_by="drafter", at=at,
                                  words="Tusker Capital — pitch on Friday", kind="investor",
                                  domain="tusker.test"),
        }
    yield url, eng, org, proposals
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": org})
    eng.dispose()


def _accepted(eng, org):
    from genios_engine.platform import company_brief_store as store
    with eng.connect() as c:
        return {ln.text: (ln.kind, ln.address, ln.domain) for ln in store.accepted(c, org)}


@pytest.mark.pg
def test_add_names_the_lines_kind_of_work_and_counterparty(tenant, capsys):
    url, eng, org, _ = tenant
    assert _module().main(["--org", org, "--database-url", url, "add", "in_motion", FUND,
                           "--kind", "Investor", "--domain", "banyanseed.test"]) == 0
    out = capsys.readouterr().out
    assert "[in_motion] as investor — in force now" in out
    assert _accepted(eng, org) == {FUND: ("investor", None, "banyanseed.test")}


@pytest.mark.pg
def test_accept_sets_clears_or_corrects_the_kind_and_the_counterparty(tenant, capsys):
    url, eng, org, p = tenant
    mod = _module()
    assert mod.main(["--org", org, "--database-url", url, "accept", p["unnamed"],
                     "--kind", "program"]) == 0
    assert mod.main(["--org", org, "--database-url", url, "accept", p["named"],
                     "--kind", "none"]) == 0
    assert mod.main(["--org", org, "--database-url", url, "accept", p["fund"],
                     "--kind", "partner", "--domain", "tuskercapital.vc"]) == 0
    out = capsys.readouterr().out
    assert f"accepted {p['unnamed']} as program" in out and f"accepted {p['named']};" in out
    assert _accepted(eng, org) == {
        "Lakshya — the accelerator application": ("program", None, None),
        "DigiVault — documents for the application": (None, None, None),
        "Tusker Capital — pitch on Friday": ("partner", None, "tuskercapital.vc")}


@pytest.mark.pg
def test_accept_with_domain_none_clears_the_counterparty_and_keeps_the_kind(tenant):
    url, eng, org, p = tenant
    assert _module().main(["--org", org, "--database-url", url, "accept", p["fund"],
                           "--domain", "none"]) == 0
    assert _accepted(eng, org) == {"Tusker Capital — pitch on Friday": ("investor", None, None)}


@pytest.mark.pg
def test_accept_with_no_kind_flag_keeps_the_proposals(tenant):
    url, eng, org, p = tenant
    assert _module().main(["--org", org, "--database-url", url, "accept", p["fund"]]) == 0
    assert _accepted(eng, org) == {"Tusker Capital — pitch on Friday": ("investor", None,
                                                                        "tusker.test")}


@pytest.mark.pg
def test_show_prints_each_lines_and_each_proposals_kind(tenant, capsys):
    url, eng, org, p = tenant
    mod = _module()
    assert mod.main(["--org", org, "--database-url", url, "accept", p["fund"]]) == 0
    capsys.readouterr()
    assert mod.main(["--org", org, "--database-url", url, "show"]) == 0
    out = capsys.readouterr().out
    assert f"{p['fund']}  [in_motion] Tusker Capital — pitch on Friday <tusker.test> (kind: investor)" \
        in out
    assert (f"{p['named']}  [in_motion] DigiVault — documents for the application (kind: compliance)"
            "   — proposed by drafter") in out
    assert f"{p['unnamed']}  [in_motion] Lakshya — the accelerator application   — proposed by" in out
    assert "investor" not in out.split("accepted lines")[0], "the brief's text showed a kind"


@pytest.mark.pg
def test_adding_what_the_brief_holds_with_another_kind_is_refused(tenant, capsys):
    url, eng, org, _ = tenant
    mod = _module()
    assert mod.main(["--org", org, "--database-url", url, "add", "in_motion", FUND]) == 0
    capsys.readouterr()
    assert mod.main(["--org", org, "--database-url", url, "add", "in_motion", FUND,
                     "--kind", "investor"]) == 1
    assert "refused:" in capsys.readouterr().out
    assert _accepted(eng, org) == {FUND: (None, None, None)}


@pytest.mark.pg
def test_a_kind_where_none_may_be_is_refused_by_the_writer(tenant, capsys):
    url, eng, org, _ = tenant
    assert _module().main(["--org", org, "--database-url", url, "add", "goals",
                           "Raise the seed round", "--kind", "investor"]) == 1
    assert "only an in-motion line" in capsys.readouterr().out
    assert _accepted(eng, org) == {}
