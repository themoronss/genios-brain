"""Wave Z6 · seam OUT E3 — the book-level daily re-rank (doc 06 OUT-2, DLG-09).

THE DEFECT, RESTATED. Every ranked surface in this product is a read-time `ORDER BY
final_utility_bp` over rows that were scored **one at a time, each against nothing but itself**. No
pass has ever compared the day's decisions against EACH OTHER, so "the three things that matter this
morning" is arithmetic over independent scores — three cards on one account all rank highly for the
same reason, a card ignored three days running returns unchanged in position four, and a decision
built on two absences outranks one built on six sources because absence never entered the number.

This module is the pass that compares them. It is **deterministic, integer-only, and invents no new
score**: existing utility is re-weighed with portfolio context, and every adjustment lands in
`rank_components` on the entry it moved. Doc 07's rule for this seam is one sentence — *"why #1
today" is data, not narrative* — so the components ARE the answer and a sentence that disagreed with
them would be a bug, not a style choice.

THE THREE TERMS, AND WHY EACH IS A PENALTY AND NOT A BONUS
-----------------------------------------------------------
    concentration   three cards on one account compete; the best carries, the rest step down
    staleness       a card surfaced N times and still unactioned decays
    coverage        a decision carrying recorded absences ranks below an evidenced one

All three are subtractions from `final_utility_bp`, never additions to it. A bonus would let the
book pass raise a decision above what Layer 4 concluded about it, which is a second scorer with
opinions the Decision Maker never had. Subtraction can only ever say *"not this one, today"* — a
statement about the DAY, which is exactly what a brief is.

WHAT "OPEN DECISIONS ABOVE THE FLOOR" MEANS HERE
--------------------------------------------------
The floor is upstream and is not re-applied: a decision below its lane's confidence floor became a
reason-coded DEFER in `decision_maker.decide` and never produced a card at all, so the card queue is
already the above-floor set. What this module adds to that is the authority predicate every other
surface uses (`reason/authority.py`) — a card is a rendering of a decision, and a decision stops
being authoritative when the graph moves, the pack changes or the signal closes. A brief is the one
surface a person acts on without opening anything else; it may not rank a superseded conclusion.

THE DAY KEY. `brief_date_key` is the UTC date of the evaluation instant, and the instant is a
PARAMETER — no clock is read below this module's callers. Per-tenant local midnight is a real
refinement and is deliberately not guessed at here: it needs the tenant's timezone, which lives on
the context snapshot rather than on the org, and a brief that silently changed day boundaries per
tenant without that being stated would make two days' briefs incomparable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.reasoning import BriefEntry, BriefRanking
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason.authority import (
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    authority_time,
)

#: The model's version, stored beside every ranking. The weights below are a judgement about a
#: portfolio, not a law of arithmetic; when one changes, yesterday's brief must still say which
#: model produced it or "the ranking moved" becomes unanswerable.
BOOK_RANKING_VERSION = "book_ranking@1"

#: One step per competing card on the same account, after the carrier. 1,000 bp is a tenth of the
#: scale: enough to lose a near-tie to a different account, never enough to bury a genuinely urgent
#: second card behind an unrelated quiet one.
CONCENTRATION_STEP_BP = 1_000
CONCENTRATION_CAP_BP = 3_000

#: One step per PRIOR surfacing. The first surfacing costs nothing — a card seen once is not stale,
#: it is new — so the count entering the arithmetic is `surfaced - 1`.
STALENESS_STEP_BP = 500
STALENESS_CAP_BP = 2_500

#: One step per absence the decision itself recorded (`reasoning_run_outputs.missing_data`, which is
#: `ReasoningDecision.uncertainty`: the missing fields, the absent units, the unevaluable rules).
#: Capped well below the other two: a decision that names what it does not know is more honest than
#: one that names nothing, and the penalty must never become a reason to record fewer absences.
COVERAGE_STEP_BP = 400
COVERAGE_CAP_BP = 2_000

#: How many entries one brief carries. A ranking is a total order over the whole open set, but a
#: stored artifact and a rendered surface are both bounded things; the cut is by rank, so the top of
#: the order is never affected by where it falls.
BRIEF_ENTRY_CAP = 25

#: The component names. Constants because they are read by the surface that answers "why #1 today",
#: and a renderer keying on a literal string is one rename away from an empty explanation.
BASE_COMPONENT = "base_utility_bp"
CONCENTRATION_COMPONENT = "concentration_penalty_bp"
STALENESS_COMPONENT = "staleness_penalty_bp"
COVERAGE_COMPONENT = "coverage_penalty_bp"
BOOK_SCORE_COMPONENT = "book_score_bp"

#: Why an open decision did not reach the brief. Recorded per drop, because a brief that silently
#: omits a card is indistinguishable from one that never saw it.
DROPPED_DUPLICATE = "duplicate_decision_id"
DROPPED_BELOW_CAP = "below_entry_cap"


@dataclass(frozen=True, slots=True)
class OpenDecision:
    """One open, authoritative decision as the book pass sees it.

    The three portfolio inputs are COUNTS, not scores, and they are separated from the identifiers
    deliberately: everything below the line is provenance for a human, and nothing below the line
    may enter the arithmetic. `account_ref` is the one borderline case and it is above the line
    because concentration is defined over it.
    """

    decision_id: str
    account_ref: str
    base_utility_bp: int
    surfaced_count: int = 0
    absence_count: int = 0
    # ── provenance; never arithmetic ────────────────────────────────────────────────────────
    card_id: str | None = None
    subject_node_id: str | None = None
    headline: str | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("surfaced_count", "absence_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
        if isinstance(self.base_utility_bp, bool) or not isinstance(self.base_utility_bp, int) \
                or not 0 <= self.base_utility_bp <= 10_000:
            raise ValueError("base_utility_bp must be integer basis points")


@dataclass(frozen=True, slots=True)
class BookRanking:
    """The ranking and the record of how it was reached.

    `BriefRanking` is the contract — closed, validated, and what a surface renders. `receipts`
    carries the COUNTS behind each penalty (three surfacings, four absences, second card on this
    account) and the drops. They are separate because `rank_components` is basis points by contract
    and a count is not a basis point: putting `surfaced_count: 3` in there would type-check and lie.
    """

    ranking: BriefRanking
    receipts: tuple[Mapping[str, Any], ...] = ()
    dropped: tuple[Mapping[str, Any], ...] = ()
    version: str = BOOK_RANKING_VERSION

    @property
    def ranking_hash(self) -> str:
        """A content address over the entries, so "did today's brief change" is a string compare."""
        return semantic_hash({
            "version": self.version,
            "org_id": self.ranking.org_id,
            "brief_date_key": self.ranking.brief_date_key,
            "entries": [{"decision_id": entry.decision_id, "rank": entry.rank,
                         "book_score_bp": entry.book_score_bp,
                         "rank_components": dict(entry.rank_components)}
                        for entry in self.ranking.entries],
        })


def brief_date_key(eval_time: datetime) -> str:
    """The tenant's brief day. UTC, deliberately — see the module docstring."""
    return eval_time.date().isoformat()


def _stepped(count: int, step_bp: int, cap_bp: int) -> int:
    """`count` steps of `step_bp`, capped. Integer throughout; a cap rather than a curve because a
    curve would need a float and a float would make the brief machine-dependent."""
    return min(max(count, 0) * step_bp, cap_bp)


def concentration_penalties(decisions: Sequence[OpenDecision]) -> dict[str, int]:
    """Per decision: the step-down for competing with better cards on the SAME account.

    The carrier is the account's best card by `(-base_utility_bp, decision_id)` — the same total
    order `rank_candidates` imposes on a decision's own field, for the same reason: a tie broken by
    iteration order is a brief that reorders itself on a re-read with nothing changed.
    """
    by_account: dict[str, list[OpenDecision]] = {}
    for decision in decisions:
        by_account.setdefault(decision.account_ref, []).append(decision)
    penalties: dict[str, int] = {}
    for account in sorted(by_account):
        ordered = sorted(by_account[account],
                         key=lambda item: (-item.base_utility_bp, item.decision_id))
        for position, decision in enumerate(ordered):
            penalties[decision.decision_id] = _stepped(
                position, CONCENTRATION_STEP_BP, CONCENTRATION_CAP_BP)
    return penalties


def book_rank(*, org_id: str, eval_time: datetime, decisions: Sequence[OpenDecision],
              entry_cap: int = BRIEF_ENTRY_CAP) -> BookRanking:
    """The one deterministic executive pass. Pure: no clock, no database, no model.

    Ordering is `(-book_score_bp, decision_id)` and ranks are contiguous from one — enforced twice,
    once here and once by `BriefRanking`'s constructor, because a brief with two #2s renders in an
    order nobody chose.
    """
    seen: dict[str, OpenDecision] = {}
    dropped: list[dict[str, Any]] = []
    for decision in sorted(decisions, key=lambda item: (-item.base_utility_bp, item.decision_id)):
        if decision.decision_id in seen:
            # Two cards claiming one decision would double-count that situation against every other
            # account in the book. The first (best, then lowest id) carries; the drop is receipted.
            dropped.append({"decision_id": decision.decision_id, "reason": DROPPED_DUPLICATE,
                            "card_id": decision.card_id})
            continue
        seen[decision.decision_id] = decision

    concentration = concentration_penalties(list(seen.values()))
    scored: list[tuple[OpenDecision, dict[str, int], dict[str, Any]]] = []
    for decision in seen.values():
        concentration_bp = concentration[decision.decision_id]
        staleness_bp = _stepped(decision.surfaced_count - 1 if decision.surfaced_count else 0,
                                STALENESS_STEP_BP, STALENESS_CAP_BP)
        coverage_bp = _stepped(decision.absence_count, COVERAGE_STEP_BP, COVERAGE_CAP_BP)
        book_score = max(0, decision.base_utility_bp
                         - concentration_bp - staleness_bp - coverage_bp)
        components = {
            BASE_COMPONENT: decision.base_utility_bp,
            CONCENTRATION_COMPONENT: concentration_bp,
            STALENESS_COMPONENT: staleness_bp,
            COVERAGE_COMPONENT: coverage_bp,
            BOOK_SCORE_COMPONENT: book_score,
        }
        receipt = {
            "decision_id": decision.decision_id,
            "account_ref": decision.account_ref,
            "card_id": decision.card_id,
            "subject_node_id": decision.subject_node_id,
            "headline": decision.headline,
            "run_id": decision.run_id,
            "surfaced_count": decision.surfaced_count,
            "absence_count": decision.absence_count,
            "components": components,
        }
        scored.append((decision, components, receipt))

    scored.sort(key=lambda item: (-item[1][BOOK_SCORE_COMPONENT], item[0].decision_id))
    kept, cut = scored[:max(entry_cap, 0)], scored[max(entry_cap, 0):]
    dropped.extend({"decision_id": decision.decision_id, "reason": DROPPED_BELOW_CAP,
                    "card_id": decision.card_id,
                    "book_score_bp": components[BOOK_SCORE_COMPONENT]}
                   for decision, components, _receipt in cut)

    entries = tuple(
        BriefEntry(decision_id=decision.decision_id, rank=rank,
                   book_score_bp=components[BOOK_SCORE_COMPONENT], rank_components=components)
        for rank, (decision, components, _receipt) in enumerate(kept, start=1))
    receipts = tuple({**receipt, "rank": rank}
                     for rank, (_decision, _components, receipt) in enumerate(kept, start=1))
    return BookRanking(
        ranking=BriefRanking(org_id=org_id, brief_date_key=brief_date_key(eval_time),
                             entries=entries),
        receipts=receipts, dropped=tuple(dropped))


# =================================================================================================
# the tenant's open, authoritative decisions — one query, the shared authority boundary
# =================================================================================================

#: `card_events` records one row per surfacing (`card.surfaced`). Counting them is what makes
#: "surfaced three times and still open" a fact rather than an inference from `created_at`.
_SURFACED_KIND = "card.surfaced"

_OPEN_DECISIONS_SQL = (
    "select ro.decision_core->>'contract_decision_id' as decision_id, "
    "rr.run_id as run_id, k.card_id, k.headline, s.subject_node_id, "
    "selected_rc.final_utility_bp as base_utility_bp, "
    "coalesce(jsonb_array_length(ro.missing_data), 0) as absence_count, "
    "(select count(*) from card_events ce where ce.org_id=k.org_id and ce.card_id=k.card_id "
    f"and ce.kind='{_SURFACED_KIND}') as surfaced_count, "
    "coalesce(account_edge.to_node_id, s.subject_node_id) as account_ref "
    "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
    + AUTHORITATIVE_SIGNAL_JOINS +
    "left join lateral (select e.to_node_id from graph_edges e "
    "where e.org_id=k.org_id and e.from_node_id=s.subject_node_id "
    "and e.edge_type='works_at' and e.valid_to is null "
    "order by e.to_node_id limit 1) account_edge on true "
    "where k.org_id=:o and k.state in ('queued','surfaced') and s.status='open' "
    "and k.expires_at > :now and " + AUTHORITATIVE_SIGNAL_PREDICATE + " "
    "and ro.decision_core->>'contract_decision_id' is not null "
    "order by selected_rc.final_utility_bp desc, k.card_id"
)


def open_decisions(engine, *, org_id: str, eval_time: datetime) -> tuple[OpenDecision, ...]:
    """Every open, authoritative decision this tenant is currently carrying.

    The account is the company the subject `works_at` when the graph knows one, and the subject
    itself when it does not — never NULL, because a null concentration key would silently group
    every unaffiliated subject into one "account" and make them compete with each other.
    """
    from sqlalchemy import text

    if engine is None:
        return ()
    as_of = authority_time(eval_time)
    with engine.connect() as conn:
        rows = conn.execute(text(_OPEN_DECISIONS_SQL),
                            {"o": org_id, "now": eval_time, "authority_time": as_of}
                            ).mappings().all()
    return tuple(OpenDecision(
        decision_id=str(row["decision_id"]),
        account_ref=str(row["account_ref"]),
        base_utility_bp=int(row["base_utility_bp"]),
        surfaced_count=int(row["surfaced_count"] or 0),
        absence_count=int(row["absence_count"] or 0),
        card_id=row["card_id"], subject_node_id=row["subject_node_id"],
        headline=row["headline"], run_id=row["run_id"],
    ) for row in rows)


# =================================================================================================
# persistence — a brief is a daily ARTIFACT, so it exists in a table
# =================================================================================================

def store_ranking(engine, ranking: BookRanking, *, computed_at: datetime) -> bool:
    """Write today's ranking for this tenant. Returns whether anything changed.

    An UPSERT keyed on `(org_id, brief_date_key)` rather than an insert-once, because the open set
    moves through the day and a brief frozen at the first read would go stale by lunchtime. What is
    kept is one row per tenant per day carrying the CURRENT ranking and the hash of it, so "was a
    brief produced for this tenant on this day, and did it change" are both single queries — which
    is the gate row (K6) and, more usefully, the thing an operator asks during a pilot.
    """
    from sqlalchemy import text

    if engine is None:
        return False
    payload = {
        "o": ranking.ranking.org_id,
        "d": ranking.ranking.brief_date_key,
        "e": _json([{"decision_id": entry.decision_id, "rank": entry.rank,
                     "book_score_bp": entry.book_score_bp,
                     "rank_components": dict(entry.rank_components)}
                    for entry in ranking.ranking.entries]),
        "r": _json(list(ranking.receipts)),
        "x": _json(list(ranking.dropped)),
        "n": len(ranking.ranking.entries),
        "v": ranking.version,
        "h": ranking.ranking_hash,
        "t": computed_at,
    }
    with engine.begin() as conn:
        return conn.execute(text(
            "insert into l4_brief_rankings (org_id, brief_date_key, entries, receipts, dropped, "
            "entry_count, model_version, ranking_hash, computed_at) "
            "values (:o,:d,cast(:e as jsonb),cast(:r as jsonb),cast(:x as jsonb),:n,:v,:h,:t) "
            "on conflict (org_id, brief_date_key) do update set "
            "entries=excluded.entries, receipts=excluded.receipts, dropped=excluded.dropped, "
            "entry_count=excluded.entry_count, model_version=excluded.model_version, "
            "ranking_hash=excluded.ranking_hash, computed_at=excluded.computed_at "
            "where l4_brief_rankings.ranking_hash <> excluded.ranking_hash"),
            payload).rowcount > 0


def stored_ranking(engine, *, org_id: str, date_key: str) -> Mapping[str, Any] | None:
    """The stored row for one tenant-day, or None. Raises rather than swallowing: an operator
    asking whether a brief was produced must see a database error, never the word 'no'."""
    from sqlalchemy import text

    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(text(
            "select org_id, brief_date_key, entries, receipts, dropped, entry_count, "
            "model_version, ranking_hash, computed_at from l4_brief_rankings "
            "where org_id=:o and brief_date_key=:d"), {"o": org_id, "d": date_key}
        ).mappings().first()
    return dict(row) if row is not None else None


def _json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)


def daily_brief_ranking(engine, *, org_id: str, eval_time: datetime,
                        entry_cap: int = BRIEF_ENTRY_CAP) -> tuple[BookRanking, bool]:
    """Read → rank → store, in that order. The one entry point a request path calls."""
    ranking = book_rank(org_id=org_id, eval_time=eval_time,
                        decisions=open_decisions(engine, org_id=org_id, eval_time=eval_time),
                        entry_cap=entry_cap)
    return ranking, store_ranking(engine, ranking, computed_at=eval_time)


__all__ = ["BASE_COMPONENT", "BOOK_RANKING_VERSION", "BOOK_SCORE_COMPONENT", "BRIEF_ENTRY_CAP",
           "CONCENTRATION_CAP_BP", "CONCENTRATION_COMPONENT", "CONCENTRATION_STEP_BP",
           "COVERAGE_CAP_BP", "COVERAGE_COMPONENT", "COVERAGE_STEP_BP", "DROPPED_BELOW_CAP",
           "DROPPED_DUPLICATE", "STALENESS_CAP_BP", "STALENESS_COMPONENT", "STALENESS_STEP_BP",
           "BookRanking", "OpenDecision", "book_rank", "brief_date_key",
           "concentration_penalties", "daily_brief_ranking", "open_decisions", "store_ranking",
           "stored_ranking"]
