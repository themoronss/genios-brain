"""G9 · coverage wiring — Wave W9.

Coverage is how the system answers "did we actually see everything we claimed to sweep". The
gate is blunt and absolute:

    pytest tests/capture/coverage/test_coverage_wiring.py -q

Expected: **every** swept event carries a non-null `coverage_ready`. A null there is not a
missing analytics column — it is an event nobody can prove was accounted for, and a coverage
report computed over a population with holes in it reports a percentage of a number it does not
know.

`coverage_fn` used to appear at five sites, ALL of them inside `capture/pipeline.py`. The three
real capture entries — `capture/acquire/sync_runner.py`, the Composio webhook, and
`capture/intake.py` — passed nothing, and a fourth (`/dev/ingest-sample`, which writes real
`source_events` rows) passed nothing either. So the parameter existed, the model computed the
right answer, and 100% of emitted events carried `None`.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timezone

import pytest

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.connectors.fake import FakeGmailConnector
from genios_engine.capture.coverage.declaration import declare_coverage
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event
from genios_engine.contracts.connection import Connection

WAVE = "W9"
GATE = "G9"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
ENGINE_ROOT = pathlib.Path(__file__).resolve().parents[3] / "genios_engine"


def _coverage_fn(*sources: str, org_id: str = "org_cov"):
    """The factory's output, built from a connection set the test states outright."""
    conns = [Connection(org_id=org_id, source_type=s, connection_id=f"con_{s}") for s in sources]
    return declare_coverage(org_id=org_id, connections=conns, company_knowledge_count=0,
                            computed_at=NOW).for_domain


# ---------------------------------------------------------------------------------------------
# ACCEPTANCE 1 — every event a SWEEP produces carries a verdict.
# ---------------------------------------------------------------------------------------------

@pytest.mark.gate
def test_every_swept_event_carries_coverage_ready():
    """No null `coverage_ready` on any event a sweep produced — the poll lane."""
    summary = run_sync(FakeGmailConnector(), org_id="org_cov", connection_id="con_cov",
                       repo=InMemorySourceEventRepository(),
                       coverage_fn=_coverage_fn("gmail", "hubspot"))

    assert summary.gated, "the sweep emitted nothing, so the gate would pass vacuously"
    assert all(g.coverage_ready is not None for g in summary.gated)
    assert all(g.coverage_ready is True for g in summary.gated), (
        "gmail + hubspot satisfies sales (communication + crm), so the verdict is a licensed yes")


@pytest.mark.gate
def test_an_org_with_only_a_mailbox_is_not_covered_for_sales():
    """The negative half. `coverage_ready=False` is a real answer and must not read as None."""
    summary = run_sync(FakeGmailConnector(), org_id="org_cov", connection_id="con_cov",
                       repo=InMemorySourceEventRepository(),
                       coverage_fn=_coverage_fn("gmail"))

    assert summary.gated
    assert all(g.coverage_ready is False for g in summary.gated), (
        "no CRM means no licence to say 'they never replied' about a sales domain")


@pytest.mark.gate
def test_an_org_with_no_support_connector_reports_support_uncovered():
    """Doc 01's third acceptance line, asked of the declaration directly."""
    declared = _coverage_fn("gmail")("support")
    assert declared["coverage_ready"] is False
    assert "support_desk" in declared["missing_required"]


# ---------------------------------------------------------------------------------------------
# ACCEPTANCE 2 — the WEBHOOK lane, which is a separate entry and was separately unwired.
# ---------------------------------------------------------------------------------------------

@pytest.mark.gate
def test_a_webhook_event_carries_coverage_ready_too():
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="hook_1",
                    occurred_at=NOW, actor_email="priya@acme.com",
                    raw={"subject": "Revised contract",
                         "body": "Budget is approved. Can you send the contract by Friday?"})
    res = capture_event(raw, org_id="org_cov", connection_id="con_cov",
                        repo=InMemorySourceEventRepository(),
                        coverage_fn=_coverage_fn("gmail", "hubspot"))
    assert res.gated is not None
    assert res.gated.coverage_ready is True


@pytest.mark.gate
def test_a_manual_intake_event_carries_coverage_ready_too():
    """`capture/intake.py` is the one door for uploads, notes and agent outcomes. It emitted
    events with a null verdict for exactly as long as it existed."""
    from genios_engine.capture.intake import ingest_manual

    res = ingest_manual(org_id="org_cov", source="internal", object_type="pricing",
                        source_object_id="price_1",
                        body="Standard pricing is $84k per year with a 12-month contract.",
                        subject="Pricing policy", internal_kind="pricing",
                        repo=InMemorySourceEventRepository(),
                        coverage_fn=_coverage_fn("gmail", "hubspot"))
    assert res.gated is not None
    assert res.gated.domain_hints, "the fixture must produce a hint or the gate is vacuous"
    assert res.gated.coverage_ready is True


def test_an_unhinted_event_keeps_a_null_verdict_on_purpose():
    """The one honest `None`, and it must stay reachable.

    `GatedEvent.coverage_ready` is documented as three-valued: True and False are verdicts about
    the tenant's SOURCES, and None means *we never classified this event into a domain*. Those are
    different states — an unclassified event is not an under-connected tenant — so a wiring change
    that made every event True-or-False by defaulting the unhinted ones would be hiding one bug
    under another. The coverage_fn is wired here and still, correctly, not consulted.
    """
    from genios_engine.capture.intake import ingest_manual

    asked: list[str] = []

    def _spy(domain: str):
        asked.append(domain)
        return {"coverage_ready": True}

    # THE FIXTURE MOVED, THE PROPERTY DID NOT. "Refund policy" used to match no pattern and so
    # demonstrated the unhinted state by accident. Admin was widened on 2026-09-11 to absorb
    # business operations — 815 of 889 live events were matching nothing at all — and a refund
    # policy is now correctly classified, which is the improvement rather than a regression.
    # An event with no business vocabulary in it at all still reaches the `None` verdict, and
    # that is what this test exists to hold. `ingest_manual` deliberately passes no fallback
    # domain either: the collector in `capture/pipeline` is offered only to a message the
    # relevance gate has already judged to be business.
    res = ingest_manual(org_id="org_cov", source="internal", object_type="note",
                        source_object_id="pol_1",
                        body="The kitchen tap on the second floor drips after midnight.",
                        subject="Note to self", internal_kind="policy",
                        repo=InMemorySourceEventRepository(), coverage_fn=_spy)
    assert res.gated is not None
    # The COLLECTOR marks it, and that is not a classification. Admin was widened on
    # 2026-09-11 and an unrecognised business message is now filed under it so Layer 2 has a
    # corpus to select — but the hint carries `source="fallback"`, nothing read this message and
    # concluded anything, and `coverage_verdict` therefore ignores it. The property this test
    # holds is unchanged and is asserted below: a fallback must not become a verdict about the
    # tenant's sources.
    assert [(h.domain, h.source) for h in res.gated.domain_hints] == [("admin", "fallback")]
    assert res.gated.coverage_ready is None
    assert asked == [], "coverage was consulted for a domain nobody classified this event into"


# ---------------------------------------------------------------------------------------------
# ACCEPTANCE 3 — the declaration is FILED. `source_coverage` had no writer for its whole life.
# ---------------------------------------------------------------------------------------------

@pytest.mark.gate
def test_building_a_coverage_fn_files_the_declaration_in_memory():
    """The factory writes as a side effect, so a sweep files coverage without the sweep having to
    remember to. Asserted against the in-memory store first: the behaviour is the factory's, not
    Postgres's, and it must hold on a deployment with no database at all."""
    from genios_engine.capture.coverage.store import InMemoryCoverageStore
    from genios_engine.platform.wiring import make_coverage_fn

    store = InMemoryCoverageStore()
    conns = [Connection(org_id="org_cov", source_type=s, connection_id=f"con_{s}")
             for s in ("gmail", "hubspot")]
    verdict = make_coverage_fn("org_cov", connections=conns, engine=None, store=store, now=NOW)

    assert verdict("sales")["coverage_ready"] is True
    rows = {r.domain: r for r in store.list("org_cov")}
    assert set(rows) == {"sales", "support", "admin", "fundraising"}
    assert rows["sales"].coverage_ready is True
    assert rows["sales"].computed_at == NOW


@pytest.mark.gate
@pytest.mark.pg
def test_source_coverage_has_rows_for_the_org_after_a_sweep_declares():
    """Doc 01's second acceptance line, against the real table. `source_coverage` was created in
    migration 0002 and referenced afterwards only by the deletion cascade — a table nothing wrote,
    carefully cleaned up."""
    import os

    from genios_engine.capture.coverage.store import PostgresCoverageStore
    from genios_engine.platform.wiring import make_coverage_fn

    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the real coverage table is not exercised")
    org = "org_scratch_tests"                      # seeded by tests/conftest.py; FK-satisfying
    store = PostgresCoverageStore(url)
    conns = [Connection(org_id=org, source_type=s, connection_id=f"con_{s}")
             for s in ("gmail", "hubspot")]

    summary = run_sync(FakeGmailConnector(), org_id=org, connection_id="con_cov",
                       repo=InMemorySourceEventRepository(),
                       coverage_fn=make_coverage_fn(org, connections=conns, engine=None,
                                                    store=store, now=NOW))
    assert summary.gated and all(g.coverage_ready is True for g in summary.gated)
    filed = {r.domain: r for r in store.list(org)}
    assert filed["sales"].coverage_ready is True
    assert filed["support"].coverage_ready is False


# ---------------------------------------------------------------------------------------------
# The structural half — a FIFTH entry must not be addable silently unwired.
# ---------------------------------------------------------------------------------------------

def _call_sites(*names: str) -> list[tuple[str, int, ast.Call]]:
    """Every call to one of `names` anywhere in the engine, by file and line."""
    wanted = set(names)
    sites: list[tuple[str, int, ast.Call]] = []
    for path in sorted(ENGINE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name in wanted:
                sites.append((str(path.relative_to(ENGINE_ROOT)), node.lineno, node))
    return sites


def _undeclared(sites) -> list[str]:
    """Sites that pass neither `coverage_fn=` nor a `**kwargs` that could carry it."""
    return [f"{path}:{line}" for path, line, call in sites
            if not any(kw.arg in (None, "coverage_fn") for kw in call.keywords)]


@pytest.mark.gate
def test_every_capture_entry_in_the_engine_declares_coverage():
    """The ratchet. A grep is how the hole was FOUND; an assertion is how it stays closed.

    A new capture entry that forgets `coverage_fn=` fails here by name and line, instead of
    quietly reintroducing a population of events nobody can account for. `**kw` counts: the
    sync runner forwards its own declared parameter that way.
    """
    sites = _call_sites("capture_event")
    assert len(sites) >= 4, (
        "the four known capture entries (sync runner, webhook, intake, /dev/ingest-sample) "
        f"were not all found — the scan is broken, not the code: {sites}")
    unwired = _undeclared(sites)
    assert unwired == [], (
        "these capture entries emit events with coverage_ready=None: " + ", ".join(unwired))


@pytest.mark.gate
def test_every_manual_intake_call_site_declares_coverage_too():
    """The third half of the ratchet — the one the first two could not see, and did not.

    `capture/intake.py` forwards its own `coverage_fn` into `capture_event`, so the
    `capture_event` scan above is satisfied by ONE line inside intake no matter how many callers
    of `ingest_manual` pass nothing. Both real callers passed nothing: `api/upload_routes.py`
    (every chunk of every uploaded file) and `api/knowledge_routes.py` (every piece of company
    canon a founder writes down) produced exactly the `coverage_ready=None` population W9 was
    built to end, through a door the gate was not looking at.
    """
    sites = _call_sites("ingest_manual", "ingest_internal_knowledge")
    assert len(sites) >= 2, f"the manual intake doors were not all found: {sites}"
    unwired = _undeclared(sites)
    assert unwired == [], (
        "these intake doors emit events with coverage_ready=None: " + ", ".join(unwired))


@pytest.mark.gate
def test_every_sweep_call_site_declares_coverage_too():
    """The second half of the ratchet, and the one the first half cannot see.

    `run_sync` forwards its own `coverage_fn` parameter into `capture_event`, so the AST check
    above is satisfied by ONE line inside `sync_runner.py` no matter how many callers of
    `run_sync` pass nothing. Every sweep entry — the auto-sync tick, the cross-org cron, the
    per-connection trigger, both onboarding backfills — has to supply it or its events go out
    undeclared exactly as before.
    """
    sites = _call_sites("run_sync", "backfill_drain")
    assert len(sites) >= 7, f"the sweep entries were not all found: {sites}"
    unwired = _undeclared(sites)
    assert unwired == [], (
        "these sweeps emit events with coverage_ready=None: " + ", ".join(unwired))
