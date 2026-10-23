#!/usr/bin/env python3
"""The ideal-card gap scorecard: each card Rohit wants, beside the card the product made, field by field.

    python scripts/ideal_card_gap.py --ideal ideal.json --product product.json [--md gap.md] [--json gap.json]
    python scripts/ideal_card_gap.py --from-dashboard <dashboard>/src/02-data.js --product product.json
    GENIOS_TARGET_DATABASE_URL=... python scripts/ideal_card_gap.py --ideal ideal.json --org org_...
        [--self you@yourco.com] [--assert-min-found N]

⛔ WHY THIS EXISTS (GeniOS-011 S44.U1). Rohit, 23 Oct: a local ideal-state dashboard shows the cards he
wants — written by a Claude session reading his real mail — and the website's cards are nothing like
them. "A good card" had been an opinion argued card by card. This makes it a measured gap: which ideal
cards the product has a card for at all, and on each of those, which fields the product fills with
something that is that card's own.

⛔ THE IDEAL FILE IS ROHIT'S MAIL. The dashboard's `02-data.js` lives OUTSIDE the repo and quotes real
mail. This script reads it where it is and writes its report where the operator says; nothing of it
belongs in the repo, a test, a fixture or a commit message. The tests use invented cards only.

INPUT A — THE IDEAL CARDS, in the dashboard's own field names (`id, head, sum, what, why, reco, how,
steps, who, by, forWhom, avoid, doneWhen, ifNot, alt, wait, goal, draft, tools, quotes, people, lane,
cat`): `--ideal` a JSON list (or `{"cards": [...]}`) the operator exported, or `--from-dashboard` the
dashboard's data file itself. That file is a browser script of top-level `const`s, so it is run by
`node` in a `vm` context with a timeout and its `CARDS` array printed as JSON — never parsed with a
regex, which reads JavaScript wrongly the first time a string holds a bracket. No `node` on the PATH is
a stated error (exit 2), not a guess. `vm` is not a security boundary: run it on the operator's own
dashboard file, which is what it is for.

INPUT B — THE PRODUCT CARDS: `--product` a JSON dump of what the API returns — a list of
`GET /cards/{id}` bodies, or `GET /cards`'s `{"cards": [...]}`, optionally with `"details": {card_id:
GET /cards/{id} body}` merged over each queue row. Or, with no `--product`, the card rows themselves,
read from `--database-url` / `GENIOS_TARGET_DATABASE_URL` (`scripts/_db`: never the app's configured
database) for `--org`, on a connection whose transaction is `read only` from its first statement
(`scripts/_gate`). The rows are the app surface's open, unexpired cards on open signals — the queue's
own state, surface and expiry clauses — but NOT its Layer 4 authority joins (those take row locks a
read-only transaction refuses), and not the API's request-time projection: a row's steps are its
signal's `candidate_steps`. The API dump is the exact read; the database read is the close one.

MATCH — by the counterparty, deterministic. An ideal card's counterparty is its `people` names, its
`forWhom` parts and the speakers and addresses of its `quotes`; a product card's is `business_subject`,
`recommended.for_whom` / `.to`, and the authors, names and recipients its `why` entries carry. Three
keys, strongest first: the same EMAIL (3); the same company DOMAIN of an email (2) — never a free-mail
domain, which would make every Gmail user one company; the same NAME (1) — one name's words all inside
the other's ("Asha" is "Asha Verma"). Every ideal × product pair is ranked by (strength desc, ideal
order, product order — the order the dump or the queue gave, i.e. rank) and taken greedily: each ideal
card gets at most one product card and each product card answers at most one ideal card, because a
product card is one situation. `--self` names the operator's own names and addresses, which are never a
counterparty.

SCORE — per ideal card, per field the IDEAL card has (a field it leaves empty is not counted against
the product). `FIELDS` below names each field's ideal keys and its product source. A field is ✓ when
the product side is present and non-empty AND:
  * `subject` is CLEAR: not cut (no trailing ellipsis, joiner word or joiner mark), at most 90
    characters, and starting with a verb from `ACTION_VERBS` (a closed, extendable list, so the check is
    the same on every run) — `GeniOS-010/06-CARDS/02-CARD-DEFINITION.md` §2.1;
  * `quotes` are the COUNTERPARTY'S OWN WORDS: a quote marked `from_counterparty` false or unknown is
    ours or no one's (`deliver/card_builder.quotable`'s rule), and a "quote" that is the card's own
    headline or situation is GeniOS's reading shown as proof (§2.4);
  * the field is the card's OWN: the same text (case and spacing ignored) in the same field of two or
    more product cards is "not its own" — a sentence written for a kind of card, not this one (§1, §4).
    `who_by` and `sources` are exempt: a person and a tool tag are rightly shared.
Not found, every counted field is ✗ "no product card".

OUTPUT. A markdown report (stdout, or `--md`) and a JSON (`--json`): per ideal card, per field ✓/✗,
why, and the product's value as it stands (truncated); totals — cards found x/N, fields filled y/M, and
each field's fill. Exit 0 for any report, whatever it says; 1 only when `--assert-min-found N` is given
and fewer than N were found (the CI lever, for later); 2 when an input cannot be read.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument                 # noqa: E402
from scripts._db import resolve_database_url                  # noqa: E402
from scripts._db import UnsafeDatabaseTarget                  # noqa: E402
from scripts._gate import read_only_connection                # noqa: E402
from scripts._gate import sql                                 # noqa: E402

UNIT = "GeniOS-011 S44.U1"

EXIT_OK = 0
EXIT_BELOW_MIN_FOUND = 1
EXIT_INPUT = 2

#: How much of a value the report shows. Enough to recognise the sentence, short enough that a table
#: of fifteen fields stays a table.
SHOWN_CHARS = 80

#: The subject's ceiling (`02-CARD-DEFINITION.md` §2.1: "about ten words at most").
SUBJECT_MAX_CHARS = 90


@dataclass(frozen=True)
class Field:
    """One scored field: the ideal card's keys that ask for it, and how the product's value is read."""

    name: str
    label: str
    ideal_keys: tuple[str, ...]
    #: Exempt from the repeated-text check: a value two cards may rightly share.
    shared_ok: bool = False


#: The fields, in the order the opened card shows them (`02-CARD-DEFINITION.md` §3). The product side
#: of each is `_product_value`.
FIELDS: tuple[Field, ...] = (
    Field("subject", "Subject — a clear action", ("head",)),
    Field("summary", "What (summary)", ("sum", "what")),
    Field("why", "Why now", ("why",)),
    Field("recommendation", "Recommendation (the move)", ("reco",)),
    Field("how_steps", "How / steps", ("how", "steps")),
    Field("who_by", "Who · by when", ("who", "by", "forWhom"), shared_ok=True),
    Field("avoid", "Avoid", ("avoid",)),
    Field("result", "Result — if you don't", ("ifNot",)),
    Field("done_when", "Done when", ("doneWhen",)),
    Field("alternative", "Alternative", ("alt",)),
    Field("wait_or_stop", "Wait or stop", ("wait",)),
    Field("goal", "Goal it moves", ("goal",)),
    Field("draft", "Draft", ("draft",)),
    Field("sources", "Source / tool tags", ("tools",), shared_ok=True),
    Field("quotes", "Quotes — their own words", ("quotes",)),
)
FIELD_NAMES: tuple[str, ...] = tuple(f.name for f in FIELDS)

#: The verbs a card's subject may start with. Closed on purpose: "starts with a verb" decided by a
#: model or a tagger would differ between runs, and a scorecard that moves without the cards moving is
#: no measurement. A real verb missing here is a one-line addition, said in the diff.
ACTION_VERBS: frozenset[str] = frozenset("""
accept acknowledge add agree answer apply approve archive arrange ask attach attend block book brief
build call cancel chase check choose clarify close collect commit complete confirm connect contact
correct create decide decline delegate deliver draft drop email escalate file finalise finalize find
finish fix flag follow forward get give hand hire hold introduce invite invoice join keep let line list
loop make mark meet message move nudge offer open pay pick ping plan post prepare present prioritise
prioritize propose push put raise read reconnect record refund register reject remind renew reply
request reschedule resend resolve respond return review revise route run schedule search see send
set settle share ship sign start stop submit suggest tell thank track transfer try unblock update
upload verify wait warn watch welcome write
""".split())

#: A subject that ENDS on one of these was cut mid-phrase: the move continues past the last word.
_JOINER_WORDS: frozenset[str] = frozenset(
    "a an and at about by for from in into of on or re the to via with".split())
_JOINER_MARKS = ("—", "–", "-", ",", ":", ";", "/", "(", "&", "+")
_ELLIPSES = ("…", "...")

#: Domains many unrelated people share. A domain match on one of these would make every Gmail user the
#: same company, so they never match by domain (an exact address still does).
FREE_MAIL_DOMAINS: frozenset[str] = frozenset("""
gmail.com googlemail.com yahoo.com yahoo.co.in ymail.com outlook.com hotmail.com live.com msn.com
icloud.com me.com mac.com aol.com proton.me protonmail.com rediffmail.com zoho.com gmx.com
""".split())

#: Words in a name field that name no one: company forms, channels, pronouns.
_NOT_A_NAME: frozenset[str] = frozenset("""
you me we us our your the and of team inc ltd llc pvt private limited co corp email mail call
meeting gmail calendar slack whatsapp linkedin
""".split())

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_LETTERS = re.compile(r"[^\W\d_]+", re.UNICODE)

STRENGTH = {"email": 3, "domain": 2, "name": 1}


class InputUnreadable(ValueError):
    """An input file that is not what this script reads — exit 2, nothing scored."""


class DashboardUnreadable(InputUnreadable):
    """The dashboard's data file could not be run for its CARDS array (no node, no array, an error)."""


# ── reading the inputs ─────────────────────────────────────────────────────────────────────────────

def _read_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise InputUnreadable(f"{path}: {err}") from err


def _cards_of(data: Any, path: str) -> list[dict]:
    cards = data.get("cards") if isinstance(data, dict) else data
    if not isinstance(cards, list) or not all(isinstance(c, dict) for c in cards):
        raise InputUnreadable(f"{path}: expected a list of card objects, or {{\"cards\": [...]}}")
    return cards


def load_ideal(path: str) -> list[dict]:
    """The operator's export of the dashboard's cards: a list, or `{"cards": [...]}`."""
    return _cards_of(_read_json(path), path)


def load_product(path: str) -> list[dict]:
    """A dump of the API's cards: `GET /cards/{id}` bodies, or `GET /cards` with optional `details`
    (card_id → `GET /cards/{id}` body) laid over each queue row — the detail is the fuller read."""
    data = _read_json(path)
    cards = _cards_of(data, path)
    details = data.get("details") if isinstance(data, dict) else None
    if isinstance(details, dict):
        cards = [{**card, **(details.get(str(card.get("card_id"))) or {})} for card in cards]
    return cards


#: Run by `node -e`. The dashboard's data file is a browser script of top-level `const`s; appended to
#: the same script, one statement can read `CARDS` (a global lexical binding, not a property of the
#: global object). `window` is the context itself so a file that writes to it still runs.
_NODE_EXTRACT = r"""
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const quiet = () => {};
const ctx = {console: {log: quiet, warn: quiet, error: quiet, info: quiet}};
ctx.window = ctx; ctx.self = ctx;
vm.createContext(ctx);
vm.runInContext(src + "\n;globalThis.__idealCards = (typeof CARDS === 'undefined') ? undefined : CARDS;",
                ctx, {timeout: 10000, filename: "dashboard-data.js"});
if (!Array.isArray(ctx.__idealCards)) { process.stderr.write("no CARDS array in the file\n"); process.exit(3); }
process.stdout.write(JSON.stringify(ctx.__idealCards));
"""


def extract_dashboard_cards(path: str) -> list[dict]:
    """The dashboard data file's `CARDS` array, as `node` evaluates it. No node is a stated error."""
    node = shutil.which("node")
    if node is None:
        raise DashboardUnreadable(
            "--from-dashboard runs the dashboard's data file with `node` to read its CARDS array, and "
            "no `node` is on the PATH. Install Node, or export the cards as JSON from the dashboard "
            "and pass --ideal.")
    if not Path(path).is_file():
        raise DashboardUnreadable(f"{path}: no such file")
    try:
        done = subprocess.run([node, "-e", _NODE_EXTRACT, str(Path(path).resolve())],
                              capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise DashboardUnreadable(f"{path}: node could not run it: {err}") from err
    if done.returncode != 0:
        raise DashboardUnreadable(
            f"{path}: node exit {done.returncode}: {done.stderr.strip()[:300]}")
    try:
        cards = json.loads(done.stdout)
    except ValueError as err:
        raise DashboardUnreadable(f"{path}: node printed no JSON: {err}") from err
    return _cards_of(cards, path)


#: The card rows the app surface shows: the queue's own state, surface, expiry and open-signal clauses
#: (`deliver/store.CardStore.queue`), without its authority joins' row locks, which a read-only
#: transaction refuses. The signal's candidate steps are the row's steps. Rank order, as the queue's.
CARD_ROWS_SQL = (
    "select k.*, s.candidate_steps from cards k "
    "join signals s on s.signal_id = k.signal_id and s.org_id = k.org_id "
    "where k.org_id = :org and k.state in ('queued', 'surfaced', 'snoozed', 'claimed') "
    "and s.status = 'open' and 'app' = any(k.surfaces) and k.expires_at > now() "
    "order by k.score desc, k.created_at asc, k.card_id")


def read_product_cards(conn, org: str) -> list[dict]:
    """The org's open app cards, on a connection the caller opened read-only."""
    return [dict(row) for row in conn.execute(sql(CARD_ROWS_SQL), {"org": org}).mappings()]


# ── values ─────────────────────────────────────────────────────────────────────────────────────────

def _text(value: Any) -> str:
    """Any value as one line of words: lists joined with ' | ', a dict by its readable keys."""
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, (list, tuple)):
        return " | ".join(t for t in (_text(v) for v in value) if t)
    if isinstance(value, dict):
        for key in ("title", "name", "text", "quote", "body", "label", "step", "what", "id"):
            if _text(value.get(key)):
                return _text(value.get(key))
        return " ".join(json.dumps(value, sort_keys=True, default=str).split())
    return str(value)


def _norm(value: str) -> str:
    return " ".join(value.split()).casefold()


def _shown(value: str) -> str:
    return value if len(value) <= SHOWN_CHARS else value[:SHOWN_CHARS - 1].rstrip() + "…"


def _first(value: Any) -> str:
    """A tuple field's first element (`["Asha Verma", "role"]` → "Asha Verma"), else the value."""
    if isinstance(value, (list, tuple)):
        return _text(value[0]) if value else ""
    return _text(value)


def _ideal_value(card: dict, f: Field) -> str:
    parts = []
    for key in f.ideal_keys:
        value = card.get(key)
        if f.name in ("quotes", "sources") and isinstance(value, list):
            value = [_first(item) for item in value]
        parts.append(_text(value))
    return " · ".join(p for p in parts if p)


def _dict(value: Any) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return [value]
    return value if isinstance(value, list) else []


def counterparty_quotes(card: dict) -> list[str]:
    """The product card's quotes that are the counterparty's own words (module docstring, SCORE).

    A `why` entry carries a quote as `quote` (a loader's observation, with `from_counterparty`) or as
    `quotes` (the expert check's held quotes: strings, or dicts). A dict that says whose words it is
    must say the counterparty's — False is ours, None is no one's. A string the check held is taken as
    the mail's. Either way, a quote that is the card's own headline or situation is not a quote."""
    own = {_norm(_text(card.get("headline"))), _norm(_text(card.get("situation")))} - {""}
    out = []
    for entry in _list(card.get("why")):
        if not isinstance(entry, dict):
            continue
        items = list(_list(entry.get("quotes")))
        if entry.get("quote") is not None:
            items.append(entry)
        for item in items:
            if isinstance(item, dict):
                if "from_counterparty" in item and item.get("from_counterparty") is not True:
                    continue
                words = _text(item.get("quote") or item.get("text"))
            else:
                words = _text(item)
            if words and _norm(words) not in own:
                out.append(words)
    return out


def _steps(card: dict) -> list[str]:
    decision = _dict(card.get("decision"))
    steps = _list(_dict(decision.get("recommendation")).get("steps"))
    if not steps:
        steps = _list(card.get("candidate_steps"))
    return [s for s in (_text(step) for step in steps) if s]


def _product_value(card: dict, name: str) -> str:
    """The product card's value for one field — a `GET /cards/{id}` body or a card row."""
    recommended = _dict(card.get("recommended"))
    if name == "subject":
        return _text(card.get("headline"))
    if name == "summary":
        return _text(card.get("situation"))
    if name == "why":
        return _text(card.get("why_now"))
    if name == "recommendation":
        return _text(recommended.get("what"))
    if name == "how_steps":
        return " | ".join(_steps(card))
    if name == "who_by":
        who, by = _text(recommended.get("who")), _text(recommended.get("by_when"))
        return " · ".join(p for p in (who, by) if p)
    if name == "avoid":
        return _text(_dict(_dict(card.get("decision")).get("recommendation")).get("avoid"))
    if name == "result":
        return _text(card.get("do_nothing_consequence"))
    if name == "done_when":
        return _text(card.get("success_signal"))
    if name == "alternative":
        return _text(card.get("alternative"))
    if name == "wait_or_stop":
        return _text(card.get("wait_or_stop"))
    if name == "goal":
        for key in ("goal", "goals", "goal_id", "suggested_goal"):
            if _text(card.get(key)):
                return _text(card.get(key))
        return ""
    if name == "draft":
        artifact = card.get("artifact")
        return _text(_dict(artifact).get("body") if not isinstance(artifact, str) else artifact)
    if name == "sources":
        return _text(_list(card.get("context_tags")))
    if name == "quotes":
        return " | ".join(counterparty_quotes(card))
    raise KeyError(name)


# ── subject clear ──────────────────────────────────────────────────────────────────────────────────

def subject_clear(subject: str) -> tuple[bool, str]:
    """(clear, why not). Not cut, at most 90 characters, and starting with an action verb."""
    s = " ".join((subject or "").split())
    if not s:
        return False, "empty"
    if s.endswith(_ELLIPSES) or s.startswith(_ELLIPSES):
        return False, "cut: ends in an ellipsis"
    if s.endswith(_JOINER_MARKS):
        return False, f"cut: ends on {s[-1]!r}"
    words = _LETTERS.findall(s)
    if words and words[-1].casefold() in _JOINER_WORDS and not s.endswith((".", "?", "!")):
        return False, f"cut: ends on {words[-1]!r}"
    if len(s) > SUBJECT_MAX_CHARS:
        return False, f"{len(s)} characters, over {SUBJECT_MAX_CHARS}"
    if not words or words[0].casefold() not in ACTION_VERBS:
        return False, f"does not start with a verb ({(words or [''])[0]!r})"
    return True, ""


# ── matching ───────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Keys:
    """Who a card is about: addresses, company domains, and names (each a set of words)."""

    emails: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)
    names: list[frozenset[str]] = field(default_factory=list)

    def add(self, value: Any, self_keys: "Keys") -> None:
        raw = _text(value)
        if not raw:
            return
        for email in _EMAIL.findall(raw):
            email = email.casefold()
            if email in self_keys.emails:
                continue
            self.emails.add(email)
            domain = email.rsplit("@", 1)[1]
            if domain not in FREE_MAIL_DOMAINS and domain not in self_keys.domains:
                self.domains.add(domain)
        words = frozenset(w.casefold() for w in _WORD.findall(_EMAIL.sub(" ", raw))
                          if len(w) >= 2 and w.casefold() not in _NOT_A_NAME)
        if words and not any(words <= own for own in self_keys.names):
            self.names.append(words)


def _self_keys(values: Iterable[str]) -> Keys:
    keys = Keys()
    for value in values or ():
        keys.add(value, Keys())
    return keys


def ideal_keys(card: dict, self_keys: Keys) -> Keys:
    """An ideal card's counterparty: its people's names, its `forWhom` parts, and its quotes' speakers
    and addresses (`[text, "Speaker · Email (a@b.c)", when]`)."""
    keys = Keys()
    for person in _list(card.get("people")):
        keys.add(_first(person) if not isinstance(person, dict) else
                 " ".join(_text(person.get(k)) for k in ("name", "email")), self_keys)
    for part in re.split(r"\s+·\s+|[()]|,", _text(card.get("forWhom"))):
        keys.add(part, self_keys)
    for quote in _list(card.get("quotes")):
        said_by = _text(quote[1]) if isinstance(quote, (list, tuple)) and len(quote) > 1 else (
            _text(quote.get("from") or quote.get("who")) if isinstance(quote, dict) else "")
        for email in _EMAIL.findall(said_by):
            keys.add(email, self_keys)
        keys.add(_EMAIL.sub(" ", said_by).split(" · ")[0], self_keys)
    return keys


def product_keys(card: dict, self_keys: Keys) -> Keys:
    """A product card's counterparty: its subject, its move's recipient, and its evidence's people."""
    keys = Keys()
    recommended = _dict(card.get("recommended"))
    for value in (card.get("business_subject"), recommended.get("for_whom"), recommended.get("to")):
        keys.add(value, self_keys)
    for entry in _list(card.get("why")):
        if not isinstance(entry, dict):
            continue
        for item in [entry, *[q for q in _list(entry.get("quotes")) if isinstance(q, dict)]]:
            for key in ("to", "author", "name", "from"):
                keys.add(item.get(key), self_keys)
    return keys


def match_strength(a: Keys, b: Keys) -> str | None:
    """The strongest key two cards share, or None."""
    if a.emails & b.emails:
        return "email"
    if a.domains & b.domains:
        return "domain"
    if any(x <= y or y <= x for x in a.names for y in b.names):
        return "name"
    return None


def match(ideal: list[dict], product: list[dict], self_keys: Keys) -> dict[int, tuple[int, str]]:
    """ideal index → (product index, key). Greedy over (strength desc, ideal order, product order)."""
    ik = [ideal_keys(card, self_keys) for card in ideal]
    pk = [product_keys(card, self_keys) for card in product]
    pairs = []
    for i, a in enumerate(ik):
        for p, b in enumerate(pk):
            how = match_strength(a, b)
            if how:
                pairs.append((-STRENGTH[how], i, p, how))
    pairs.sort()
    taken: dict[int, tuple[int, str]] = {}
    used: set[int] = set()
    for _, i, p, how in pairs:
        if i in taken or p in used:
            continue
        taken[i] = (p, how)
        used.add(p)
    return taken


# ── scoring ────────────────────────────────────────────────────────────────────────────────────────

def repeated_values(product: list[dict]) -> dict[str, set[str]]:
    """field → the normalized values that two or more product cards hold in that field."""
    seen: dict[str, dict[str, set[int]]] = {f.name: {} for f in FIELDS if not f.shared_ok}
    for index, card in enumerate(product):
        for name, cards_by_value in seen.items():
            value = _norm(_product_value(card, name))
            if value:
                cards_by_value.setdefault(value, set()).add(index)
    return {name: {v for v, cards in by_value.items() if len(cards) >= 2}
            for name, by_value in seen.items()}


def _score_field(f: Field, card: dict, repeated: dict[str, set[str]]) -> tuple[bool, str, str]:
    """(ok, why not, the product's value) for one field of one matched product card."""
    if f.name == "who_by":
        recommended = _dict(card.get("recommended"))
        who, by = _text(recommended.get("who")), _text(recommended.get("by_when"))
        value = _product_value(card, f.name)
        if not who or not by:
            missing = " and ".join(n for n, v in (("who", who), ("by when", by)) if not v)
            return False, f"no {missing}", value
        return True, "", value
    value = _product_value(card, f.name)
    if not value:
        return False, "empty", value
    if f.name == "subject":
        ok, why = subject_clear(value)
        if not ok:
            return False, why, value
    if not f.shared_ok and _norm(value) in repeated.get(f.name, set()):
        return False, "not its own: the same text is on another product card", value
    return True, "", value


def build_report(ideal: list[dict], product: list[dict],
                 self_keys: Iterable[str] = ()) -> dict:
    """The scorecard: per ideal card, per field it has, ✓/✗ with the product's value; and totals."""
    me = _self_keys(self_keys)
    matched = match(ideal, product, me)
    repeated = repeated_values(product)
    cards = []
    per_field = {f.name: {"filled": 0, "asked": 0} for f in FIELDS}
    for i, card in enumerate(ideal):
        hit = matched.get(i)
        pcard = product[hit[0]] if hit else None
        fields = {}
        for f in FIELDS:
            ideal_value = _ideal_value(card, f)
            if f.name != "subject" and not ideal_value:
                continue
            if pcard is None:
                ok, why, value = False, "no product card", ""
            else:
                ok, why, value = _score_field(f, pcard, repeated)
            per_field[f.name]["asked"] += 1
            per_field[f.name]["filled"] += int(ok)
            fields[f.name] = {"ok": ok, "why": why, "product": _shown(value),
                              "ideal": _shown(ideal_value)}
        cards.append({
            "ideal_id": _text(card.get("id")) or f"#{i + 1}",
            "ideal_head": _shown(_text(card.get("head"))),
            "lane": _text(card.get("lane")), "cat": _text(card.get("cat")),
            "found": pcard is not None,
            "product_card_id": _text(pcard.get("card_id")) if pcard else None,
            "matched_by": hit[1] if hit else None,
            "fields": fields,
        })
    totals = {
        "cards": len(ideal), "cards_found": sum(c["found"] for c in cards),
        "fields": sum(len(c["fields"]) for c in cards),
        "fields_filled": sum(f["ok"] for c in cards for f in c["fields"].values()),
        "product_cards": len(product),
    }
    return {"unit": UNIT, "totals": totals, "per_field": per_field, "cards": cards}


# ── the report ─────────────────────────────────────────────────────────────────────────────────────

def _cell(value: str) -> str:
    return (value or "—").replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict) -> str:
    t = report["totals"]
    lines = [
        "# The ideal-card gap",
        "",
        f"**cards found {t['cards_found']}/{t['cards']}** · **fields filled "
        f"{t['fields_filled']}/{t['fields']}** · product cards read {t['product_cards']}",
        "",
        "| Field | Filled |",
        "|---|---|",
    ]
    labels = {f.name: f.label for f in FIELDS}
    for name, count in report["per_field"].items():
        if count["asked"]:
            lines.append(f"| {_cell(labels[name])} | {count['filled']}/{count['asked']} |")
    for card in report["cards"]:
        found = (f"found: `{card['product_card_id']}` by {card['matched_by']}" if card["found"]
                 else "**not found** — no product card for this counterparty")
        filled = sum(f["ok"] for f in card["fields"].values())
        lines += ["", f"## {_cell(card['ideal_id'])} · {_cell(card['ideal_head'])}", "",
                  f"{found} · fields {filled}/{len(card['fields'])}", "",
                  "| Field | | Product | Why not | Ideal |", "|---|---|---|---|---|"]
        for name, f in card["fields"].items():
            mark = "✓" if f["ok"] else "✗"
            lines.append(f"| {name} | {mark} | {_cell(f['product'])} | {_cell(f['why'])} | "
                         f"{_cell(f['ideal'])} |")
    return "\n".join(lines) + "\n"


# ── the command ────────────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--ideal", help="the ideal cards: a JSON list, or {\"cards\": [...]}")
    source.add_argument("--from-dashboard", dest="dashboard",
                        help="the dashboard's data file (src/02-data.js), read through node")
    ap.add_argument("--product", help="the product cards: a JSON dump of GET /cards (+ details)")
    add_database_argument(ap)
    ap.add_argument("--org", help="the org whose cards are read, when they come from the database")
    ap.add_argument("--self", dest="self_keys", action="append", default=[],
                    help="the operator's own name or address, never a counterparty (repeatable)")
    ap.add_argument("--md", help="write the markdown here (default: stdout)")
    ap.add_argument("--json", dest="json_out", help="write the JSON here")
    ap.add_argument("--assert-min-found", type=int, default=None,
                    help="exit 1 when fewer ideal cards than this have a product card")
    args = ap.parse_args(argv)

    try:
        ideal = (load_ideal(args.ideal) if args.ideal else extract_dashboard_cards(args.dashboard))
        if args.product:
            product = load_product(args.product)
        else:
            if not args.org:
                raise InputUnreadable("reading cards from a database needs --org")
            url = resolve_database_url(args, purpose=f"{UNIT} card read (read-only)",
                                       stream=sys.stderr)
            from genios_engine.platform.db import get_engine
            conn = read_only_connection(get_engine(url))
            try:
                product = read_product_cards(conn, args.org)
            finally:
                conn.close()
    except (InputUnreadable, UnsafeDatabaseTarget) as err:
        print(f"ideal_card_gap: {err}", file=sys.stderr)
        return EXIT_INPUT

    report = build_report(ideal, product, self_keys=args.self_keys)
    md = render_markdown(report)
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
    else:
        sys.stdout.write(md)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    t = report["totals"]
    print(f"cards found {t['cards_found']}/{t['cards']} · fields filled "
          f"{t['fields_filled']}/{t['fields']}", file=sys.stderr)
    if args.assert_min_found is not None and t["cards_found"] < args.assert_min_found:
        print(f"below --assert-min-found {args.assert_min_found}", file=sys.stderr)
        return EXIT_BELOW_MIN_FOUND
    return EXIT_OK


if __name__ == "__main__":        # pragma: no cover
    raise SystemExit(main())
