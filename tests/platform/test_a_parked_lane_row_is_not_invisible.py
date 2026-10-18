"""A warm-lane row parked "for a human" is excluded from every count — and now from no receipt.

⛔ `migrations/0136_warm_lane.sql` comments the column itself: *"attempts ran out: parked for a
human, never retried, never blocking a re-enqueue."* ⛔⛔ **And every reader uses `parked_at` only
as an exclusion:** `warm_lane._OPEN` is `done_at is null and parked_at is null`, `api/routes`'s
backlog count repeats it, `housekeep` warns on the age of the OPEN backlog and prunes only
finished rows.

⛔ So a tenant whose rows park stops being processed **silently and permanently**, while the health
signal reports zero open rows and looks fine. *A refusal nobody can see is a silent stop* — and this
is the worst version in the product, because the health check does not merely miss the parked rows,
it **excludes them by construction**.

⛔ L1 already makes this claim for the other parked table (*"the parked queue is not a black hole"*,
over `parked_events`), so receipt 43 is that precedent applied to the table that lacked it, not an
invention.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from genios_engine.platform import receipt_coverage as RC
from genios_engine.platform import table_coverage as TC
from genios_engine.platform.receipts import receipts
from genios_engine.platform.warm_lane import _OPEN

_CLAIM = "no warm-lane row is parked where nothing can see it"
_ENGINE = Path(__file__).resolve().parents[2] / "genios_engine"
_TABLE = "l2_work_queue"


def _receipt():
    found = [r for r in receipts("org_probe") if r.claim == _CLAIM]
    assert len(found) == 1, f"expected exactly one receipt for {_CLAIM!r}, got {len(found)}"
    return found[0]


# ── the receipt asks the right question, and it can fail ───────────────────────────────────────

def test_the_receipt_exists_and_is_correctness_shaped():
    r = _receipt()
    assert r.expect(0) is True and r.expect(1) is False, (
        "⛔ a presence check here would pass the moment anything parked, which is the opposite of "
        "the claim")


def test_the_receipt_asks_about_parked_rows_and_is_org_filtered():
    sql = " ".join(_receipt().sql.lower().split())
    assert f"from {_TABLE}" in sql and "parked_at is not null" in sql
    assert "org_id = :org" in sql, (
        "a parked row belongs to one tenant; an unfiltered count would report another tenant's "
        "stuck lane on this one's readiness page")


def test_the_receipt_is_declared_under_the_package_that_owns_the_lane():
    package, why = RC.RECEIPT_PACKAGE[_CLAIM]
    assert package == "platform"
    assert "warm_lane" in why and len(why) > 120


# ── the derivation: it must cover exactly what the lane hides ──────────────────────────────────

def test_the_lane_still_excludes_parked_rows_from_open():
    """⛔ The receipt's predicate is derived from `_OPEN`, and the builder asserts the shape. If the
    lane ever counts parked rows as open they are visible, and this receipt should be deleted
    deliberately rather than left asking a question nobody needs."""
    clauses = {c.strip() for c in _OPEN.split(" and ")}
    assert "parked_at is null" in clauses, _OPEN
    assert "done_at is null" in clauses, _OPEN


def test_the_receipt_builder_refuses_a_lane_that_changed_its_mind(monkeypatch):
    """The assertion inside the SQL builder is the real guard — this proves it fires."""
    import genios_engine.platform.warm_lane as W
    from genios_engine.platform.receipts import _PARKED_WARM_LANE_SQL

    monkeypatch.setattr(W, "_OPEN", "done_at is null", raising=True)
    with pytest.raises(AssertionError, match="no longer excludes parked rows"):
        _PARKED_WARM_LANE_SQL("org_probe")


# ── the finding itself, guarded: nothing selects a parked row ──────────────────────────────────

def test_nothing_but_the_receipt_selects_a_parked_row():
    """⛔ This is the finding, pinned. The day somebody builds the human surface the schema promises,
    this fails — and that is the signal to re-read the receipt, not to widen the test."""
    readers: list[str] = []
    known = TC._known_tables()
    for path in sorted(_ENGINE.rglob("*.py")):
        if "__pycache__" in str(path) or path.name == "receipts.py":
            continue
        for blob, _ in TC._statements(path.read_text(encoding="utf-8"), known):
            sql = " ".join(blob.lower().split())
            if _TABLE in sql and "parked_at is not null" in sql:
                readers.append(str(path.relative_to(_ENGINE)))
    assert not readers, (
        f"{readers} now read parked warm-lane rows. ⛔ If that is a human surface, the receipt's "
        "claim has been answered and the receipt should be re-read; if it is another exclusion, "
        "nothing changed")


def test_the_prune_leaves_parked_rows_alone():
    """⛔ Why the receipt is meaningful: parked rows ACCUMULATE. `housekeep` deletes only rows with
    a `done_at`, so a parked row is permanent — invisible and growing, which is the opposite of a
    transient blip."""
    src = (_ENGINE / "platform" / "warm_lane.py").read_text(encoding="utf-8")
    known = TC._known_tables()
    deletes = [" ".join(b.lower().split()) for b, _ in TC._statements(src, known)
               if "delete from l2_work_queue" in " ".join(b.lower().split())]
    assert deletes, "the prune is gone; parked rows were already permanent, now everything is"
    for sql in deletes:
        assert "done_at <" in sql, (
            f"the prune no longer restricts itself to finished rows: {sql}. ⛔ Deleting a parked "
            "row would make the silent stop silent forever, including to this receipt")


def test_the_backlog_warning_measures_open_rows_only():
    """The health signal's predicate IS the exclusion. Pinned so the receipt's reason stays true."""
    src = (_ENGINE / "platform" / "warm_lane.py").read_text(encoding="utf-8")
    assert "_OPEN = \"done_at is null and parked_at is null\"" in src
    assert "warm lane backlog" in src, "the staleness warning is gone; re-read this file"


def test_the_schema_still_says_what_the_claim_quotes():
    """⛔ A claim about PROSE needs attribution: the receipt quotes the migration's comment, so the
    comment is where the claim comes from and it is checked rather than remembered."""
    sql = (Path(__file__).resolve().parents[2] / "migrations" / "0136_warm_lane.sql"
           ).read_text(encoding="utf-8")
    assert "parked for a human" in sql, (
        "the column comment the receipt quotes is gone — either the park changed meaning or the "
        "quote is now unattributed")


def test_something_still_parks_a_row():
    """⛔ A receipt whose subject cannot occur is structurally green forever — *a gate that is
    always green is a gate nobody reads*. This pins the writer, so the receipt stays a question
    about something that can happen."""
    src = (_ENGINE / "platform" / "warm_lane.py").read_text(encoding="utf-8")
    known = TC._known_tables()
    parks = [" ".join(b.lower().split()) for b, _ in TC._statements(src, known)
             if "parked_at = now()" in " ".join(b.lower().split())]
    assert parks, (
        "nothing parks a warm-lane row any more. ⛔ Either the retry policy changed — and a row "
        "that runs out of attempts now does something else, which needs reading — or the receipt "
        "is asking about a state that can no longer occur")


# ── and the precedent it was derived from still exists ─────────────────────────────────────────

def test_the_l1_precedent_is_still_there():
    """⛔ This receipt is L1's claim applied to the table that lacked it. If the precedent is gone,
    this one needs its own justification rather than a pointer."""
    assert any(r.claim == "the parked queue is not a black hole" for r in receipts("org_probe"))
