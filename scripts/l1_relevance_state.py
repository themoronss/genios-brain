"""U-S1-01 · Is Layer 1's relevance judgment switched on, and what did it decide?

WHY THIS EXISTS. `no_model_wired = 251` was read once as "relevance has no model wired in prod"
and then as "a one-line wiring fix". Both readings were wrong, and the second would have had
somebody editing `wiring.py`, which is correct as it stands.

The real chain is three hops and none of them is a bug:

    platform/wiring.py:780   is_semantic_activated(engine, org) is False
                             -> make_semantic_lane returns None
    capture/pipeline.py:1272 stage.relevance_llm is therefore None
    esqe/relevance.py:752    assess_relevance takes the fail-open and files
                             RULE_NO_MODEL_WIRED at authority 3000

`is_semantic_activated` is **fail-closed by design** — no live row in `l1_semantic_activation`
means no judgment. So the question this script answers is not "what is broken" but "is the switch
on, and did turning it on change what the layer decided".

⛔ THE FAIL-OPEN IS CORRECT AND THIS SCRIPT MUST NOT BE READ AS A BUG REPORT. An unjudged event is
KEPT, at the same authority (3000) the cascade gives an unknown actor, because that is what it
means: nobody decided. Nothing is lost. What is missing is judgment, not data.

WHERE THE RULE ACTUALLY LIVES. Not on `source_events` — that column does not exist, and a handoff
query that named it could not run. The rule is filed on the S4 trace row as
`event_trace.reason_code` at `stage = 's4_esqe'`, which is what this reads. Same source as
`scripts/speedrun008_measurements.py` item 13, deliberately, so the two cannot disagree.

READ-ONLY BY CONSTRUCTION. One transaction, opened `read only`, so a statement that tried to write
is refused by Postgres rather than by a reviewer. No `GENIOS_ALLOW_PROD_WRITE` is needed or
accepted: that variable is named for writes because it was written for writes, and setting it to
run a report is the wrong shape of permission.

USAGE
    export GENIOS_DATABASE_URL="postgresql://..."        # or let it read .env
    .venv/bin/python scripts/l1_relevance_state.py [--org org_...]
    .venv/bin/python scripts/l1_relevance_state.py --assert-judged     # U-S1-04's gate
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: The tenant every Layer 1 number in the YCW27 baseline was taken against.
_PILOT_ORG = "org_e97e86f858ad48b2bbf64b8a"

#: The rule `assess_relevance` files when no client reached it. Imported rather than retyped so a
#: rename in `relevance.py` fails here loudly instead of making this script quietly report zero.
from genios_engine.capture.esqe.relevance import (  # noqa: E402
    RULE_NO_MODEL_WIRED,
    RULE_LLM_BUSINESS,
    RULE_LLM_NOT_BUSINESS,
    RULE_LLM_UNAVAILABLE,
)

#: The buckets that only exist because a model answered. If every one of these is zero the switch
#: is not doing anything, whatever the activation row says.
_JUDGED_RULES = (RULE_LLM_BUSINESS, RULE_LLM_NOT_BUSINESS)

_ACTIVATION = """
    select org_id, enabled_at, enabled_by, disabled_at
      from l1_semantic_activation
     where org_id = :o
"""

#: Item 13's query, plus `source` — and the source column is the whole point.
#:
#: ⛔ WITHOUT IT THIS REPORT LIES BY OMISSION, and it already did once. A bare rule histogram shows
#: `no_model_wired` at 76% and reads as "Layer 1's judgment is broken". Split by source it reads as
#: what it is: Gmail is judged on every event, and the screen instant lane deliberately does not
#: buy a second model call. Two facts about two lanes, summed into one alarming number.
#:
#: `action` rides along because "kept" and "refused" under the same rule are different facts.
_HISTOGRAM = """
    select source,
           coalesce(reason_code, '(none)') as relevance_rule,
           action,
           count(*)                        as n
      from event_trace
     where org_id = :o and stage = 's4_esqe'
     group by 1, 2, 3
     order by source, n desc
"""

#: ⛔ THE SCREEN INSTANT LANE IS SUPPOSED TO REACH S4 WITH NO CLIENT, and this constant is what
#: stops a future reader treating that as a defect.
#:
#: `platform/screen_promoter.py:183` builds the wiring with `semantic=None if instant else …`, and
#: its own comment gives the reason: *"S4's relevance page never re-asks a model what S2's one call
#: (or the verdict) already answered for this screen object — at most ONE AI call per object."*
#: The instant lane also carries a 3.5 s hard timeout, so a second call could not fit inside it
#: even if it were wanted.
#:
#: So for this source, `no_model_wired` is the CORRECT outcome and the fail-open at authority 3000
#: is the designed one. Judging it a failure is how somebody ends up "fixing" a budget guarantee.
_MODEL_FREE_BY_DESIGN = frozenset({"screen_session"})


def _url() -> str:
    """The database, from the environment or from whichever `.env` actually holds it.

    ⛔ THE REPO ROOT IS NOT WHERE THE `.env` LIVES on this checkout — it sits one level up, beside
    the repo rather than inside it. A script that only looked at `_ROOT / ".env"` reported "no url"
    on a machine that had one, which reads as a missing secret and is really a missing directory.
    Both are checked, nearest first, and neither is required.
    """
    url = os.environ.get("GENIOS_DATABASE_URL")
    if url:
        return url
    for env in (_ROOT / ".env", _ROOT.parent / ".env"):
        if not env.exists():
            continue
        for line in env.read_text().splitlines():
            if line.startswith("GENIOS_DATABASE_URL="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    sys.exit("GENIOS_DATABASE_URL is not set, and no .env beside or above the repo carries one")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--org", default=_PILOT_ORG)
    ap.add_argument("--assert-judged", action="store_true",
                    help="exit 1 unless the switch is live AND a model actually decided "
                         "something. U-S1-04's gate.")
    args = ap.parse_args()

    from sqlalchemy import text

    # ⛔ THE APP'S OWN FACTORY, NOT `create_engine`. The project ships psycopg **v3** and SQLAlchemy
    # maps a bare `postgresql://` to psycopg2, which is not installed — so a hand-rolled engine
    # dies on `ModuleNotFoundError` against a database that is perfectly reachable. `get_engine`
    # already normalises the scheme, and `scripts/speedrun008_measurements.py` uses it for the
    # same reason.
    from genios_engine.platform.db import get_engine

    engine = get_engine(_url())
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("set transaction read only"))
        activation = conn.execute(text(_ACTIVATION), {"o": args.org}).mappings().first()
        rows = list(conn.execute(text(_HISTOGRAM), {"o": args.org}).mappings())

    print(f"\norg: {args.org}\n")

    # ── the switch ────────────────────────────────────────────────────────────────────────────
    print("SEMANTIC ACTIVATION (l1_semantic_activation)")
    if activation is None:
        live = False
        print("  no row  ->  NOT ACTIVATED. `is_semantic_activated` is fail-closed, so the")
        print("              SemanticLane is never built and relevance runs rule-only.")
    elif activation["disabled_at"] is not None:
        live = False
        print(f"  disabled_at = {activation['disabled_at']}  ->  NOT ACTIVATED (row kept, as 0090 "
              f"intends)")
    else:
        live = True
        print(f"  LIVE since {activation['enabled_at']} by {activation['enabled_by']}")

    # ── what it decided, PER SOURCE ───────────────────────────────────────────────────────────
    total = sum(r["n"] for r in rows)
    print(f"\nRELEVANCE RULES  (event_trace, stage='s4_esqe')   {total} rows, by source")
    if not rows:
        print("  none — S4 has not run for this org, so this says nothing about the switch.")

    sources: dict[str, dict[str, int]] = {}
    for r in rows:
        sources.setdefault(r["source"], {})
        key = r["relevance_rule"]
        sources[r["source"]][key] = sources[r["source"]].get(key, 0) + r["n"]

    verdicts: list[tuple[str, bool, str]] = []
    for source in sorted(sources):
        by_rule = sources[source]
        n = sum(by_rule.values())
        unwired = by_rule.get(RULE_NO_MODEL_WIRED, 0)
        judged = sum(by_rule.get(k, 0) for k in _JUDGED_RULES)
        unavailable = by_rule.get(RULE_LLM_UNAVAILABLE, 0)
        by_design = source in _MODEL_FREE_BY_DESIGN

        print(f"\n  {source}   ({n} rows)")
        for rule, count in sorted(by_rule.items(), key=lambda kv: -kv[1]):
            note = ""
            if rule == RULE_NO_MODEL_WIRED:
                note = "  <- by design, one AI call at S2" if by_design else "  <- NOBODY DECIDED"
            print(f"      {rule:<26} {count:>6}{note}")

        if by_design:
            ok = judged == 0 or unwired > 0
            verdicts.append((source, True, "model-free by design — nothing to judge here"))
        elif unwired:
            verdicts.append((source, False, f"{unwired} events reached S4 with no client"))
        elif judged:
            verdicts.append((source, True, f"{judged} judged by a model"))
        else:
            verdicts.append((source, True, "decided by rules alone; the model was never needed"))

        if unavailable:
            verdicts.append((source, False,
                             f"{unavailable} × {RULE_LLM_UNAVAILABLE} — a client WAS wired and the "
                             f"call did not come back. A reliability problem, not a wiring one"))

    # ── the verdict ───────────────────────────────────────────────────────────────────────────
    print("\nVERDICT")
    for source, ok, why in verdicts:
        print(f"  {'ok  ' if ok else 'FAIL'}  {source:<16} {why}")

    if not args.assert_judged:
        print()
        return 0

    failures = [(s, w) for s, ok, w in verdicts if not ok]
    print()
    if not live:
        print("FAIL  the activation row is not live")
        return 1
    if failures:
        return 1
    print("PASS  every source is either judged or model-free by design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
