"""Your corrections of a file, kept — in your words, with their scope (STEP-16, learning from you).

`speedrun008/YC-II W27/` STEP-16 §8.4 item 2 and S16-D1, tree `yc2_w27_s16` M46.C3.L-data.V1.U02; the table is
`founder_corrections` (migration 0241). A correction is your word on a file, and it stands as you wrote it:

  * `correct` keeps it — your words verbatim (one line), on a file, with its SCOPE: `FILE` (this file),
    `KIND` (every file of this kind of work — the kind recorded, one of `contracts/company_brief.WORK_KINDS`)
    or `COMPANY` (how your company works: your own preferences line of the brief, written through the
    brief's one writer, `platform/company_brief_store.add` — accepted as written — its line id kept);
    optionally the card it was about, the verdict it rode on and that verdict's reason (one of the eleven);
  * `withdraw` takes it back — kept, withdrawn, with who and when; a company correction's line leaves the
    brief in the same act;
  * `standing_for` reads what the file's dossier prints: the file's own (on its anchor or one of its
    people) and its kind's, newest first, bounded — the cut counted, never dropped silently. A company
    correction is the brief's, which the dossier already prints: it is not read here.

A correction's id is its content's — the tenant, the file, the words, the scope — so the same words again
are the same correction and no id is minted twice (`03` F170's rule): saying again what you withdrew makes
it stand again, now. Nothing is deleted.

⛔ NOT A LEARNING OBJECT (S16-D1, S16-D8). Nothing here proposes a pattern, writes a learned brain or enters
L6's evidence route; one click generalises nothing — a correction is only ever words you wrote. The guard
`tests/feedback/test_learning_from_you_arms_nothing.py` holds this module to it.

Pure SQL over the caller's connection; the caller owns the transaction.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.contracts.company_brief import WORK_KINDS
from genios_engine.contracts.learning_attribution import ALL_REASONS

# One name to a line: `tests/test_no_missing_module_deps` reads what a module defines by its assignments.
STANDING = "standing"
WITHDRAWN = "withdrawn"
#: This file.
FILE = "file"
#: Every file of this kind of work.
KIND = "kind"
#: How your company works — your preferences line of the brief.
COMPANY = "company"
SCOPES = (FILE, KIND, COMPANY)
#: Your words are one line (0241's own bound).
MAX_WORDS = 500
#: How many standing corrections a file's dossier prints — newest first; the rest is counted.
SHOWN = 8
#: The brief's section a company correction is written to.
COMPANY_SECTION = "preferences"


@dataclass(frozen=True, slots=True)
class Correction:
    correction_id: str
    file_id: str
    card_id: str | None
    feedback_id: str | None
    reason: str | None
    words: str
    scope: str
    kind: str | None
    brief_line_id: str | None
    corrected_by: str
    corrected_at: datetime
    state: str
    withdrawn_by: str | None = None
    withdrawn_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Standing:
    """What stands for a file: the newest `SHOWN` (or the caller's bound), and how many more."""
    corrections: tuple[Correction, ...]
    cut: int


_COLUMNS = ("correction_id, file_id, card_id, feedback_id, reason, words, scope, kind, brief_line_id, "
            "corrected_by, corrected_at, state, withdrawn_by, withdrawn_at")


def correction_id_for(org_id: str, file_id: str, words: str, scope: str) -> str:
    """The correction's id, from what it is."""
    digest = hashlib.sha256("\x1f".join((org_id, file_id, words, scope)).encode()).hexdigest()
    return f"fc_{digest[:24]}"


def _row(r) -> Correction:
    return Correction(**{k: getattr(r, k) for k in Correction.__slots__})


def _said(words: str | None) -> str:
    said = str(words or "").strip()
    if not said:
        raise ValueError("a correction that says nothing is no correction")
    if "\n" in said or "\r" in said:
        raise ValueError("a correction is one line — your words, as you would say them")
    if len(said) > MAX_WORDS:
        raise ValueError(f"a correction is at most {MAX_WORDS} characters")
    return said


def _checked(scope: str, reason: str | None, kind: str | None) -> str | None:
    if scope not in SCOPES:
        raise ValueError(f"a correction's scope is one of {SCOPES}, not {scope!r}")
    if reason is not None and reason not in ALL_REASONS:
        raise ValueError(f"{reason!r} is none of the eleven reasons")
    word = str(kind or "").strip().lower() or None
    if scope == KIND and word not in WORK_KINDS:
        raise ValueError(f"a correction for a kind of work names one of {WORK_KINDS}, not {kind!r}")
    if scope != KIND and word is not None:
        raise ValueError("only a correction for a kind of work names a kind")
    return word


def refused(words: str | None, scope: str) -> str | None:
    """Why these words with this scope are no correction — or None. Pure, so a door can refuse before it writes
    anything: words that say nothing, are not one line or run past `MAX_WORDS`, a scope outside the closed list,
    and a `COMPANY` correction longer than a line of the brief may be (`contracts/company_brief.MAX_LINE_CHARS`)."""
    from genios_engine.contracts.company_brief import MAX_LINE_CHARS
    try:
        said = _said(words)
    except ValueError as exc:
        return str(exc)
    if scope not in SCOPES:
        return f"a correction's scope is one of {SCOPES}, not {scope!r}"
    if scope == COMPANY and len(said) > MAX_LINE_CHARS:
        return f"a correction of how your company works is a line of the brief, at most {MAX_LINE_CHARS} characters"
    return None


#: The file a card is about (STEP-16 M46.C3.L-integration.V3.U04): a file's card names its file (`cards.file_id`,
#: 0220); any other card's file is the one its subject belongs to — the subject, when a correlation is anchored on
#: it; else the anchor it works at; else the subject itself (whose corrections a file of its company reads, since a
#: file's people are read with it).
_FILE_OF_CARD = (
    "select coalesce(k.file_id, "
    "  (select c.anchor_node_id from context_correlations c where c.org_id = k.org_id "
    "    and c.anchor_node_id = s.subject_node_id limit 1), "
    "  (select e.to_node_id from graph_edges e join context_correlations c on c.org_id = e.org_id "
    "    and c.anchor_node_id = e.to_node_id where e.org_id = k.org_id and e.edge_type = 'works_at' "
    "    and e.valid_to is null and e.from_node_id = s.subject_node_id order by e.to_node_id limit 1), "
    "  s.subject_node_id) as file_id "
    "from cards k join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id "
    "where k.org_id = :o and k.card_id = :c")


def file_of_card(conn, *, org_id: str, card_id: str) -> str | None:
    """The file a card is about — see `_FILE_OF_CARD`. None for a card this tenant does not hold."""
    return conn.execute(text(_FILE_OF_CARD), {"o": org_id, "c": card_id}).scalar()


def by_id(conn, org_id: str, correction_id: str) -> Correction | None:
    r = conn.execute(text(
        "select correction_id, file_id, card_id, feedback_id, reason, words, scope, kind, brief_line_id, "
        "corrected_by, corrected_at, state, withdrawn_by, withdrawn_at from founder_corrections "
        "where org_id = :o and correction_id = :c"), {"o": org_id, "c": correction_id}).first()
    return _row(r) if r else None


def correct(conn, *, org_id: str, file_id: str, words: str, scope: str, by: str, at: datetime,
            card_id: str | None = None, feedback_id: str | None = None, reason: str | None = None,
            kind: str | None = None) -> Correction:
    """Keep your correction of the file. The same words with the same scope again are that correction —
    unchanged while it stands, standing again (said now) when you had withdrawn it. ValueError for words
    that say nothing, are not one line or run past `MAX_WORDS`, a scope or a reason outside the closed
    lists, or a kind on the wrong scope — before anything is written. A `COMPANY` correction is written to
    the brief first, as your own accepted line (whose own rules — 200 characters — it then meets)."""
    said = _said(words)
    kind = _checked(scope, reason, kind)
    line_id = None
    if scope == COMPANY:
        from genios_engine.platform import company_brief_store
        line_id = company_brief_store.add(conn, org_id=org_id, section=COMPANY_SECTION, words=said,
                                          decided_by=by, at=at)
    cid = correction_id_for(org_id, file_id, said, scope)
    conn.execute(text(
        "insert into founder_corrections (org_id, correction_id, file_id, card_id, feedback_id, reason, words, "
        "scope, kind, brief_line_id, corrected_by, corrected_at, state) values (:o, :c, :f, :card, :fb, "
        ":reason, :w, :scope, :kind, :line, :by, :at, 'standing') "
        "on conflict (org_id, correction_id) do update set state = 'standing', withdrawn_by = null, "
        "withdrawn_at = null, corrected_by = excluded.corrected_by, corrected_at = excluded.corrected_at, "
        "brief_line_id = excluded.brief_line_id "
        "where founder_corrections.state = 'withdrawn'"),
        {"o": org_id, "c": cid, "f": file_id, "card": card_id, "fb": feedback_id, "reason": reason,
         "w": said, "scope": scope, "kind": kind, "line": line_id, "by": by, "at": at})
    return by_id(conn, org_id, cid)


def withdraw(conn, *, org_id: str, correction_id: str, by: str, at: datetime) -> Correction:
    """Take your correction back: kept, withdrawn, with who and when. A company correction's line leaves the
    brief in the same act (unless you already removed it there). ValueError for one that is not standing."""
    r = conn.execute(text(
        "update founder_corrections set state = 'withdrawn', withdrawn_by = :by, withdrawn_at = :at "
        "where org_id = :o and correction_id = :c and state = 'standing' returning correction_id, file_id, "
        "card_id, feedback_id, reason, words, scope, kind, brief_line_id, corrected_by, corrected_at, state, "
        "withdrawn_by, withdrawn_at"),
        {"o": org_id, "c": correction_id, "by": by, "at": at}).first()
    if r is None:
        raise ValueError(f"correction {correction_id} is not standing")
    withdrawn = _row(r)
    if withdrawn.scope == COMPANY and withdrawn.brief_line_id:
        from genios_engine.platform import company_brief_store
        try:
            company_brief_store.remove(conn, org_id=org_id, line_id=withdrawn.brief_line_id, decided_by=by,
                                       at=at)
        except company_brief_store.CompanyBriefError as exc:
            if exc.code != "not_accepted":
                raise
    return withdrawn


def standing_for(conn, org_id: str, file_id: str, *, people: tuple[str, ...] = (), kind: str | None = None,
                 limit: int = SHOWN) -> Standing:
    """What stands for the file: its own corrections (on its anchor or one of its people) and its kind of
    work's, newest first — at most `limit`, the rest counted in `cut`. A company correction is the brief's."""
    ids = sorted({str(file_id), *(str(p) for p in people)})
    rows = conn.execute(text(
        "select correction_id, file_id, card_id, feedback_id, reason, words, scope, kind, brief_line_id, "
        "corrected_by, corrected_at, state, withdrawn_by, withdrawn_at, count(*) over () as total "
        "from founder_corrections where org_id = :o and state = 'standing' "
        "and ((scope = 'file' and file_id = any(:ids)) "
        "or (scope = 'kind' and cast(:k as text) is not null and kind = :k)) "
        "order by corrected_at desc, correction_id limit :n"),
        {"o": org_id, "ids": ids, "k": kind, "n": max(0, int(limit))}).fetchall()
    total = int(rows[0].total) if rows else 0
    return Standing(corrections=tuple(_row(r) for r in rows), cut=max(0, total - len(rows)))


def made_between(conn, org_id: str, *, since: datetime, until: datetime) -> tuple[Correction, ...]:
    """Every correction made in [since, until) — standing or withdrawn since — oldest first: the week's
    (`feedback/scorecard`, STEP-16 M47.C3.L-logic.V5.U01)."""
    return tuple(_row(r) for r in conn.execute(text(
        f"select {_COLUMNS} from founder_corrections where org_id = :o and corrected_at >= :since "
        "and corrected_at < :until order by corrected_at, correction_id"),
        {"o": org_id, "since": since, "until": until}))


__all__ = ["COMPANY", "COMPANY_SECTION", "Correction", "FILE", "KIND", "MAX_WORDS", "SCOPES", "SHOWN",
           "STANDING", "Standing", "WITHDRAWN", "by_id", "correct", "correction_id_for", "file_of_card",
           "made_between", "refused", "standing_for", "withdraw"]
