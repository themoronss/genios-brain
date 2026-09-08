"""R-1's fire rate — how often the ambiguity interpreter would actually consult a model.

    A site that fires on everything is a cost line. A site that fires on nothing is dead code.

Layer 2 paid for the second half of that sentence: fifteen of twenty-one deep sales rules never
fired because they gated on `thread.ball_in_court`, a field only 9% of records carried, and the test
suite was green the whole time. A precondition is therefore not something to be satisfied with; it is
something to be MEASURED, on the tenant's own data, before the site is switched on.

WHAT IS MEASURED
----------------
For every text-bearing fact on a tenant's current graph:

    scanned          every current fact row
    text             values that are free text at all (a number cannot be ambiguous)
    in_band          text inside R-1's length band — long enough to carry a stance, short enough
                     not to be a document
    hedged           text carrying a marker from the closed hedge vocabulary
    fires            what R-1 would actually consult on, after the per-situation cap
    subjects         how many distinct entities carry at least one

and the derived rates: the share of facts, and the share of ENTITIES — the second is the one that
predicts spend, because R-1 runs per situation and caps at three.

    ./.venv/bin/python scripts/ambiguity_fire_rate.py --org org_7173
    ./.venv/bin/python scripts/ambiguity_fire_rate.py --seeded 400

`--seeded` needs no database. It builds a population from a fixed corpus of business sentences in a
declared hedged/settled mix, which is how the detector's behaviour can be checked against a KNOWN
answer: a detector that fires on 100% of a 25%-hedged population is broken in a way no production
number would reveal, because on production nobody knows the true rate.

THIS SCRIPT NEVER CALLS A MODEL. It runs the precondition only, so measuring the fire rate costs
nothing and can be run on a tenant before the tenant is switched on.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from genios_engine.reason.interpretation import (      # noqa: E402
    MAX_FLAGS_PER_SITUATION,
    MAX_SPAN_CHARS,
    MIN_SPAN_CHARS,
    _HEDGE,
)

#: The seeded corpus. Every line is a sentence a real B2B inbox produces; the first block genuinely
#: hedges and the second genuinely does not. Both are needed: a detector is only as good as its
#: FALSE positive rate, and a corpus of ambiguity alone cannot measure one.
HEDGED = (
    "They are considering moving some workloads to another vendor next quarter.",
    "We might need to revisit the pricing before the board meeting.",
    "The team is exploring a couple of alternatives alongside ours.",
    "Not sure we can commit to the March timeline just yet, will confirm.",
    "Legal is probably going to want another look at the indemnity clause.",
    "Budget approval is tbd until the new CFO settles in next month.",
    "Hum log soch rahe hain ki is quarter mein hi start kar dein.",
    "We are open to a longer contract if the support terms improve.",
)

SETTLED = (
    "The renewal has been signed and countersigned this morning.",
    "Please send the invoice to accounts@northwind.example by Friday.",
    "Our security review is complete and we have no further questions.",
    "The kickoff is confirmed for the fifteenth with the full team.",
    "We have decided to proceed with your proposal as written.",
    "Attached is the executed order form for the annual plan.",
    "The migration finished last night with no downtime reported.",
    "Thanks — that answers it. Closing this thread.",
    "Invoice paid. Reference 88213 for your records.",
    "I have added you to the shared channel for the rollout.",
    "The account team is unchanged for this renewal cycle.",
    "Confirming receipt of the signed MSA.",
)


def _fires(values, *, per_subject_cap: int = MAX_FLAGS_PER_SITUATION) -> dict[str, int]:
    """The precondition's TEXT half, over a population of (subject, value) pairs.

    The plan-read check and the typed-absence check are per-run and cannot be evaluated off a raw
    fact table, so what this reports is an UPPER BOUND on the fire rate: every field this counts is
    one a plan would additionally have to declare. Stated rather than hidden, because a measurement
    whose direction of error is unknown is not a measurement.
    """
    counts = {"scanned": 0, "text": 0, "in_band": 0, "hedged": 0, "fires": 0}
    per_subject: dict[str, int] = {}
    for subject, value in values:
        counts["scanned"] += 1
        if not isinstance(value, str):
            continue
        body = value.strip()
        if not body:
            continue
        counts["text"] += 1
        if not MIN_SPAN_CHARS <= len(body) <= MAX_SPAN_CHARS:
            continue
        counts["in_band"] += 1
        if not _HEDGE.search(body):
            continue
        counts["hedged"] += 1
        if per_subject.get(subject, 0) >= per_subject_cap:
            continue
        per_subject[subject] = per_subject.get(subject, 0) + 1
        counts["fires"] += 1
    counts["subjects_firing"] = len(per_subject)
    return counts


def _report(counts: dict[str, int], subjects: int, label: str) -> dict:
    scanned = max(1, counts["scanned"])
    out = {
        "population": label,
        **counts,
        "subjects_total": subjects,
        "fire_rate_per_fact_pct": round(100.0 * counts["fires"] / scanned, 2),
        "fire_rate_per_subject_pct": (round(100.0 * counts["subjects_firing"] / subjects, 2)
                                      if subjects else 0.0),
        "false_positive_check": "compare against the declared mix when --seeded",
    }
    return out


def seeded(count: int, *, hedged_share: float = 0.25, seed: int = 20260905) -> dict:
    rng = random.Random(seed)
    rows: list[tuple[str, str]] = []
    planted = 0
    for index in range(count):
        subject = f"node_{index // 4}"      # four facts per entity, the shape a real graph has
        if rng.random() < hedged_share:
            rows.append((subject, rng.choice(HEDGED)))
            planted += 1
        else:
            rows.append((subject, rng.choice(SETTLED)))
    counts = _fires(rows)
    subjects = len({subject for subject, _ in rows})
    report = _report(counts, subjects, f"seeded n={count} hedged_share={hedged_share}")
    report["planted_hedged"] = planted
    report["detector_recall_pct"] = round(100.0 * counts["hedged"] / max(1, planted), 2)
    report["detector_false_positive_pct"] = round(
        100.0 * max(0, counts["hedged"] - planted) / max(1, counts["scanned"] - planted), 2)
    return report


def from_database(org_id: str, database_url: str, limit: int) -> dict:
    from sqlalchemy import text

    # `platform.db.get_engine` and not `create_engine`: the deployment's driver, pool and keepalives
    # are decided there, and a script that opened its own connection would be measuring a tenant
    # through a door the engine does not use.
    from genios_engine.platform.db import get_engine
    engine = get_engine(database_url)
    rows: list[tuple[str, object]] = []
    with engine.connect() as conn:
        for row in conn.execute(text(
                "select subject_node_id, value from graph_facts "
                "where org_id = :o and valid_to is null and status = 'active' "
                "order by subject_node_id, field limit :lim"),
                {"o": org_id, "lim": limit}):
            value = row.value
            if isinstance(value, str):
                # jsonb comes back as a JSON scalar on some drivers: a stored string is '"text"'.
                try:
                    value = json.loads(value)
                except ValueError:
                    pass
            rows.append((row.subject_node_id, value))
    counts = _fires(rows)
    subjects = len({subject for subject, _ in rows})
    return _report(counts, subjects, f"org={org_id} facts={len(rows)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org")
    parser.add_argument("--database-url", default=os.environ.get("GENIOS_DATABASE_URL", ""))
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--seeded", type=int, default=0)
    parser.add_argument("--hedged-share", type=float, default=0.25)
    args = parser.parse_args()

    if args.seeded:
        print(json.dumps(seeded(args.seeded, hedged_share=args.hedged_share), indent=2))
        return 0
    if not args.org or not args.database_url:
        parser.error("either --seeded N, or --org with --database-url / GENIOS_DATABASE_URL")
    print(json.dumps(from_database(args.org, args.database_url, args.limit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
