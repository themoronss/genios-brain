"""STEP-11 · a programme or a portal is never decided as an investor — it is refused `misfiled_kind`.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_a_programme_is_not_decided_as_an_investor.py -q

`yc2_w27_align` M34.C2.L-logic.V0.U10. Layer 2 has no situation type for an application (`06` D32), and
its hint files accelerators, incubators and cohorts under `fundraising` by construction, so a
programme's mail and a government portal's form `investor_relationship` — F17's accelerator, F24's,
F01's and F02's portal (STEP-11 §8.1) — and route to the Founder Office's investor capability, whose own
situation calls that a misfile. Nothing shows it today: the capability is unreviewed, so the live
compile refuses every fundraising file `unreviewed`. The day the founder admits the investor sheet
(`06` D45), every one of them would be decided as a fund.

So a file the company brief names as a programme's or a portal's (`06` D31) is refused `misfiled_kind`
after admission and before the compile — counted, its end recorded, no investor package published — and
a fund's file in the same sweep is compiled as before. Proven with the investor capability ADMITTED in a
test corpus: a copy of the Founder Office corpus, admitted by the founder's own ceremony
(`scripts/playbook_review_sheet.apply`, every line accepted), so the refusal is not the review's.
"""
from __future__ import annotations

import importlib
import shutil
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import situations
from genios_engine.context.pipeline import process_event
from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine

from ..l1_supply import attach_l1_signals
from ..test_admin_support_packs import NOW, _FakeLLM, _erase_tenant, _seed_event, _seed_org

PROGRAMME = "gulflaunchpad.test"
FUND = "banyanseed.test"

# Every fact below is substring-backed: the grounding guard drops what it cannot find in the content.
_PROGRAMME_MAIL = ("Rhea at Gulf Launchpad wrote that our application to the accelerator cohort is "
                   "under review. The interview round opens next week.")
_PROGRAMME_READ = {
    "relevance": 0.9, "noise_type": "none", "domains": ["fundraising"],
    "entity_mentions": [
        {"type": "person", "name": "Rhea", "email": f"rhea@{PROGRAMME}",
         "evidence_text": "Rhea at Gulf Launchpad"},
        {"type": "company", "name": "Gulf Launchpad", "email": None,
         "evidence_text": "at Gulf Launchpad"}],
    "fact_candidates": [
        {"subject": "Rhea", "field": "thread.ball_in_court", "value": "them",
         "evidence_text": "our application to the accelerator cohort is under review"}],
    "commitments": [], "questions": [], "observations": [],
}
_FUND_MAIL = ("Arjun at Banyan Seed Fund asked for our latest deck and the metrics from last quarter "
              "before the partner meeting.")
_FUND_READ = {
    "relevance": 0.9, "noise_type": "none", "domains": ["fundraising"],
    "entity_mentions": [
        {"type": "person", "name": "Arjun", "email": f"arjun@{FUND}",
         "evidence_text": "Arjun at Banyan Seed Fund"},
        {"type": "company", "name": "Banyan Seed Fund", "email": None,
         "evidence_text": "at Banyan Seed Fund"}],
    "fact_candidates": [
        {"subject": "Arjun", "field": "thread.ball_in_court", "value": "us",
         "evidence_text": "asked for our latest deck"}],
    "commitments": [], "questions": [], "observations": [],
}


@pytest.fixture(scope="module")
def admitted(tmp_path_factory):
    """The Founder Office corpus, copied, with its investor capability admitted line by line."""
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root

    root = tmp_path_factory.mktemp("u10") / "Domain Expertise"
    shutil.copytree(default_authoring_root() / "Founder Office Expertise",
                    root / "Founder Office Expertise")
    review = importlib.import_module("scripts.playbook_review_sheet")
    catalog = ExpertBrainCatalog(root)
    filled = review.sheet(catalog, "investor")
    for line in filled["lines"]:
        line["decision"] = "accept"
    assert review.apply(catalog, root, filled, "the founder, in a test corpus",
                        today="2026-10-10") == 0
    return ExpertBrainCatalog(root)


def _brief(*lines: tuple[str, str | None, str | None]) -> CompanyBrief:
    return CompanyBrief(org_id="org_u10", lines=tuple(
        CompanyBriefLine(line_id=f"cbl_{n}", section="in_motion", text=f"Line {n}", domain=domain,
                         address=address, kind=kind)
        for n, (kind, domain, address) in enumerate(lines)))


def test_the_investor_capability_is_admitted_in_the_test_corpus(admitted):
    """The premise: what refuses a programme below is not the review — the capability is admitted."""
    from genios_engine.packs.compiler.capability_resolver import _admission_reason
    from genios_engine.reason.domain_shadow import INVESTOR_CAPABILITY

    founder = admitted.domains["founder_office"]
    assert _admission_reason(founder.capabilities[INVESTOR_CAPABILITY]) is None
    for situation_type in ("investor_relationship", "investor_contact"):
        assert INVESTOR_CAPABILITY in founder.routes[situation_type]["capabilities"]


@pytest.mark.parametrize("kind, refused", [
    ("program", True), ("compliance", True),
    ("investor", False), ("intro", False), ("hiring", False), ("partner", False), ("vendor", False),
    (None, False)])
def test_only_a_programme_or_a_portal_is_misfiled(admitted, kind, refused):
    from genios_engine.reason.domain_shadow import misfiled_kind
    for situation_type in ("investor_relationship", "investor_contact"):
        assert misfiled_kind(admitted, domain="founder_office", situation_type=situation_type,
                             kind=kind) is refused


def test_a_situation_the_investor_capability_does_not_decide_is_never_misfiled(admitted):
    from genios_engine.reason.domain_shadow import misfiled_kind
    assert not misfiled_kind(admitted, domain="founder_office", situation_type="account_admin",
                             kind="program")
    assert not misfiled_kind(admitted, domain=None, situation_type="investor_relationship",
                             kind="program")
    assert not misfiled_kind(admitted, domain="admin", situation_type="investor_relationship",
                             kind="compliance")


class _NoRead:
    def execute(self, *_a, **_k):
        raise AssertionError("the graph was read for a brief that names no programme or portal")


def test_a_brief_that_names_no_programme_or_portal_refuses_nothing_and_reads_nothing():
    from genios_engine.reason.domain_shadow import file_kinds
    assert file_kinds(_NoRead(), "org_u10", CompanyBrief(org_id="org_u10"), ["node_1"]) == {}
    assert file_kinds(_NoRead(), "org_u10", _brief(("investor", FUND, None), ("partner", "x.test", None)),
                      ["node_1"]) == {}


# ── the sweep, end to end ────────────────────────────────────────────────────────────────────────

def _mail(store, org: str, event_id: str, content: str, sender: str, read: dict) -> None:
    with store.engine.begin() as conn:
        _seed_event(conn, org, event_id, "fundraising")
    res = process_event(org_id=org, event_id=event_id, source="gmail", content=content,
                        sender_email=sender, occurred_at=NOW, llm=_FakeLLM(read), store=store,
                        is_inbound=True, internal_emails=frozenset(),
                        domain_hints=[{"domain": "fundraising"}])
    assert res.outcome == "committed", res


def _tenant(store, org: str):
    """A founder with a programme's mail and a fund's, the Founder Office on, and a brief naming both."""
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.platform import company_brief, company_brief_store, l3_activation

    _seed_org(store, org)
    _erase_tenant(store, org)
    with store.engine.begin() as conn:
        for table in ("situation_outcomes", "situation_admission_decisions", "signals",
                      "company_brief_lines"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
    _mail(store, org, f"{org}_programme", _PROGRAMME_MAIL, f"rhea@{PROGRAMME}", _PROGRAMME_READ)
    _mail(store, org, f"{org}_fund", _FUND_MAIL, f"arjun@{FUND}", _FUND_READ)
    situations.refresh_situations(store, org, eval_time=NOW)
    assert attach_l1_signals(store, org, eval_time=NOW) > 0
    with store.engine.begin() as conn:
        company_brief_store.add(conn, org_id=org, section="in_motion",
                                words="Program · Gulf Launchpad — applied", domain=PROGRAMME,
                                kind="program", decided_by="the founder", at=NOW - timedelta(days=2))
        company_brief_store.add(conn, org_id=org, section="in_motion",
                                words="Raise · Banyan Seed Fund — written to in the seed wave",
                                domain=FUND, kind="investor", decided_by="the founder",
                                at=NOW - timedelta(days=1))
    company_brief.invalidate(org)
    l3_activation.activate(store.engine, org, domain="founder_office", by="test",
                           notes="the founder's own work, as the pilot org (06 D2)")
    registry = make_registry(store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    return registry


def _by_counterparty(store, org: str) -> dict[str, set[str]]:
    """Each active fundraising situation, by the domain its anchor is at."""
    with store.engine.connect() as conn:
        rows = conn.execute(text(
            "select s.situation_id, n.canonical_key from context_situations s "
            "  join graph_nodes n on n.org_id = s.org_id and n.node_id = s.anchor_node_id "
            "       and n.valid_to is null "
            " where s.org_id = :o and s.domain = 'fundraising' and s.status in ('active', 'partial')"),
            {"o": org}).all()
    out: dict[str, set[str]] = {}
    for r in rows:
        key = str(r.canonical_key).lower()
        out.setdefault(key.rsplit("@", 1)[-1], set()).add(str(r.situation_id))
    return out


@pytest.mark.pg
def test_the_sweep_refuses_the_programme_and_compiles_the_fund(pg_store, admitted, monkeypatch):
    from genios_engine.reason import domain_shadow

    org = "u10_misfiled_kind"
    registry = _tenant(pg_store, org)
    files = _by_counterparty(pg_store, org)
    assert files.get(PROGRAMME) and files.get(FUND), files
    monkeypatch.setattr(domain_shadow, "expert_catalog", lambda: admitted)

    counts = domain_shadow.shadow_compile(store=pg_store, org_id=org, eval_time=NOW,
                                          live_domains=frozenset({"founder_office"}),
                                          registry=registry)

    assert counts.get("misfiled_kind") == len(files[PROGRAMME]), counts
    assert counts.get("unsupported_unreviewed", 0) == 0, "the capability is admitted: nothing hides"
    assert counts.get("compiled") == len(files[FUND]), counts
    with pg_store.engine.connect() as conn:
        ends = {r.situation_id: (r.outcome, r.reason) for r in conn.execute(text(
            "select situation_id, outcome, reason from situation_outcomes where org_id = :o"),
            {"o": org})}
        packaged = {r.situation_id for r in conn.execute(text(
            "select situation_id from expertise_packages where org_id = :o"), {"o": org})}
    for situation_id in files[PROGRAMME]:
        assert ends.get(situation_id) == ("unsupported", "misfiled_kind"), ends
        assert situation_id not in packaged, "an investor package was published for a programme"
    assert files[FUND] <= packaged, "the fund's file was not compiled as an investor's"


@pytest.mark.pg
def test_a_brief_that_names_nothing_leaves_the_programme_as_it_was(pg_store, admitted, monkeypatch):
    """The negative control: with no line naming its kind, the same file is compiled as before."""
    from genios_engine.reason import domain_shadow
    from genios_engine.platform import company_brief

    org = "u10_unnamed_kind"
    registry = _tenant(pg_store, org)
    with pg_store.engine.begin() as conn:
        conn.execute(text("delete from company_brief_lines where org_id = :o"), {"o": org})
    company_brief.invalidate(org)
    files = _by_counterparty(pg_store, org)
    monkeypatch.setattr(domain_shadow, "expert_catalog", lambda: admitted)

    counts = domain_shadow.shadow_compile(store=pg_store, org_id=org, eval_time=NOW,
                                          live_domains=frozenset({"founder_office"}),
                                          registry=registry)

    assert counts.get("misfiled_kind", 0) == 0, counts
    assert counts.get("compiled") == len(files[PROGRAMME]) + len(files[FUND]), counts
