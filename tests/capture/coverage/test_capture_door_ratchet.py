"""G9 · W9 defect #4 and #5 — coverage_ready on EVERY door, and a guard that can SEE every door.

Defect #4 is two doors that still emit `coverage_ready=None`: `POST /human-events` and
`POST /agent-events`. Defect #5 is the reason nobody noticed — the ratchet in
`test_coverage_wiring.py` enumerates call sites of a HAND-WRITTEN list of names
(`capture_event`, `ingest_manual`, `ingest_internal_knowledge`, `run_sync`, `backfill_drain`).
`ingest_human_event` and `ingest_agent_event` are not on that list, so the gate reported a fully
wired system while two doors in `api/routes.py` fed nulls into `source_events`.

A name list is the same class of guard as a convention: it protects exactly the doors somebody
remembered. So the ratchet here does not use one. `capture/coverage/audit.py` starts at
`capture_event` and closes over FORWARDING — a function that hands a door its own `coverage_fn`
parameter or its own `**kwargs` IS a door, whatever it is called — and then judges every call to
every discovered door. `ingest_human_event` and `ingest_agent_event` are found by what they do.
"""

from __future__ import annotations

import pathlib
import textwrap
from datetime import datetime, timezone

import pytest

from genios_engine.capture.coverage.audit import audit_capture_doors
from genios_engine.capture.coverage.declaration import declare_coverage
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.connection import Connection
from genios_engine.contracts.events import AgentEvent, HumanEvent

WAVE = "W9"
GATE = "G9"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: Every tree in this repository that can land a real `source_events` row. `scripts/` is in it on
#: purpose: `scripts/gmail_l1.py` runs a real sweep against a real database, and an undeclared
#: sweep there produces exactly the population W9 exists to end.
SOURCE_ROOTS = (REPO_ROOT / "genios_engine", REPO_ROOT / "scripts")


def _coverage_fn(*sources: str, org_id: str = "org_cov"):
    conns = [Connection(org_id=org_id, source_type=s, connection_id=f"con_{s}") for s in sources]
    return declare_coverage(org_id=org_id, connections=conns, company_knowledge_count=0,
                            computed_at=NOW).for_domain


# ---------------------------------------------------------------------------------------------
# DEFECT #4 — the two doors themselves.
# ---------------------------------------------------------------------------------------------

#: The org `tests/conftest.py` seeds into `orgs`. The route doors write to `human_events` /
#: `agent_registry`, both of which carry an org FK, so a made-up tenant id passes hermetically
#: and fails the moment the same test runs against the real schema — which is the lane that
#: matters, since the FK is what production has.
SEEDED_ORG = "org_scratch_tests"


def _human_event(org_id: str = SEEDED_ORG) -> HumanEvent:
    return HumanEvent(
        type="human.manual_context", org_id=org_id, actor_id="u_1",
        target={"entity": "Acme"},
        detail={"text": "Acme asked for pricing and a contract before the deal closes "
                        "next quarter."},
        occurred_at=NOW)


def _agent_event(org_id: str = SEEDED_ORG) -> AgentEvent:
    return AgentEvent(
        org_id=org_id, agent_id="agent_1", client_event_id="k_1", action_taken="email_sent",
        target_hint={"email": "priya@acme.com"}, result="sent",
        detail={"subject": "Pricing and contract for the Acme deal"}, occurred_at=NOW)


@pytest.mark.gate
def test_the_human_event_route_emits_a_non_null_coverage_verdict():
    """`POST /human-events` is a capture entry: the human's correction becomes a `source_events`
    row L2 reads. It called `ingest_human_event` with no `coverage_fn`, so every correction a
    founder ever made entered the population with `coverage_ready=None`."""
    seen = _call_route_human()
    assert seen.gated is not None
    assert seen.gated.domain_hints, "the fixture produced no hint, so the assertion is vacuous"
    assert seen.gated.coverage_ready is True


@pytest.mark.gate
def test_the_agent_event_route_emits_a_non_null_coverage_verdict():
    """`POST /agent-events` — same hole, different door. An executor's completed action is how
    GeniOS learns outcomes; undeclared, every outcome was unaccountable."""
    seen = _call_route_agent()
    assert seen.gated is not None
    assert seen.gated.domain_hints, "the fixture produced no hint, so the assertion is vacuous"
    assert seen.gated.coverage_ready is True


@pytest.mark.gate
def test_the_routes_declare_coverage_for_their_own_tenant():
    """Coverage is a fact about ONE org's sources. A door that declared with the wrong org would
    be worse than one that declared nothing — a confident verdict computed from another tenant's
    connections."""
    assert _asked_orgs(_call_route_human) == [SEEDED_ORG]
    assert _asked_orgs(_call_route_agent) == [SEEDED_ORG]


# -- the two route calls, with the real pipeline underneath and only observation added ---------

def _route_probe(kind: str, org_id: str = SEEDED_ORG):
    """Call the real route function, with the real intake door and the real pipeline, recording
    the CaptureResult and every org coverage was declared for."""
    import genios_engine.api.routes as R
    from genios_engine.capture import intake
    from genios_engine.platform.auth import AuthCtx

    captured: list = []
    asked: list[str] = []
    real = getattr(intake, f"ingest_{kind}_event")

    def _spy(ev, **kw):
        res = real(ev, **kw)
        captured.append(res)
        return res

    def _fn_for(org: str, connections=None):
        asked.append(org)
        return _coverage_fn("gmail", "hubspot", org_id=org)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(intake, f"ingest_{kind}_event", _spy)
        mp.setattr(R, "_coverage_fn_for", _fn_for)
        mp.setattr(R, "_repo", InMemorySourceEventRepository())
        mp.setattr(R, "_payload_store", None)
        mp.setattr(R, "_prepared_store", None)
        mp.setattr(R, "_trace_repo", None)
        if kind == "human":
            R.human_event(_human_event(org_id), ctx=AuthCtx(org_id=org_id, actor_id="u_1"))
        else:
            R._agent_registry.register(org_id, "agent_1", "secret_key", ["email_sent"])
            R.agent_event(_agent_event(org_id), x_agent_key="secret_key")
    assert captured, "the route did not reach the intake door at all"
    return captured[0], asked


def _call_route_human():
    return _route_probe("human")[0]


def _call_route_agent():
    return _route_probe("agent")[0]


def _asked_orgs(call) -> list[str]:
    kind = "human" if call is _call_route_human else "agent"
    return _route_probe(kind)[1]


# ---------------------------------------------------------------------------------------------
# DEFECT #5 — the ratchet that can see a door it was never told about.
# ---------------------------------------------------------------------------------------------

@pytest.mark.gate
def test_no_capture_door_call_site_in_the_repo_omits_coverage():
    """THE GATE. Every call to every discovered door declares coverage, by file and line.

    This is the whole criterion — *every swept event carries a non-null `coverage_ready`* —
    expressed structurally, so it holds for events no test happens to produce.
    """
    audit = audit_capture_doors(SOURCE_ROOTS)
    assert audit.undeclared == (), (
        "these capture doors emit events with coverage_ready=None:\n  "
        + "\n  ".join(str(s) for s in audit.undeclared))


@pytest.mark.gate
def test_the_doors_are_discovered_by_forwarding_not_by_a_name_list():
    """The two doors the old ratchet could not see must be in the set, and must be there because
    of what they do. `ingest_human_event` appears nowhere in `audit.py`."""
    audit = audit_capture_doors(SOURCE_ROOTS)
    from genios_engine.capture.coverage import audit as audit_module

    expected = {"capture_event", "run_sync", "backfill_drain", "ingest_manual",
                "ingest_internal_knowledge", "ingest_human_event", "ingest_agent_event"}
    missing = expected - set(audit.doors)
    assert not missing, f"the forwarding closure missed real capture doors: {sorted(missing)}"

    # Prose may name them — that is how the defect is explained. CODE may not: an identifier or
    # a string literal carrying a door's name is a name list wearing a different hat.
    executable = _code_tokens(pathlib.Path(audit_module.__file__))
    for name in ("ingest_human_event", "ingest_agent_event", "ingest_manual", "run_sync",
                 "backfill_drain", "ingest_internal_knowledge"):
        assert name not in executable, (
            f"{name} is hard-coded in audit.py — the scan is a name list again, and the next "
            "door added under a name nobody wrote down is invisible exactly as these were")


def _code_tokens(path: pathlib.Path) -> set[str]:
    """Every identifier and every non-docstring string literal in a module — the parts that can
    act as a hard-coded list. Docstrings and comments are excluded on purpose."""
    import ast as _ast
    tree = _ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = {_ast.get_docstring(n) for n in _ast.walk(tree)
                  if isinstance(n, (_ast.Module, _ast.ClassDef, _ast.FunctionDef,
                                    _ast.AsyncFunctionDef))}
    out: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Name):
            out.add(node.id)
        elif isinstance(node, _ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, _ast.Constant) and isinstance(node.value, str):
            if node.value not in docstrings:
                out.add(node.value)
    return out


@pytest.mark.gate
def test_a_deliberately_unwired_new_door_is_caught(tmp_path: pathlib.Path):
    """The ratchet's own failure test: add a door the scanner has never heard of, leave its
    caller unwired, and the scan must name it. Without this, 'the gate is green' means only
    'nobody added a door today'."""
    tree = _fixture_tree(tmp_path, wired=False)
    audit = audit_capture_doors([tree])

    assert "ingest_smoke_signal" in audit.doors, (
        "a function that forwards its own coverage_fn into capture_event was not recognised "
        "as a door")
    caught = [s for s in audit.undeclared if s.callee == "ingest_smoke_signal"]
    assert len(caught) == 1, f"the unwired fifth door was not caught: {audit.sites}"
    assert caught[0].line == _UNWIRED_LINE
    assert "coverage_ready=None" in caught[0].reason


@pytest.mark.gate
def test_the_same_new_door_passes_once_it_is_wired(tmp_path: pathlib.Path):
    """The other half — the ratchet must not simply fail on everything new."""
    tree = _fixture_tree(tmp_path, wired=True)
    audit = audit_capture_doors([tree])
    assert "ingest_smoke_signal" in audit.doors
    assert audit.undeclared == (), [str(s) for s in audit.undeclared]


#: Line of the unwired caller inside the fixture module below, asserted so a scan that reports
#: the wrong site (the definition, say) does not pass as a catch.
_UNWIRED_LINE = 12

_FIXTURE = '''\
"""A fifth capture door, added the way the previous four were: quietly."""
from genios_engine.capture.pipeline import capture_event


def ingest_smoke_signal(payload, *, org_id, repo, coverage_fn=None):
    """A brand-new door. Its NAME appears in no list anywhere in the engine."""
    return capture_event(payload, org_id=org_id, connection_id="smoke", repo=repo,
                         coverage_fn=coverage_fn)


def smoke_route(payload, org_id, repo):
    return ingest_smoke_signal(payload, org_id=org_id, repo=repo{extra})
'''


def _fixture_tree(tmp_path: pathlib.Path, *, wired: bool) -> pathlib.Path:
    root = tmp_path / "fake_engine"
    root.mkdir(exist_ok=True)
    extra = ", coverage_fn=make_coverage_fn(org_id)" if wired else ""
    (root / "smoke_door.py").write_text(_FIXTURE.format(extra=extra), encoding="utf-8")
    return root


# ---------------------------------------------------------------------------------------------
# How a call site is JUDGED — one row per spelling a call site can use.
# ---------------------------------------------------------------------------------------------

_SPELLINGS = [
    ("bare",            "capture_event(raw, org_id=o, repo=r)",                    False),
    ("explicit None",   "capture_event(raw, repo=r, coverage_fn=None)",            False),
    ("a real fn",       "capture_event(raw, repo=r, coverage_fn=fn)",              True),
    ("a factory call",  "capture_event(raw, repo=r, coverage_fn=_for(org))",       True),
    ("foreign splat",   "capture_event(raw, repo=r, **opts)",                      False),
    ("own kwargs",      "capture_event(raw, repo=r, **kw)",                        True),
]


@pytest.mark.parametrize("label,call,declared", _SPELLINGS, ids=[s[0] for s in _SPELLINGS])
def test_how_each_call_site_spelling_is_judged(tmp_path: pathlib.Path, label: str, call: str,
                                               declared: bool):
    """`coverage_fn=None` is the row that matters: it is what `capture/intake.py` defaulted to,
    and a scan that reads a keyword's presence rather than its VALUE calls it wired.

    `**kw` is accepted only when `kw` is the enclosing function's OWN kwargs — because that is
    what makes the enclosing function a door, so the obligation moves up to ITS callers rather
    than evaporating. A splat of some other dict (`**opts`) proves nothing and is refused.
    """
    root = tmp_path / f"spelling_{label.replace(' ', '_')}"
    root.mkdir()
    (root / "m.py").write_text(textwrap.dedent(f'''\
        from genios_engine.capture.pipeline import capture_event


        def door(raw, o, r, fn, opts, **kw):
            return {call}
        '''), encoding="utf-8")
    audit = audit_capture_doors([root])
    site = next(s for s in audit.sites if s.callee == "capture_event")
    assert site.declared is declared, site.reason


def test_the_scan_reads_source_without_importing_it(tmp_path: pathlib.Path):
    """A module that explodes on import must still be auditable — otherwise the ratchet's
    coverage of the tree depends on which modules happen to be importable in a test process."""
    root = tmp_path / "explodes"
    root.mkdir()
    (root / "boom.py").write_text(textwrap.dedent('''\
        raise RuntimeError("imported")


        def door(raw, repo, coverage_fn=None):
            return capture_event(raw, repo=repo, coverage_fn=coverage_fn)
        '''), encoding="utf-8")
    audit = audit_capture_doors([root])
    assert "door" in audit.doors
