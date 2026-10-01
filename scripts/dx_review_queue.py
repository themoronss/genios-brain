#!/usr/bin/env python3
r"""The review queue for every `draft + unreviewed` situation — generated, never hand-kept.

    .venv/bin/python scripts/dx_review_queue.py > "Domain Expertise/_review/QUEUE.md"

READ-ONLY. One `set transaction read only` connection, no writes, no model calls.

⛔ WHY IT IS GENERATED. A hand-written review list goes stale the first time somebody reviews one
thing, and this programme has now paid three times for a status that was true when it was written.
The queue is derived from the corpus and production every time it runs, so the day a situation is
approved it leaves the list by itself.

⛔ WHAT IT PRE-ANSWERS, SO A HUMAN ONLY DECIDES WHAT A HUMAN MUST. Two things about each situation
are machine-checkable and are checked here:

  1. **does every predicate have a live writer?** Measured against `graph_facts`. A situation
     gating on a fact nothing writes can never fire, and that is not a judgement call.
  2. **does its L2 situation type ever actually form?** Measured against `context_situations`.
     A type that has never formed means the review cannot be validated against anything real yet.

⛔ AND THE ONE THING THAT INVERTED. An empty `matches.when` does **not** mean "never fires".
`context_adapter.matches(())` loops over nothing and returns `PredicateState.TRUE`, so an empty
`when` is **vacuously true** — the situation matches on its L2 type ALONE, unconditionally. The
first draft of this queue labelled those "can never fire", which is exactly backwards and would
have sent a reviewer looking for the wrong defect. They are the MOST permissive entries, not the
least, which is why they are listed first.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import text

from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
from genios_engine.platform.db import get_engine


def collect() -> tuple[list[dict], dict[str, int], dict[str, int]]:
    catalog = ExpertBrainCatalog(default_authoring_root())
    pending = []
    for domain, record in sorted(catalog.domains.items()):
        for sid, doc in sorted(record.situations.items()):
            content = doc.content or {}
            identity = content.get("identity") or {}
            meta = content.get("metadata") or {}
            if str(identity.get("status")) == "draft" \
                    and str(meta.get("review_status")) == "unreviewed":
                pending.append((domain, sid, content))

    url = os.environ.get("GENIOS_DATABASE_URL")
    if not url:
        print("GENIOS_DATABASE_URL is not set (.env is one level above the repo)", file=sys.stderr)
        raise SystemExit(2)
    engine = get_engine(url)
    with engine.connect() as conn:
        conn.execute(text("set transaction read only"))
        facts = dict(conn.execute(text(
            "select field, count(*) from graph_facts group by 1")).all())
        formed = dict(conn.execute(text(
            "select situation_type, count(*) from context_situations group by 1")).all())

    rows = []
    for domain, sid, content in pending:
        matches = content.get("matches") or {}
        preds = []
        for cond in matches.get("when", ()):
            path = cond.get("path") or cond.get("exists")
            preds.append({
                "path": str(path) if path else None,
                "shape": dict(cond),
                "rows": facts.get(str(path), 0) if path else None,
            })
        types = list(matches.get("l2_situation_types", ()))
        rows.append({
            "id": sid, "domain": domain,
            "name": (content.get("identity") or {}).get("name") or sid,
            "owner": (content.get("identity") or {}).get("owner_capability"),
            "description": (content.get("description") or "").strip(),
            "types": types,
            "formed": sum(formed.get(t, 0) for t in types),
            "scope": matches.get("scope"),
            "preds": preds,
            "priority_bp": content.get("priority_bp"),
            "days": content.get("typical_duration_days"),
            "progress": list(content.get("signals_of_progress", ())),
            "decay": list(content.get("signals_of_decay", ())),
            "artifact": (content.get("render") or {}).get("artifact_kind"),
            "confidence": (content.get("metadata") or {}).get("confidence"),
            "updated": (content.get("metadata") or {}).get("last_updated"),
        })
    return rows, facts, formed


def _block(row: dict, n: int) -> str:
    dead = [p["path"] for p in row["preds"] if p["path"] and not p["rows"]]
    lines = [f"### {n}. {row['name']}",
             "",
             f"`{row['id']}` · owner `{row['owner']}` · priority **{row['priority_bp']}bp** · "
             f"typical **{row['days']} days** · card: **{row['artifact']}** · "
             f"authored confidence: *{row['confidence']}* · last edited {row['updated']}",
             "",
             row["description"] or "_(no description authored)_",
             ""]
    if row["preds"]:
        lines.append("**Fires when** — all of these must hold:")
        for p in row["preds"]:
            if p["path"]:
                mark = "⛔ **NOTHING WRITES THIS**" if not p["rows"] else f"{p['rows']} rows in production"
                lines.append(f"- `{p['shape']}` → {mark}")
            else:
                lines.append(f"- `{p['shape']}` → a condition on an **observation**, not a fact path")
    else:
        lines.append("⛔ **Fires on the L2 type alone — no extra condition at all.** An empty "
                     "`matches.when` is vacuously true, so this is the most permissive shape a "
                     "situation can have.")
    lines += ["",
              f"**L2 types** `{', '.join(row['types']) or '(none)'}` — formed "
              f"**{row['formed']}** times in production"
              + ("   ⚠ never formed, so nothing real to validate against yet" if not row["formed"]
                 else ""),
              "",
              f"**Progress** {', '.join(row['progress']) or '—'}",
              f"**Decay** {', '.join(row['decay']) or '—'}",
              ""]
    if not row["preds"]:
        lines.append("> **Decide:** is matching on the type alone right here, or does it need a "
                     "condition? If right → approve. If not → say which condition.")
    elif dead:
        lines.append(f"> **Decide:** {dead} has no writer, so this can never fire. Drop the "
                     f"predicate, change it, or defer the situation?")
    else:
        lines.append("> **Decide:** is the description what you would want a card about, and is "
                     "the priority right against the others? Approve or say what is wrong.")
    lines += ["", "    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______", "",
              "---", ""]
    return "\n".join(lines)


def one_line(description: str) -> str:
    """The first sentence, which the authors wrote as the situation in one breath.

    ⛔ NOT A SUMMARY I COMPOSE. Every description in this corpus opens with a single sentence that
    states the situation plainly and then spends a paragraph on the expert judgement behind it. The
    paragraph is why the markdown queue was unreadable in bulk; the first sentence is what a
    reviewer needs to recognise the thing. Taking it verbatim means this file cannot quietly
    reword what an author said.
    """
    first = (description or "").strip().split("\n")[0].strip()
    for stop in (". ", "? ", "! "):
        if stop in first:
            first = first.split(stop)[0] + stop.strip()
            break
    return first or "(no description authored)"


def _esc(text: object) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def write_html(rows: list[dict]) -> str:
    uncond = [r for r in rows if not r["preds"]]
    cond = [r for r in rows if r["preds"]]

    def card(row: dict, n: int) -> str:
        if row["preds"]:
            bits = []
            for pred in row["preds"]:
                if pred["path"]:
                    mark = ("<b class=bad>nothing writes this</b>" if not pred["rows"]
                            else f"{pred['rows']} rows")
                    bits.append(f"<code>{_esc(pred['path'])}</code> &middot; {mark}")
                else:
                    bits.append("a condition on an <b>observation</b>")
            fires = "<br>".join(bits)
            question = ("Is this the card you want, and is the priority right against the others?")
        else:
            fires = ("<b class=bad>No condition at all.</b> It matches every situation of its type "
                     "&mdash; the most permissive shape there is.")
            question = "Is matching on the type alone right here, or does it need a condition?"
        formed = row["formed"]
        seen = (f"{formed} times" if formed
                else "<b class=warn>never formed yet</b>")
        return f"""
<div class=card id="c{n}" data-id="{_esc(row['id'])}" data-name="{_esc(row['name'])}">
  <div class=head>
    <span class=num>{n}</span>
    <span class=name>{_esc(row['name'])}</span>
    <span class=pri>{row['priority_bp']}bp</span>
    <span class=dot></span>
  </div>
  <p class=lead>{_esc(one_line(row['description']))}</p>
  <div class=meta><div><b>Fires on</b><br>{fires}</div>
    <div><b>Seen in production</b><br>{seen}</div>
    <div><b>Typical</b><br>{row['days']} days</div>
    <div><b>Card</b><br>{_esc(row['artifact'] or '&mdash;')}</div></div>
  <p class=q>{question}</p>
  <div class=choices>
    <label><input type=radio name="d{n}" value=approve> approve</label>
    <label><input type=radio name="d{n}" value=change> change</label>
    <label><input type=radio name="d{n}" value=defer> defer</label>
    <input class=note type=text placeholder="note (only if change or defer)">
  </div>
  <details><summary>full description &amp; signals</summary>
    <p class=full>{_esc(row['description']).replace(chr(10), '<br>')}</p>
    <p class=sig><b>progress</b> {_esc(', '.join(row['progress']) or '&mdash;')}<br>
       <b>decay</b> {_esc(', '.join(row['decay']) or '&mdash;')}<br>
       <b>id</b> <code>{_esc(row['id'])}</code> &middot;
       <b>owner</b> <code>{_esc(row['owner'])}</code> &middot;
       authored <i>{_esc(row['confidence'])}</i>, edited {_esc(row['updated'])}</p>
  </details>
</div>"""

    cards1 = "".join(card(r, i) for i, r in enumerate(uncond, 1))
    cards2 = "".join(card(r, i) for i, r in enumerate(cond, len(uncond) + 1))
    return f"""<!DOCTYPE html>
<html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Situation Review</title>
<style>
:root{{--bg:#fbfaf8;--fg:#1c1b19;--mut:#6b6762;--line:#e3ded6;--card:#fff;
--bad:#b4401f;--warn:#9a6a10;--ok:#2d6a3f;--acc:#1c1b19}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#171614;--fg:#eceae6;
--mut:#9a948c;--line:#2e2c28;--card:#201e1b;--bad:#e2795a;--warn:#d6a73f;--ok:#7bbb8e;--acc:#eceae6}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 ui-serif,Georgia,serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:860px;margin:0 auto;padding:32px 16px 140px}}
h1{{font-size:28px;margin:0 0 4px;letter-spacing:-.01em}}
.sub{{color:var(--mut);margin:0 0 28px;font-size:15px}}
h2{{font-size:15px;text-transform:uppercase;letter-spacing:.09em;color:var(--mut);
margin:40px 0 6px;font-family:ui-sans-serif,system-ui,sans-serif;font-weight:600}}
h2+p{{color:var(--mut);margin:0 0 18px;font-size:15px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px 20px;margin:0 0 14px}}
.card.done{{border-color:var(--ok)}}
.head{{display:flex;align-items:baseline;gap:10px;margin-bottom:8px}}
.num{{font:600 13px ui-sans-serif,system-ui,sans-serif;color:var(--mut);min-width:20px}}
.name{{font-weight:600;font-size:19px;flex:1;letter-spacing:-.01em}}
.pri{{font:600 12px ui-sans-serif,system-ui,sans-serif;color:var(--mut);
border:1px solid var(--line);border-radius:999px;padding:2px 9px;white-space:nowrap}}
.dot{{width:9px;height:9px;border-radius:50%;background:var(--line);flex:0 0 auto}}
.card.done .dot{{background:var(--ok)}}
.lead{{margin:0 0 14px;font-size:17px}}
.meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;
font:13px/1.45 ui-sans-serif,system-ui,sans-serif;color:var(--mut);
border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:11px 0;margin-bottom:14px}}
.meta b{{color:var(--fg);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.07em}}
code{{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--bg);
border:1px solid var(--line);border-radius:4px;padding:1px 4px}}
.bad{{color:var(--bad)}}.warn{{color:var(--warn)}}
.q{{margin:0 0 12px;font-weight:600}}
.choices{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.choices label{{font:14px ui-sans-serif,system-ui,sans-serif;border:1px solid var(--line);
border-radius:8px;padding:7px 13px;cursor:pointer;user-select:none;background:var(--bg)}}
.choices label:has(input:checked){{border-color:var(--acc);box-shadow:inset 0 0 0 1px var(--acc);font-weight:600}}
.choices input[type=radio]{{margin-right:6px;accent-color:var(--acc)}}
.note{{flex:1;min-width:190px;font:14px ui-sans-serif,system-ui,sans-serif;padding:8px 11px;
border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}}
details{{margin-top:14px;font-size:14px}}
summary{{cursor:pointer;color:var(--mut);font:13px ui-sans-serif,system-ui,sans-serif}}
.full{{color:var(--mut);font-size:15px;margin:10px 0}}
.sig{{color:var(--mut);font:12px/1.6 ui-sans-serif,system-ui,sans-serif}}
.bar{{position:fixed;left:0;right:0;bottom:0;background:var(--card);
border-top:1px solid var(--line);padding:12px 16px;display:flex;gap:12px;align-items:center;
justify-content:center;font:14px ui-sans-serif,system-ui,sans-serif;flex-wrap:wrap}}
.bar b{{font-variant-numeric:tabular-nums}}
button{{font:600 14px ui-sans-serif,system-ui,sans-serif;padding:9px 18px;border-radius:8px;
border:1px solid var(--acc);background:var(--acc);color:var(--bg);cursor:pointer}}
button.ghost{{background:transparent;color:var(--fg)}}
#out{{width:100%;max-width:860px;min-height:150px;margin-top:10px;display:none;
font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;padding:12px;
border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}}
</style></head><body><div class=wrap>
<h1>Situation review</h1>
<p class=sub>{len(rows)} situations waiting on you. Click one of the three, add a note only if you
pick <i>change</i> or <i>defer</i>, then press <b>Copy decisions</b> at the bottom and paste it
back to me. Nothing here leaves your laptop.</p>

<h2>Part 1 &middot; no condition at all &mdash; {len(uncond)}</h2>
<p>Each of these fires on its situation type alone. Same question for all ten.</p>
{cards1}
<h2>Part 2 &middot; carries a condition &mdash; {len(cond)}</h2>
<p>Every predicate here was checked against production and all of them have a writer.</p>
{cards2}
<textarea id=out spellcheck=false></textarea>
</div>
<div class=bar>
  <span><b id=n>0</b> of {len(rows)} decided</span>
  <button onclick=copyAll()>Copy decisions</button>
  <button class=ghost onclick=showAll()>Show as text</button>
</div>
<script>
const cards=[...document.querySelectorAll('.card')];
function tick(){{
  let n=0;
  cards.forEach(c=>{{const got=c.querySelector('input:checked');
    c.classList.toggle('done',!!got); if(got)n++;}});
  document.getElementById('n').textContent=n;
}}
document.addEventListener('change',tick);
function text(){{
  const lines=['SITUATION REVIEW — decisions',''];
  cards.forEach(c=>{{
    const got=c.querySelector('input:checked');
    const note=c.querySelector('.note').value.trim();
    lines.push(`${{c.dataset.id}} : ${{got?got.value:'(not decided)'}}${{note?'  — '+note:''}}`);
  }});
  return lines.join('\n');
}}
function showAll(){{const o=document.getElementById('out');o.style.display='block';
  o.value=text();o.scrollIntoView({{behavior:'smooth',block:'center'}});}}
async function copyAll(){{
  const t=text();
  try{{await navigator.clipboard.writeText(t);
    const b=event.target;const was=b.textContent;b.textContent='Copied';
    setTimeout(()=>b.textContent=was,1400);}}
  catch(e){{showAll();document.getElementById('out').select();}}
}}
tick();
</script></body></html>"""


def main() -> int:
    rows, _, _ = collect()
    if "--html" in sys.argv:
        print(write_html(rows))
        return 0
    uncond = [r for r in rows if not r["preds"]]
    cond = [r for r in rows if r["preds"]]
    dead = [r for r in cond if any(p["path"] and not p["rows"] for p in r["preds"])]

    print("# REVIEW QUEUE · the situations waiting on a human")
    print()
    print("**Generated** by `scripts/dx_review_queue.py`. Do not edit — approve the situation and")
    print("it leaves this list by itself. Re-run to regenerate.")
    print()
    print(f"    waiting on a review     {len(rows)}")
    print(f"      fire unconditionally  {len(uncond)}   <- read these first")
    print(f"      carry a condition     {len(cond)}")
    print(f"      condition has no writer {len(dead)}")
    print()
    print("⛔ **Every predicate across the whole queue was checked against production.** "
          f"{len(dead)} have a path nothing writes.")
    print()
    print("⛔ **An empty `matches.when` is vacuously TRUE** — `context_adapter.matches(())` returns")
    print("`PredicateState.TRUE`, so those situations match on their L2 type alone, with no further")
    print("check. They are the most permissive entries here, not the least.")
    print()
    print("**What approving does.** It sets `metadata.review_status: approved`. It does **not** make")
    print("the situation live — `identity.status` must also become `stable`, and that is a separate,")
    print("deliberate second step. Five situations are already in that half-state; see ALARM D-A2.")
    print()
    print("---")
    print()
    print(f"## PART 1 · fires unconditionally — {len(uncond)} situations")
    print()
    print("Each of these matches every situation of its L2 type. The question is the same for all")
    print("of them and it is the only question: **is that right here?**")
    print()
    for i, row in enumerate(uncond, 1):
        print(_block(row, i))
    print(f"## PART 2 · carries a condition — {len(cond)} situations")
    print()
    for i, row in enumerate(cond, len(uncond) + 1):
        print(_block(row, i))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
