from __future__ import annotations

# E6 (digest part) · the 08:30 morning summary (§5.15). ONE line: "N cards waiting · top: <headline>".
# Not a card, consumes no budget, outside the 2-notification cap. Computed ON DEMAND when the
# surface asks (no periodic Celery task — Upstash quota rule); the client schedules the 08:30 fetch.


def build_digest(card_store, org_id: str, *, assignee: str | None = None, admin: bool = False) -> dict:
    # Reuse the shared Layer 4 authority projection; a digest must not resurrect revoked cards.
    rows = card_store.queue(
        org_id, assignee=assignee, admin=admin,
        states=("queued", "surfaced", "snoozed"), record_impressions=False)
    n = len(rows)
    top = rows[0]["headline"] if rows else None
    crit = sum(1 for r in rows if r["urgency_band"] == "critical")
    high = sum(1 for r in rows if r["urgency_band"] == "high")
    text_line = (f"{n} card{'s' if n != 1 else ''} waiting" + (f" · top: {top}" if top else "")) \
        if n else "No cards waiting — you're clear."
    return {"count": n, "critical": crit, "high": high, "top": top, "text": text_line,
            "cards": rows[:5]}
