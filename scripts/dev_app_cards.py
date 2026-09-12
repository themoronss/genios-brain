"""Exactly what the Mac app receives for one org — from the REAL API handlers, on the local copy.

Calls `GET /cards` and `GET /cards/{id}` (the two endpoints `Extension/src/desktop/api.ts` uses)
through FastAPI's TestClient WITHOUT entering its lifespan, so the scheduler and sync worker never
start: nothing is sent anywhere. Auth is a real owner JWT for the org's own email, minted with the
same `jwt_encode` the login route uses. Writes the raw JSON and an HTML view of it.

    scripts/dev_localdb.sh app-cards <org_id>
"""
import html
import json
import os
import sys
import time

ORG = os.environ.get("GENIOS_DEV_ORG", "").strip() or sys.exit("GENIOS_DEV_ORG is required")
OUT = os.environ.get("GENIOS_DEV_OUT", os.path.expanduser("~/.genios-localdb/app_cards"))

from genios_engine.platform.config import get_settings  # noqa: E402

s = get_settings()
if "@localhost:" not in s.database_url and "@127.0.0.1:" not in s.database_url:
    sys.exit("refusing: GENIOS_DATABASE_URL is not a localhost database")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from genios_engine.main import app  # noqa: E402
from genios_engine.platform.auth import jwt_encode  # noqa: E402

with create_engine(s.database_url).connect() as c:
    email = c.execute(text("select email from orgs where id=:o"), {"o": ORG}).scalar()
token = jwt_encode({"org_id": ORG, "email": email, "exp": time.time() + 3600}, s.jwt_secret)
client = TestClient(app)                      # no `with`: lifespan (scheduler, worker) never runs
auth = {"Authorization": f"Bearer {token}"}

listing = client.get("/cards", headers=auth)
listing.raise_for_status()
cards = listing.json().get("cards") or []
details = []
for card in cards:
    r = client.get(f"/cards/{card['card_id']}", headers=auth)
    details.append(r.json() if r.status_code == 200 else {"card_id": card["card_id"],
                                                          "error": r.status_code, "body": r.text})

os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/cards.json", "w", encoding="utf-8") as f:
    json.dump({"org": ORG, "viewer": email, "list": cards, "details": details}, f, indent=1,
              default=str, ensure_ascii=False)


def e(v) -> str:
    return html.escape("" if v is None else str(v))


def block(title, body) -> str:
    return f"<div class=sec><div class=h>{e(title)}</div>{body}</div>" if body else ""


def rows(items, fmt) -> str:
    return "".join(f"<li>{fmt(i)}</li>" for i in (items or [])) and \
        f"<ul>{''.join(f'<li>{fmt(i)}</li>' for i in (items or []))}</ul>"


parts = [f"<h1>{len(cards)} cards — what the Mac app receives</h1>"
         f"<p class=sub>org {e(ORG)} · viewer {e(email)} · from GET /cards + GET /cards/{{id}} "
         f"on the local copy · raw: cards.json</p>"]
for i, (card, d) in enumerate(zip(cards, details), 1):
    ctx = d.get("context") or {}
    dec = (d.get("decision") or {}).get("recommendation") or {}
    act = d.get("actionability") or {}
    parts.append(
        f"<div class='card {e(card.get('urgency_band'))}'>"
        f"<div class=top><span class=band>{e(card.get('urgency_band'))}</span>"
        f"<span class=score>score {e(card.get('score'))}</span>"
        f"<span class=state>{e(card.get('state'))}</span></div>"
        f"<div class=title>{i}. {e(card.get('headline'))}</div>"
        f"<div class=situ>{e(card.get('situation'))}</div>"
        + (f"<div class=warn>{e(act.get('message'))} {e(act.get('recommended'))}</div>"
           if act.get("state") == "context_incomplete" else "")
        + block("Recommendation", (f"<b>{e(dec.get('verdict'))}</b> — {e(dec.get('objective'))}"
                                   + rows(dec.get("steps"), e)
                                   + (f"<div>Avoid: {e(dec.get('avoid'))}</div>"
                                      if dec.get("avoid") else "")) if dec else "")
        + block("Who / context", rows(ctx.get("profile"),
                                      lambda p: f"{e(p.get('field'))}: {e(p.get('value'))}"))
        + block("Signals", rows(ctx.get("signals"),
                                lambda p: f"{e(p.get('label'))} ×{e(p.get('count'))}"))
        + block("Commitments", rows(ctx.get("commitments"),
                                    lambda p: f"{e(p.get('text'))} (due {e(p.get('due_at'))})"))
        + block("Meetings", rows(ctx.get("interactions"),
                                 lambda p: f"{e(p.get('title'))} — {e(p.get('state_label'))}"))
        + block("Evidence", rows(d.get("why"),
                                 lambda p: f"{e(p.get('field'))} = {e(p.get('value'))} "
                                           f"<i>({e(p.get('source'))})</i>"))
        + block("Buttons", rows(d.get("actions"),
                                lambda p: f"{e(p.get('label') or p.get('type'))}"
                                          f"{' — ' + e(p.get('effect')) if p.get('effect') else ''}"))
        + (f"<div class=err>detail error {e(d.get('error'))}: {e(d.get('body'))}</div>"
           if d.get("error") else "")
        + "</div>")

page = """<!doctype html><meta charset=utf-8><title>Mac app cards</title><style>
body{font:14px -apple-system,system-ui,sans-serif;background:#f6f4ef;color:#222;max-width:820px;
margin:24px auto;padding:0 16px}h1{font-size:20px}.sub{color:#777;font-size:12px}
.card{background:#fff;border:1px solid #e4e0d6;border-left:4px solid #bbb;border-radius:8px;
padding:14px 16px;margin:14px 0}.card.high{border-left-color:#d08a00}.card.critical{border-left-color:#8a1c2b}
.top{display:flex;gap:10px;font-size:11px;text-transform:uppercase;color:#888}
.title{font-size:16px;font-weight:600;margin:6px 0}.situ{color:#444}
.sec{margin-top:10px}.h{font-size:11px;text-transform:uppercase;color:#999;margin-bottom:2px}
ul{margin:2px 0 0 18px;padding:0}.warn{background:#fff6e0;padding:6px 8px;border-radius:6px;
margin-top:8px}.err{color:#a00}</style>""" + "".join(parts)
with open(f"{OUT}/cards.html", "w", encoding="utf-8") as f:
    f.write(page)
print(f"{len(cards)} cards from GET /cards -> {OUT}/cards.html")
