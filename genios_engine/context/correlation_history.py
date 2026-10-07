"""Cross History — what happened the LAST time this anchor was in this situation.

    pytest tests/context/test_cross_history.py -q

THE MISSING CORRELATOR. Eight are named and built: Tool, Resource, User, Timeline,
Conversation, Domain, Organization, Dependency. Every one of them correlates observations that
coexist. Not one of them correlates a situation against ITS OWN PAST, so every customer's second
time through anything is treated as their first.

The failure is concrete. In March a customer raised a billing complaint; a card went out, it was
refunded, `execution_outcomes` recorded `succeeded`, and the correlation went cold. In September
the same customer raises the same complaint. `find_or_open` reads generation 1, `joins_window`
says the window has passed, and it opens generation 2 AS A STRANGER — same anchor, same domain,
a base key that provably matches. The engine cannot say "this is the third time this quarter",
cannot say "last time the refund closed it", and cannot say "we already sent this exact card and
they marked it wrong".

WHY NO MIGRATION. `context_correlations`' own comment says generations exist so *"the old one
stays findable instead of overwritten"* — and that is true, the chain is already queryable by
`(org, anchor, domain)` ordered by generation. Nothing was missing from the schema. What was
missing is a READER, which is the shape this branch has found ten times over: a capability
exists and nothing consumes it at the point that needs it.

WHAT THIS PUBLISHES — per (anchor, domain), each name below qualified by its domain (`@<domain>`,
WHERE EACH PAST IS KEPT below) — and the line each one refuses to cross:

  derived.history.times_seen          how many generations this anchor has had in this domain.
                                      A COUNT, not a judgment: three visits may be three
                                      unrelated questions from a good customer or one problem
                                      nobody fixed, and nothing here can tell those apart.
  derived.history.days_since_prior    how long the gap was. Two weeks and two years mean
                                      different things and only the reader knows which.
  derived.history.prior_outcome       how the LAST generation's execution ended, verbatim from
                                      `execution_outcomes.label`. Never re-graded here — a
                                      second opinion on what an ending means is how two
                                      spellings of the same question come to disagree.
  derived.history.prior_card_verdict  what the person DID with the last card about this anchor,
                                      as `cause` or `cause:reason` —
                                      `run_play | do_it_myself | wrong:not_relevant | …`
                                      (eleven `wrong:*` reasons — see `learning_attribution`).
                                      "We already told them this and they dismissed it" is the
                                      single most useful thing this file can say, and the
                                      hardest to say honestly.

WHAT IT MAY NOT SAY. Recurrence is not causation and it is not fault. That an anchor is on its
fourth generation says nothing about whose fault that is, whether the earlier fix was wrong, or
whether it will recur again. `FX-36` and `CC-35` both draw this line: a co-occurrence, however
many times it repeats, cannot become a `causes` edge. These facts exist so an authored situation
can SAY "this is the third time" and let a person decide what that means.

ABSENCE IS TYPED, and it matters more here than almost anywhere. A first-generation anchor has
no prior — that is GENUINELY_ABSENT, a real finding ("we have never seen this before"). An
anchor whose prior generation exists but whose execution was never recorded is UNKNOWABLE — we
do not know how it ended. Collapsing those two would let "no record of last time" read as "there
was no last time", which is exactly the inversion the publication gate exists to prevent, so the
two are published as different values rather than as one missing field.

WHERE EACH PAST IS KEPT (STEP-10, `yc2_w27_s10 · M29.C2.L-logic.V0.U03`). The past is computed per
(anchor, domain) — the vocabulary declares `derived.history.times_seen` as the generations "of this
anchor in this domain" — and was published per ANCHOR: a fact's id is prefix + node + field
(`analytic/publish.derived_fact_version_id`), so an anchor in two domains wrote both pasts onto one
row per fact and kept whichever domain sorted last (`STEP-10` §8.1, golden F29). A file — one anchor
in every domain — showed one past, and its two domains rewrote each other's rows on every sweep.
`graph_facts` holds ONE current value per (org, subject, field): no index enforces it
(`graph_facts_current` is not unique), every reader assumes it. So the domain had to go into the
subject, the value or the field:

  * the SUBJECT stays the anchor. A fact's subject is a node — a merge repoints it, the file reads
    by it (`context/workstreams`) — and no node stands for an (anchor, domain) pair; one minted per
    pair is a node no merge, erasure or as-of read knows about;
  * the VALUE stays the declared scalar. `times_seen` is a count a predicate compares (`> 1`); a map
    of domains would turn every such comparison into a type error;
  * so the FIELD carries the domain: `derived.history.<fact>@<domain>` (`history_field`). The
    declared path is its stem, so the family is still exactly the four names of
    `packs/substrate_demand.HISTORY_FIELDS`, and the corpus measure still finds each one.

The bare paths are no longer written. No single domain answers "this domain" for an anchor in two,
and a bare value that is right only while the anchor stays in one domain is the same defect waiting
for a second domain. Nothing reads them (zero corpus readers, `packs/substrate_demand`); the first
reader resolves a declared path in the domain it is evaluating — its situation's. What a sweep did
not write is closed (`analytic/publish.close_derived_facts`): the per-anchor rows the old shape left,
and the past of a pair the chain no longer holds. Closed, never deleted — an as-of read of last week
still answers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import bindparam, text

from genios_engine.context.analytic.publish import close_derived_facts, publish_derived_fact

#: Every fact this module writes. One prefix so `publish_derived_fact` can only ever close its
#: own rows — an open row on the same field written by another writer is left exactly alone.
VERSION_PREFIX = "fv_history:"

#: A prior generation exists and we know how it ended. Anything else is one of the two typed
#: absences below, never a blank.
UNKNOWN_OUTCOME = "unrecorded"
#: There IS no prior. Not a gap — a finding: this anchor has never been here before.
NO_PRIOR = "first_time"

#: What joins a declared path to the domain its value was measured in (`history_field`).
DOMAIN_MARK = "@"


def history_field(path: str, domain: str) -> str:
    """The field one domain's past is published under: `derived.history.times_seen@admin`."""
    return f"{path}{DOMAIN_MARK}{domain}"


@dataclass(frozen=True)
class AnchorHistory:
    """One anchor's own past, as far as this tenant's own records can establish it."""

    anchor_node_id: str
    domain: str
    #: How many times this anchor has opened in this domain, INCLUDING the live one. 1 means
    #: this is the first time.
    #:
    #: THE GENERATION NUMBER, NOT THE ROW COUNT. `find_or_open` increments `generation`
    #: monotonically and never reuses one, so it is the authoritative count even after
    #: retention has pruned an early row. Counting rows would report a customer's fourth
    #: complaint as their second the day the first two aged out — an undercount that arrives
    #: silently and always in the direction of "this is not a pattern".
    times_seen: int
    #: Whole days between the prior generation's last event and this one's first. None when
    #: there is no prior, or when either timestamp is missing — never 0, which would read as
    #: "it recurred the same day".
    days_since_prior: int | None
    #: `execution_outcomes.label` for the prior generation, verbatim. `NO_PRIOR` when this is
    #: generation 1; `UNKNOWN_OUTCOME` when a prior exists and nothing recorded its ending.
    prior_outcome: str
    #: The last terminal card verdict on this anchor. Same two sentinels, same reason.
    prior_card_verdict: str

    @property
    def is_recurrence(self) -> bool:
        return self.times_seen > 1


#: EVERY GENERATION FOR EVERY ANCHOR, in one statement. The shape `find_organizations` and
#: `read_dependency_claims` already keep: a sweep may not issue one query per anchor, because a
#: tenant with four thousand anchors then issues four thousand queries and the sweep that was
#: supposed to add a fact becomes the reason the drain times out.
_GENERATIONS = text(
    "select anchor_node_id, domain, generation, first_event_at, last_event_at, correlation_id "
    "from context_correlations where org_id = :o "
    "order by anchor_node_id, domain, generation"
)

#: How the PRIOR generation's work ended, reached in TWO HOPS and not one.
#:
#: The obvious join is wrong and would have matched nothing, silently, forever.
#: `execution_outcomes.subject_ref` is NOT a node id: `deliver/pipeline.py:357` writes
#: `signal:<signal_id>`, `lifecycle/resolution.py:223` writes a situation-and-event pair, and
#: `analytic/cohort.py:1682` writes `cohort-draft:<hash>`. It is a free-text reference whose
#: shape depends on which layer opened the execution. Only the `signal:` shape reaches an
#: anchor, and it reaches it through `signals.subject_node_id`.
#:
#: So the join is stated as what it actually is — outcomes whose subject is a signal, and that
#: signal's subject node. An execution opened by any other route is not counted here rather
#: than matched by luck.
_PRIOR_OUTCOMES = text(
    "select s.subject_node_id as anchor, o.label, o.closed_at "
    "from execution_outcomes o "
    "join signals s on s.org_id = o.org_id "
    # `substr(x, 8)`, NOT `substring(x from 8)`. The second is Postgres-only and would make this
    # module untestable on SQLite — and a suite where this file can only SKIP is a suite that
    # reports green about a query nobody ran. Both engines implement the two-argument form.
    # 8 is one past `len('signal:')`.
    "  and s.signal_id = substr(o.subject_ref, 8) "
    "where o.org_id = :o and o.subject_ref like 'signal:%' "
    "  and s.subject_node_id in :anchors "
    "order by o.closed_at"
).bindparams(bindparam("anchors", expanding=True))

#: What the person DID with the last card about this anchor, same two hops for the same reason:
#: `cards` carries `signal_id` and no anchor column at all.
#:
#: THE COLUMN IS `cause`, NOT `verdict`. Its check constraint fixes the vocabulary at
#: `run_play | do_it_myself | wrong`, and `reason` narrows a `wrong` to one of the ELEVEN in
#: `contracts/learning_attribution.WrongReason` — three until 2026-09-30, and the three keep their
#: exact spellings so every row already written still reads the same. Those are different sentences
#: and the pair is carried whole:
#: "they did it themselves" is not "we were wrong", and reporting either as the other is the
#: precision-denominator defect this branch already fixed once at the feedback layer.
_PRIOR_VERDICTS = text(
    "select s.subject_node_id as anchor, v.cause, v.reason, v.occurred_at "
    "from card_feedback_verdicts v "
    "join cards c on c.org_id = v.org_id and c.card_id = v.card_id "
    "join signals s on s.org_id = c.org_id and s.signal_id = c.signal_id "
    "where v.org_id = :o and s.subject_node_id in :anchors "
    "order by v.occurred_at"
).bindparams(bindparam("anchors", expanding=True))


def _instant(value: object) -> datetime | None:
    """A timestamp from either driver, or None.

    PSYCOPG HANDS BACK A `datetime`; SQLITE HANDS BACK A STRING. Without this the arithmetic
    below raised TypeError on SQLite and `_days` swallowed it into None — so every hermetic
    test would have reported "no gap recorded" while the production path worked, which is the
    worst possible split: green locally, and no test covering what actually ships. The test
    caught it, which is the reason the test is hermetic rather than Postgres-only.
    """
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _days(later: object, earlier: object) -> int | None:
    """Whole days between two instants, or None when either is missing or unreadable.

    NONE, NOT ZERO, on a missing timestamp — the same rule `waiting._days` follows. A zero here
    would read as "it recurred the same day", which is a claim, where None is the absence of one.
    """
    left, right = _instant(later), _instant(earlier)
    if left is None or right is None:
        return None
    try:
        # A NAIVE AND AN AWARE INSTANT CANNOT BE SUBTRACTED, and mixing them is possible here:
        # SQLite returns naive strings while the live column is `timestamptz`. Comparing them
        # by assuming UTC would invent an offset; refusing is the honest answer, and the gap
        # is then simply not published rather than published wrong.
        return max(0, int((left - right).total_seconds() // 86_400))
    except (TypeError, ValueError):
        return None


def read_histories(conn, org_id: str) -> tuple[AnchorHistory, ...]:
    """Every anchor's own past, in three statements regardless of how many anchors there are."""
    rows = conn.execute(_GENERATIONS, {"o": org_id}).mappings().all()
    if not rows:
        return ()

    # (anchor, domain) -> its generations in order. The query orders them, so `append` preserves
    # generation order without a second sort.
    chains: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        chains.setdefault((str(row["anchor_node_id"]), str(row["domain"])), []).append(dict(row))

    anchors = sorted({key[0] for key in chains})

    # LAST WINS, and the queries order by time so the last row read is the most recent. A
    # `max()` over a dict would need a comparison on possibly-None timestamps; ordering in SQL
    # puts that burden where it belongs.
    outcomes: dict[str, str] = {}
    for row in _rows(conn, _PRIOR_OUTCOMES, {"o": org_id, "anchors": anchors}):
        label = str(row["label"] or "").strip()
        if label:
            outcomes[str(row["anchor"])] = label

    verdicts: dict[str, str] = {}
    for row in _rows(conn, _PRIOR_VERDICTS, {"o": org_id, "anchors": anchors}):
        cause = str(row["cause"] or "").strip()
        if not cause:
            continue
        # BOTH HALVES OR NEITHER. `wrong` alone loses why, and the three reasons mean different
        # things to a reader deciding whether to send a fourth card: `bad_timing` invites a
        # later retry, `not_relevant` does not.
        reason = str(row["reason"] or "").strip()
        verdicts[str(row["anchor"])] = f"{cause}:{reason}" if reason else cause

    out: list[AnchorHistory] = []
    for (anchor, domain), chain in sorted(chains.items()):
        times_seen = max(int(row.get("generation") or 1) for row in chain)
        first_of_current = chain[-1].get("first_event_at")
        # THE PRIOR ROW WE STILL HAVE, which is not always generation N-1. After a retention
        # prune the gap is measured against the newest surviving earlier row and is therefore a
        # LOWER bound on the true gap — reported rather than withheld, because "at least this
        # long ago" is useful and a missing number is not. When no earlier row survives at all
        # the gap is None, never a guess.
        last_of_prior = chain[-2].get("last_event_at") if len(chain) > 1 else None
        out.append(AnchorHistory(
            anchor_node_id=anchor, domain=domain, times_seen=times_seen,
            days_since_prior=_days(first_of_current, last_of_prior),
            # THE TWO ABSENCES ARE DIFFERENT ANSWERS. `first_time` is a finding — we have never
            # seen this before. `unrecorded` is an admission — it happened and we do not know how
            # it went. Collapsing them would let "no record of last time" read as "there was no
            # last time", which inverts the meaning of the fact.
            prior_outcome=(NO_PRIOR if times_seen == 1
                           else outcomes.get(anchor, UNKNOWN_OUTCOME)),
            prior_card_verdict=(NO_PRIOR if times_seen == 1
                                else verdicts.get(anchor, UNKNOWN_OUTCOME))))
    return tuple(out)


def _rows(conn, statement, params) -> Sequence:
    """One optional-table read. A tenant whose `cards` or `execution_outcomes` table is empty or
    absent must not take the whole history sweep down with it — the generation chain is the
    load-bearing half and it stands on its own."""
    try:
        return conn.execute(statement, params).mappings().all()
    except Exception:      # noqa: BLE001 — an enrichment, never a reason to lose the chain
        return ()


def publish_histories(conn, org_id: str, *, eval_time: datetime) -> int:
    """Write each anchor's past in each of its domains as `derived.history.*@<domain>` facts, and
    close the history facts this sweep did not write. Returns the rows it changed: written and
    closed.

    PUBLISHED FOR EVERY ANCHOR, INCLUDING FIRST-TIMERS, deliberately. A rule that asks "is this
    a recurrence?" must get FALSE on a first visit, not UNKNOWN — and it only can if the fact is
    there to be read. Writing only the recurrences would make "this has never happened before"
    indistinguishable from "we have not looked", which is the same inversion the two absence
    sentinels exist to prevent one level down.
    """
    written = 0
    kept: list[str] = []
    for history in read_histories(conn, org_id):
        for field, value, value_type in (
            ("derived.history.times_seen", history.times_seen, "count"),
            ("derived.history.days_since_prior", history.days_since_prior, "days"),
            ("derived.history.prior_outcome", history.prior_outcome, "label"),
            ("derived.history.prior_card_verdict", history.prior_card_verdict, "label"),
        ):
            if value is None:
                # A missing gap is not a gap of zero. Nothing is written, so the predicate reads
                # the field as absent and abstains — which is the honest answer.
                continue
            published = publish_derived_fact(
                conn, org_id=org_id, subject_node_id=history.anchor_node_id,
                field=history_field(field, history.domain), value=value, eval_time=eval_time,
                value_type=value_type, visibility_scope="org", version_prefix=VERSION_PREFIX)
            # The id the publisher RETURNED: an unchanged fact keeps the id of its first period.
            kept.append(published.version_id)
            written += int(published.wrote)
    # WHAT THIS SWEEP DID NOT WRITE IS NO LONGER TRUE: a per-anchor row of the old shape (the
    # last-sorted domain's past), the past of a pair a merge moved or retention pruned, a gap that
    # can no longer be measured. Closed, never deleted.
    return written + close_derived_facts(conn, org_id=org_id, version_prefix=VERSION_PREFIX,
                                         keep=kept, eval_time=eval_time)


__all__ = ["DOMAIN_MARK", "NO_PRIOR", "UNKNOWN_OUTCOME", "VERSION_PREFIX", "AnchorHistory",
           "history_field", "publish_histories", "read_histories"]
