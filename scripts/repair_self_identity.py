"""Undo what the engine did before it knew who "us" is — threads named after us, signals and cards about us.

    python scripts/repair_self_identity.py --org <org_id> --database-url postgresql://…          # dry run
    python scripts/repair_self_identity.py --org <org_id> --database-url postgresql://… --apply  # writes

**Why (STEP-04).** "Who is us" was decided in eighteen places, and for the design partner they missed
his second address and his company's domain (`speedrun008/YC-II W27/` STEP-04 §8.2). So production
holds what that produced: threads named *"Mr Rohit Swerashi — <the pitch>"* (a label the engine never
renames), and open cards and signals whose subject is the founder himself — *"Send Mr Rohit Swerashi
your traction metrics"*. STEP-04 stops new ones; this removes the ones already there. Run it AFTER the
deploy, and after `scripts/declare_self_identity.py` has declared the tenant's addresses and domains —
the repair reads the same answer the engine now asks, `platform/self_identity.identity_for`.

**What it changes, and only this.** One tenant (`--org`):

  * a thread named "<one of us> — <what it is for>" is renamed after its other side — the oldest
    person it corresponded with who is not one of us — or by what it is for alone;
  * an open signal whose subject node is one of us expires (`status = 'expired'`);
  * an open card whose subject is one of us — by its signal's subject node, or by a
    `business_subject` that names us — is retired to `expired`, and each retirement writes a
    `card_event` (`card.retired`, cause `subject_is_us`) saying so, so it can be audited and rebuilt.

Situations anchored on one of our nodes are LISTED, not changed: the correlation rebuild
(`context/backfill.backfill_correlations(rebuild=True)`) re-derives them, and since STEP-04 it no
longer anchors on us. The tenant node's own period situations are ours by design and never listed.

**Read-only until `--apply`** (`06` D14: Harsh runs the dry run, Rohit reads its list, then `--apply`).
The target goes through `scripts/_db.py`: no fallback to the application's database, and
`GENIOS_ALLOW_PROD_WRITE=1` for a production host.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

#: `CardStore.OPEN_STATES` — a card in any of these is still in front of somebody.
OPEN_STATES = ("queued", "surfaced", "snoozed", "claimed", "delivered")
#: The separator `context/graph_store.thread_label` writes between who and what.
_DASH = " — "


@dataclass
class Plan:
    org_id: str
    threads: list[tuple[str, str, str]] = field(default_factory=list)       # node, before, after
    signals: list[tuple[str, str]] = field(default_factory=list)            # signal, subject node
    cards: list[tuple[str, str]] = field(default_factory=list)              # card, subject
    situations: list[tuple[str, str, str]] = field(default_factory=list)    # situation, type, anchor

    def summary(self) -> str:
        return (f"{len(self.threads)} thread(s) to rename, {len(self.signals)} open signal(s) and "
                f"{len(self.cards)} open card(s) about us to retire, {len(self.situations)} "
                "situation(s) anchored on us (listed; the correlation rebuild re-derives them)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the one tenant to repair")
    ap.add_argument("--apply", action="store_true", help="write (default: a dry run that lists)")
    return ap.parse_args(argv)


def _names_us(text: str | None, names: set[str], us) -> bool:
    """A subject that IS one of us: one of our full names, an address of ours, or a declared domain."""
    value = " ".join(str(text or "").split()).lower()
    if not value:
        return False
    if any(re.search(rf"(?<![0-9a-z]){re.escape(n)}(?![0-9a-z])", value) for n in names):
        return True
    words = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|[a-z0-9-]+(?:\.[a-z0-9-]+)+", value)
    return any(us.is_us(w) if "@" in w else us.is_us_domain(w) for w in words)


def plan(conn, org_id: str) -> Plan:
    """Everything the repair would change for one tenant. Reads only."""
    from sqlalchemy import text

    from genios_engine.context.graph_store import thread_label
    from genios_engine.platform.self_identity import identity_for

    us = identity_for(conn, org_id)
    out = Plan(org_id=org_id)
    nodes = conn.execute(text(
        "select node_id, node_type, canonical_key, display_name from graph_nodes "
        " where org_id = :o and valid_to is null and node_type in ('person', 'service', 'company')"),
        {"o": org_id}).fetchall()
    ours = {n.node_id: n for n in nodes if us.is_us_node(n.node_type, n.canonical_key)}
    org = conn.execute(text("select name, first_name, last_name from orgs where id = :o"),
                       {"o": org_id}).first()
    names = {" ".join(str(n.display_name or "").split()).lower()
             for n in ours.values() if n.node_type in ("person", "service")}
    if org is not None:
        names.add(" ".join(str(org.name or "").split()).lower())
        if org.first_name and org.last_name:
            names.add(f"{org.first_name} {org.last_name}".lower())
    names = {n for n in names if len(n) >= 3 and "@" not in n}

    for t in conn.execute(text(
            "select node_id, display_name from graph_nodes "
            " where org_id = :o and valid_to is null and node_type = 'thread' "
            "   and display_name like '%' || :dash || '%'"), {"o": org_id, "dash": _DASH}):
        who, _, what = str(t.display_name).partition(_DASH)
        if not _names_us(who, names, us):
            continue
        parties = conn.execute(text(
            "select p.display_name, p.canonical_key from graph_edges e "
            "  join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
            "       and p.node_type = 'person' and p.valid_to is null "
            " where e.org_id = :o and e.to_node_id = :n and e.edge_type = 'corresponded_with' "
            "   and e.valid_to is null order by e.created_at, p.node_id"),
            {"o": org_id, "n": t.node_id}).fetchall()
        other = next((p.display_name or p.canonical_key for p in parties
                      if not us.is_us(p.canonical_key)), None)
        after = thread_label(objective=what, counterparty=other)
        if after and after != t.display_name:
            out.threads.append((t.node_id, t.display_name, after))

    for s in conn.execute(text(
            "select signal_id, subject_node_id from signals where org_id = :o and status = 'open' "
            " order by signal_id"), {"o": org_id}):
        if s.subject_node_id in ours:
            out.signals.append((s.signal_id, s.subject_node_id))
    retired_signals = {sid for sid, _ in out.signals}
    for c in conn.execute(text(
            "select c.card_id, c.business_subject, c.signal_id from cards c "
            " where c.org_id = :o and c.state = any(:open) order by c.card_id"),
            {"o": org_id, "open": list(OPEN_STATES)}):
        if c.signal_id in retired_signals or _names_us(c.business_subject, names, us):
            out.cards.append((c.card_id, c.business_subject or ""))
    for s in conn.execute(text(
            "select situation_id, situation_type, anchor_node_id from context_situations "
            " where org_id = :o and status in ('active', 'dormant', 'partial') order by situation_id"),
            {"o": org_id}):
        if s.anchor_node_id in ours:
            out.situations.append((s.situation_id, s.situation_type, s.anchor_node_id))
    return out


def apply(engine, repair: Plan) -> dict[str, int]:
    """Write the plan in one transaction. Guarded on the current state, so a second run, or a card
    that moved meanwhile, changes nothing."""
    from sqlalchemy import text

    from genios_engine.platform.ids import new_id

    done = {"threads": 0, "signals": 0, "cards": 0}
    org = repair.org_id
    with engine.begin() as c:
        for node_id, before, after in repair.threads:
            done["threads"] += c.execute(text(
                "update graph_nodes set display_name = :after where org_id = :o and node_id = :n "
                "   and valid_to is null and display_name = :before"),
                {"after": after[:120], "o": org, "n": node_id, "before": before}).rowcount
        for signal_id, _node in repair.signals:
            done["signals"] += c.execute(text(
                "update signals set status = 'expired' where org_id = :o and signal_id = :s "
                "   and status = 'open'"), {"o": org, "s": signal_id}).rowcount
        for card_id, subject in repair.cards:
            changed = c.execute(text(
                "update cards set state = 'expired' where org_id = :o and card_id = :c "
                "   and state = any(:open)"), {"o": org, "c": card_id, "open": list(OPEN_STATES)}).rowcount
            if changed:
                c.execute(text(
                    "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
                    "values (:id, :c, :o, 'card.retired', 'subject_is_us', 'repair_self_identity', "
                    "        cast(:d as jsonb))"),
                    {"id": new_id("cev"), "c": card_id, "o": org,
                     "d": json.dumps({"business_subject": subject, "by": "scripts/repair_self_identity.py"})})
                done["cards"] += changed
    return done


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    url = resolve_database_url(args, purpose="repair what the engine did before it knew who us is")
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    with engine.connect() as conn:
        conn.exec_driver_sql("set transaction read only")
        repair = plan(conn, args.org)
    print(repair.summary())
    for node_id, before, after in repair.threads:
        print(f"  thread {node_id}: {before!r} -> {after!r}")
    for card_id, subject in repair.cards:
        print(f"  card {card_id}: subject {subject!r}")
    for situation_id, kind, anchor in repair.situations:
        print(f"  situation {situation_id} ({kind}) anchored on {anchor}")
    if not args.apply:
        print("DRY RUN — nothing written. Read the list (06 D14), then re-run with --apply.")
        return 0
    print("applied:", apply(engine, repair))
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
