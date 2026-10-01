r"""Plane D `U07` · the three-way diagnosis reads a field, not a sentence.

⛔ WHAT WAS WRONG. `scripts/corpus_route_probe.py` — the tool routing coverage is READ from — told
four causes apart with three substring tests and an `else`::

    text_ = str(exc)
    if "unknown domains" in text_:   key = "unknown_domain_hint"
    elif "no authored" in text_:     key = "no_route_predicate"
    else:                            key = "no_route_type"

Measured against the resolver's four real messages: `domain_not_activated` matched neither pattern
and was reported as `no_route_type`. An operations fact published as an authoring gap.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib

import pytest

from genios_engine.packs.compiler.errors import NoExpertiseRoute

REPO = pathlib.Path(__file__).resolve().parents[2]


def _probe():
    spec = importlib.util.spec_from_file_location(
        "corpus_route_probe", REPO / "scripts/corpus_route_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)                                      # type: ignore[union-attr]
    return module


# ── the mapping is closed both ways ───────────────────────────────────────────────────────────

def test_every_refusal_reason_has_a_probe_key():
    """A reason with no key would raise mid-probe, on a tenant, in a reporting run."""
    assert set(_probe()._PROBE_KEY) == NoExpertiseRoute.REASONS


def test_no_probe_key_exists_for_something_that_cannot_be_raised():
    """Dead vocabulary in a report somebody makes a decision from."""
    assert set(_probe()._PROBE_KEY) - NoExpertiseRoute.REASONS == set()


def test_the_two_keys_that_already_existed_kept_their_names():
    """⛔ Reports and saved CSVs read them. Renaming a key to improve a taxonomy breaks every
    reader of the measurement the taxonomy was improved for."""
    table = _probe()._PROBE_KEY
    assert table["predicate_rejected"] == "no_route_predicate"
    assert table["no_situation_binds_type"] == "no_route_type"
    assert table["unknown_domain_hint"] == "unknown_domain_hint"


def test_the_two_that_used_to_collapse_now_have_different_keys():
    table = _probe()._PROBE_KEY
    assert table["domain_not_activated"] != table["no_situation_binds_type"]


def test_the_four_keys_are_distinct():
    table = _probe()._PROBE_KEY
    assert len(set(table.values())) == 4


# ── and no module diagnoses a refusal from its text ───────────────────────────────────────────

_WATCHED = (
    "scripts/corpus_route_probe.py",
    "genios_engine/reason/domain_shadow.py",
    "genios_engine/packs/compiler/capability_resolver.py",
)


@pytest.mark.parametrize("relative", _WATCHED)
def test_no_watched_module_compares_against_an_exceptions_text(relative):
    """⛔ AST, NOT A GREP — AND THAT IS NOT A STYLE CHOICE HERE. The probe now carries the OLD code
    quoted in a comment, precisely so the next reader understands why the field exists. A grep for
    `str(exc)` would match that comment and fail on the documentation of the fix.
    """
    tree = ast.parse((REPO / relative).read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for side in (node.left, *node.comparators):
            if (isinstance(side, ast.Call) and isinstance(side.func, ast.Name)
                    and side.func.id == "str"
                    and any(isinstance(a, ast.Name) and a.id in ("exc", "e", "err", "error")
                            for a in side.args)):
                offenders.append(f"{relative}:{node.lineno}")
    assert not offenders, offenders


@pytest.mark.parametrize("relative", _WATCHED)
def test_no_watched_module_assigns_a_key_from_a_message_substring(relative):
    """The other half of the same shape: `if "some words" in text:` where `text` came from an
    exception. Caught by looking for a `Compare` whose `In` operand is a name the module bound from
    `str(exc)` — which, now that none exists, must simply be absent."""
    src = (REPO / relative).read_text()
    tree = ast.parse(src)
    bound_from_exception: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "str"
                and any(isinstance(a, ast.Name) and a.id in ("exc", "e", "err")
                        for a in node.value.args)):
            bound_from_exception |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    assert not bound_from_exception, f"{relative} binds {sorted(bound_from_exception)} from an " \
                                    f"exception's text"


def test_the_probe_reads_the_reason_attribute():
    """The positive half: absence of a grep is not presence of a field."""
    tree = ast.parse((REPO / "scripts/corpus_route_probe.py").read_text())
    handler = [h for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler)
               and isinstance(h.type, ast.Name) and h.type.id == "NoExpertiseRoute"]
    assert len(handler) == 1
    rendered = ast.unparse(handler[0])
    assert "exc.reason" in rendered
    assert "_PROBE_KEY" in rendered


def test_the_sample_message_is_still_captured_for_a_human():
    """The structured field replaces the DIAGNOSIS, not the evidence. An operator still needs the
    sentence to see which situation and which domains."""
    rendered = ast.unparse(ast.parse((REPO / "scripts/corpus_route_probe.py").read_text()))
    assert "samples.setdefault" in rendered
