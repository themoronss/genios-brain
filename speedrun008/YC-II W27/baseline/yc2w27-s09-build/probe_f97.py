"""F97 probe: does `platform/company_brief.current(conn)` read through the caller's connection?"""
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from genios_engine.platform import company_brief, company_brief_store
e = create_engine("postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test")
org = "org_s09_probe_current"
with e.begin() as c:
    c.execute(text("delete from orgs where id=:o"), {"o": org})
    c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"), {"o": org, "e": org + "@probe.test"})
company_brief.invalidate(org)
try:
    with e.begin() as c:
        company_brief_store.add(c, org_id=org, section="connectors", address="hello@introly.test",
                                words="Introly — introduces", decided_by="probe", at=datetime.now(timezone.utc))
        print("current(conn) inside the writing transaction sees the line:", bool(company_brief.current(c, org).lines))
        print("brief_for(conn) sees it:", bool(company_brief.brief_for(c, org).lines))
    print("after commit, current() serves:", bool(company_brief.current(e, org).lines))
finally:
    with e.begin() as c:
        c.execute(text("delete from orgs where id=:o"), {"o": org})
    company_brief.invalidate(org)
