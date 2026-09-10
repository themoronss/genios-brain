"""The branch's signature defect, made mechanical.

    pytest tests/test_nothing_is_written_and_never_read.py -q

THE SHAPE, found ten separate times by an eight-group audit of this branch: **a capability exists
and nothing consumes it at the point that needs it.** Not a bug in any one module — every one of
these was correct code with tests passing:

    textguard                              written, unimported by capture
    the `owns` edge                        written, never read
    derived.timeline.condition_review      written since it shipped, surfaced by nothing
    derived.contract_spend.summary         a correlator runs every drain, nobody reads its answer
    derived.timeline.dormant_condition     written every sweep, read by nothing
    correlation_conversation               shipped on this branch, imported by no engine module
    contracts/outcomes                     11 outcomes, 42 tests, zero importers
    correlation_organization.resolve_people  written, tested eight ways, called by nothing
    graph_nodes.attributes                 two readers, zero writers
    HoldReason.SOURCE_COVERAGE_INSUFFICIENT  a hold whose metadata key has no writer

Every one passed every gate, because a test suite tests what a module DOES, not whether anybody
asks. This file asks.

WHAT IT IS NOT. It is not a general dead-code detector — Python has those and they are noisy on a
codebase with dynamic dispatch, plugin registries and API routers. It is a NAMED ROSTER: modules
whose whole reason to exist is that something else calls them. Adding a module here is a promise;
removing one requires saying why in `RETIRED`.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = pytest.mark.unit

ENGINE = pathlib.Path("genios_engine")

#: Modules that exist ONLY to be consumed. Each entry is `module stem -> what must import it`,
#: and "what must import it" is a prose reminder for whoever the failure lands on, not a check.
#:
#: THE EIGHT CORRELATORS ARE ALL HERE because three of them were dead when this was written.
#: `correlation.py` is the anchor/tool/user join; the rest are their own modules.
MUST_BE_CONSUMED: dict[str, str] = {
    "correlation": "context/pipeline.py and structured.py, via correlate_event",
    "correlation_resource": "context/runner.py, via refresh_contract_spend",
    "correlation_timeline": "context/runner.py and condition_situations.py",
    "correlation_dependency": "context/runner.py and importance.py",
    "correlation_conversation": "context/outreach_situations.py `_gather`, via find_campaigns",
    "correlation_organization": "context/outreach_situations.py `_gather`, via find_organizations",
    "correlation_domain": "reason/domain_shadow.py, via read_contradictions",
    # L2 readings and the surfaces that turn them into situations.
    "condition_situations": "context/outreach_situations.py READINGS",
    "outreach_situations": "context/runner.py, via refresh_state_situations",
    "support_situations": "context/runner.py, via refresh_support_situations",
    "meeting_touch": "context/runner.py, via refresh_channel_touch_situations",
    "document_register": "context/runner.py, via refresh_document_situations",
    "periodic": "context/runner.py, via refresh_period_situations",
    "waiting": "context/runner.py, via compute_waiting",
    # Contracts that only mean something when a producer or consumer names them.
    "abstention": "deliver/pipeline.py and card_builder.py",
    # Added the moment it gained a consumer, and it was DEAD when this roster was written:
    # eleven outcomes, forty-two tests, zero importers. `deliver/pipeline` now folds the push
    # decision through `project`/`interrupts`, which is what gave ASK_DECISION a route.
    "outcomes": "deliver/pipeline.py, via project() and interrupts()",
}

#: Retired entries, kept so a reader can see the module was considered and why it left. A module
#: deleted for being unconsumed belongs here, not silently absent.
RETIRED: dict[str, str] = {
    "correlation_organization.resolve_people":
        "Deleted 2026-09-10. Written, tested eight ways, called by nothing: `_gather` asks for "
        "every organisation and lets `read_organization_silence` narrow, which is the correct "
        "order. `correlation_domain._SITUATIONS_BY_PERSON` does the same walk for a consumer "
        "that exists.",
}


#: DERIVED FACTS AND HOLD REASONS — the same defect, one level down from a module.
#:
#: A module with no importer is caught above. A FIELD with no reader is not: the module is
#: imported, the sweep runs it, the row is written, and nothing ever selects it. Three of the ten
#: instances in the audit were this shape — `derived.contract_spend.summary`,
#: `derived.timeline.dormant_condition`, `graph_nodes.attributes` — and so was
#: `HoldReason.SOURCE_COVERAGE_INSUFFICIENT`, a gate that could not fire because the metadata key
#: it reads had no writer.
#:
#: Each entry names what must read it. A field here with no reader fails; a field that should not
#: have one belongs in `KNOWN_UNREAD` with a reason and the condition that would move it.
MUST_BE_READ: dict[str, str] = {
    "derived.timeline.condition_review": "context/condition_situations.py",
    "thread.days_waiting": "context/outreach_situations.py, read_awaiting_response",
    "thread.ball_in_court": "context/correlation_domain.py, as the exclusion arbiter",
    "commitment.status": "context/outreach_situations.py, read_overdue_commitments",
    "requires_complete_coverage": "context/situation_publisher.py, _preflight",
    "contradicted_by": "context/situation_publisher.py, _preflight",
}

#: Written on purpose and read by nothing YET. Each says why it is not a defect to fix today and
#: what would change that. An entry here is a declared exception a reviewer can argue with; the
#: silent version is what this whole file exists to end.
KNOWN_UNREAD: dict[str, str] = {
    "derived.contract_spend.summary":
        "The Cross Resource correlator publishes it every drain and nothing selects it. Building "
        "a reading TODAY would add more dead code, not less: `_resource_inputs` reads only nodes "
        "typed contract/subscription/invoice/payment/spend, and nothing mints those on a tenant "
        "using the built-in mappings — only a client-supplied GENIOS_STRUCTURED_MAPPINGS does. So "
        "the field is empty on every real tenant and a consumer would have nothing to consume. "
        "MOVES WHEN: a tenant emits those node types, at which point "
        "`admin.sit.spend_against_a_commitment` is the authored situation already waiting for it.",
    "derived.timeline.dormant_condition":
        "The third of `correlation_timeline`'s three published fields — parsed conditions that "
        "are not yet true, one row per subject node. `condition_review` (the unparseable ones) "
        "now reaches a card through `condition_situations.py`; this one is the PARSED half, and "
        "surfacing it needs a situation that can say 'this becomes true when X', which nothing "
        "authors yet. MOVES WHEN: that situation is authored.",
}


#: A field whose writer BUILDS the name rather than spelling it — `correlation_timeline` writes
#: `f"{FACT_PREFIX}.condition_review"` — is invisible to a literal scan. Naming the shared
#: constant makes the writer countable, and importing that constant on the reader's side is what
#: made the two spellings one in the first place. A field with no entry here is scanned by its
#: literal alone, which is the right default.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "derived.timeline.condition_review": ("FIELD_REVIEW", "REVIEW_FIELD"),
    "derived.contract_spend.summary": ("derived.contract_spend.summary",),
    "derived.timeline.dormant_condition": ("FIELD_DORMANT",),
}


def _tokens_for(field: str) -> tuple[str, ...]:
    return (field, *FIELD_ALIASES.get(field, ()))


def _modules_mentioning(field: str) -> list[str]:
    """Files that name the field, by literal or by its shared constant."""
    tokens = _tokens_for(field)
    out: list[str] = []
    for path in ENGINE.rglob("*.py"):
        try:
            body = path.read_text()
        except (OSError, UnicodeDecodeError):  # pragma: no cover
            continue
        if any(f'"{t}"' in body or f"'{t}'" in body or f" {t}" in body for t in tokens):
            out.append(str(path))
    return out


def _fields_read_anywhere() -> set[str]:
    """Every string literal in genios_engine/ that names one of the rosters' fields.

    A field is READ if its name appears in a module other than the one that writes it. Crude on
    purpose: the alternative is tracing SQL, and a false PASS here is worse than a false FAIL,
    which a reviewer resolves in one grep.
    """
    seen: set[str] = set()
    watched = set(MUST_BE_READ) | set(KNOWN_UNREAD)
    for path in ENGINE.rglob("*.py"):
        try:
            body = path.read_text()
        except (OSError, UnicodeDecodeError):  # pragma: no cover
            continue
        for field in watched:
            if body.count(f'"{field}"') + body.count(f"'{field}'") > 0:
                seen.add(field)
    return seen


def _module_paths() -> dict[str, pathlib.Path]:
    """Every module in the roster, resolved to its file. A roster entry naming nothing is itself
    a defect — the module was renamed or deleted and this list did not notice."""
    found: dict[str, pathlib.Path] = {}
    for path in ENGINE.rglob("*.py"):
        if path.stem in MUST_BE_CONSUMED:
            found.setdefault(path.stem, path)
    return found


def _imports_in(path: pathlib.Path) -> set[str]:
    """Module stems this file imports, from real AST nodes rather than a text grep.

    A grep matches the module's name inside its own prose — every one of these files documents the
    others at length — and a guard fooled by a comment is worse than none.
    """
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover — a broken file fails elsewhere
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.rsplit(".", 1)[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module.rsplit(".", 1)[-1])
                # `from genios_engine.context import waiting` names the module in the alias.
                for alias in node.names:
                    out.add(alias.name)
    return out


def _consumers() -> dict[str, set[str]]:
    """module stem -> the engine files that import it, excluding itself."""
    paths = _module_paths()
    consumers: dict[str, set[str]] = {stem: set() for stem in MUST_BE_CONSUMED}
    for path in ENGINE.rglob("*.py"):
        imported = _imports_in(path)
        for stem in MUST_BE_CONSUMED:
            if stem in imported and path != paths.get(stem):
                consumers[stem].add(str(path))
    return consumers


# =============================================================================================
# The guard.
# =============================================================================================
def test_every_module_on_the_roster_still_exists():
    """A roster that names a deleted module quietly stops guarding it."""
    missing = sorted(set(MUST_BE_CONSUMED) - set(_module_paths()))

    assert not missing, (
        f"the roster names {missing}, which no file in genios_engine/ provides. Either the "
        f"module was renamed (update the roster) or deleted (move it to RETIRED with a reason).")


@pytest.mark.parametrize("stem", sorted(MUST_BE_CONSUMED))
def test_something_in_the_engine_actually_imports_it(stem):
    """THE WHOLE POINT. A module nothing imports is not shipped intelligence — it is a file.

    Parametrised so a failure names the one module that went dark, rather than handing whoever
    broke it a list of sixteen.
    """
    consumers = _consumers()[stem]

    assert consumers, (
        f"NOTHING IN genios_engine/ IMPORTS {stem}.py.\n"
        f"  Expected consumer: {MUST_BE_CONSUMED[stem]}\n"
        f"  This is the defect this file exists for. Two honest fixes: wire it at the seam that "
        f"needs it, or delete it and record why in RETIRED. Adding it to neither, and leaving "
        f"its tests green, is what put ten of these in one branch.")


def test_the_eight_named_correlators_are_all_on_the_roster():
    """The architecture names eight. Three of them were dead when this file was written, and a
    roster that quietly lost one would let the fourth go the same way."""
    correlators = {stem for stem in MUST_BE_CONSUMED if stem.startswith("correlation")}

    assert len(correlators) == 7, sorted(correlators)   # correlation.py carries Tool AND User


def test_the_guard_is_not_vacuous():
    """A checker that cannot fail passes forever. This proves the import scan finds real edges:
    at least one roster module has a consumer, and the scanner never counts a module as its own.
    """
    consumers = _consumers()
    paths = _module_paths()

    assert any(consumers.values()), "the AST import scan found no edges at all — it is broken"
    for stem, files in consumers.items():
        assert str(paths[stem]) not in files, f"{stem} counted as its own consumer"


def test_prose_alone_does_not_count_as_a_consumer():
    """The reason this reads the AST rather than grepping. Every one of these modules documents
    the others in long comments; `contracts/outcomes` was found dead precisely because its only
    mention outside tests was a sentence in `deliver/executive_bridge.py`."""
    prose_only = ast.parse(
        "# correlation_domain read_contradictions is described here\n"
        "'''correlation_conversation is the fifth correlator.'''\n")
    stems = set()
    for node in ast.walk(prose_only):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            stems.add(node)

    assert not stems


# =============================================================================================
# The same defect one level down: a field, not a module.
# =============================================================================================
@pytest.mark.parametrize("field", sorted(MUST_BE_READ))
def test_a_field_something_writes_is_read_by_something_else(field):
    """`derived.timeline.condition_review` was written since the correlator shipped and surfaced
    by nothing; twenty-four of them sat unread on the pilot. `requires_complete_coverage` was the
    inverse — a gate reading a key nobody wrote, so a hold reason that could never fire."""
    files = _modules_mentioning(field)

    assert len(files) >= 2, (
        f"{field} appears in {files or 'no file'} — one module cannot be both its writer and its "
        f"reader.\n  Expected reader: {MUST_BE_READ[field]}\n"
        f"  Either wire it, or move it to KNOWN_UNREAD with a reason and the condition that "
        f"would move it back.")


def test_every_known_unread_field_says_what_would_change_it():
    """A permanent exception list is a way to never fix anything. Each entry has to name the
    condition under which it stops being an exception."""
    for field, reason in KNOWN_UNREAD.items():
        assert "MOVES WHEN:" in reason, field
        assert len(reason.split()) >= 30, field


def test_the_two_rosters_do_not_overlap():
    """A field cannot be both required-to-be-read and known-unread; one of the two entries would
    silently win and nobody would know which."""
    assert not (set(MUST_BE_READ) & set(KNOWN_UNREAD))


def test_every_hold_reason_has_a_writer_for_the_key_it_reads():
    """A hold nothing can trigger is a gate that reports healthy forever.
    `SOURCE_COVERAGE_INSUFFICIENT` read `requires_complete_coverage`, nothing wrote it, and the
    only test that exercised it set the key by hand — so the guard passed and the gate was dead.
    """
    import inspect

    from genios_engine.context import situation_bso, situation_publisher

    gate = inspect.getsource(situation_publisher._preflight)
    writers = inspect.getsource(situation_bso)

    keys = {"importance_source", "evidence_verified_spans", "split_required",
            "requires_complete_coverage", "conflict_ids", "pattern_activated",
            "contradicted_by"}
    for key in sorted(keys):
        assert f'"{key}"' in gate, f"{key} is no longer read by the gate"
        assert f'"{key}"' in writers, (
            f"the gate reads {key!r} and situation_bso never writes it — a hold reason nobody "
            f"can trigger is a gate that reports healthy forever")
