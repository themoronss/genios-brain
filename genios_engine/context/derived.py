"""Derived facts — the numbers every rule reads and nothing has ever written.

`derived.engagement`, `derived.sentiment` and `derived.momentum` are consulted across the sales
pack (`derived.engagement <= 0.5`, `derived.sentiment <= -0.34`) and by the compiled L3
capabilities, which declare them as required context. The extraction vocabulary deliberately
excludes them — vocab.py says so plainly: *"computed by the reasoner from other facts, never
extracted"*, because offering them to the model invites a plausible invented number.

Nothing computed them. They were absent from every node in the graph, which means every rule and
every capability gated on them was dead on arrival: the deep sales rules never fired once, and all
18 compiled capabilities returned INSUFFICIENT_CONTEXT against a graph that held everything else
they needed. The shallow output the product shows — nine `unanswered_email` cards out of thirteen —
is exactly what is left when only the fields nobody derives are missing.

Deterministic and LLM-free by construction. These are counts over observations the extractor has
already committed, so the same graph yields the same numbers on every run, and a value can always
be traced back to the rows that produced it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.pipeline import _normalise_deal_status

#: Observation kinds that carry direction. Weighted by how strongly each commits the counterparty:
#: a booked next step is worth more than a warm reply, an explicit loss more than a single
#: objection. Grounded in the kinds the extractor actually emits, not an invented taxonomy.
_SENTIMENT_WEIGHTS: dict[str, float] = {
    "next_step_agreed": 1.0, "demo_requested": 1.0, "proposal_sent": 0.6,
    "positive_reply": 0.6, "meeting_request": 0.5, "introduction": 0.3,
    "question": 0.1,
    "objection": -0.6, "negative_reply": -0.8, "timeline_slip": -0.7,
    "closed_lost_mention": -1.0,
}

#: Kinds that mean the relationship MOVED, as opposed to merely made noise. Momentum asks whether
#: anything advanced recently, which is a different question from whether the tone was warm.
_PROGRESS_KINDS = frozenset({
    "next_step_agreed", "demo_requested", "proposal_sent", "meeting_request", "followup_sent",
})

_RECENT_DAYS = 14          # "lately"
_BASELINE_DAYS = 56        # four times the recent window → a stable denominator, not last week's noise


def _rate(count: int, days: int) -> float:
    return count / days if days > 0 else 0.0


def _new_acc() -> dict:
    return {"recent": 0, "baseline": 0, "pos": 0.0, "neg": 0.0, "progress_recent": 0}


def _accumulate(acc: dict, kind: str, recent_n: int, baseline_n: int) -> None:
    """Fold one (kind, recent_n, baseline_n) group into an accumulator."""
    acc["recent"] += recent_n
    acc["baseline"] += baseline_n
    weight = _SENTIMENT_WEIGHTS.get(kind)
    if weight is not None:
        # Sentiment reads the WHOLE baseline window, not just the recent one: a single sour
        # reply this fortnight should not outweigh a quarter of warm ones.
        if weight > 0:
            acc["pos"] += weight * baseline_n
        else:
            acc["neg"] += -weight * baseline_n
    if kind in _PROGRESS_KINDS:
        acc["progress_recent"] += recent_n


def _metrics(acc: dict) -> tuple[float, float, float]:
    """(engagement, sentiment, momentum) from one accumulator. ONE formula, two callers.

    `compute` folds one PERSON's observations into an accumulator; `compute_account_view` folds
    the union of an account's people's observations into the same shape. The arithmetic has to be
    literally shared or `derived.engagement` means one thing on a person and a subtly different
    thing on the company above them — and the sales pack compares both against the same
    threshold (`derived.engagement <= 0.5`), so a second formula would be invisible until it
    mis-fired.
    """
    recent_rate = _rate(acc["recent"], _RECENT_DAYS)
    baseline_rate = _rate(acc["baseline"], _BASELINE_DAYS)
    # Engagement is a RATIO against this relationship's own history, never an absolute count —
    # "halved" has to mean halved for THIS account, whether it ran at forty emails a week or
    # four. A node with no history reads 1.0 (neutral), not 0.0, or every brand-new contact
    # would look like it had gone cold.
    engagement = 1.0 if baseline_rate <= 0 else min(recent_rate / baseline_rate, 3.0)
    total = acc["pos"] + acc["neg"]
    sentiment = 0.0 if total <= 0 else (acc["pos"] - acc["neg"]) / total
    momentum = _rate(acc["progress_recent"], _RECENT_DAYS) * 7.0     # progress events/week
    return engagement, sentiment, momentum


def _observation_counts(c, org_id: str, recent_from: datetime, baseline_from: datetime):
    """Per (node, kind) recent/baseline observation counts. One bulk query, no per-node reads."""
    return c.execute(text(
        "select subject_node_id, kind, "
        "count(*) filter (where occurred_at >= :recent) as recent_n, "
        "count(*) filter (where occurred_at >= :baseline) as baseline_n "
        "from graph_observations "
        "where org_id = :o and status = 'active' and occurred_at >= :baseline "
        "group by subject_node_id, kind"),
        {"o": org_id, "recent": recent_from, "baseline": baseline_from}).all()


#: The one INSERT every derived writer uses. `graph_facts` is version-keyed — its only unique
#: index is `fact_version_id` — so a derived value is a RECOMPUTE, not a new observation of
#: history: it overwrites its own deterministic version id rather than appending a row per drain.
#: Otherwise every sync would grow the table by three rows per node forever and a reader picking
#: "latest" would be sifting duplicates.
_UPSERT_FACT = (
    "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
    "field, value, value_type, status, authority_rank, confidence, occurred_at, "
    "valid_from, visibility_scope) values "
    "(:vid, :fid, :o, :n, :f, cast(:v as jsonb), :t, 'active', 100, 0.9, :now, :now, 'org') "
    "on conflict (fact_version_id) do update set value = excluded.value, "
    "occurred_at = excluded.occurred_at, valid_from = excluded.valid_from")


def _write_fact(c, org_id: str, node_id: str, field: str, value: str, value_type: str,
                now: datetime) -> None:
    c.execute(text(_UPSERT_FACT), {
        "vid": f"fv_derived_{node_id}_{field}", "fid": f"f_derived_{node_id}_{field}",
        "o": org_id, "n": node_id, "f": field, "v": value, "t": value_type, "now": now})


def compute(store, org_id: str, *, now: datetime | None = None) -> int:
    """Write derived.* for every node this org has observations on. Returns rows written.

    One pass, three bulk queries, no per-node round-trips — the same reason attention refreshes
    for the whole org rather than per touched node.
    """
    now = now or datetime.now(timezone.utc)
    recent_from = now - timedelta(days=_RECENT_DAYS)
    baseline_from = now - timedelta(days=_BASELINE_DAYS)

    with store.engine.begin() as c:
        rows = _observation_counts(c, org_id, recent_from, baseline_from)

        per_node: dict[str, dict] = {}
        for node_id, kind, recent_n, baseline_n in rows:
            _accumulate(per_node.setdefault(node_id, _new_acc()), kind, recent_n, baseline_n)

        written = 0
        for node_id, acc in per_node.items():
            engagement, sentiment, momentum = _metrics(acc)
            for field, value in (("derived.engagement", engagement),
                                 ("derived.sentiment", sentiment),
                                 ("derived.momentum", momentum)):
                _write_fact(c, org_id, node_id, field, repr(round(value, 4)), "number", now)
                written += 1
    return written


#: Observation kinds that place a relationship at a stage. Ordered by how far along they put it,
#: so the furthest-reached stage wins rather than the most recent noise.
#:
#: These words are a STAGE vocabulary, not a status one. `engaged`, `evaluating` and `proposing`
#: all describe a deal that is OPEN, and `pipeline._normalise_deal_status` is the single place
#: that mapping lives — see `_stage_pairs` below for why this distinction is load-bearing.
_STAGE_BY_KIND: tuple[tuple[str, str], ...] = (
    ("closed_lost_mention", "lost"),
    ("proposal_sent", "proposing"),
    ("demo_requested", "evaluating"),
    ("next_step_agreed", "engaged"),
    ("meeting_request", "engaged"),
    ("introduction", "new"),
)
_STAGE_RANK = {"new": 0, "engaged": 1, "evaluating": 2, "proposing": 3, "lost": 4}


def compute_deal_view(store, org_id: str, *, now: datetime | None = None) -> int:
    """Roll thread-level truth up to the deal fields the rules ask for. Returns rows written.

    `deal.status` and `deal.last_inbound` were missing on 16 of 18 companies not because the
    information is absent but because nobody ever wrote it at the deal's own level: the extractor
    records `thread.last_inbound` per thread and stage observations per person, and the deal — the
    relationship as a whole — is precisely the roll-up of those. Asking a language model to restate
    it per email would be inviting a guess at something already known exactly.

    `deal.value` is deliberately NOT derived. There is no honest way to infer a number nobody
    stated, and a wrong one would flow straight into prioritisation. A capability that needs it
    should keep reporting insufficient context until an email actually says so.
    """
    now = now or datetime.now(timezone.utc)
    with store.engine.begin() as c:
        # Latest inbound anywhere under each company, through its edges.
        rows = c.execute(text(
            "select e.from_node_id as company, max(f.value #>> '{}') as last_inbound "
            "from graph_edges e "
            "join graph_facts f on f.subject_node_id = e.to_node_id and f.org_id = e.org_id "
            "where e.org_id = :o and f.field = 'thread.last_inbound' and f.status = 'active' "
            "group by e.from_node_id"), {"o": org_id}).all()
        stages = c.execute(text(
            "select e.from_node_id as company, o2.kind "
            "from graph_edges e "
            "join graph_observations o2 on o2.subject_node_id = e.to_node_id "
            "and o2.org_id = e.org_id "
            "where e.org_id = :o and o2.status = 'active'"), {"o": org_id}).all()

        best_stage: dict[str, str] = {}
        kind_to_stage = dict(_STAGE_BY_KIND)
        for company, kind in stages:
            stage = kind_to_stage.get(kind)
            if stage is None:
                continue
            held = best_stage.get(company)
            if held is None or _STAGE_RANK[stage] > _STAGE_RANK[held]:
                best_stage[company] = stage

        # Commitments sit TWO hops out: company -> person -> commitment. A 1-hop neighbourhood
        # can never see them, which is why `commitment.action` and `commitment.due_at` were missing
        # on all 18 companies while the promises themselves were extracted correctly and stored on
        # their own nodes. The company's open obligation is the soonest-due one among its people —
        # a roll-up of fact, not a new claim.
        #
        # `commitment.action` is also a NAME gap: the pipeline writes the normalised obligation as
        # `commitment.text`, and both the sales pack and the compiled capabilities ask for
        # `commitment.action`. Reading the former and publishing the latter closes it here rather
        # than renaming a field other readers already depend on.
        commitments = c.execute(text(
            "select e1.from_node_id as company, "
            "min(due.value #>> '{}') as due_at, "
            "min(act.value #>> '{}') as action "
            "from graph_edges e1 "
            "join graph_edges e2 on e2.from_node_id = e1.to_node_id and e2.org_id = e1.org_id "
            "join graph_facts due on due.subject_node_id = e2.to_node_id "
            "and due.org_id = e1.org_id and due.field = 'commitment.due_at' "
            "and due.status = 'active' "
            "left join graph_facts act on act.subject_node_id = e2.to_node_id "
            "and act.org_id = e1.org_id and act.field = 'commitment.text' "
            "and act.status = 'active' "
            "join graph_facts st on st.subject_node_id = e2.to_node_id "
            "and st.org_id = e1.org_id and st.field = 'commitment.status' "
            "and st.status = 'active' and st.value #>> '{}' = 'open' "
            "where e1.org_id = :o group by e1.from_node_id"), {"o": org_id}).all()

        written = 0
        pairs: list[tuple[str, str, str]] = []
        for company, due_at, action in commitments:
            if due_at:
                pairs.append((company, "commitment.due_at", due_at))
            if action:
                pairs.append((company, "commitment.action", action))
        for company, last_inbound in rows:
            if last_inbound:
                pairs.append((company, "deal.last_inbound", last_inbound))
        # THE STAGE IS NOT THE STATUS, and conflating them silently un-routes the entire deal lane.
        #
        # This roll-up used to write its own vocabulary — `new`, `engaged`, `evaluating`,
        # `proposing` — straight into `deal.status`, bypassing `_normalise_deal_status`, at
        # authority_rank 100. Rank 100 outranks the extractor's rank-2 write, so every sync
        # OVERWROTE the canonical `open` the extraction path had just produced. Six `sales_v1`
        # rules and all three Sales `deal` situations gate on the literal `open`, so the effect
        # was that the deal lane worked immediately after a backfill and went to zero again on the
        # next sync — on the design partner's org, 20 of 20 deal situations `no_route_predicate`
        # with `deal.status` reading `engaged` (23), `evaluating` and `new`.
        #
        # The fix is not a new mapping. It is using the one that already exists, and publishing
        # the rich word where readers expect to find it: `deal.stage`, exactly as the extraction
        # path does. `deal_cooling`, `slots.py` and `card_builder.py` all already prefer
        # `deal.stage` for display and fall back to status, so the informative word is not lost.
        for company, stage in best_stage.items():
            status, raw = _normalise_deal_status(stage)
            if status is None:
                continue
            pairs.append((company, "deal.status", status))
            if raw.lower() != status:
                pairs.append((company, "deal.stage", raw))
        for node_id, field, value in pairs:
            _write_fact(c, org_id, node_id, field, f'"{value}"', "string", now)
            written += 1
    return written


#: The two words `thread.ball_in_court` is allowed to hold. Anything else on a person is dropped
#: rather than rolled up: on the design partner's graph the field holds `us` (63) and `them` (59)
#: — and on one node a bare email address, which the extractor produced and no reader compares
#: against. Rolling that up would put an address where every predicate expects a side.
_BALL_WORDS = ("us", "them")


def _person_neighbours(c, org_id: str) -> dict[str, set[str]]:
    """account node -> the person nodes one hop away, IN EITHER EDGE DIRECTION.

    THIS IS THE BUG THIS FUNCTION EXISTS TO NOT REPEAT, and it is worth naming precisely because
    two shipped roll-ups already have it.

    `pipeline.py::_works_at` writes the edge PERSON -> COMPANY. Both existing account roll-ups
    assume the opposite:

      * `compute_deal_view` selects `e.from_node_id as company` and joins facts on `e.to_node_id`.
        The only edges with a company on the FROM side are `owns` (company -> deal), and deals
        carry no thread facts — so on the live graph it writes `deal.*` onto persons and deals and
        reaches a company NEVER. 33 of 40 companies hold zero facts of any kind.
      * `baselines.py::_account_rows` filters `n.node_type = 'company'` on `e.from_node_id`, lands
        on the 33 `owns` edges, looks up `person_times[<deal id>]`, finds nothing, and writes a
        contact rate for zero accounts. Measured on production the morning this was written:
        `baselines` held 387 rows for the org — exactly 129 people x 3 person metrics — and not
        one `contact_frequency` row, from a build that had run ten minutes earlier.

    `support_situations.py` already found this and fixed it in place, with the comment "Accept
    both rather than assume, or a whole tenant's roll-up is silently empty". That is the rule
    applied here.

    Reading BOTH directions is also what makes the writer agree with the reader: `reason/runner.py`
    builds its 1-hop adjacency undirected (`adj[from].add(to)` and `adj[to].add(from)`), so
    `neighbor_has_obs` on a company already sees its people's observations. A writer that walks
    the graph more narrowly than the reader produces facts that contradict the predicates.
    """
    neighbours: dict[str, set[str]] = {}
    for row in c.execute(text(
            "select a.node_id as account, p.node_id as person "
            "from graph_nodes a "
            "join graph_edges e on e.org_id = a.org_id "
            "  and (e.from_node_id = a.node_id or e.to_node_id = a.node_id) "
            "  and e.valid_to is null "
            "join graph_nodes p on p.org_id = a.org_id and p.valid_to is null "
            "  and p.node_type = 'person' "
            "  and p.node_id = case when e.from_node_id = a.node_id "
            "                       then e.to_node_id else e.from_node_id end "
            "where a.org_id = :o and a.valid_to is null "
            "  and a.node_type in ('company', 'deal')"), {"o": org_id}):
        neighbours.setdefault(row.account, set()).add(row.person)
    return neighbours


def compute_account_view(store, org_id: str, *, now: datetime | None = None) -> int:
    """Roll person-level truth up to the COMPANY and DEAL nodes. Returns rows written.

    `compute_deal_view` established the shape: the deal is the roll-up of its threads, and asking
    a language model to restate something already known exactly would be inviting a guess. This
    is the same argument one level out. A company's state IS its people's state — nobody writes
    an email "to Acme", they write to a person who works there — so every account-level fact here
    is an aggregate of rows that already exist, never a new claim.

    WHAT IT IS AND IS NOT WORTH, measured rather than assumed, because the obvious claim is
    wrong. On the design partner's graph person nodes hold 1,279 facts across 129 nodes while
    COMPANY nodes hold 18 across 40 — 33 of the 40 hold none — and 49 of the org's 103 live
    situations are anchored on a company or a deal. It is tempting to conclude that the
    account-anchored half of the product reasons over empty nodes. IT DOES NOT.
    `adapters/native.py` already resolves a root field absent on the anchor from its 1-hop
    neighbourhood, and `reason/runner.py::_neighbourhood` fills that with the latest value per
    field across neighbours. Running this function read-only against production and comparing
    every value it would write against what that borrow already finds: across the 287 values in
    the six fields the comparison covers, the borrow finds all 287 and this changes 5 — 2
    `derived.sentiment` and 3 `deal.status`, on the 7 accounts with more than one person.

    So the honest value here is narrow and worth stating plainly rather than overselling:

      * The value becomes the ACCOUNT's. The borrow takes whichever neighbour was written last,
        so a company with four contacts inherited one person's engagement ratio; this computes
        the ratio over the union of its people's observations. It matters on 7 accounts today
        and on every multi-contact account the org ever adds.
      * The fact becomes the account's OWN, at `context_scope` root rather than `neighbor`, so
        evidence refs cite the account instead of a person who happens to work there.
      * It exists as a ROW, which the borrow never produces. Everything that reads `graph_facts`
        without going through the reasoner's neighbourhood — read models, `entity_360`, card
        rendering, exports — saw an empty company and now does not.

    The one strictly-new signal is not here at all: `derived.contact_frequency`, which no person
    carries and the borrow therefore cannot find. It comes from `reason/baselines.py`, whose
    account pass had the same edge-direction defect and wrote a contact rate for ZERO accounts;
    fixed alongside this, it yields 37.

    WHAT IS DELIBERATELY NOT DERIVED, and this is the same line `compute_deal_view` holds:

      * `deal.value`. There is no honest way to infer a number nobody stated, and a wrong one
        flows straight into prioritisation. `sales.deal_cooling` REQUIRES it and returned
        INSUFFICIENT_CONTEXT on 501 runs for that reason; `deal.value` is present on exactly one
        node in the org. This function closes three of that capability's four required fields and
        leaves the fourth open, so those runs stay insufficient — correctly.
      * `account.industry`, `account.geography`, `account.employee_count`, `account.segment`.
        These are the Sales corpus's top-ranked asks (8, 3, 2 and 2 blocked patterns) and none is
        derivable from correspondence. They are firmographic enrichment; guessing an industry
        from an email domain is exactly the fabrication the rule above forbids. They stay in
        `planned_substrate` with no writer, which is where a name with no measurement belongs.
      * Committee size. The Buying Committee object wants a roster, and only 6 of 40 companies
        have more than one person attached, so a count would describe our contact list rather
        than their committee.

    Ownership is split from `compute_deal_view` on purpose: that function already writes
    `deal.status`/`deal.stage` onto DEAL nodes (32 of 33 on production) through the `involves`
    edge, and it works. This one writes those two fields for COMPANIES only, so one row never has
    two writers racing over the same `fact_version_id`. `derived.*` and `thread.*` on companies
    and deals have no other writer at all.
    """
    now = now or datetime.now(timezone.utc)
    recent_from = now - timedelta(days=_RECENT_DAYS)
    baseline_from = now - timedelta(days=_BASELINE_DAYS)

    with store.engine.begin() as c:
        neighbours = _person_neighbours(c, org_id)
        if not neighbours:
            return 0
        people = {p for members in neighbours.values() for p in members}

        # Three bulk reads for the whole org, then all folding in memory — the same reason
        # `compute` refuses per-node round-trips. Against a remote Postgres a per-account read
        # would be 73 network turns for this org alone.
        obs_counts: dict[str, list[tuple[str, int, int]]] = {}
        for node_id, kind, recent_n, baseline_n in _observation_counts(
                c, org_id, recent_from, baseline_from):
            if node_id in people:
                obs_counts.setdefault(node_id, []).append((kind, recent_n, baseline_n))

        stage_kinds: dict[str, set[str]] = {}
        for row in c.execute(text(
                "select subject_node_id, kind from graph_observations "
                "where org_id = :o and status = 'active'"), {"o": org_id}):
            if row.subject_node_id in people:
                stage_kinds.setdefault(row.subject_node_id, set()).add(row.kind)

        thread_facts: dict[str, dict[str, str]] = {}
        for row in c.execute(text(
                "select subject_node_id, field, value #>> '{}' as v from graph_facts "
                "where org_id = :o and status = 'active' and valid_to is null "
                "  and field in ('thread.last_inbound', 'thread.last_outbound', "
                "                'thread.ball_in_court')"), {"o": org_id}):
            if row.subject_node_id in people and row.v:
                thread_facts.setdefault(row.subject_node_id, {})[row.field] = row.v

        node_types = {r.node_id: r.node_type for r in c.execute(text(
            "select node_id, node_type from graph_nodes where org_id = :o and valid_to is null "
            "and node_type in ('company', 'deal')"), {"o": org_id})}

        kind_to_stage = dict(_STAGE_BY_KIND)
        written = 0
        for account, members in neighbours.items():
            acc = _new_acc()
            saw_observation = False
            for person in members:
                for kind, recent_n, baseline_n in obs_counts.get(person, ()):
                    _accumulate(acc, kind, recent_n, baseline_n)
                    saw_observation = True
            # An account with no observations in the window gets NO derived.* at all, rather than
            # the neutral 1.0 `_metrics` returns for an empty accumulator. The neutral value is
            # right for a person we have merely not heard from lately and wrong for an account we
            # have never heard from: "engagement is normal" and "there is nothing to measure" are
            # different claims, and only the first should reach a rule.
            if saw_observation:
                engagement, sentiment, momentum = _metrics(acc)
                for field, value in (("derived.engagement", engagement),
                                     ("derived.sentiment", sentiment),
                                     ("derived.momentum", momentum)):
                    _write_fact(c, org_id, account, field, repr(round(value, 4)), "number", now)
                    written += 1

            # Correspondence, rolled up under the names the readers already use. The account's
            # last inbound is the LATEST across its people — an account is not quiet because one
            # contact is. These are ISO timestamp strings written by the same extractor, so max()
            # on the string is max() on the instant.
            for field in ("thread.last_inbound", "thread.last_outbound"):
                values = [thread_facts[p][field] for p in members
                          if field in thread_facts.get(p, {})]
                if values:
                    _write_fact(c, org_id, account, field, f'"{max(values)}"', "string", now)
                    written += 1

            # `us` WINS over `them`, and the asymmetry is deliberate: if anyone at the account is
            # waiting on us, the account is waiting on us. Taking the majority or the most recent
            # would let one answered contact hide an unanswered one, which is the failure the
            # field exists to catch.
            ball = {thread_facts[p].get("thread.ball_in_court") for p in members
                    if p in thread_facts}
            for word in _BALL_WORDS:
                if word in ball:
                    _write_fact(c, org_id, account, "thread.ball_in_court", f'"{word}"',
                                "string", now)
                    written += 1
                    break

            # Stage, for COMPANIES only — see the ownership note in the docstring. The furthest
            # stage any of the account's people reached wins, and it is published through
            # `_normalise_deal_status` exactly as `compute_deal_view` does: the rank-100 write
            # outranks the extractor's rank-2 one, so writing a stage word into `deal.status`
            # here would un-route every Sales deal situation on the next sync, which is the
            # regression that cost the deal lane 20 of 20 situations once already.
            if node_types.get(account) != "company":
                continue
            best: str | None = None
            for person in members:
                for kind in stage_kinds.get(person, ()):
                    stage = kind_to_stage.get(kind)
                    if stage and (best is None or _STAGE_RANK[stage] > _STAGE_RANK[best]):
                        best = stage
            if best is None:
                continue
            status, raw = _normalise_deal_status(best)
            if status is None:
                continue
            _write_fact(c, org_id, account, "deal.status", f'"{status}"', "string", now)
            written += 1
            if raw.lower() != status:
                _write_fact(c, org_id, account, "deal.stage", f'"{raw}"', "string", now)
                written += 1
    return written


__all__ = ["compute", "compute_account_view", "compute_deal_view"]
