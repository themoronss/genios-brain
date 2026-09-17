"""Draft review — `POST /v1/moments/evaluate` with `draft_text` (SCREEN_INTEL_P4 §3.4).

Only when the org allows draft assist AND the seat turned it on (`effective_policy.draft_assist`).
The answer is a moment (`capability_id: moment.draft_review`) whose body is AT MOST TWO NOTES and
whose `evidence[]` says what each note rests on. It never proposes wording: there is no
replacement-text field in the response, notes that copy the draft are dropped, and the draft text
itself is NEVER stored — only its sha256 travels (evidence + dedupe key).

    still open         (deterministic) what this person is STILL waiting on — the seat's own open
                       screen follow-ups with them, ≤ 14 days old, that the draft does not
                       already cover. This is the one check that works for somebody GeniOS only
                       knows from the screen, so it runs with no graph subject and, when it is
                       alone, with no model call at all;
    stale-value check  (deterministic) the draft states a value the graph has since replaced
                       (`slice.recent_changes`, seat-visible, 90 d);
    critique           (only when a reasoned run exists for the subject; the seam's refusal —
                       its 409 — is caught and skipped) GeniOS's own read disagrees;
    one Haiku call     turns the facts + the two findings into ≤ 2 notes. No key / failure →
                       the deterministic notes alone.
HARD TIMEOUT 2.8 s for the whole review → None (the route answers 204). Never credit-charged (D6);
the model call's cost is recorded in `llm_costs` like every other call.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.logging import get_logger
from genios_engine.reason.moments.common import (VISIBLE_FACT_SQL, iso, parse_ts, text_of,
                                                 value_of, viewer_key)

_log = get_logger("genios.moments.draft")

CAPABILITY_ID = "moment.draft_review"
CAPABILITY_VERSION = "1"
TIMEOUT_S = 2.8
TTL_SECONDS = 600
MAX_NOTES = 2
NOTE_MAX_CHARS = 240
STALE_DAYS = 90
#: An open item older than this is not what they are writing about any more.
OWED_DAYS = 14
OWED_MAX = 2
#: Words too common to prove the draft covers an item.
_THIN = frozenset({"about", "after", "again", "been", "before", "being", "could", "from", "have",
                   "into", "just", "like", "more", "much", "need", "needs", "only", "over",
                   "please", "same", "send", "sent", "some", "soon", "that", "their", "them",
                   "then", "there", "these", "they", "this", "time", "very", "want", "wants",
                   "well", "were", "what", "when", "which", "will", "with", "would", "your"})
#: A note that repeats this many consecutive characters of the draft is rewriting it — dropped.
COPY_WINDOW = 40
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="draft-review")

_LABEL = {"deal.status": "the deal status", "deal.stage": "the deal stage",
          "deal.value": "the deal value", "deal.amount": "the deal amount",
          "deal.close_date": "the close date", "deal.owner": "the deal owner",
          "commitment.due_at": "the due date", "commitment.status": "the commitment",
          "commitment.owner": "the owner", "meeting.start_at": "the meeting time",
          "meeting.status": "the meeting", "meeting.title": "the meeting title",
          "person.title": "their title", "company.name": "the company name",
          "contract.status": "the contract status", "contract.end_date": "the contract end",
          "contract.value": "the contract value"}
_CONTEXT_FIELDS = ("commitment.text",)


def draft_digest(draft: str) -> str:
    return hashlib.sha256((draft or "").encode("utf-8")).hexdigest()


# ── reads ───────────────────────────────────────────────────────────────────────────────────────
def related_nodes(conn, *, org_id: str, subject_ids: list[str]) -> list[str]:
    """The subjects, their one-hop companies / deals / commitments / meetings, and those
    companies' deals. Two statements."""
    ids = list(dict.fromkeys(subject_ids))
    if not ids:
        return []
    hop = conn.execute(text(
        "select distinct x.nid, g.node_type from (select e.to_node_id as nid from graph_edges e "
        " where e.org_id = :o and e.from_node_id = any(:ids) and e.valid_to is null "
        " union select e.from_node_id from graph_edges e where e.org_id = :o "
        " and e.to_node_id = any(:ids) and e.valid_to is null) x "
        "join graph_nodes g on g.org_id = :o and g.node_id = x.nid and g.valid_to is null "
        "and g.node_type = any(array['company', 'deal', 'commitment', 'meeting'])"),
        {"o": org_id, "ids": ids}).fetchall()
    out = ids + [r.nid for r in hop]
    companies = [r.nid for r in hop if r.node_type == "company"]
    if companies:
        out += [r.nid for r in conn.execute(text(
            "select distinct x.nid from (select e.to_node_id as nid from graph_edges e "
            " where e.org_id = :o and e.from_node_id = any(:c) and e.valid_to is null "
            " union select e.from_node_id from graph_edges e where e.org_id = :o "
            " and e.to_node_id = any(:c) and e.valid_to is null) x "
            "join graph_nodes g on g.org_id = :o and g.node_id = x.nid and g.valid_to is null "
            "and g.node_type = 'deal'"), {"o": org_id, "c": companies})]
    return list(dict.fromkeys(out))


def current_facts(conn, *, org_id: str, node_ids: list[str], viewer: str | None,
                  limit: int = 30) -> list[dict]:
    from genios_engine.reason.moments.slice import CHANGE_FIELDS
    if not node_ids:
        return []
    rows = conn.execute(text(
        "select f.subject_node_id, f.field, f.value, n.display_name from graph_facts f "
        "left join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
        "and n.valid_to is null where f.org_id = :o and f.subject_node_id = any(:ids) "
        "and f.field = any(:fields) and f.valid_to is null and f.status = 'active' and "
        + VISIBLE_FACT_SQL + " order by (f.visibility_scope = 'private') desc, "
        "f.occurred_at desc nulls last limit :n"),
        {"o": org_id, "ids": node_ids, "fields": list(CHANGE_FIELDS) + list(_CONTEXT_FIELDS),
         "viewer": viewer, "n": limit * 2}).fetchall()
    out, seen = [], set()
    for r in rows:
        if (r.subject_node_id, r.field) in seen:
            continue
        seen.add((r.subject_node_id, r.field))
        out.append({"node_id": r.subject_node_id, "name": r.display_name, "field": r.field,
                    "value": plain(r.value)})
    return out[:limit]


# ── the three checks ────────────────────────────────────────────────────────────────────────────
def plain(raw) -> str | None:
    v = value_of(raw)
    if isinstance(v, dict) and "minor_units" in v:
        try:
            return f"{v.get('currency') or ''} {int(v['minor_units']) / 100:,.0f}".strip()
        except (TypeError, ValueError):
            return None
    return text_of(v)


def mentions(haystack_casefolded: str, value: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(value.casefold()) + r"(?!\w)",
                     haystack_casefolded) is not None


def stale_notes(changes: list[dict], draft: str) -> list[dict]:
    """The draft states a value that has since been replaced, and not the new one."""
    low = (draft or "").casefold()
    notes = []
    for ch in changes:
        old_t, new_t = plain(ch.get("old")), plain(ch.get("new"))
        if not old_t or not new_t or len(old_t) < 3 or parse_ts(old_t) is not None:
            continue
        if not mentions(low, old_t) or mentions(low, new_t):
            continue
        when = (ch.get("changed_at") or "")[:10]
        notes.append({"text": f"Your draft says “{old_t}”, but {_LABEL.get(ch['field'], ch['field'])}"
                              f" changed to “{new_t}”" + (f" on {when}" if when else "") + ".",
                      "evidence": [{"kind": "fact_change", **{k: ch.get(k) for k in (
                          "node_id", "field", "old", "new", "changed_at")}}],
                      "source": "stale"})
    return notes


def name_key(s: str | None) -> str:
    """"Priya Shah (Acme)" / "Shah, Priya" → "priya shah" / "shah" — the name part, lower case."""
    return " ".join((s or "").split("(")[0].split(",")[0].split()).casefold()


def same_person(a: str, b: str) -> bool:
    """Same name, or one is the other's leading word(s) ("priya" ~ "priya shah")."""
    if len(a) < 2 or len(b) < 2:
        return False
    lead = lambda long, short: long.startswith(short + " ")      # noqa: E731
    return a == b or lead(a, b) or lead(b, a)


def covered(draft: str, *parts: str | None) -> bool:
    """Does the draft already say this? Half of an item's own words being in the draft is enough
    — the manager writing "quote bhej raha hoon" has covered "send the revised quote"."""
    low = (draft or "").casefold()
    words = {w for part in parts for w in re.findall(r"[a-z0-9]{4,}", (part or "").casefold())
             if w not in _THIN}
    if not words:
        return False
    hit = sum(1 for w in words if w in low)
    return hit * 2 >= len(words)


def owed_notes(conn, *, org_id: str, seat_id: str | None, names: list[str], draft: str,
               now: datetime) -> list[dict]:
    """What the person being written to is still waiting on. The manager knows what they meant to
    write; what they forget is the thing from three days ago — so this is the note worth making."""
    keys = [k for k in (name_key(n) for n in names) if len(k) >= 2]
    if not seat_id or not keys:
        return []
    rows = conn.execute(text(
        "select kind, text, who, due_at, created_at from screen_followups "
        "where org_id = :o and seat_id = :s and resolved_at is null and who is not null "
        "and kind in ('ask', 'my_promise', 'their_promise') "
        "and created_at > :since order by created_at desc limit 20"),
        {"o": org_id, "s": seat_id, "since": now - timedelta(days=OWED_DAYS)}).fetchall()
    notes = []
    for r in rows:
        who = name_key(r.who)
        if not any(same_person(who, k) for k in keys) or covered(draft, r.text):
            continue
        first = (r.who or "").split("(")[0].split(",")[0].strip().split(" ")[0]
        asked = iso(r.created_at)[:10] if r.created_at else None
        due = iso(r.due_at)[:10] if r.due_at else None
        lead = {"ask": f"{first} asked for this and it is still open",
                "my_promise": f"you promised {first} this",
                "their_promise": f"{first} promised you this"}[r.kind]
        when = f" (due {due})" if due else (f" (since {asked})" if asked else "")
        notes.append({"text": f"Not in the draft: {r.text} — {lead}{when}.",
                      "source": "owed",
                      "evidence": [{"kind": "followup", "followup_kind": r.kind, "who": r.who,
                                    "text": r.text, "created_at": asked, "due_at": due}]})
        if len(notes) >= OWED_MAX:
            break
    return notes


def critique_notes(engine, *, org_id: str, subject_ids: list[str], draft: str,
                   digest: str) -> list[dict]:
    """GeniOS's own read of the subject disagrees with sending this. Only when the tenant has the
    critique seam activated AND a reasoned run exists; a refusal (the seam's 409) is skipped."""
    from genios_engine.platform import l4_activation
    if not l4_activation.is_l4_activated(engine, org_id, l4_activation.FEATURE_CRITIQUE):
        return []
    from genios_engine.contracts.reasoning import MAX_EXTERNAL_DRAFT_CHARS, ExternalCandidate
    from genios_engine.reason import critique as CR
    from genios_engine.reason.store import ReasoningStore
    for sid in subject_ids[:2]:
        run_id = CR.latest_reasoned_run(engine, org_id=org_id, target_ref=sid)
        if run_id is None:
            continue
        try:
            outcome = CR.critique_target(
                store=ReasoningStore(engine=engine), org_id=org_id,
                proposal=ExternalCandidate(proposal_id=f"draft_{digest[:16]}",
                                           agent_id="genios.draft_review", kind="email_draft",
                                           draft=draft[:MAX_EXTERNAL_DRAFT_CHARS], params={},
                                           target_ref=sid))
        except CR.CritiqueRefused:
            continue                      # 409 at the seam: no run it can answer from
        except (TypeError, ValueError):
            continue
        v = outcome.verdict
        if v.verdict == CR.PROCEED or not str(v.rationale or "").strip():
            continue
        first = re.split(r"(?<=[.!?])\s", str(v.rationale).strip(), maxsplit=1)[0]
        return [{"text": first, "source": "critique",
                 "evidence": [{"kind": "critique", "node_id": sid, "verdict": v.verdict,
                               "run_id": run_id}]}]
    return []


_PROMPT = """You check an email/chat DRAFT against what the sender's company knows. You never
rewrite the draft and never suggest replacement wording.

FACTS (current, id: subject · field = value):
{facts}

FINDINGS ALREADY MADE (may be empty):
{findings}

DRAFT (sha256 {digest}):
<<<
{draft}
>>>

Return JSON only: {{"notes": [{{"text": "...", "facts": ["F1"]}}]}}
Rules: at most 2 notes; each ≤ 25 words, a plain observation a colleague would make ("The deal is
marked lost since 12 Sep."), citing the fact ids it rests on; include a finding only if it matters;
no quoting the draft back; if nothing is wrong return {{"notes": []}}."""


def llm_notes(engine, *, org_id: str, facts: list[dict], findings: list[dict], draft: str,
              digest: str, deadline: float) -> list[dict] | None:
    """One Haiku call. None when no model is configured, time is short, or the call failed."""
    from genios_engine.platform.config import get_settings
    settings = get_settings()
    remaining = deadline - time.monotonic() - 0.15
    if (not getattr(settings, "use_real_llm", False) or not settings.anthropic_api_key
            or remaining < 0.5):
        return None
    from anthropic import Anthropic

    from genios_engine.reason.llm_sites import tier_model
    model = tier_model("T1")
    ids = {f"F{i + 1}": f for i, f in enumerate(facts)}
    prompt = _PROMPT.format(
        facts="\n".join(f"{k}: {f.get('name') or f['node_id']} · {f['field']} = {f['value']}"
                        for k, f in ids.items()) or "(none)",
        findings="\n".join("- " + n["text"] for n in findings) or "(none)",
        digest=digest[:12], draft=draft[:6000])
    try:
        client = Anthropic(api_key=settings.anthropic_api_key, timeout=remaining, max_retries=0)
        resp = client.messages.create(model=model, max_tokens=300, temperature=0,
                                      messages=[{"role": "user", "content": prompt}])
    except Exception:      # noqa: BLE001 — timeout / transport: the deterministic notes stand
        _log.info("draft review: model call failed or timed out org=%s", org_id)
        return None
    usage = getattr(resp, "usage", None)
    try:
        from genios_engine.context.graph_store import GraphStore
        GraphStore(engine=engine).record_cost(
            org_id=org_id, model=model, purpose="moment.draft_review",
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0))
    except Exception:      # noqa: BLE001 — cost bookkeeping never fails the review
        _log.exception("draft review: cost record failed")
    raw = "".join(getattr(b, "text", "") for b in resp.content
                  if getattr(b, "type", None) == "text").strip()
    from genios_engine.context.llm.parse import parse_json_lenient, strip_code_fence
    parsed = parse_json_lenient(strip_code_fence(raw)) or {}
    out = []
    for n in (parsed.get("notes") or [])[:MAX_NOTES]:
        if not isinstance(n, dict) or not str(n.get("text") or "").strip():
            continue
        cited = [ids[k] for k in (n.get("facts") or []) if isinstance(k, str) and k in ids]
        out.append({"text": str(n["text"]).strip(), "source": "model",
                    "evidence": [{"kind": "fact", "node_id": f["node_id"], "field": f["field"],
                                  "value": f["value"]} for f in cited]})
    return out


# ── assembly ────────────────────────────────────────────────────────────────────────────────────
def copies_draft(note: str, draft: str) -> bool:
    """A note that repeats the draft (or a COPY_WINDOW-character run of it) is rewriting it."""
    d, n = " ".join((draft or "").split()).casefold(), " ".join((note or "").split()).casefold()
    if not d:
        return False
    if len(d) < COPY_WINDOW:
        return len(d) >= 12 and d in n
    return any(d[i:i + COPY_WINDOW] in n for i in range(0, len(d) - COPY_WINDOW + 1, 10))


def finalize(candidates: list[dict], draft: str) -> list[dict]:
    out, seen = [], set()
    for n in candidates:
        t = " ".join(str(n.get("text") or "").split())[:NOTE_MAX_CHARS]
        if not t or t.casefold() in seen or copies_draft(t, draft):
            continue
        seen.add(t.casefold())
        out.append({"text": t, "evidence": list(n.get("evidence") or []),
                    "source": n.get("source")})
        if len(out) >= MAX_NOTES:
            break
    return out


def moment_content(notes: list[dict], *, digest: str) -> dict:
    """The §6.2 moment. Keys are exactly the moment keys — there is no field that carries text
    to put into the draft."""
    evidence = [e for n in notes for e in n["evidence"]][:18]
    evidence.append({"kind": "draft", "sha256": digest})
    return {"kind": "advice", "priority": "normal", "headline": "Before you send",
            "body": "\n".join("• " + n["text"] for n in notes), "actions": [],
            "evidence": evidence, "ttl_seconds": TTL_SECONDS, "capability_id": CAPABILITY_ID,
            "capability_version": CAPABILITY_VERSION}


def _compute(engine, *, org_id: str, email: str | None, participants, entities, draft: str,
             now: datetime, deadline: float, seat_id: str | None = None) -> dict | None:
    from genios_engine.reason.moments import recall as R
    from genios_engine.reason.moments.slice import recent_changes
    digest = draft_digest(draft)
    viewer = viewer_key(email)
    names = [n for n in ([getattr(pp, "name", None) for pp in (participants or [])]
                         + list(entities or [])) if isinstance(n, str) and n.strip()]
    stale: list[dict] = []
    facts: list[dict] = []
    with engine.connect() as c:
        subjects, _me = R.resolve(c, org_id=org_id, participants=participants,
                                  entities=entities, seat_email=email)
        sids = [s.node_id for s in subjects[:3]]
        # The person may be known only from the screen, so this one does not need the graph.
        owed = owed_notes(c, org_id=org_id, seat_id=seat_id, names=names, draft=draft, now=now)
        if not sids and not owed:
            return None
        if sids:
            nodes = related_nodes(c, org_id=org_id, subject_ids=sids)
            stale = stale_notes(recent_changes(c, org_id=org_id, node_ids=nodes, viewer=viewer,
                                               now=now, days=STALE_DAYS), draft)
            facts = current_facts(c, org_id=org_id, node_ids=nodes, viewer=viewer)
    crit = []
    if sids and time.monotonic() < deadline - 1.0:
        try:
            crit = critique_notes(engine, org_id=org_id, subject_ids=sids, draft=draft,
                                  digest=digest)
        except Exception:      # noqa: BLE001 — a critique failure costs a note, never the review
            _log.exception("draft review: critique sub-check failed org=%s", org_id)
    graph = stale + crit
    # ROUTER CHECK 5, HERE TOO: with nothing but open items and no facts to weigh them against,
    # the sentence is already written and a model call would only rephrase it. Pay for nothing.
    model = (llm_notes(engine, org_id=org_id, facts=facts, findings=owed + graph, draft=draft,
                       digest=digest, deadline=deadline) if facts or graph else None)
    # An open item is a fact about this person, not an opinion — the model never drops it.
    notes = finalize(owed + ((model or []) or graph), draft)
    if not notes:
        return None
    return {"subject_ids": sids, "content": moment_content(notes, digest=digest)}


def review(engine, *, org_id: str, email: str | None, participants, entities, draft: str,
           now: datetime | None = None, timeout_s: float = TIMEOUT_S,
           seat_id: str | None = None) -> dict | None:
    """`{"subject_ids", "content"}` or None (nothing to say, or the 2.8 s budget ran out)."""
    now = now or datetime.now(timezone.utc)
    deadline = time.monotonic() + timeout_s
    fut = _POOL.submit(_compute, engine, org_id=org_id, email=email, participants=participants,
                       entities=entities, draft=draft, now=now, deadline=deadline,
                       seat_id=seat_id)
    try:
        return fut.result(timeout=max(0.0, deadline - time.monotonic()))
    except FutureTimeout:
        _log.info("draft review timed out org=%s", org_id)
        return None
    except Exception:      # noqa: BLE001 — a failed review is silence (204), never an error
        _log.exception("draft review failed org=%s", org_id)
        return None


__all__ = ["CAPABILITY_ID", "CAPABILITY_VERSION", "TIMEOUT_S", "copies_draft", "covered",
           "draft_digest", "finalize", "moment_content", "owed_notes", "review", "stale_notes"]
