"""Every org has at least one seat: the person who signed up.

`org_seats` had ZERO rows in the entire database, and it is the join every layer reaches for
when it needs to know who works here:

  * L2 excludes "us" from counterparty correlation by reading it — with the table empty the
    exclusion was a no-op, so the founder and his own company were correlated as prospects;
  * L4 resolves a signal's owner through it;
  * L5's escalation ladder is built from it, so every commitment was born unroutable and the
    reminder engine was permanently quiet;
  * L6 assigns a card's recipient from it, so all 43 cards carried `assignee = NULL`.

The only writer was an admin seat-management endpoint nobody had called. Signup created an org
row with an email on it and no seat, so the table's emptiness was not a configuration the
tenants chose — it was a step that did not exist.

The owner's seat is derived, not invented: `orgs.email` is who signed up, and role `admin` is
what `assignment.PgSeatDirectory.admins()` looks for when an escalation runs out of ladder.
"""
from __future__ import annotations

from sqlalchemy import text

#: Deterministic, so re-running is an upsert rather than a second seat for the same human.
OWNER_SEAT_ID = "seat_owner"


def ensure_owner_seat(conn, org_id: str) -> dict:
    """Create (or refresh) the owner's seat from `orgs.email`. Idempotent.

    Never deactivates and never rewrites a role: an admin who demoted the founder's seat or
    pointed it at a different address made a deliberate choice, and a backfill that silently
    reversed it would be worse than the empty table this fixes.
    """
    email = conn.execute(text("select email from orgs where id=:o"), {"o": org_id}).scalar()
    if not email:
        # An org with no email has no owner to derive. Say so rather than mint a seat with a
        # null address that every downstream lookup would then fail to match.
        return {"org_id": org_id, "seat_id": None, "reason": "org_has_no_email"}

    existing = conn.execute(text(
        "select seat_id from org_seats where org_id=:o and lower(email)=lower(:e)"),
        {"o": org_id, "e": email}).scalar()
    if existing:
        return {"org_id": org_id, "seat_id": existing, "reason": "already_seated"}

    conn.execute(text(
        "insert into org_seats (org_id, seat_id, email, role, active) "
        "values (:o, :s, :e, 'admin', true) "
        "on conflict (org_id, seat_id) do nothing"),
        {"o": org_id, "s": OWNER_SEAT_ID, "e": email})
    return {"org_id": org_id, "seat_id": OWNER_SEAT_ID, "reason": "created"}


def backfill_owner_seats(conn) -> list[dict]:
    """Seat every org that has none. Orgs with seats are left completely alone."""
    orgs = [r[0] for r in conn.execute(text(
        "select id from orgs where not exists ("
        "  select 1 from org_seats s where s.org_id = orgs.id)"))]
    return [ensure_owner_seat(conn, o) for o in orgs]


def ensure_pull_surface(conn, org_id: str) -> bool:
    """Give the org the durable pull surface it already has in practice.

    `run_distribution` enumerates `select distinct org_id from org_channels where active`, and
    that table had zero rows for every tenant — so the sweep found no orgs, and not one delivery
    has ever occurred: no digest, no commitment reminder, no push. Every card was visible only if
    somebody opened the dashboard, which means the product has had no proactive surface at all.

    `in_app` is not an integration a tenant configures. `routing.PULL_SURFACE` calls it "the
    durable pull surface every human recipient always has" and makes it the floor of every human
    ladder — so a row asserting it is a statement of fact, not a setting. Chat channels stay
    opt-in and credentialed as before.

    It is emphatically NOT a transport, and this row alone does not make the org deliverable.
    `get_channel('in_app')` is None — there is nothing to send, because the card is already on
    the surface the row names. `outbox.deliverable_channels` therefore intersects `org_channels`
    with the channels that have an adapter, and an org holding only this row is counted as
    `no_deliverable_channel` by the sweep rather than being queued a message that the drain
    would kill on sight. Making that row a transport is what produced production's entire
    delivery history: 3 rows, all `failed_terminal`.

    Returns True when a row was created.
    """
    from genios_engine.deliver.routing import PULL_SURFACE
    return conn.execute(text(
        "insert into org_channels (org_id, channel, config, active) "
        "values (:o, :ch, cast('{}' as jsonb), true) "
        "on conflict (org_id, channel) do nothing"),
        {"o": org_id, "ch": PULL_SURFACE}).rowcount > 0


class SeatLimitReached(Exception):
    """Adding one more seat would exceed the plan's allowance."""

    def __init__(self, tier: str, limit: int, used: int) -> None:
        self.tier, self.limit, self.used = tier, limit, used
        super().__init__(f"seat limit reached for the {tier} plan ({limit} seats)")


def seats_in_use(conn, org_id: str, *, excluding_email: str | None = None) -> int:
    """Seats this org is consuming: every ACTIVE seat plus every invite still waiting to be
    accepted (an unexpired, unaccepted invite for an address that holds no active seat).

    A pending invite counts because accepting it must never be the step that fails — the admin who
    sent it was told there was room. `excluding_email` leaves one address's own pending invite out,
    so re-sending or accepting an invite is not counted against itself.
    """
    active = int(conn.execute(text(
        "select count(*) from org_seats where org_id=:o and active"), {"o": org_id}).scalar() or 0)
    pending = int(conn.execute(text(
        "select count(*) from org_invites i where i.org_id=:o and i.accepted_at is null "
        "and (i.expires_at is null or i.expires_at > now()) "
        "and lower(i.email) <> lower(coalesce(cast(:x as text), '')) "
        "and not exists (select 1 from org_seats s where s.org_id=i.org_id and s.active "
        "and lower(s.email)=lower(i.email))"),
        {"o": org_id, "x": excluding_email}).scalar() or 0)
    return active + pending


def assert_seat_capacity(conn, org_id: str, *, adding_email: str | None = None) -> dict:
    """THE seat limit — one rule for inviting, accepting and seeding a seat.

    Three writers used to answer this three ways: `/seats` against a hardcoded
    `{"trial": 2, "startup": 5, ...}` that disagreed with billing, invites against
    `billing.plan_seat_limit` while counting members that nothing ever wrote. The plan's own
    `seats` is now the only number, and `seats_in_use` the only count.

    Locks the org row for the rest of the caller's transaction, so two concurrent additions cannot
    both see the last free seat. Raises `SeatLimitReached`.
    """
    from genios_engine.platform.billing import plan_seat_limit
    tier = str(conn.execute(text("select subscription_tier from orgs where id=:o for update"),
                            {"o": org_id}).scalar() or "trial").lower()
    ensure_owner_seat(conn, org_id)          # the owner occupies a seat whether or not it was seeded
    limit = plan_seat_limit(tier)
    used = seats_in_use(conn, org_id, excluding_email=adding_email)
    if used + 1 > limit:
        raise SeatLimitReached(tier, limit, used)
    return {"tier": tier, "limit": limit, "used": used}


def provision_org(conn, org_id: str) -> dict:
    """Everything an org must have before any layer can route for it."""
    return {"seat": ensure_owner_seat(conn, org_id),
            "pull_surface": ensure_pull_surface(conn, org_id)}


def backfill_provisioning(conn) -> list[dict]:
    """Seat and surface every org missing either. Idempotent; leaves configured orgs alone."""
    orgs = [r[0] for r in conn.execute(text("select id from orgs"))]
    return [{"org_id": o, **provision_org(conn, o)} for o in orgs]


__all__ = ["OWNER_SEAT_ID", "backfill_owner_seats", "backfill_provisioning",
           "ensure_owner_seat", "ensure_pull_surface", "provision_org"]
