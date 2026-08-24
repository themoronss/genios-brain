"""`org_seats` had zero rows in the entire database, and four layers read it.

Not a configuration any tenant chose — signup created an org row carrying the owner's email and
never created a seat, and the only writer was an admin endpoint nobody had called. Each affected
layer then failed in a way that looked like something else:

  * L2's "us" exclusion became a no-op, so the founder and his own company were correlated as
    prospects — which reads as bad entity resolution;
  * L5 built every commitment with an empty escalation ladder, so the reminder engine was
    permanently quiet — which reads as a scheduler bug;
  * L6 assigned `NULL` to all 43 cards — which reads as a delivery bug.
"""
import pytest
from sqlalchemy import create_engine, text

from genios_engine.platform.seats import OWNER_SEAT_ID, backfill_owner_seats, ensure_owner_seat


@pytest.fixture()
def conn():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as c:
        c.execute(text("create table orgs (id text primary key, email text)"))
        c.execute(text(
            "create table org_seats (org_id text, seat_id text, email text, role text, "
            "active boolean, primary key (org_id, seat_id))"))
        yield c


def test_an_org_gets_its_owner_seated(conn):
    conn.execute(text("insert into orgs values ('org_1', 'founder@acme.com')"))
    assert ensure_owner_seat(conn, "org_1")["seat_id"] == OWNER_SEAT_ID
    row = conn.execute(text("select email, role, active from org_seats")).first()
    # `admin` because that is what `assignment.PgSeatDirectory.admins()` looks for when an
    # escalation runs out of ladder — a seat with any other role is invisible to the last rung.
    assert row.email == "founder@acme.com"
    assert row.role == "admin"


def test_running_it_twice_does_not_seat_the_founder_twice(conn):
    conn.execute(text("insert into orgs values ('org_1', 'founder@acme.com')"))
    ensure_owner_seat(conn, "org_1")
    ensure_owner_seat(conn, "org_1")
    assert conn.execute(text("select count(*) from org_seats")).scalar() == 1


def test_a_seat_an_admin_already_configured_is_left_alone(conn):
    """An admin who renamed the founder's seat or changed its role made a deliberate choice. A
    backfill that silently reversed it would be a worse bug than the empty table it fixes."""
    conn.execute(text("insert into orgs values ('org_1', 'founder@acme.com')"))
    conn.execute(text(
        "insert into org_seats values ('org_1', 'seat_custom', 'founder@acme.com', 'member', 1)"))
    result = ensure_owner_seat(conn, "org_1")
    assert result["reason"] == "already_seated"
    assert result["seat_id"] == "seat_custom"
    assert conn.execute(text("select role from org_seats")).scalar() == "member"


def test_an_org_with_no_email_is_reported_not_papered_over(conn):
    """Minting a seat with a null address would satisfy `count(*) > 0` while matching no lookup
    anywhere — the emptiness would move from visible to hidden."""
    conn.execute(text("insert into orgs values ('org_1', null)"))
    assert ensure_owner_seat(conn, "org_1")["reason"] == "org_has_no_email"
    assert conn.execute(text("select count(*) from org_seats")).scalar() == 0


def test_backfill_touches_only_orgs_that_have_no_seats_at_all(conn):
    conn.execute(text("insert into orgs values ('org_1', 'a@x.com'), ('org_2', 'b@x.com')"))
    conn.execute(text("insert into org_seats values ('org_2', 'seat_x', 'b@x.com', 'admin', 1)"))
    done = backfill_owner_seats(conn)
    assert [d["org_id"] for d in done] == ["org_1"]


def test_signup_seats_the_owner_in_the_same_transaction():
    """A seat created by a later backfill leaves a window where the org exists and no layer can
    route anything for it. Signup is where the owner is known."""
    import inspect

    from genios_engine.api import auth_routes

    src = inspect.getsource(auth_routes)
    assert "provision_org(c, org_id)" in src
