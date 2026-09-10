"""The second gate: an authored corpus compiles, reasons, and could never become a card.

    pytest tests/packs/test_an_authored_corpus_gets_an_authority_lane.py -q

`persist_complete` compares the config snapshot's `pack_id` against the capability's `domain`.
With no `tenant_packs` row for that domain, every capability dies at `domain_shadow.py` under
`no_tenant_pack` — which is exactly what had been happening to all 106 Admin capabilities before
`admin_v1.py` was written by hand. `wiring.py`'s own comment claimed *"Adding a pack = import it
+ register it here … Zero engine change"*, and the first half is the engine change.

So a fifth corpus repeated the Admin outage silently: folder authored, catalog loads it, resolver
routes to it, compile succeeds, zero cards, no error anybody can act on.
"""

from __future__ import annotations

import pytest

from genios_engine.packs import wiring
from genios_engine.packs.admin_v1 import ADMIN_V1
from genios_engine.packs.wiring import BUILTIN_PACKS, _corpus_packs

pytestmark = pytest.mark.unit


def _corpus(tmp_path, name, domain_id, version="0.1.0"):
    (tmp_path / name).mkdir()
    (tmp_path / name / "domain.yaml").write_text(
        f"identity:\n  id: {domain_id}\n  name: {name}\n  version: {version}\n")


def test_an_authored_corpus_gets_a_lane(tmp_path, monkeypatch):
    _corpus(tmp_path, "Clinic Expertise", "clinic", "0.2.0")
    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root",
                        lambda: tmp_path)

    packs = _corpus_packs()

    assert [(p["id"], p["version"]) for p in packs] == [("clinic", "0.2.0")]


def test_a_hand_written_pack_is_never_shadowed(tmp_path, monkeypatch):
    """`admin_v1` carries a real `schema.fields` list with real writers behind it. An empty
    synthesised lane replacing it would silence the extractor for the domain that works."""
    _corpus(tmp_path, "Admin Expertise", "admin")
    _corpus(tmp_path, "Clinic Expertise", "clinic")
    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root",
                        lambda: tmp_path)

    assert [p["id"] for p in _corpus_packs()] == ["clinic"]


def test_a_synthesised_lane_tells_the_extractor_nothing(tmp_path, monkeypatch):
    """THE LOAD-BEARING GUARD. `context/extract/vocab.py::field_vocabulary` unions every pack's
    `schema.fields` into the L2 EXTRACTION PROMPT — a field named here is a field the model is
    told to go and find. A synthesised pack has no evidence that a writer exists for anything, so
    naming one would invite an invented value for a fact nobody stated."""
    _corpus(tmp_path, "Clinic Expertise", "clinic")
    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root",
                        lambda: tmp_path)

    pack = _corpus_packs()[0]

    assert pack["schema"]["fields"] == []
    assert pack["rules"] == []
    assert pack["plays"] == {}


def test_the_shared_budget_is_not_gamed_by_a_new_domain(tmp_path, monkeypatch):
    """Cards from every pack are ranked against each other inside ONE daily budget. A new domain
    with its own gate or bands would win every tie on scale rather than on merit."""
    _corpus(tmp_path, "Clinic Expertise", "clinic")
    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root",
                        lambda: tmp_path)

    assert _corpus_packs()[0]["scoring_defaults"] == ADMIN_V1["scoring_defaults"]


def test_a_corpus_without_an_identity_id_is_skipped(tmp_path, monkeypatch):
    (tmp_path / "Broken Expertise").mkdir()
    (tmp_path / "Broken Expertise" / "domain.yaml").write_text("identity:\n  name: Broken\n")
    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root",
                        lambda: tmp_path)

    assert _corpus_packs() == []


def test_an_unreadable_corpus_does_not_stop_the_shipped_packs(monkeypatch):
    def boom():
        raise OSError("corpus volume not mounted")

    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root", boom)

    assert _corpus_packs() == []
    assert len(BUILTIN_PACKS) == 4


def test_today_the_three_corpora_are_all_hand_written():
    """A live statement, not a fixture: every authored corpus currently has its own pack module,
    so nothing is synthesised. When that stops being true this test says so."""
    assert _corpus_packs() == []


def test_the_registry_registers_both_sets():
    import inspect

    source = inspect.getsource(wiring.make_registry)

    assert "for pack in BUILTIN_PACKS:" in source
    assert "for pack in _corpus_packs():" in source
