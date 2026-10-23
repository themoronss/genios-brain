"""C1 · the card writer — one checked model call per new card version (GeniOS-011 S34.U3).

`speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md` §5 C1 and `02-CARD-DEFINITION.md` §2–§3, Rohit's binding card
contract: the subject is an action (verb first, about ten words, names the person or the thing, never a cut
sentence or a placeholder); under it one or two lines say what to do and how; every field is this card's own and
one or two lines long; every claim points to its source; following the steps leads to the stated result. Today
five writers make a headline (`card_builder.gold_headline`'s cut of the move, the formula renderer, the question,
`executive_bridge`, the P4 team cards) and none of them can write the result, the steps or the goal a card moves —
which is why "what doing it gets you" is a stock line, the steps are stock or empty, and the goal is never served.

WHAT IT DOES. After a card is built (`card_builder.build_draft`), rendered (`render.render_copy` /
`render.review_copy`), passed by the card contract and written — inserted, refreshed or versioned
(`deliver/pipeline.build_cards_for_org`) — this module:

  1. lays out the card's OWN facts, each with an id (`card_facts`): the quotes the recipient may see
     (`quote:N`), the gold lines the expert's check held (`line:*`, `reason/expert/decide._render`), the card's
     own fields (`card:*`), the typed graph facts it was built from (`fact:*`), and the company brief's ACCEPTED
     goals (their `cbl_…` line ids). Nothing from another card, and no stock sentence (`DO_NOTHING_WITHHELD`);
  2. asks ONE model call (`reason/bundle/sites.SITE_CARD_COPY`, R-10) through the one gate
     (`reason/llm_sites.run_site` → `reason/bundle/gate.RSiteGate`): the tenant's switch (`card_copy`, off by
     default), its own day and per-call ceiling (`reason/bundle/budget.OWN_BUDGETS`), the generation cache, thinking
     off, one repair on syntax only, a cut answer never parsed — and every outcome on `l4_r_site_calls`;
  3. holds every sentence to the facts it names (`check_copy`): each id must be one the card holds, and the
     sentence must say nothing those facts do not (`deliver/claim_validator.claims_ok`, the renderer's own V-02
     rule, run over the CITED facts alone). **A sentence that rests on nothing is dropped, never shipped**, and the
     reason is kept beside the copy (`dropped`);
  4. stores what stands in `cards.copy` (migration 0252) for the version it was written for
     (`deliver/store.CardStore.set_copy`). A version or a refresh clears it in the same statement that rewrites
     the card's words, so a copy never shows over words it was not written from.

WHERE THE MODEL CALL LIVES. `00-ARCHITECTURE.md` "The layers": L5 Delivery may hold a model for "wording only,
validated", and "never adds a fact". This module writes words and nothing else — no score, lane, recipient,
permission or deadline is the model's — and the check is what makes "never adds a fact" true of them. The call
itself goes through the bundle package's one gate, which every R-site uses
(`tests/test_rule3_model_sites_stay_in_their_layer.py`).

ONE CALL PER NEW CARD VERSION, NEVER PER VIEW. The only engine module that imports this one is the card pass; no
read (`CardStore.queue`, `get_authoritative_card`, the API) calls it — they serve what it stored. The cache key is
the card's subject (its file, else its signal) and the digest of its facts, so a version whose facts did not move
is answered from the record at no cost, and new facts are one new call.

FAILS CLOSED. Switched off, no model configured, over budget, a cut, unparseable or misshapen answer, nothing that
stands, a store that refuses — every one of them writes no copy, and the card shows today's fields. Nothing here
raises into the card pass: a copy failure costs the copy, never the card.

THE LIVE PROBE IS NOT RUN HERE. Claude 5 models think by default and spend thinking from `max_tokens`; the site asks
with thinking off and its 1,600-token ceiling is `[MODELLED]`. `scripts/card_copy_probe.py` makes one or two live
calls on invented cards and prints the token counts — run only on Rohit's yes to spend.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from genios_engine.platform.canonical import semantic_hash
from genios_engine.platform.grounding import _digit_runs
from genios_engine.platform.grounding import _expand_dates
from genios_engine.platform.l4_activation import FEATURE_CARD_COPY
from genios_engine.platform.logging import get_logger
from genios_engine.reason.bundle.gate import MALFORMED
from genios_engine.reason.bundle.gate import REPAIR_SYNTAX
from genios_engine.reason.bundle.sites import SITE_CARD_COPY
from genios_engine.reason.llm_sites import SiteRejection
from genios_engine.reason.llm_sites import make_site_client
from genios_engine.reason.llm_sites import run_site
from genios_engine.reason.llm_sites import with_correction

_log = get_logger("genios.deliver.card_copy")

#: Bumped whenever the prompt or the check changes: it is inside the cache key, so an answer written under an old
#: prompt or held by an old check is never served for the new one.
COPY_VERSION = "card_copy.v1"

#: The sentences the writer is asked for, in the order the opened card shows them (`02-CARD-DEFINITION.md` §3).
#: `steps` is a list and `goal` an object; both are checked like these.
SENTENCE_FIELDS: tuple[str, ...] = ("subject", "summary", "how", "result", "avoid", "done_when", "if_not",
                                    "alternative")
FIELDS: tuple[str, ...] = (*SENTENCE_FIELDS, "steps", "goal")

#: Characters per field. The subject is the card's face, so it is the headline's own cap (`render.HEADLINE_CAP`);
#: the two lines are two lines; the rest are one line, two at most (§2.3).
CAPS: dict[str, int] = {"subject": 60, "summary": 240, "how": 200, "result": 200, "avoid": 200,
                        "done_when": 200, "if_not": 200, "alternative": 200}
STEP_CAP = 160
#: "2–4 steps" (01-INTEGRATION §5 C1): a fifth is dropped, said.
MAX_STEPS = 4
#: "about ten words at most" (§2.1).
SUBJECT_MAX_WORDS = 10
#: How a card relates to the goal it names (01-INTEGRATION §5 C1, `goal.how`).
GOAL_HOW: tuple[str, ...] = ("advances", "threatens", "depends_on")

#: The fact table's bounds: what the per-call ceiling (`OWN_BUDGETS`) is sized for.
MAX_FACTS = 40
FACT_CHARS = 400
MAX_QUOTES = 8

#: A placeholder, an elision or an unfilled slot: a sentence carrying one was not finished (§2.1, "…to body").
_PLACEHOLDER = re.compile(r"[{}<>]|…|\.\.\.|\b(?:TBD|TODO|N/A)\b")

#: Why a sentence was dropped — the vocabulary `cards.copy.dropped` is written in.
NOTHING = "rests_on_nothing"
UNKNOWN = "rests_on_unknown"
OVER_CAP = "over_cap"
PLACEHOLDER = "placeholder"
CUT = "cut_sentence"
OVER_TEN = "over_ten_words"
OVER_FOUR = "over_four"
NOT_A_GOAL = "not_an_accepted_goal"
HOW_UNKNOWN = "how_unknown"
NOT_ITS_GOAL = "does_not_rest_on_its_goal"
#: The refusal when not one sentence stands: a substance refusal, so the gate does not ask again.
NOTHING_STANDS = "nothing_stands"


@dataclass(frozen=True, slots=True)
class Fact:
    """One thing the card holds, with the id a sentence names it by."""

    id: str
    kind: str                       # quote · line · card · fact · goal
    text: str
    source: Mapping[str, Any] = field(default_factory=dict)


# ── 1 · the card's own facts ─────────────────────────────────────────────────────────────────

def _plain(value: Any) -> str:
    if isinstance(value, Mapping) and "value" in value:
        value = value.get("value")
    if value is None or value == "" or value == [] or value == {}:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    return " ".join(text.split())


def _gold(signal: Mapping[str, Any] | None) -> Mapping[str, Any]:
    render = (signal or {}).get("capability_render")
    gold = render.get("gold") if isinstance(render, Mapping) else None
    return gold if isinstance(gold, Mapping) else {}


def _goal_lines(goals: Sequence[Any]) -> list[tuple[str, str]]:
    """(line id, words) of the company brief's accepted GOALS — a `CompanyBriefLine` or its mapping."""
    out = []
    for goal in goals or ():
        get = goal.get if isinstance(goal, Mapping) else (lambda k, g=goal: getattr(g, k, None))
        section = get("section")
        if section not in (None, "goals"):
            continue
        line_id, words = str(get("line_id") or "").strip(), _plain(get("text"))
        if line_id and words:
            out.append((line_id, words))
    return out


def card_facts(card: Mapping[str, Any], copy: Mapping[str, Any], signal: Mapping[str, Any] | None = None, *,
               goals: Sequence[Any] = ()) -> tuple[Fact, ...]:
    """Everything this card holds that a sentence may rest on, each with its id — this card's and nothing else.

    The quotes are the RECIPIENT'S (`build_draft` narrowed them, `_quotes`); the gold lines are the ones the
    expert's check let stand; the withheld do-nothing line is a stock sentence and is left out. Bounded
    (`MAX_FACTS` × `FACT_CHARS`, `MAX_QUOTES`), the accepted goals after the bound so a long card cannot crowd
    them out."""
    from genios_engine.reason.expert.decide import DO_NOTHING_WITHHELD

    out: list[Fact] = []
    seen: set[str] = set()

    def add(fid: str, kind: str, value: Any, **source: Any) -> None:
        text = _plain(value)
        if not text or fid in seen or text == DO_NOTHING_WITHHELD:
            return
        seen.add(fid)
        out.append(Fact(fid, kind, text[:FACT_CHARS], {k: v for k, v in source.items() if v}))

    for i, quote in enumerate(list(card.get("_quotes") or ())[:MAX_QUOTES], 1):
        if isinstance(quote, Mapping):
            add(f"quote:{i}", "quote", quote.get("quote"), event_id=quote.get("event_id"),
                name=quote.get("name"), author=quote.get("author"))
    gold = _gold(signal)
    for key in ("subject", "company", "kind_of_work", "role", "why_now", "alternative", "wait_or_stop",
                # C2 (S34.U2) carries the expert's checked result and done-when on the gold block; read when there.
                "act", "done_when"):
        add(f"line:{key}", "line", gold.get(key))
    for i, remains in enumerate(gold.get("what_remains") or (), 1):
        add(f"line:remains.{i}", "line", remains)
    recommended = gold.get("recommended") if isinstance(gold.get("recommended"), Mapping) else \
        (card.get("recommended") if isinstance(card.get("recommended"), Mapping) else {})
    add("line:move", "line", recommended.get("what"))
    add("line:for_whom", "line", recommended.get("for_whom"))
    add("line:to", "line", recommended.get("to"))
    add("line:by_when", "line", recommended.get("by_when"))
    window = gold.get("window") if isinstance(gold.get("window"), Mapping) else {}
    if window.get("days"):
        add("line:window", "line", f"{window['days']} days — {window.get('said') or 'the window'}")
    add("card:situation", "card", copy.get("situation"))
    for key in ("business_subject", "relationship_role", "unresolved_item", "why_now", "success_signal",
                "do_nothing_consequence", "alternative", "wait_or_stop"):
        add(f"card:{key}", "card", card.get(key))
    if card.get("outcome_window_days"):
        add("card:window_days", "card", f"{card['outcome_window_days']} days")
    for name, value in sorted((card.get("_facts") or {}).items()):
        words = _plain(value)
        if words:
            add(f"fact:{name}", "fact", f"{str(name).replace('.', ' ').replace('_', ' ')}: {words}")
    bounded = out[:MAX_FACTS]
    for line_id, words in _goal_lines(goals):
        if line_id not in seen:
            seen.add(line_id)
            bounded.append(Fact(line_id, "goal", words[:FACT_CHARS], {}))
    return tuple(bounded)


# ── 2 · the prompt ───────────────────────────────────────────────────────────────────────────

def build_prompt(facts: Sequence[Fact]) -> str:
    """The one prompt: the card's facts by id, the shape asked for, and the one rule — rest every sentence on
    the ids it uses. Never the tenant's own addresses (they ground a sentence; they are not a fact about it)."""
    held = [f for f in facts if f.kind != "goal"]
    goals = [f for f in facts if f.kind == "goal"]
    lines = "\n".join(f"[{f.id}] ({f.kind}) {f.text}" for f in held)
    goal_lines = "\n".join(f"[{f.id}] {f.text}" for f in goals) or "(none accepted)"
    return (
        "You are the founder's chief of staff, writing the words of ONE card for them to act on. Write to the "
        "founder as \"you\". Use ONLY the facts below. Each fact has an id in brackets. Every sentence you write "
        "names, in \"rests_on\", the ids of the facts it uses — a sentence that rests on no fact, or names "
        "anything its facts do not (a person, a company, a number, a date), is thrown away. Write null for a "
        "field the facts do not support.\n\n"
        f"THE CARD'S FACTS\n{lines}\n\n"
        f"THE COMPANY'S ACCEPTED GOALS\n{goal_lines}\n\n"
        "Return exactly one JSON object and nothing else:\n"
        '{"subject": {"text": "the action: starts with a verb, at most 10 words, names the person or thing, '
        "at most " + str(CAPS["subject"]) + ' characters", "rests_on": ["ids"]},\n'
        ' "summary": {"text": "one or two lines: what to do and how", "rests_on": ["ids"]},\n'
        ' "how": {"text": "how to do it, one line", "rests_on": ["ids"]},\n'
        ' "steps": [{"text": "one step", "rests_on": ["ids"]}],\n'
        ' "result": {"text": "what doing it gets you", "rests_on": ["ids"]},\n'
        ' "avoid": {"text": "what to avoid", "rests_on": ["ids"]},\n'
        ' "done_when": {"text": "what done looks like", "rests_on": ["ids"]},\n'
        ' "if_not": {"text": "what happens if it is not done", "rests_on": ["ids"]},\n'
        ' "alternative": {"text": "what to do if it cannot be done", "rests_on": ["ids"]},\n'
        ' "goal": {"line_id": "one accepted goal id", "how": "advances | threatens | depends_on", '
        '"why": "one line", "rests_on": ["the goal id and the ids it uses"]} or null}\n'
        f"Two to {MAX_STEPS} steps. Each field one line, two at most, about THIS card only — no sentence that "
        "would read the same on another card."
    )


# ── 3 · the check ────────────────────────────────────────────────────────────────────────────

def _corpus_of(cited: Sequence[Fact], identities: Sequence[str]) -> tuple[str, set[str]]:
    """What a sentence may say: the facts IT names, the quotes' speakers, and the tenant's own names — the
    renderer's corpus rule (`render._corpus`), narrowed to the citation."""
    parts: list[str] = [str(i) for i in identities if i]
    for fact in cited:
        parts.append(fact.text)
        parts.extend(_expand_dates(fact.text))
        parts.extend(str(fact.source[k]) for k in ("name", "author") if fact.source.get(k))
    nums: set[str] = set()
    for part in parts:
        nums |= _digit_runs(part)
    return " ".join(parts).lower(), nums


def _ids(entry: Mapping[str, Any]) -> tuple[str, ...]:
    raw = entry.get("rests_on")
    if not isinstance(raw, list):
        return ()
    return tuple(dict.fromkeys(str(i).strip() for i in raw if isinstance(i, str) and i.strip()))


def _sentence(entry: Any, name: str, by_id: Mapping[str, Fact], identities: Sequence[str], *, cap: int,
              subject: bool = False) -> tuple[str | None, tuple[str, ...], str | None]:
    """(text, ids, None) when the sentence stands; (None, (), why) when it is dropped; (None, (), None) when the
    model wrote none. A value that is not the shape asked for is a refusal the gate repairs once."""
    from genios_engine.deliver.card_builder import FUNCTION_WORDS
    from genios_engine.deliver.claim_validator import claims_ok

    if entry is None:
        return None, (), None
    if not isinstance(entry, Mapping):
        raise SiteRejection(MALFORMED, f'"{name}" must be {{"text": …, "rests_on": [ids]}} or null')
    text = " ".join(str(entry.get("text") or "").split())
    if not text:
        return None, (), None
    ids = _ids(entry)
    if not ids:
        return None, (), NOTHING
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        return None, (), f"{UNKNOWN}:{unknown[0]}"
    if _PLACEHOLDER.search(text):
        return None, (), PLACEHOLDER
    if subject:
        words = text.rstrip(".!").split()
        if len(words) > SUBJECT_MAX_WORDS:
            return None, (), OVER_TEN
        if words[-1].lower().strip(",;:—–'\"") in FUNCTION_WORDS:
            return None, (), CUT
    if len(text) > cap:
        return None, (), f"{OVER_CAP}:{len(text)}"
    cited = [by_id[i] for i in ids]
    corpus, nums = _corpus_of(cited, identities)
    ok, why, _refusals = claims_ok(text, corpus, nums, quotes_something=any(f.kind == "quote" for f in cited))
    if not ok:
        return None, (), f"claim:{why}"
    return text, ids, None


def check_copy(payload: Mapping[str, Any], facts: Sequence[Fact], *,
               identities: Sequence[str] = ()) -> dict[str, Any]:
    """The answer, held sentence by sentence to the facts each one names. What stands is kept with its ids; what
    does not is dropped with its reason. Raises `SiteRejection` — `MALFORMED` for a shape not asked for (repaired
    once), `NOTHING_STANDS` when not one sentence stands (a refusal on substance: no copy)."""
    if not isinstance(payload, Mapping):
        raise SiteRejection(MALFORMED, "the answer must be one JSON object")
    by_id = {f.id: f for f in facts}
    goal_ids = {f.id for f in facts if f.kind == "goal"}
    out: dict[str, Any] = {"copy_version": COPY_VERSION}
    rests_on: dict[str, Any] = {}
    dropped: dict[str, Any] = {}

    for name in SENTENCE_FIELDS:
        text, ids, why = _sentence(payload.get(name), name, by_id, identities, cap=CAPS[name],
                                   subject=name == "subject")
        out[name] = text
        if text is not None:
            rests_on[name] = list(ids)
        elif why:
            dropped[name] = why

    steps = payload.get("steps")
    if steps is not None and not isinstance(steps, list):
        raise SiteRejection(MALFORMED, '"steps" must be a list of {"text": …, "rests_on": [ids]}')
    kept: list[str] = []
    kept_ids: list[list[str]] = []
    step_drops: dict[str, str] = {}
    for n, entry in enumerate(steps or (), 1):
        if n > MAX_STEPS:
            step_drops[str(n)] = OVER_FOUR
            continue
        text, ids, why = _sentence(entry, f"steps[{n}]", by_id, identities, cap=STEP_CAP)
        if text is not None:
            kept.append(text)
            kept_ids.append(list(ids))
        elif why:
            step_drops[str(n)] = why
    out["steps"] = kept
    if kept:
        rests_on["steps"] = kept_ids
    if step_drops:
        dropped["steps"] = step_drops

    goal, why = _goal(payload.get("goal"), by_id, goal_ids, identities)
    out["goal"] = goal
    if goal is not None:
        rests_on["goal"] = list(_ids(payload["goal"]))
    elif why:
        dropped["goal"] = why

    if not any(out[name] for name in SENTENCE_FIELDS) and not kept and goal is None:
        raise SiteRejection(NOTHING_STANDS, json.dumps(dropped, sort_keys=True)[:300])
    out["rests_on"] = rests_on
    out["dropped"] = dropped
    cited: set[str] = set()
    for name, ids in rests_on.items():
        cited.update(i for row in ids for i in row) if name == "steps" else cited.update(ids)
    # Where each cited fact came from, so a reader can show the source beside the sentence (§2.4).
    out["sources"] = {i: {"kind": by_id[i].kind, **({"event_id": by_id[i].source["event_id"]}
                                                    if by_id[i].source.get("event_id") else {})}
                      for i in sorted(cited)}
    return out


def _goal(entry: Any, by_id: Mapping[str, Fact], goal_ids: set[str],
          identities: Sequence[str]) -> tuple[dict[str, str] | None, str | None]:
    """The goal the card moves: one the company brief ACCEPTED, how it moves it, and a line resting on it."""
    if entry is None:
        return None, None               # none named: the card reads "Not linked to a goal yet" (§2.5)
    if not isinstance(entry, Mapping):
        raise SiteRejection(MALFORMED, '"goal" must be {"line_id", "how", "why", "rests_on"} or null')
    line_id = str(entry.get("line_id") or "").strip()
    if line_id not in goal_ids:
        return None, NOT_A_GOAL
    how = str(entry.get("how") or "").strip()
    if how not in GOAL_HOW:
        return None, HOW_UNKNOWN
    why_text, ids, why = _sentence({"text": entry.get("why"), "rests_on": entry.get("rests_on")}, "goal",
                                   by_id, identities, cap=CAPS["result"])
    if why_text is None:
        return None, why or NOTHING
    if line_id not in ids:
        return None, NOT_ITS_GOAL
    return {"line_id": line_id, "how": how, "why": why_text}, None


# ── 4 · the writer ───────────────────────────────────────────────────────────────────────────

class CopyWriter:
    """One tenant's card writer for one card pass: one gate (its switch read once, its budget advancing in
    process), one cache, the tenant's own names and the brief's accepted goals read once."""

    def __init__(self, *, org_id: str, gate: Any, cache: Any = None, identities: Sequence[str] = (),
                 goals: Sequence[Any] = ()) -> None:
        self.org_id = org_id
        self._gate = gate
        self._cache = cache
        self._identities = tuple(identities)
        self._goals = tuple(goals)
        #: The last consult's receipt (`reason/llm_sites.SiteReceipt`): what happened, for a caller or a test.
        self.last_receipt: Any = None

    @classmethod
    def for_pass(cls, *, graph: Any, org_id: str, activated: frozenset[str], eval_time: Any,
                 identities: Sequence[str] = (), client: Any = None, cache: Any = None) -> CopyWriter | None:
        """The writer for a card pass, or None when the tenant's switch is off — then nothing is built, read or
        spent. Never raises: a writer that cannot be built is a pass with today's fields."""
        if FEATURE_CARD_COPY not in activated:
            return None
        try:
            from genios_engine.reason.bundle.budget import NarrativeBudget
            from genios_engine.reason.bundle.gate import RSiteGate
            from genios_engine.reason.bundle.sites import tier_for
            from genios_engine.reason.bundle.store import BundleStore
            from genios_engine.reason.llm_sites import PostgresSiteCache

            engine = getattr(graph, "engine", None)
            client = client if client is not None else make_site_client(tier_for(SITE_CARD_COPY))
            gate = RSiteGate(org_id=org_id, engine=engine, client=client,
                             store=BundleStore(engine) if engine is not None else None,
                             budget=NarrativeBudget.for_site(SITE_CARD_COPY, org_id=org_id, engine=engine,
                                                             now=eval_time),
                             activated=activated, cost_recorder=getattr(graph, "record_cost", None),
                             eval_time=eval_time)
            return cls(org_id=org_id, gate=gate,
                       cache=cache if cache is not None else (PostgresSiteCache(engine) if engine is not None
                                                              else None),
                       identities=identities, goals=_accepted_goals(engine, org_id, eval_time))
        except Exception:      # noqa: BLE001 — no writer is today's fields, never a failed pass
            _log.exception("could not build the card writer for org=%s — cards keep today's fields", org_id)
            return None

    def write(self, card_store: Any, *, card_id: str, version: int | None, card: Mapping[str, Any],
              copy: Mapping[str, Any], signal: Mapping[str, Any] | None) -> dict[str, Any] | None:
        """Word one new card version, check it, store what stands. Returns the stored copy, or None (no copy:
        the card shows today's fields). Never raises."""
        try:
            facts = card_facts(card, copy, signal, goals=self._goals)
            subject = str(card.get("file_id") or card.get("signal_id") or card_id)
            seed = {"copy": COPY_VERSION, "subject": subject,
                    "facts": semantic_hash([[f.id, f.kind, f.text] for f in facts]),
                    "identities": semantic_hash(sorted(self._identities))}
            prompt = build_prompt(facts)
            result = run_site(
                site=SITE_CARD_COPY, org_id=self.org_id, seed=seed,
                precondition=any(f.kind != "goal" for f in facts),
                build_prompt=lambda feedback: with_correction(prompt, feedback),
                parse=lambda payload: check_copy(payload, facts, identities=self._identities),
                fallback=dict, gate=self._gate, cache=self._cache, feature=FEATURE_CARD_COPY,
                subject_ref=f"card:{card_id}", repair=REPAIR_SYNTAX)
            self.last_receipt = result.receipt
            if result.fell_back or not result.payload:
                return None
            stored = {**dict(result.payload), "card_version": version, "generation": result.generation}
            if not card_store.set_copy(self.org_id, card_id, stored, version=version,
                                       headline=str(copy.get("headline") or "")):
                return None
            return stored
        except Exception:      # noqa: BLE001 — a copy failure costs the copy, never the card
            _log.exception("the card writer failed for org=%s card=%s — the card keeps today's fields",
                           self.org_id, card_id)
            return None


def _accepted_goals(engine: Any, org_id: str, at: Any) -> tuple[Any, ...]:
    """The company brief's accepted GOALS now (`platform/company_brief_store.accepted`), or none. Never raises: a
    brief that cannot be read is a card with no goal line, which it already is today."""
    if engine is None:
        return ()
    try:
        from genios_engine.platform.company_brief_store import accepted

        with engine.connect() as conn:
            return tuple(line for line in accepted(conn, org_id) if line.section == "goals")
    except Exception:      # noqa: BLE001
        _log.warning("could not read the company brief's goals for org=%s", org_id)
        return ()


__all__ = ["CAPS", "COPY_VERSION", "CopyWriter", "FACT_CHARS", "FIELDS", "Fact", "GOAL_HOW", "MAX_FACTS",
           "MAX_QUOTES", "MAX_STEPS", "NOTHING_STANDS", "SENTENCE_FIELDS", "STEP_CAP", "SUBJECT_MAX_WORDS",
           "build_prompt", "card_facts", "check_copy"]
