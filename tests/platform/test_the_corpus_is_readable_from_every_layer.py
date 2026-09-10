"""One corpus reader, because four layers need it and none may import the others.

    pytest tests/platform/test_the_corpus_is_readable_from_every_layer.py -q

`capture` must know which business vocabularies exist; `context` which situation types may be
minted; `packs` which corpora to compile; `platform` which domains a tenant may activate. When
`capture/domain/hints.py` and `capture/coverage/model.py` reached UP into `packs` to find out,
`tests/test_layer_topology.py` refused it in the same run — *"a package may import same-or-lower
layers only … lower layers never import up."*

`platform` is the answer the architecture already had: CROSS_CUTTING, *"the composition root,
may import anything"*.
"""

from __future__ import annotations

import pytest

from genios_engine.platform.corpus import (
    authored_domain_ids,
    authored_domains,
    corpus_root,
    engine_domain_aliases,
    speaks_for,
)

pytestmark = pytest.mark.unit


def corpus(tmp_path, name, domain_id, extra=""):
    (tmp_path / name).mkdir(exist_ok=True)
    (tmp_path / name / "domain.yaml").write_text(
        f"identity:\n  id: {domain_id}\n  name: {name}\n  version: 0.1.0\n{extra}")


@pytest.fixture
def authored(tmp_path, monkeypatch):
    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root", lambda: tmp_path)
    return tmp_path


# =============================================================================================
# It reads the real corpus.
# =============================================================================================
def test_the_root_is_the_real_directory():
    """Two hand-counted `parents[]` depths of the same directory — `authoring.py` used 3 and
    `expertise_routes.py` used 2 — are one refactor away from disagreeing silently."""
    assert corpus_root().is_dir()
    assert corpus_root().name == "Domain Expertise"


def test_the_three_shipped_corpora_are_found():
    assert set(authored_domain_ids()) >= {"admin", "customer_support", "sales"}


# =============================================================================================
# One bad corpus must not hide the others.
# =============================================================================================
def test_a_file_that_will_not_parse_costs_only_itself(authored):
    """A tenant whose logistics file has an unbalanced quote should lose logistics, not sales."""
    corpus(authored, "Good Expertise", "good")
    (authored / "Broken Expertise").mkdir()
    (authored / "Broken Expertise" / "domain.yaml").write_text("identity: [unclosed\n")

    assert authored_domain_ids() == ("good",)


def test_an_entry_with_no_id_is_skipped(authored):
    corpus(authored, "Good Expertise", "good")
    (authored / "Nameless Expertise").mkdir()
    (authored / "Nameless Expertise" / "domain.yaml").write_text("identity:\n  name: Nameless\n")

    assert authored_domain_ids() == ("good",)


def test_underscore_folders_and_folders_without_a_domain_file_are_skipped(authored):
    corpus(authored, "Good Expertise", "good")
    (authored / "_schema").mkdir()
    (authored / "_schema" / "domain.yaml").write_text("identity:\n  id: schema\n")
    (authored / "Notes").mkdir()

    assert authored_domain_ids() == ("good",)


def test_a_missing_root_yields_nothing_rather_than_raising(monkeypatch, tmp_path):
    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root",
                        lambda: tmp_path / "does-not-exist")

    assert authored_domain_ids() == ()
    assert list(authored_domains()) == []


def test_an_unreadable_root_yields_nothing_rather_than_raising(monkeypatch):
    def boom():
        raise OSError("volume not mounted")

    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root", boom)

    assert authored_domain_ids() == ()


def test_the_contents_come_back_whole(authored):
    """Each caller reads a different block — `hints`, `coverage`, `situation_types` — so the
    reader hands back the document rather than pre-selecting one layer's slice."""
    corpus(authored, "Logistics Expertise", "logistics",
           "hints:\n  rank: 15\ncoverage:\n  required: [communication]\n")

    _domain_id, data = next(iter(authored_domains()))

    assert data["hints"]["rank"] == 15
    assert data["coverage"]["required"] == ["communication"]


# =============================================================================================
# The alias table, read without importing upward.
# =============================================================================================
def test_the_alias_table_is_the_one_packs_owns():
    from genios_engine.packs.compiler.capability_resolver import DOMAIN_ALIASES

    assert engine_domain_aliases() == dict(DOMAIN_ALIASES)


@pytest.mark.parametrize("name", ["sales", "admin", "support", "customer_support",
                                  "fundraising", "investor"])
def test_a_shipped_set_speaks_for_every_name_that_resolves_into_it(name):
    """THE BUG THIS FUNCTION EXISTS FOR. `DOMAIN_ALIASES` is many-to-one, so inverting it is not
    a function: `reverse['sales']` gave `'investor'`, `sales` looked like a brand-new authored
    domain, and its real coverage requirements were overwritten with a bare default — a tenant
    with a connected CRM told sales coverage was complete without one."""
    assert speaks_for(name, {"sales", "admin", "support", "fundraising"})


def test_a_genuinely_new_domain_is_not_spoken_for():
    assert not speaks_for("logistics", {"sales", "admin", "support", "fundraising"})
