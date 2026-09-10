"""Doc 09's closing table, executed as ONE suite — the seven things that must still be true
after eight waves and twenty new modules.

`02-Layer-2-Plan/09-Build-Order-and-Acceptance.md` ends with a table titled **"What must not
regress"**. Every row of it names a property that no single wave owns: item 6 is a promise
`derived.py` makes to `metric_history` (X1), item 3 is a promise `situations.py` makes to
`contracts/situation.py` (X0) and to `situation_bso` (X5), item 4 is a promise `correlation.py`
made in step 3 and that X7's dependency correlators inherited. A property owned by nobody is a
property that drifts, and it drifts silently: each wave's own gate stays green while the
guarantee between them quietly stops holding.

Parts of the table were already pinned when this file was written, and this suite does NOT
restate them. Where a real check exists it is **INVOKED FROM HERE** — loaded off its own file and
called — so that deleting or renaming it turns this file red too, and so the seven read as one
set from one place:

| # | Must not regress                                       | Proved by                                    |
|---|--------------------------------------------------------|----------------------------------------------|
| 1 | no embeddings, no edit distance in identity            | HERE (§1) — the imports and the comparisons  |
| 2 | governed merges — proposal, history, reversibility     | HERE (§2, real Postgres) + test_entity_resolution / test_l2_completeness (source shape) |
| 3 | the confidence VECTOR, never collapsed to a scalar     | HERE (§3, incl. the columns) + test_situation_confidence (the sixth axis) |
| 4 | tenant node excluded from `ANCHOR_PRIORITY`            | test_dependency_correlation §3, INVOKED here |
| 5 | correlation refuses to prioritise/score/recommend      | test_dependency_correlation §2, INVOKED here |
| 6 | `graph_facts` keeps OVERWRITING the current value      | HERE (§6, real Postgres row-growth)          |
| 7 | layer import direction                                 | tests/test_layer_topology.py, INVOKED here   |

**WHAT WAS ACTUALLY UNCHECKED before this file, stated precisely, because "partly covered" is
the state that hides a regression:**

* **Item 1** had one hermetic assertion (`test_matching_is_string_equality_and_nothing_else`)
  that three derived keys differ. Nothing scanned the identity path's IMPORTS or its SQL, so
  `import difflib` or a `%`/`<->` trigram predicate could have landed in `resolve_alias` with
  every existing test still green.
* **Item 2** was covered ENTIRELY by `inspect.getsource(...)` string assertions — eleven of
  them, across two files. `"insert into merge_history" in source` passes whether or not the row
  is ever written, and `"update graph_nodes set valid_to=null" in source` passes whether or not
  a reversal restores anything. No test had ever executed `apply_merge` or `reverse_merge`
  against a database. §2 is that execution.
* **Item 3** was covered as a SHAPE (six axes exist, the sixth composes correctly). Nothing
  checked that the vector SURVIVES THE WRITE — that the five per-axis columns are named by
  every module that inserts a situation and that six distinct axis values read back as six
  distinct numbers rather than as one repeated overall.
* **Item 6** was covered per-writer (`test_publish.py` proves the four L2.4 writers keep their
  windows) but never as the table-level property doc 09 states: **row growth over many sweeps of
  an unchanging value must be FLAT.** §6 measures it, on real Postgres, over both writer shapes.

**No clocks.** Every instant below is a module constant. `derived.compute` and every writer this
file drives take their instant as a parameter, and that is itself one of the things being held.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context import derived
from genios_engine.context.analytic.publish import (PublishAction, publish_derived_fact)
from genios_engine.context.identity import (ALIAS_COMPANY_NAME, ALIAS_PERSON_NAME,
                                            company_name_keys, record_alias,
                                            register_node_identity,
                                            resolve_alias, resolve_company_mention)
from genios_engine.context.merge import apply_merge, reverse_merge
from genios_engine.context.situations import (COVERAGE_UNKNOWN, SCORE_MAX, coverage_is_known,
                                              score_situation)
from genios_engine.contracts.situation import CONFIDENCE_AXES, ConfidenceVector
from genios_engine.platform import identity as platform_identity

_ENGINE_ROOT = Path(__file__).resolve().parents[2] / "genios_engine"
_TESTS_ROOT = Path(__file__).resolve().parents[1]

#: The instant every sweep in this file is evaluated at. A constant, never `now()` — doctrine 4.
AT = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)


def _load(path: Path):
    """Load another test module off its path so its checks can be CALLED from here.

    `tests/` is not a package, so a plain import cannot reach `tests/test_layer_topology.py`
    from `tests/context/`. Loading it by path is what lets item 4, 5 and 7 be *invoked* rather
    than *described*: if somebody deletes the upstream test or renames it, the `getattr` below
    raises and this suite goes red, which is the only way one file can hold seven invariants
    without restating four of them.
    """
    spec = importlib.util.spec_from_file_location(f"_mnr_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call_upstream(path: Path, *names, **kwargs):
    module = _load(path)
    for name in names:
        fn = getattr(module, name, None)
        assert fn is not None, (
            f"{path.name} no longer defines {name}() — doc 09's must-not-regress table points at "
            f"it, so removing it removes the only check of that row")
        fn(**kwargs)
    return module


# =================================================================================================
# 1 · NO EMBEDDINGS, NO EDIT DISTANCE IN IDENTITY   (doc 09 item 1 — `identity.py:25`)
# =================================================================================================
#
# The module docstring already says it ("No edit distance, no embeddings, no '0.87 similar'").
# A docstring is not a check. What follows reads the AST and the SQL, because the three ways this
# regresses are all invisible to a behavioural test that passes: a `difflib` import used on one
# branch, a `%`/`<->` trigram predicate inside one query, and a helper named `_similar` that
# nothing else calls yet.

#: Every module on the identity path — what derives a key, what compares one, what acts on the
#: answer. `merge.py` is included because it EXECUTES the join: a similarity check that snuck in
#: there would be worse than one in the resolver, not better.
IDENTITY_PATH = (_ENGINE_ROOT / "context" / "identity.py",
                 _ENGINE_ROOT / "platform" / "identity.py",
                 _ENGINE_ROOT / "context" / "merge.py")

#: Import roots that can only be there to measure similarity. `difflib` is the one that ships with
#: Python and therefore the one most likely to appear — `SequenceMatcher` is three lines away from
#: looking reasonable.
BANNED_IMPORTS = frozenset({
    "difflib", "Levenshtein", "python_Levenshtein", "rapidfuzz", "fuzzywuzzy", "jellyfish",
    "textdistance", "pylev", "editdistance", "metaphone", "fuzzy",
    "numpy", "scipy", "sklearn", "faiss", "annoy", "hnswlib", "pgvector", "chromadb",
    "sentence_transformers", "transformers", "gensim", "openai", "anthropic", "cohere",
    "tiktoken", "torch", "voyageai"})

#: Names a comparison-by-degree wears, in a call or an attribute. `ratio`, `distance` and
#: `similarity` cover the library surface; `embed`/`vector`/`cosine` cover the other kind.
BANNED_CALL_TOKENS = ("sequencematcher", "get_close_matches", "levenshtein", "jaro", "jaccard",
                      "hamming", "damerau", "soundex", "metaphone", "cosine", "embed",
                      "similarity", "edit_distance", "editdistance", "fuzzy", "nearest")

#: SQL that compares by degree. `%` is pg_trgm's similarity operator and `<->` its distance
#: operator; `similarity(` and `word_similarity(` are its functions. All four turn an exact
#: lookup into a threshold nobody can see in the Python.
BANNED_SQL = ("pg_trgm", "similarity(", "word_similarity(", "<->", "levenshtein(", "soundex(",
              "difference(", "% ", "vector")


def _ast_of(path: Path) -> ast.AST:
    return ast.parse(path.read_text(), filename=str(path))


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _dotted(node: ast.AST) -> str:
    """`a.b.c` for an attribute chain, the bare name for a Name, "" otherwise."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


@pytest.mark.gate
@pytest.mark.parametrize("path", IDENTITY_PATH, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_the_identity_path_imports_nothing_that_can_measure_similarity(path: Path) -> None:
    """Item 1, read off the IMPORTS rather than off the docstring.

    Every one of these libraries exists to answer "how close are these two strings/vectors", and
    the law the module states — *exact key equality is the ONLY auto-merge* — has no use for that
    answer. An import is the cheapest possible warning: the thing cannot be used without one.
    """
    found = sorted(_imported_roots(_ast_of(path)) & BANNED_IMPORTS)
    assert found == [], (
        f"{path.name} imports {found}. `context/identity.py:25` states the law: no edit distance, "
        "no embeddings, no '0.87 similar' — every one of those turns a coin-flip into a "
        "permanent, invisible join between two real entities, and nothing in the graph records "
        "that a guess was made")


@pytest.mark.gate
@pytest.mark.parametrize("path", IDENTITY_PATH, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_function_on_the_identity_path_compares_by_degree(path: Path) -> None:
    """The COMPARISON functions, not the module docstring — every call and every def name.

    An import ban alone is defeated by `str.__eq__`-shaped hand-rolled code: a private
    `_similarity(a, b)` counting shared trigrams needs no library at all. So the callables are
    checked too, defined and invoked.
    """
    tree = _ast_of(path)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted(node.func).lower()
            offenders += [f"call {name}" for token in BANNED_CALL_TOKENS if token in name]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name.lower()
            offenders += [f"def {node.name}" for token in BANNED_CALL_TOKENS if token in name]
    assert offenders == [], (
        f"{path.name} compares by degree: {sorted(set(offenders))}. Fuzziness is allowed in how a "
        "key is DERIVED (stripping 'Inc.', lowercasing, taking a domain's label) and forbidden in "
        "how keys are COMPARED — comparison is string equality, forever")


@pytest.mark.gate
@pytest.mark.parametrize("path", IDENTITY_PATH, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_sql_on_the_identity_path_matches_approximately(path: Path) -> None:
    """The third hiding place, and the one an AST walk over Python names would miss entirely.

    `where alias_key % :k` is a pg_trgm similarity predicate with a threshold set by a GUC — a
    fuzzy join with no number anywhere in this repository. `<->` is the same thing sorted by
    distance. A `like` with a leading wildcard is prefix matching, which is not equality either.
    """
    offenders: list[str] = []
    for node in ast.walk(_ast_of(path)):
        # Only what is actually EXECUTED — the literals handed to `sqlalchemy.text(...)`.
        # Scanning every string constant instead reads the prose in the docstrings, where "two
        # nodes look like one thing" is a sentence about the law and not a `like` predicate.
        if not (isinstance(node, ast.Call) and _dotted(node.func).split(".")[-1] == "text"):
            continue
        for literal in ast.walk(node):
            if not (isinstance(literal, ast.Constant) and isinstance(literal.value, str)):
                continue
            sql = literal.value.lower()
            offenders += [f"{token!r} in {sql[:60]!r}" for token in BANNED_SQL if token in sql]
            if "like" in sql:
                offenders.append(f"LIKE in {sql[:60]!r}")
    assert offenders == [], (
        f"{path.name} matches approximately in SQL: {offenders}. Every lookup on this path is "
        "`alias_key = :k`; a trigram or prefix predicate is a similarity threshold that never "
        "appears in the Python and cannot be reviewed")


@pytest.mark.gate
def test_a_near_miss_derives_a_different_key_and_therefore_never_matches() -> None:
    """The behaviour the three scans exist to protect, stated once.

    Not a restatement of `test_matching_is_string_equality_and_nothing_else` — that test asserts
    two slugs differ. This one carries the difference all the way to the LOOKUP KEYS a mention is
    resolved by, which is the surface a similarity match would actually be inserted into.
    """
    for a, b in (("Acme", "Acmee"), ("Acme", "Acme Global"), ("Stripe", "Strype"),
                 ("Little Legends", "Little Legend")):
        assert set(company_name_keys(a)).isdisjoint(company_name_keys(b)), (
            f"{a!r} and {b!r} share a lookup key — one of them would resolve to the other's node")
    # And the derivation that IS allowed still lands on equality: two words squash to the domain
    # label, and that is a second exact key, not a tolerance.
    assert company_name_keys("DevDash Labs") == ["devdash labs", "devdashlabs"]
    assert platform_identity.person_name_key("Rohit  S.") == platform_identity.person_name_key(
        "ROHIT S")


@pytest.mark.pg
@pytest.mark.gate
def test_a_near_miss_resolves_to_nobody_against_a_real_alias_table(pg_store) -> None:
    """The scans read the code; this runs the query. A company anchored under one name must not
    be reachable from a name one character away, and an AMBIGUOUS key must resolve to nobody
    rather than to whichever row Postgres returned first."""
    org = "org_mnr_identity"
    _seed_org(pg_store, org)
    try:
        with pg_store.engine.begin() as conn:
            _node(conn, org, "n_acme", "company", "acme.io", "Acme")
            register_node_identity(conn, org_id=org, node_id="n_acme", node_type="company",
                                   canonical_key="acme.io", display_name="Acme")
        with pg_store.engine.connect() as conn:
            assert resolve_company_mention(conn, org_id=org, name="Acme") == "n_acme"
            for near in ("Acmee", "Acme Global", "Acm", "Acme Technologies"):
                assert resolve_company_mention(conn, org_id=org, name=near) is None, (
                    f"{near!r} resolved to the Acme node — the lookup stopped being equality")

        # Two people genuinely called the same thing. The key is single-owner BY SCHEMA
        # (`graph_aliases` primary key is `(org, alias_type, alias_key)`), so the second claim
        # cannot overwrite the first: it comes back as a COLLISION the caller must act on, and
        # the resolution the graph already had does not move under it. A reassignment here would
        # silently redirect every "Rohit said yes" written since the first claim.
        with pg_store.engine.begin() as conn:
            for node_id, email in (("n_john_a", "john@a.example"), ("n_john_b", "john@b.example")):
                _node(conn, org, node_id, "person", email, "John Smith")
            first = record_alias(conn, org_id=org, node_id="n_john_a",
                                 alias_type=ALIAS_PERSON_NAME, alias_key="john smith",
                                 origin="observed")
            second = record_alias(conn, org_id=org, node_id="n_john_b",
                                  alias_type=ALIAS_PERSON_NAME, alias_key="john smith",
                                  origin="observed")
        assert first is None, "the first claimant did not get the key"
        assert second == "n_john_a", (
            "the second claim on a taken key did not report the holder — a caller that gets None "
            "here believes it owns the key and no proposal is ever raised")
        with pg_store.engine.connect() as conn:
            assert resolve_alias(conn, org_id=org, alias_type=ALIAS_PERSON_NAME,
                                 alias_key="john smith") == "n_john_a", (
                "the second John took the key from the first — every fact written from a bare "
                "name mention since then lands on the wrong person, and nothing records it")
    finally:
        _drop_org(pg_store, org)


# =================================================================================================
# 2 · GOVERNED ENTITY MERGES — PROPOSAL, HISTORY, REVERSIBILITY   (doc 09 item 2)
# =================================================================================================
#
# THE GAP THIS SECTION FILLS. `tests/test_entity_resolution.py` and `tests/test_l2_completeness.py`
# hold eleven assertions about merging and every one of them is `inspect.getsource(...)`:
#
#     assert "insert into merge_history" in source
#     assert "update graph_nodes set valid_to=null" in source
#
# Those pass if the string is present. They pass if the statement is inside a branch that never
# runs, if it is commented out inside a longer literal, if the snapshot it writes is empty, and if
# `reverse_merge` restores nothing. Nothing anywhere executed a merge against a database. Doc 09
# does not ask for the strings; it asks for proposal, history and REVERSIBILITY, and the only way
# to check reversibility is to reverse one.

@pytest.mark.pg
@pytest.mark.gate
def test_a_contested_key_produces_a_proposal_and_merges_nothing(pg_store) -> None:
    """The first half of the governance: identity PROPOSES, and changes nothing while it waits.

    Two company nodes claim `acme.io`. If registration merged them, one of the tenant's customers
    would silently absorb the other; the graph is supposed to ask instead.
    """
    org = "org_mnr_propose"
    _seed_org(pg_store, org)
    try:
        with pg_store.engine.begin() as conn:
            _node(conn, org, "n_left", "company", "acme.io", "Acme")
            register_node_identity(conn, org_id=org, node_id="n_left", node_type="company",
                                   canonical_key="acme.io", display_name="Acme")
            _node(conn, org, "n_right", "company", "acme.io", "Acme, Inc.")
            raised = register_node_identity(conn, org_id=org, node_id="n_right",
                                            node_type="company", canonical_key="acme.io",
                                            display_name="Acme, Inc.")
        assert raised, "a contested strong alias raised no proposal — the duplicate is invisible"
        with pg_store.engine.connect() as conn:
            proposals = conn.execute(text(
                "select id, status from merge_proposals where org_id=:o"), {"o": org}).all()
            assert [p.status for p in proposals] == ["open"]
            assert conn.execute(text(
                "select count(*) from merge_history where org_id=:o"), {"o": org}).scalar() == 0, (
                "registration wrote merge history — nothing may merge without a human")
            assert conn.execute(text(
                "select count(*) from graph_nodes where org_id=:o and valid_to is null"),
                {"o": org}).scalar() == 2, "a node was closed by a mere proposal"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
@pytest.mark.gate
def test_a_merge_is_recorded_with_enough_snapshot_to_undo_it_and_then_is_undone(pg_store) -> None:
    """History and reversibility, EXECUTED. The whole round trip in one transaction each way.

    A merge rewrites who every fact, observation and alias is about. "Merge them back" is not a
    repair — the original ownership is gone — so the test that matters is not that the code
    contains an insert, it is that the rows are where they started afterwards.
    """
    org = "org_mnr_merge"
    _seed_org(pg_store, org)
    try:
        with pg_store.engine.begin() as conn:
            _node(conn, org, "n_surv", "company", "acme.io", "Acme")
            _node(conn, org, "n_dupe", "company", "acme-inc.example", "Acme, Inc.")
            _fact(conn, org, "n_dupe", "deal.stage", '"negotiation"', "fv_dupe_stage")
            _fact(conn, org, "n_surv", "deal.stage", '"proposal"', "fv_surv_stage")
            conn.execute(text(
                "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
                "occurred_at, status) values ('obs_dupe', :o, 'n_dupe', 'positive_reply', :t, "
                "'active')"), {"o": org, "t": AT})
            conn.execute(text(
                "insert into graph_aliases (org_id, node_id, alias_type, alias_key, origin) "
                "values (:o, 'n_dupe', :t, 'acme, inc', 'observed')"),
                {"o": org, "t": ALIAS_COMPANY_NAME})

        with pg_store.engine.begin() as conn:
            result = apply_merge(conn, org_id=org, survivor_node_id="n_surv",
                                 merged_node_id="n_dupe", reason="human said so")
        merge_id = result["merge_id"]

        with pg_store.engine.connect() as conn:
            # HISTORY: the row exists AND carries the snapshot, not just the ids.
            row = conn.execute(text(
                "select snapshots, reason, reversed from merge_history where org_id=:o and id=:i"),
                {"o": org, "i": merge_id}).mappings().first()
            assert row is not None, "no merge_history row — the merge cannot be undone"
            payload = row["snapshots"] if isinstance(row["snapshots"], dict) else json.loads(
                row["snapshots"])
            owned = payload["snapshots"]["merged"]["owned"]
            assert set(owned) >= {"graph_facts", "graph_observations", "graph_aliases"}, (
                f"the snapshot names {sorted(owned)} — a merge_history row that does not list the "
                "rows it moved records that a merge happened and nothing about how to undo it")
            assert "fv_dupe_stage" in owned["graph_facts"]
            assert "obs_dupe" in owned["graph_observations"]
            assert f"{ALIAS_COMPANY_NAME}:acme, inc" in owned["graph_aliases"]
            assert row["reversed"] is False

            # The merge actually moved the rows, and closed the duplicate rather than deleting it.
            assert _owner(conn, org, "graph_facts", "fact_version_id",
                          "fv_dupe_stage") == "n_surv"
            assert _owner(conn, org, "graph_observations", "observation_id",
                          "obs_dupe") == "n_surv"
            assert conn.execute(text(
                "select valid_to from graph_nodes where org_id=:o and node_id='n_dupe'"),
                {"o": org}).scalar() is not None, "the merged node was deleted, not closed"
            # One active value per (subject, field) — invariant 1. The loser is superseded.
            active = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and subject_node_id='n_surv' "
                "and field='deal.stage' and status='active' and valid_to is null"),
                {"o": org}).scalar()
            assert active == 1, (
                f"{active} active `deal.stage` rows on the survivor — every reader takes `limit 1`, "
                "so 'the' stage becomes whichever row the planner returns first")

        # REVERSIBILITY, executed.
        with pg_store.engine.begin() as conn:
            reverse_merge(conn, org_id=org, merge_id=merge_id)
        with pg_store.engine.connect() as conn:
            assert _owner(conn, org, "graph_facts", "fact_version_id",
                          "fv_dupe_stage") == "n_dupe", "the reversal did not put the fact back"
            assert _owner(conn, org, "graph_observations", "observation_id",
                          "obs_dupe") == "n_dupe"
            assert _owner(conn, org, "graph_aliases", "alias_key", "acme, inc") == "n_dupe"
            assert conn.execute(text(
                "select valid_to from graph_nodes where org_id=:o and node_id='n_dupe'"),
                {"o": org}).scalar() is None, "the reversed node stayed closed"
            assert conn.execute(text(
                "select status from graph_facts where fact_version_id='fv_dupe_stage'")
            ).scalar() == "active", "the fact the merge superseded was not reactivated"
            assert conn.execute(text(
                "select reversed from merge_history where org_id=:o and id=:i"),
                {"o": org, "i": merge_id}).scalar() is True

        # And it cannot be run twice: the snapshot describes a world already restored.
        with pytest.raises(ValueError, match="already reversed"):
            with pg_store.engine.begin() as conn:
                reverse_merge(conn, org_id=org, merge_id=merge_id)
    finally:
        _drop_org(pg_store, org)


@pytest.mark.gate
def test_the_source_shaped_merge_guards_upstream_are_still_present() -> None:
    """The eleven `inspect.getsource` assertions are weak on their own and useful as a SET —
    they are the only thing standing between a refactor and a silently ungoverned merge. Invoked
    from here so deleting one is a failure in doc 09's own file, not a quiet subtraction."""
    _call_upstream(_TESTS_ROOT / "test_entity_resolution.py",
                   "test_nothing_in_this_module_merges_anything",
                   "test_a_merge_can_always_be_undone",
                   "test_the_merged_node_is_closed_not_deleted",
                   "test_merging_a_node_into_itself_is_refused",
                   "test_a_rejected_pair_is_never_proposed_again")
    _call_upstream(_TESTS_ROOT / "test_l2_completeness.py",
                   "test_the_documented_undo_actually_exists",
                   "test_reversing_restores_the_graph_and_rebuilds_the_derived_views",
                   "test_a_merge_cannot_be_reversed_twice")


# =================================================================================================
# 3 · THE CONFIDENCE VECTOR — NEVER COLLAPSED TO A SCALAR   (doc 09 item 3, situations.py:102-227)
# =================================================================================================
#
# X5 extended the vector to six axes and `tests/context/test_situation_confidence.py` proves the
# sixth composes correctly. What no test held is the part doc 09 names: that the vector stays a
# VECTOR — through the dataclass, through the INSERT, through the column list of every module that
# writes a situation, and back out of the table as six numbers rather than one repeated one.

@pytest.mark.gate
def test_the_scorer_returns_six_named_axes_and_not_one_number() -> None:
    """The dataclass, against the contract's own list of axis names. A field dropped here is a
    consumer reading `getattr(confidence, 'coverage')` and getting an AttributeError at runtime,
    or worse, a renderer falling back to `overall`."""
    scored = score_situation(event_count=3, source_count=2, last_seen_at=AT - timedelta(days=2),
                             open_discrepancies=1, open_merge_proposals=0,
                             present_fields={"deal.stage"},
                             expected_fields={"deal.stage": "stage", "deal.value": "value"},
                             now=AT)
    for axis in CONFIDENCE_AXES:
        assert hasattr(scored, axis), (
            f"`Confidence` lost the {axis!r} axis — `contracts/situation.CONFIDENCE_AXES` names "
            "six and a consumer reading the missing one gets `overall` or an exception")
    assert scored.overall == min(scored.evidence, scored.consistency, scored.identity,
                                 scored.freshness), "overall stopped being the weakest link"
    # The axes carry DIFFERENT information: a vector whose members always agree is a scalar with
    # six names. This input is built to separate them, and they must separate.
    measured = {scored.evidence, scored.freshness, scored.consistency, scored.identity}
    assert len(measured) > 1, (
        "every axis returned the same number on an input designed to move them apart — the "
        "vector has collapsed to a scalar wearing six labels")
    # `coverage` and `analytic` are REPORTED beside the composition, never folded into it: not
    # knowing a close date does not make the stage we do know less true.
    assert scored.overall != scored.coverage or scored.coverage in measured
    assert scored.analytic == COVERAGE_UNKNOWN and not coverage_is_known(scored.analytic)


@pytest.mark.gate
def test_an_unmeasured_axis_is_a_sentinel_and_can_never_be_averaged_back_in() -> None:
    """The mechanism that keeps the vector honest rather than merely wide. A missing axis scored
    0 would be indistinguishable from a bad one, and averaging is what a scalar is."""
    assert COVERAGE_UNKNOWN < 0 and not 0 <= COVERAGE_UNKNOWN <= SCORE_MAX, (
        "the not-applicable sentinel moved inside 0..100, so a consumer can now average "
        "'we never measured this' into a percentage")
    blind = score_situation(event_count=1, source_count=1, last_seen_at=None,
                            open_discrepancies=0, open_merge_proposals=0, present_fields=set(),
                            expected_fields={}, now=AT)
    assert blind.coverage == COVERAGE_UNKNOWN
    assert blind.inputs["freshness_known"] is False
    assert blind.inputs["coverage_known"] is False
    assert blind.inputs["analytic_known"] is False
    # ...and none of the three unmeasured axes dragged `overall` to the floor.
    assert blind.overall > 0


@pytest.mark.gate
def test_the_contract_refuses_a_scalar_dressed_as_a_vector() -> None:
    """`ConfidenceVector` is the shape the BSO carries to Layer 3. Composing over an axis with no
    basis is exactly the collapse doc 09 forbids — one number standing in for six."""
    with pytest.raises(ValueError, match="no basis"):
        ConfidenceVector(overall_bp=5_000, evidence_bp=5_000, freshness_bp=None,
                         consistency_bp=None, identity_bp=None, coverage_bp=None,
                         analytic_bp=None, composed_from=("evidence", "freshness"))
    with pytest.raises(ValueError, match="composed from nothing"):
        ConfidenceVector(overall_bp=5_000, evidence_bp=5_000, freshness_bp=None,
                         consistency_bp=None, identity_bp=None, coverage_bp=None,
                         analytic_bp=None, composed_from=())
    with pytest.raises(ValueError, match="weakest composed axis"):
        ConfidenceVector(overall_bp=9_000, evidence_bp=3_000, freshness_bp=9_000,
                         consistency_bp=None, identity_bp=None, coverage_bp=None,
                         analytic_bp=None, composed_from=("evidence", "freshness"))
    ok = ConfidenceVector(overall_bp=3_000, evidence_bp=3_000, freshness_bp=9_000,
                          consistency_bp=None, identity_bp=None, coverage_bp=None,
                          analytic_bp=None, composed_from=("evidence", "freshness"))
    assert ok.axes["consistency"] is None, "an unmeasured axis was coerced to 0"
    assert set(ok.axes) == set(CONFIDENCE_AXES)


#: Every module that INSERTs a row into `context_situations`. A writer that names only
#: `confidence_overall` stores a scalar and leaves the other four columns null, and every reader
#: downstream then has one number where the plan promises five.
SITUATION_WRITERS = ("situations.py", "periodic.py", "meeting_touch.py", "support_situations.py",
                     "document_register.py")

AXIS_COLUMNS = ("confidence_overall", "confidence_evidence", "confidence_freshness",
                "confidence_consistency", "confidence_identity", "coverage")


@pytest.mark.gate
@pytest.mark.parametrize("module_name", SITUATION_WRITERS)
def test_every_situation_writer_names_all_five_axis_columns(module_name: str) -> None:
    """The write path, where the vector is most easily lost — one INSERT that names
    `confidence_overall` and stops.

    This checks the COLUMN LIST, which is the part a reader downstream depends on. What each
    writer BINDS to those columns is its own business and differs legitimately (a tenant-period
    aggregate has one honest confidence for four axes); what it may not do is leave four of the
    five columns unwritten and let a null read as a zero.
    """
    source = (_ENGINE_ROOT / "context" / module_name).read_text()
    assert "insert into context_situations" in source, (
        f"{module_name} no longer writes situations — update SITUATION_WRITERS")
    # THE COLUMN LIST ONLY — everything between `insert into context_situations (` and the
    # `) values` that closes it. Scanning a fixed window instead reaches the `on conflict do
    # update set confidence_freshness = excluded.confidence_freshness` below, so a column
    # DROPPED from the insert would still be found in the update clause and the check would
    # pass on exactly the mutation it exists to catch.
    start = source.index("insert into context_situations")
    end = source.index("values", start)
    columns = re.sub(r"[\s\"']+", " ", source[start:end])
    missing = [column for column in AXIS_COLUMNS if column not in columns]
    assert missing == [], (
        f"{module_name}'s situation INSERT does not name {missing} — those columns stay null and "
        "a reader takes the nulls for zeroes, which is the confidence vector collapsed to "
        "`confidence_overall` by omission")


@pytest.mark.pg
@pytest.mark.gate
def test_six_distinct_axes_survive_the_round_trip_through_the_table(pg_store) -> None:
    """The columns exist AND keep their own values. A migration that dropped one, or an ORM
    mapping that wrote `overall` into all five, would pass every hermetic test above."""
    org = "org_mnr_vector"
    _seed_org(pg_store, org)
    values = {"confidence_overall": 41, "confidence_evidence": 62, "confidence_freshness": 73,
              "confidence_consistency": 84, "confidence_identity": 95, "coverage": 26}
    try:
        with pg_store.engine.begin() as conn:
            _node(conn, org, "n_vec", "company", "vec.example", "Vec")
            conn.execute(text(
                "insert into context_situations (situation_id, org_id, correlation_id, "
                "anchor_node_id, situation_type, domain, status, confidence_overall, "
                "confidence_evidence, confidence_freshness, confidence_consistency, "
                "confidence_identity, coverage, confidence_analytic, missing, inputs, "
                "first_seen_at, last_seen_at, computed_at) values "
                "(:s, :o, :c, 'n_vec', 'x', 'general', 'active', :confidence_overall, "
                ":confidence_evidence, :confidence_freshness, :confidence_consistency, "
                ":confidence_identity, :coverage, :analytic, '[]'::jsonb, '{}'::jsonb, "
                ":t, :t, :t)"),
                {"s": "sit_vec", "o": org, "c": "corr_vec", "t": AT, "analytic": 17, **values})
        with pg_store.engine.connect() as conn:
            row = conn.execute(text(
                "select confidence_overall, confidence_evidence, confidence_freshness, "
                "confidence_consistency, confidence_identity, coverage, confidence_analytic "
                "from context_situations where org_id=:o and situation_id='sit_vec'"),
                {"o": org}).mappings().first()
        stored = dict(row)
        assert stored.pop("confidence_analytic") == 17, (
            "`confidence_analytic` — X5's sixth axis — did not survive the write")
        assert stored == values, (
            f"the vector did not round-trip: wrote {values}, read {stored}. Six axes must stay "
            "six numbers; one repeated value is doc 09 item 3 broken at the column")
        assert len(set(stored.values())) == len(stored), "two axes collapsed onto one value"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.gate
def test_the_sixth_axis_suite_is_still_the_one_proving_the_vector_composes() -> None:
    """X5's file owns the composition rule; this suite owns the survival of the vector. Invoked
    so the two cannot be separated by a delete."""
    _call_upstream(_TESTS_ROOT / "context" / "test_situation_confidence.py",
                   "test_the_vector_has_six_axes_and_still_reports_a_weakest",
                   "test_no_comparison_is_not_a_bad_comparison",
                   "test_a_thin_comparison_does_not_make_the_situation_less_true",
                   "test_the_five_older_axes_are_untouched_by_the_sixth")


# =================================================================================================
# 4 · TENANT NODE EXCLUDED FROM `ANCHOR_PRIORITY`   (doc 09 item 4)
# =================================================================================================
#
# ALREADY PINNED, and pinned for real: `tests/context/test_dependency_correlation.py` §3 asserts
# the exact tuple and that an event naming only the tenant anchors on nothing. Invoked rather than
# restated. What is added here is the other half of the same question — that `tenant` is a node
# type the system genuinely PRODUCES, so the exclusion is guarding a live case and not a word
# nothing writes any more.

@pytest.mark.gate
def test_the_tenant_exclusion_is_still_asserted_where_x7_put_it() -> None:
    _call_upstream(_TESTS_ROOT / "context" / "test_dependency_correlation.py",
                   "test_the_tenant_node_is_not_an_anchoring_type",
                   "test_an_event_naming_the_tenant_anchors_on_the_business_subject_beside_it",
                   "test_an_event_that_names_only_the_tenant_anchors_on_nothing_rather_than_on_"
                   "the_tenant")


@pytest.mark.gate
def test_the_tenant_node_type_the_exclusion_guards_is_one_the_system_really_writes() -> None:
    """The exclusion is only load-bearing if something creates a `tenant` node. `periodic.py`
    does, one per org, and every outbound message in the tenant's own history names it — which is
    the mechanism by which one node would swallow every conversation."""
    source = (_ENGINE_ROOT / "context" / "periodic.py").read_text()
    assert "'tenant'" in source or '"tenant"' in source, (
        "nothing writes a tenant node any more; if that is true the exclusion is dead code and "
        "doc 09 item 4 needs restating, and if it is not true the node moved somewhere unguarded")
    from genios_engine.context.correlation import ANCHOR_PRIORITY, choose_anchors
    # The failure mode, stated as behaviour rather than as membership: a mixed event does not
    # file under the tenant, and a tenant-only event files nowhere.
    assert "tenant" not in ANCHOR_PRIORITY
    mixed = choose_anchors({"n_t": "tenant", "n_c": "company", "n_p": "person"}, "sales")
    assert [a.node_id for a in mixed] == ["n_c"], (
        "the tenant tier out-ranked the company — every conversation in the org lands in one "
        "group and no situation is about anybody")


# =================================================================================================
# 5 · CORRELATION REFUSES TO PRIORITISE, SCORE RISK OR RECOMMEND   (doc 09 item 5)
# =================================================================================================
#
# ALREADY PINNED by X7 over the three correlator modules' public surface and over the fields the
# two sweeps publish. Invoked. The part that was NOT covered: the module surface test looks at
# NAMES, so a ranking imported from elsewhere and re-exported under an innocent name would pass.
# The import check below is the complement — correlation may not reach the layer that ranks.

@pytest.mark.gate
def test_the_refusal_is_still_asserted_where_x7_put_it() -> None:
    from genios_engine.context import (
        correlation,
        correlation_conversation,
        correlation_dependency,
        correlation_domain,
        correlation_organization,
        correlation_resource,
        correlation_timeline,
    )
    module = _call_upstream(
        _TESTS_ROOT / "context" / "test_dependency_correlation.py",
        "test_a_chain_carries_a_blocked_count_and_no_score_a_reader_could_rank_on",
        "test_the_facts_the_two_sweeps_write_are_findings_and_never_a_ranking")
    surface = getattr(module, "test_no_correlator_exposes_a_way_to_prioritise_score_risk_or_"
                              "recommend")
    # ALL EIGHT. Four of them — conversation, domain, organization, resource — were outside
    # every correlator gate until the audit that found it, so the ratchet has to name them too
    # or the upstream list can shrink again without this noticing.
    for correlator in (correlation, correlation_conversation, correlation_dependency,
                       correlation_domain, correlation_organization, correlation_resource,
                       correlation_timeline):
        surface(correlator)


@pytest.mark.gate
@pytest.mark.parametrize("module_name", ("correlation.py", "correlation_conversation.py",
                                         "correlation_dependency.py", "correlation_domain.py",
                                         "correlation_organization.py",
                                         "correlation_resource.py", "correlation_timeline.py"))
def test_no_correlator_imports_the_machinery_that_ranks(module_name: str) -> None:
    """The complement to the name scan. `importance.py` composes a rank, `attention.py` sorts one
    and `reason/` acts on one; a correlator that imported any of them could attach a ranking under
    a name no forbidden-verb list contains — `correlate()` returning a sorted list, say."""
    tree = _ast_of(_ENGINE_ROOT / "context" / module_name)
    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.add(node.module)
        elif isinstance(node, ast.Import):
            reached.update(alias.name for alias in node.names)
    banned = sorted(m for m in reached
                    if m.endswith(("context.importance", "context.attention"))
                    or ".reason" in m or m.startswith("genios_engine.reason")
                    or m.endswith("context.situation_bso"))
    assert banned == [], (
        f"{module_name} imports {banned}. Correlation answers 'do these belong to the same "
        "thing?' and nothing else — a rank produced by a JOIN has no population behind it, "
        "cannot be explained, and every reader downstream would treat it as measured")


# =================================================================================================
# 6 · `graph_facts` KEEPS OVERWRITING THE CURRENT VALUE   (doc 09 item 6, derived.py)
# =================================================================================================
#
# **THE ONE DOC 09 SAYS IS MOST LIKELY TO BE GOT WRONG**, and the one this whole file was written
# for. X1 added `metric_history` — append-only, "what was true THEN". The instinct on reading "we
# need history" is to stop overwriting `graph_facts`; that would grow the table by three rows per
# node per drain forever and make every "latest" read sift duplicates, which is the failure
# `expertise_packages` already caused on this database (181 MB, read-only). **Two tables, two
# questions.**
#
# X3/X5/X6 then added several new derived writers, and the X3/X4/X7 review found four of them
# moving `valid_from`; the fix routed those four through `context/analytic/publish.py`, which is
# PERIOD-KEYED. Period keying is the thing that could have turned this table append-only by
# accident: one row per (node, field) per ISO week is 52 rows a year IF the value changes weekly.
# The property doc 09 states, and what §6 measures on real Postgres, is the other case — **an
# unchanging value swept many times must produce FLAT row growth**, under both writer shapes.

#: The nodes and the sweeps the growth measurement uses. Twelve sweeps because that is more than
#: any plausible drain cadence within one period AND spans several periods once dated forward.
GROWTH_SWEEPS = 12


@pytest.mark.pg
@pytest.mark.gate
def test_the_current_value_writer_holds_graph_facts_flat_across_many_sweeps(pg_store) -> None:
    """`derived.compute` re-derives `engagement`, `sentiment` and `momentum` on every drain.

    Twelve sweeps of an UNCHANGING observation set must leave exactly three rows per node — the
    deterministic `fv_derived_{node}_{field}` id taking the conflict path every time. One row per
    sweep instead is 3 rows x nodes x drains forever, and a reader picking "latest" starts sifting
    duplicates on a table that has no index for it.
    """
    org = "org_mnr_growth"
    _seed_org(pg_store, org)
    nodes = ("n_growth_a", "n_growth_b")
    try:
        with pg_store.engine.begin() as conn:
            for i, node_id in enumerate(nodes):
                _node(conn, org, node_id, "person", f"g{i}@growth.example", f"G{i}")
                for j, kind in enumerate(("positive_reply", "question", "next_step_agreed")):
                    conn.execute(text(
                        "insert into graph_observations (observation_id, org_id, "
                        "subject_node_id, kind, occurred_at, status) "
                        "values (:id, :o, :n, :k, :t, 'active')"),
                        {"id": f"obs_{node_id}_{j}", "o": org, "n": node_id, "k": kind,
                         "t": AT - timedelta(days=3)})

        counts: list[int] = []
        for sweep in range(GROWTH_SWEEPS):
            # The clock is a PARAMETER — and it MOVES, week by week, which is exactly the case a
            # period-keyed writer would answer with a new row.
            derived.compute(pg_store, org, now=AT + timedelta(days=7 * sweep))
            counts.append(_derived_rows(pg_store, org))

        assert counts[0] == 3 * len(nodes), (
            f"first sweep wrote {counts[0]} rows for {len(nodes)} nodes x 3 fields")
        assert len(set(counts)) == 1, (
            f"`graph_facts` grew across {GROWTH_SWEEPS} sweeps of an unchanging value: {counts}. "
            "doc 09 item 6 — history is a SEPARATE table (`metric_history`), not a change to this "
            "one. An appending `graph_facts` is three rows per node per drain forever, and it is "
            "the shape that put this database into read-only")

        # And what it holds is the CURRENT value: one live row per (node, field), no stale twin.
        with pg_store.engine.connect() as conn:
            live = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field='derived.engagement' "
                "and valid_to is null and status='active'"), {"o": org}).scalar()
        assert live == len(nodes), f"{live} live `derived.engagement` rows for {len(nodes)} nodes"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
@pytest.mark.gate
def test_period_keying_did_not_turn_the_table_append_only(pg_store) -> None:
    """The NEW writer, and the specific way X3/X5/X6 could have broken item 6 without noticing.

    `publish_derived_fact` keys a row per ISO week, so a naive reading says "52 rows a year per
    fact". The module's actual bound is *the number of weeks in which the value CHANGED*, and the
    branch that delivers it is `UNCHANGED`, which writes nothing at all. Twelve weekly sweeps of
    one unchanging value must be ONE row — not twelve — and the row must keep the `valid_from` it
    opened with, or `read_graph(as_of=week 1)` answers nothing about a fact published in week 1.
    """
    org = "org_mnr_publish"
    _seed_org(pg_store, org)
    field, value = "derived.cohort.position", {"percentile_bp": 4_200, "population_size": 180}
    try:
        with pg_store.engine.begin() as conn:
            _node(conn, org, "n_pub", "company", "pub.example", "Pub")

        actions, counts = [], []
        for sweep in range(GROWTH_SWEEPS):
            published = publish_derived_fact(
                pg_store.engine, org_id=org, subject_node_id="n_pub", field=field, value=value,
                eval_time=AT + timedelta(days=7 * sweep), value_type="json",
                visibility_scope="org", version_prefix="fv_mnr_")
            actions.append(published.action)
            counts.append(_field_rows(pg_store, org, field))

        assert actions[0] is PublishAction.INSERTED
        assert set(actions[1:]) == {PublishAction.UNCHANGED}, (
            f"a re-confirming sweep wrote something: {actions}. A sweep that agrees with what is "
            "stored has produced no fact")
        assert counts == [1] * GROWTH_SWEEPS, (
            f"row count per weekly sweep of ONE unchanging value: {counts}. Period keying bounds "
            "growth by CHANGES, not by sweeps — a row per sweep is `graph_facts` turned "
            "append-only, which is doc 09 item 6")

        with pg_store.engine.connect() as conn:
            opened = conn.execute(text(
                "select valid_from from graph_facts where org_id=:o and field=:f"),
                {"o": org, "f": field}).scalar()
        assert opened.astimezone(timezone.utc) == AT, (
            "the unchanged sweeps moved `valid_from` forward — an as-of read of the week the fact "
            "was published now returns nothing about a fact GeniOS itself published then")
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
@pytest.mark.gate
def test_history_lives_in_its_own_table_and_that_one_is_the_append_only_one(pg_store) -> None:
    """"Two tables, two questions" — asserted as two tables. `metric_history` answers "what was
    true THEN" and grows a row per period; `graph_facts` answers "what is true NOW" and does not.
    A single table that tried to answer both is the regression."""
    with pg_store.engine.connect() as conn:
        for table in ("graph_facts", "metric_history"):
            assert conn.execute(text(
                "select 1 from information_schema.tables where table_name = :t"),
                {"t": table}).scalar() == 1, f"{table} is gone — item 6's two tables are now one"
        # `metric_history` is keyed by PERIOD, which is what makes it the historical one; the
        # current-value table is keyed by fact VERSION and has no period column at all.
        history_key = _primary_key(conn, "metric_history")
        facts_key = _primary_key(conn, "graph_facts")
    # `metric_history`'s key CONTAINS THE PERIOD (`observed_at`, "the PERIOD this value
    # describes"), so a new period is by definition a new row: append-only, and "what was true
    # THEN" is answerable.
    assert "observed_at" in history_key, (
        f"`metric_history`'s primary key is {history_key} and no longer contains the period — a "
        "recompute would now overwrite a period that has passed, and the history table stops "
        "being a history")
    # `graph_facts`' key is the fact VERSION and nothing else, so a derived recompute lands on
    # the row it wrote last time. A period in this key is the two questions being answered by
    # one table, which is the instinct doc 09 item 6 exists to refuse.
    assert facts_key == ["fact_version_id"], (
        f"`graph_facts`' primary key became {facts_key}. Adding a period to it turns every "
        "recompute into an append — three rows per node per drain forever, and every 'latest' "
        "read sifting duplicates")


#: Every module that writes `graph_facts` with SQL of its own, and why each is allowed to.
#: A NEW name here is a new writer that nobody has judged against item 6, which is precisely how
#: the four `valid_from = excluded.valid_from` copies got in.
GRAPH_FACT_WRITERS = {
    "context/graph_store.py": "the observed-fact writer: appends a version and supersedes the "
                              "old one — this IS the graph's own history and is not a derived "
                              "recompute",
    "context/derived.py": "current value, overwrite — doc 09 item 6 names this file",
    "context/periodic.py": "current value, overwrite (tenant window aggregate)",
    "context/document_register.py": "current value, overwrite (per document)",
    "context/support_situations.py": "current value, overwrite (per finding)",
    # NOT a blessing. `analytic/trend.py:537` still carries its own copy of the upsert ending
    # `valid_from = excluded.valid_from` — the same clause the X3/X4/X7 review removed from
    # `comparator`, `anomaly`, `correlation_dependency` and `correlation_timeline` by routing them
    # through `analytic/publish.py`. It does not break item 6 (it still overwrites, so growth is
    # flat), which is why it is listed rather than asserted against; it breaks the point-in-time
    # read that publish.py exists to protect. Recorded here so the next reader finds it.
    "context/analytic/trend.py": "current value, overwrite — BUT still moves `valid_from` on "
                                 "conflict; not routed through analytic/publish.py (open)",
}


@pytest.mark.gate
def test_the_set_of_modules_writing_graph_facts_is_the_set_somebody_judged() -> None:
    """An inventory, because item 6 is a property of the TABLE and any module can break it.

    A writer added without a decision about overwrite-versus-append is how three rows per node per
    drain arrives, and the module that does it will have a docstring explaining why it is fine.
    """
    found = sorted(str(path.relative_to(_ENGINE_ROOT))
                   for path in _ENGINE_ROOT.rglob("*.py")
                   if "insert into graph_facts" in path.read_text())
    assert found == sorted(GRAPH_FACT_WRITERS), (
        f"the set of `graph_facts` writers changed.\n  found:    {found}\n  judged:   "
        f"{sorted(GRAPH_FACT_WRITERS)}\nEvery writer must state whether it overwrites the CURRENT "
        "value (doc 09 item 6) or appends a version, and a new one has stated nothing")


@pytest.mark.gate
def test_the_current_value_writers_still_take_the_conflict_path(_=None) -> None:
    """The mechanism, read off the SQL: a deterministic version id plus `on conflict do update`.

    Without the conflict clause every sweep is an INSERT and the primary key is the only thing
    between this table and unbounded growth — which is a 500 to the caller, not a slow leak, but
    the same defect. Without a deterministic id the conflict never fires and the growth is
    silent.
    """
    source = (_ENGINE_ROOT / "context" / "derived.py").read_text()
    assert "on conflict (fact_version_id) do update" in source, (
        "`derived.py` stopped overwriting its own row. doc 09 item 6: history is a separate "
        "table, not a change to this one")
    assert "fv_derived_{node_id}_{field}" in source, (
        "the derived version id is no longer deterministic per (node, field) — the conflict "
        "clause can never fire and every drain appends")
    assert "insert into metric_history" not in source, (
        "`derived.py` writes the history table too; two writers, one grain, and neither owns it")


# =================================================================================================
# 7 · LAYER IMPORT DIRECTION   (doc 09 item 7)
# =================================================================================================
#
# Has its own file and needs nothing added. Invoked so that "the seven" is a set one command can
# run, and so that deleting the topology test is a failure in doc 09's own suite.

@pytest.mark.gate
def test_the_import_direction_ratchet_still_holds() -> None:
    _call_upstream(_TESTS_ROOT / "test_layer_topology.py",
                   "test_import_direction",
                   "test_contracts_import_nothing_above_platform",
                   "test_every_layer_package_exists")


# =================================================================================================
# THE SET, AS A SET
# =================================================================================================

@pytest.mark.gate
def test_all_seven_rows_of_doc_09s_table_are_claimed_by_a_test_in_this_file() -> None:
    """The suite's own manifest. Doc 09's table has seven rows that survive the build; a row with
    no test is the state this file exists to end, and a row that quietly loses its test later
    should fail HERE rather than be discovered by a customer."""
    claimed = {
        1: "test_the_identity_path_imports_nothing_that_can_measure_similarity",
        2: "test_a_merge_is_recorded_with_enough_snapshot_to_undo_it_and_then_is_undone",
        3: "test_six_distinct_axes_survive_the_round_trip_through_the_table",
        4: "test_the_tenant_exclusion_is_still_asserted_where_x7_put_it",
        5: "test_the_refusal_is_still_asserted_where_x7_put_it",
        6: "test_the_current_value_writer_holds_graph_facts_flat_across_many_sweeps",
        7: "test_the_import_direction_ratchet_still_holds"}
    here = globals()
    missing = sorted(f"item {n}: {name}" for n, name in claimed.items() if name not in here)
    assert missing == [], f"a must-not-regress row lost its test: {missing}"
    assert len(claimed) == 7


# =================================================================================================
# pg helpers
# =================================================================================================

def _seed_org(store, org: str) -> None:
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'MustNotRegress') "
                          "on conflict (id) do nothing"), {"o": org})


def _drop_org(store, org: str) -> None:
    with store.engine.begin() as conn:
        for table in ("context_situations", "context_correlation_members", "context_correlations",
                      "graph_facts", "graph_observations", "graph_aliases", "graph_edges",
                      "merge_proposals", "merge_history", "graph_nodes", "context_attention"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        conn.execute(text("delete from orgs where id = :o"), {"o": org})


def _node(conn, org: str, node_id: str, node_type: str, key: str, name: str) -> None:
    conn.execute(text(
        "insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name, "
        "valid_from) values (:n, :o, :ty, :k, :d, :t) on conflict do nothing"),
        {"n": node_id, "o": org, "ty": node_type, "k": key, "d": name,
         "t": AT - timedelta(days=90)})


def _fact(conn, org: str, node_id: str, field: str, value: str, version_id: str) -> None:
    conn.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
        "value, value_type, status, authority_rank, confidence, occurred_at, valid_from) "
        "values (:v, :f, :o, :n, :fi, cast(:val as jsonb), 'string', 'active', 3, 0.9, :t, :t)"),
        {"v": version_id, "f": f"f_{version_id}", "o": org, "n": node_id, "fi": field,
         "val": value, "t": AT - timedelta(days=10)})


def _owner(conn, org: str, table: str, key_column: str, key: str) -> str | None:
    column = "node_id" if table == "graph_aliases" else "subject_node_id"
    return conn.execute(text(
        f"select {column} from {table} where org_id=:o and {key_column}=:k"),
        {"o": org, "k": key}).scalar()


def _derived_rows(store, org: str) -> int:
    with store.engine.connect() as conn:
        return conn.execute(text(
            "select count(*) from graph_facts where org_id=:o and field like 'derived.%'"),
            {"o": org}).scalar()


def _field_rows(store, org: str, field: str) -> int:
    with store.engine.connect() as conn:
        return conn.execute(text(
            "select count(*) from graph_facts where org_id=:o and field=:f"),
            {"o": org, "f": field}).scalar()


def _primary_key(conn, table: str) -> list[str]:
    """The primary-key columns of a table, in key order. The structural difference between the
    two tables item 6 keeps apart: one is keyed by period, the other is not."""
    return [r[0] for r in conn.execute(text(
        "select a.attname from pg_index i "
        "join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey) "
        "where i.indrelid = cast(:t as regclass) and i.indisprimary "
        "order by array_position(i.indkey, a.attnum)"), {"t": table}).all()]
