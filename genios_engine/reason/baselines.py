from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore

# C9 — Baseline Builder. Closed-form per-contact statistics from graph/event history.
# reply_cadence = median gap (days) between a contact's messages. Cold-start fallback when
# there isn't enough history yet. Deterministic; stored versioned for replay.
#
# C1 extends it to two more per-contact metrics computed from the SAME event scan (no extra query):
#   momentum   = median(last-3 gaps) / median(all gaps)  — >1 the contact is cooling, <1 heating up.
#   engagement = events in the last 14d / events in the prior 14d — <1 interaction is thinning out.
# Both are stored as their own baseline keys and surfaced to rules as derived.* facts.
#
# ACCOUNT LEVEL. Everything above is per PERSON, and the corpus says plainly why that is not
# enough: `churn-risk.yaml` calls `derived.contact_frequency` "the account-level counterpart to
# derived.engagement", and notes that every executable going-quiet pattern today "reads a THREAD
# and infers an ACCOUNT — an account can be silent on one thread and busy on four others."
# Two keys are written per company, from the SAME event scan the per-person pass already ran:
#   contact_frequency        = contacts/week over the recent window — how often they write NOW.
#   contact_rate_per_account = contacts/week over the baseline window — this account's own norm.
# Both are needed together and neither is useful alone: the corpus is explicit that "absence needs
# a baseline or it is not evidence — a hundred-seat account opening four tickets a week is normal;
# a two-seat account doing the same is a churn signal."
#
# Rate, not ratio, deliberately. `engagement` is already a ratio against the node's own history;
# restating it at the account level would add a second way to say the same thing. Frequency is an
# absolute rate because the CS patterns that read it ("the same unresolved thing asked again")
# count contacts, and a ratio cannot distinguish three contacts from thirty.

MIN_SAMPLES = 3
COLD_START_DAYS = 3.0

#: Windows shared with `context/derived.py` so an account's frequency and a person's engagement
#: describe the same two spans of time. Divergent windows here would make the pair incomparable
#: in exactly the comparison the churn patterns make.
RECENT_DAYS = 14
BASELINE_DAYS = 56


def _momentum(gaps: list[float]) -> float:
    """Recent cadence vs the contact's own norm. Needs ≥4 gaps to be meaningful, else neutral 1.0."""
    if len(gaps) < 4:
        return 1.0
    base = statistics.median(gaps)
    if base <= 0:
        return 1.0
    recent = statistics.median(gaps[-3:])
    return round(recent / base, 3)


def _engagement(times: list, eval_time: datetime) -> float:
    """Last-14d event volume vs the prior 14d. Neutral 1.0 until there's enough history in the window."""
    cut1 = eval_time - timedelta(days=14)
    cut2 = eval_time - timedelta(days=28)
    last = sum(1 for t in times if t and t >= cut1)
    prev = sum(1 for t in times if t and cut2 <= t < cut1)
    if prev == 0:
        return 1.0 if last <= 1 else 2.0        # ramping from cold, but don't divide by zero
    return round(last / float(prev), 3)


def _per_week(times: list, eval_time: datetime, days: int) -> float:
    """Contacts per week over the last `days`. Zero events is a real zero, not a neutral 1.0.

    The neutral-on-no-history rule that `_engagement` and `_momentum` use is right for a RATIO —
    a brand-new contact has not gone cold — and wrong for a RATE. An account nobody has heard
    from contacts us zero times a week, and that is the finding, not a missing measurement. The
    baseline key is what says whether zero is unusual for this account.
    """
    cut = eval_time - timedelta(days=days)
    n = sum(1 for t in times if t and t >= cut)
    return round(n * 7.0 / days, 3) if days > 0 else 0.0


def _account_rows(c, org_id: str, person_times: dict[str, list], eval_time: datetime) -> list[dict]:
    """Roll each company's people up into the two account-level contact keys.

    Reuses the event scan the per-person pass already did — `person_times` is keyed by person
    node_id — so this costs exactly one extra query (the edges) rather than a second history read.
    Edge direction follows `derived.compute_deal_view`: from_node_id is the company, to_node_id
    the person.
    """
    edges = c.execute(text(
        "select e.from_node_id as company, e.to_node_id as person "
        "from graph_edges e join graph_nodes n "
        "  on n.org_id = e.org_id and n.node_id = e.from_node_id and n.valid_to is null "
        "where e.org_id = :o and n.node_type = 'company'"), {"o": org_id}).fetchall()

    by_company: dict[str, list] = {}
    for e in edges:
        by_company.setdefault(e.company, []).extend(person_times.get(e.person, ()))

    rows: list[dict] = []
    for company, times in by_company.items():
        rows.append({"o": org_id, "k": f"contact_frequency:{company}",
                     "v": _per_week(times, eval_time, RECENT_DAYS),
                     "n": len(times), "c": len(times) <= MIN_SAMPLES})
        rows.append({"o": org_id, "k": f"contact_rate_per_account:{company}",
                     "v": _per_week(times, eval_time, BASELINE_DAYS),
                     "n": len(times), "c": len(times) <= MIN_SAMPLES})
    return rows


def build_baselines(store: GraphStore, org_id: str, eval_time: datetime | None = None) -> dict:
    eval_time = eval_time or datetime.now(timezone.utc)
    built = {"computed": 0, "cold_start": 0}
    with store.engine.connect() as c:
        people = c.execute(text(
            "select node_id, canonical_key from graph_nodes where org_id=:o "
            "and node_type='person' and canonical_key is not null and valid_to is null"),
            {"o": org_id}).fetchall()
        # ONE query for every person's history instead of one per person. The loop issued a
        # separate round trip per node — 110 people here — and against a remote Postgres each
        # costs a full network turn, so the pass took tens of minutes and the link died partway
        # through, which is why a live re-run could not be completed at all. Same rows, same
        # ordering, one wait.
        by_email: dict[str, list] = {}
        for r in c.execute(text(
                "select actor->>'email' as email, occurred_at from source_events "
                "where org_id=:o and actor->>'email' is not null "
                "order by actor->>'email', occurred_at"), {"o": org_id}):
            by_email.setdefault(r.email, []).append(r.occurred_at)

        rows = []
        person_times: dict[str, list] = {}
        for p in people:
            times = list(by_email.get(p.canonical_key, ()))
            times = [t if t is None or t.tzinfo else t.replace(tzinfo=timezone.utc) for t in times]
            person_times[p.node_id] = times
            if len(times) > MIN_SAMPLES:
                gaps = [max(0.0, (times[i + 1] - times[i]).total_seconds() / 86400.0)
                        for i in range(len(times) - 1)]
                val, cold, n = statistics.median(gaps) or COLD_START_DAYS, False, len(gaps)
                built["computed"] += 1
                mom = _momentum(gaps)
            else:
                gaps = []
                val, cold, n = COLD_START_DAYS, True, len(times)
                built["cold_start"] += 1
                mom = 1.0
            eng = _engagement(times, eval_time)
            rows.append([{"o": org_id, "k": f"reply_cadence:{p.node_id}", "v": float(val), "n": n, "c": cold},
                         {"o": org_id, "k": f"momentum:{p.node_id}", "v": float(mom), "n": len(gaps), "c": cold},
                         {"o": org_id, "k": f"engagement:{p.node_id}", "v": float(eng), "n": len(times), "c": cold}])

        # Account level, inside the same connection so it reuses the scan above.
        account_rows = _account_rows(c, org_id, person_times, eval_time)
        built["accounts"] = len(account_rows) // 2
    # One statement for every baseline, not one per baseline. 110 people x 3 metrics was 330
    # sequential inserts inside a single transaction — the write half of the same problem.
    flat = [r for triple in rows for r in triple] + account_rows
    with store.engine.begin() as c:
        if flat:
            # ONE statement, not one per row. Handing SQLAlchemy a list of parameter dicts against
            # a raw `text()` still issues a round trip each — 330 of them here, ~170ms apiece over
            # a remote link, which is most of a minute for a pass that computes in milliseconds.
            # `unnest` turns the whole batch into a single exchange by sending five arrays.
            c.execute(text(
                "insert into baselines (org_id, key, value, sample_size, cold_start, computed_at) "
                "select :o, k, v, n, cs, now() from unnest("
                "  cast(:keys as text[]), cast(:vals as double precision[]), "
                "  cast(:samples as int[]), cast(:colds as boolean[])"
                ") as t(k, v, n, cs) "
                "on conflict (org_id, key) do update set "
                "value=excluded.value, sample_size=excluded.sample_size, "
                "cold_start=excluded.cold_start, computed_at=now()"),
                {"o": org_id,
                 "keys": [r["k"] for r in flat],
                 "vals": [r["v"] for r in flat],
                 "samples": [r["n"] for r in flat],
                 "colds": [r["c"] for r in flat]})
    return built


def load_baselines(store: GraphStore, org_id: str, node_id: str) -> dict[str, float]:
    """Back-compat: just the reply_cadence baseline used by `{baseline}` threshold resolution."""
    with store.engine.connect() as c:
        rows = c.execute(text("select key, value from baselines where org_id=:o and key=:k"),
                         {"o": org_id, "k": f"reply_cadence:{node_id}"}).fetchall()
    return {"reply_cadence": float(r.value) for r in rows} if rows else {}


def load_node_metrics(store: GraphStore, org_id: str, node_id: str):
    """One query for ALL of a node's baseline keys → (baselines, derived_facts). baselines feed
    `{baseline}` threshold resolution; derived_facts (momentum/engagement) are injected into
    ctx.facts as derived.* so pack rules can threshold them like any typed fact."""
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select key, value from baselines where org_id=:o and key like :pat"),
            {"o": org_id, "pat": f"%:{node_id}"}).fetchall()
    baselines: dict[str, float] = {}
    derived: dict[str, dict] = {}
    for r in rows:
        metric = str(r.key).split(":", 1)[0]
        v = float(r.value)
        if metric == "reply_cadence":
            baselines["reply_cadence"] = v
        elif metric == "contact_rate_per_account":
            # A baseline, not a fact: the corpus asks for it as the denominator a frequency is
            # judged against (`{baseline: contact_rate_per_account}`), never as a value a rule
            # reads on its own.
            baselines["contact_rate_per_account"] = v
        elif metric in ("momentum", "engagement", "contact_frequency"):
            derived[f"derived.{metric}"] = {"value": v, "confidence": 0.85,
                                            "authority_rank": 2, "occurred_at": None, "src_count": 1}
    return baselines, derived
