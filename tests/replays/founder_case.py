"""The founder case — STEP-01's second exam, as a type, a loader, and the report a run of it makes.

`speedrun008/YC-II W27/` STEP-01 §3.1. The twelve
Atlas replays (`harness.py`) are specifications of decisions; a founder case is an INPUT the real
chain is run on: the founder's mail and calendar as the providers would hand them over, the instants
the sweeps run at, and what a correct GeniOS shows after each sweep — and must never show.

**Synthetic, always.** A case is modelled on a real item by sender and date only
(`golden-labels.md`); every name, address and line of text in it is invented. `REAL_NAMES` is the
deny-list that holds that rule: no person or organisation from the founder's mailbox may appear
anywhere in a case.

**Three rules a case cannot be written without**, because each closes a way for the exam to pass
on nothing:

  * a must-abstain case carries a WITNESS — a stage the run must show it reached. Today almost
    nothing becomes a card, so "no card" without a witness would pass every abstain case for the
    reason the must-detect cases fail;
  * what the engine cannot express yet is DECLARED, with its reason, in `not_expressible`, and
    reported apart — never silently skipped, never counted as a pass (`NOT_EXPRESSIBLE_TODAY`);
  * an empty or missing set is an error, never "0 cases passed".

The founder set lives in `specs/founder/`, one level below the Atlas specs, so `load_specs` (which
globs one level) keeps reading exactly twelve.
"""
from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from typing import Any

FOUNDER_DIR = Path(__file__).parent / "specs" / "founder"
#: The recorded model: one file per case, `{key: answer}`, written by `scripts/golden_eval.py`.
CASSETTE_DIR = FOUNDER_DIR / "cassettes"

KINDS = ("must_detect", "must_abstain")
LABELLERS = ("claude", "rohit")
#: The providers a case can hand the chain. `gcal` is the calendar connector's own source name.
SOURCES = ("gmail", "gcal")
#: `CaptureResult.outcome` — what Layer 1 did with an object, as `capture/pipeline.py` writes it
#: (`{"drop": "dropped", "park": "parked", "archive": "archived"}`, else `emitted`; plus `duplicate` and
#: `quarantined`). `archived` is STEP-03's: a mail the gate used to delete, kept and read by no model.
#: An expectation may add the reason code after a colon (`archived:N-02`, `parked:DOC-05`).
GATE_OUTCOMES = ("emitted", "dropped", "parked", "archived", "duplicate", "quarantined")
#: Where a must-abstain case proves the engine was exercised. Each is a stage the runner reports.
WITNESS_STAGES = ("gate", "memory", "situation", "card")
#: The sites a case may script per object (`read`) — the ideal reader serves them.
READ_SITES = ("gate", "relevance", "extraction", "domains")
#: An attachment's fetch, as the provider answers it.
FETCHES = ("refused", "ok")

#: What the engine cannot express yet, and why. A case that expects one of these MUST declare it
#: in its own `not_expressible`, so the board counts it apart. When a capability lands, its row is
#: deleted here, and every case that declared it is then judged on it.
NOT_EXPRESSIBLE_TODAY: dict[str, str] = {
    "workstream": "STEP-09 — the engine forms no workstream; nothing to compare against",
    "stage": "STEP-09 — no stage is derived for a workstream",
    "lane": "F10 — cards.output_lane is written NULL on the decided path",
    "brief": "STEP-15 — there is no morning brief to appear in",
}
#: Expectation keys the runner can check today.
EXPRESSIBLE_KEYS = ("gate", "memory", "cards")
EXPECTATION_KEYS = EXPRESSIBLE_KEYS + tuple(NOT_EXPRESSIBLE_TODAY)

#: People and organisations from the founder's real mailbox (`04-NOW-VS-SHOULD-VS-EXPECTED.md` §2,
#: `STEP-01` §4). Matched whole-word and case-insensitively on every string of a case, so `Sal` is
#: refused and `salary` is not. Common English words that are also names there (`Together`,
#: `Surge`, `Neon`, `Titan`, `Insight`) are listed only in the form that names the organisation.
REAL_NAMES: frozenset[str] = frozenset({
    # the founder and his own company
    "Rohit", "Swerashi", "mrrohitswerashi", "Homians", "GeniOS", "thegenios", "Harsh",
    # investors
    "Khushi", "Agarwal", "247VC", "ydvkhushi721", "Troy", "Kirwin", "a16z", "Neel",
    "Insight Partners", "insightpartners", "Theresa", "Hoffmann", "Antler", "Manik",
    "Titan Capital", "Afore", "Peak XV", "3one4", "Z Fellows", "IIMA",
    # the connector and the people it introduced
    "Boardy", "Pankaj", "saka", "Sal", "Stabler", "Nexlayer", "Maria", "Exconde", "Alyst",
    "Nitesh", "Pant", "DevDash", "Lalitha", "Silas", "eclipta", "Ori", "tryeverguide",
    "Everguide",
    # programs, incubators, government
    "NSRCEL", "Deepthi", "Chandrashekhar", "IIITD", "Navin", "Gaur", "Rajni", "Rani", "Naresh",
    "Sood", "Esha", "Hub71", "iHub", "FITT", "Saket", "IIM Lucknow", "GUSEC", "StartinUP",
    "Entrepreneurs First", "SINE", "Sankalp", "Intellecap", "Startup India", "DPIIT",
    "DigiLocker", "accubate",
    # partners and peers
    "Evokoa", "Tejas", "Tryclean", "Aditi", "Noveum", "Asmit", "Supymem", "Engramme", "Reticle",
    "actual.ai",
    # vendors the real mailbox carries
    "Composio", "Stripe", "Notion", "Apple", "Google",
})

_REAL = re.compile(r"(?<![0-9A-Za-z])(?:" + "|".join(
    re.escape(n).replace(r"\ ", r"\s+") for n in sorted(REAL_NAMES, key=len, reverse=True))
    + r")(?![0-9A-Za-z])", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


class CaseError(ValueError):
    """A case that does not satisfy the contract. Raised at load, never at judgement."""


# =================================================================================================
# the case
# =================================================================================================
@dataclass(frozen=True)
class Founder:
    name: str
    email: str
    company: str
    timezone: str
    #: STEP-04. The founder's other addresses and the company's own domains, declared as the tenant's
    #: — production's shape: the design partner writes from Gmail, has a second address that only
    #: ever receives his own mail, and a company domain. The golden founder had ONE address and it
    #: was `orgs.email`, which is why the set showed none of the "who is us" defects. The runner
    #: declares them the way `scripts/declare_self_identity.py` does (`org_self_identities`).
    also: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()

    @property
    def domain(self) -> str:
        return self.email.rsplit("@", 1)[-1]

    @property
    def addresses(self) -> tuple[str, ...]:
        """Every address of the founder's, the primary first."""
        return (self.email, *self.also)


@dataclass(frozen=True)
class Attachment:
    filename: str
    mime: str
    #: `refused` — the provider refuses the download, and production lands a `fetch_failed` stub
    #: that parks; `ok` — the bytes arrive (`text`, served as the file's content).
    fetch: str
    text: str = ""


@dataclass(frozen=True)
class CaseObject:
    """One thing a provider hands the chain: a Gmail message or a calendar event."""

    object_id: str
    source: str
    sweep: int
    occurred_at: datetime
    case_id: str
    owner: str                                  # the founder's address — the calendar's `self`
    sender: str = ""
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    thread: str = ""
    subject: str = ""
    body: str = ""
    labels: tuple[str, ...] = ()
    headers: Mapping[str, str] = field(default_factory=dict)
    attachments: tuple[Attachment, ...] = ()
    event: Mapping[str, Any] = field(default_factory=dict)
    #: The ideal reader's answers for this object, per site (`READ_SITES`). Served by
    #: `ideal_reader.py`; recorded into the case's cassette by `scripts/golden_eval.py`.
    read: Mapping[str, Any] = field(default_factory=dict)

    @property
    def provider_id(self) -> str:
        """The id the provider gives this object. Stable per case, so a re-run lands the same."""
        return f"{self.case_id.lower()}-{self.object_id}"

    @property
    def sender_email(self) -> str | None:
        m = _EMAIL.search(self.sender or "")
        return m.group(0).lower() if m else None

    def provider_message(self) -> dict[str, Any]:
        """The Gmail API message the connector's own mapping (`composio._to_objects`) reads."""
        if self.source != "gmail":
            raise CaseError(f"{self.provider_id} is not a Gmail message")
        headers = [{"name": "From", "value": self.sender},
                   {"name": "To", "value": ", ".join(self.to)}]
        if self.cc:
            headers.append({"name": "Cc", "value": ", ".join(self.cc)})
        headers += [{"name": "Subject", "value": self.subject},
                    {"name": "Date", "value": format_datetime(self.occurred_at)}]
        headers += [{"name": k, "value": v} for k, v in self.headers.items()]
        parts: list[dict[str, Any]] = [{"mimeType": "text/plain",
                                        "body": {"data": _b64(self.body)}}]
        for i, a in enumerate(self.attachments, start=1):
            parts.append({"filename": a.filename, "mimeType": a.mime,
                          "body": {"attachmentId": f"att{i}", "size": max(len(a.text), 1024)}})
        return {"messageId": self.provider_id, "threadId": self.thread or self.provider_id,
                "labelIds": list(self.labels), "messageTimestamp": self.occurred_at.isoformat(),
                "snippet": " ".join(self.body.split())[:200],
                "payload": {"mimeType": "multipart/mixed", "headers": headers, "parts": parts}}

    def attachment_response(self, attachment_id: str) -> dict[str, Any]:
        """What `GMAIL_GET_ATTACHMENT` answers for one of this message's files."""
        index = int(attachment_id.removeprefix("att")) - 1
        a = self.attachments[index]
        if a.fetch == "refused":
            return {"successful": False, "error": "Invalid request data provided"}
        return {"successful": True, "data": {"data": _b64(a.text)}}

    def provider_event(self) -> dict[str, Any]:
        """The Google Calendar event the calendar connector's own mapping (`_to_raw`) reads."""
        if self.source != "gcal":
            raise CaseError(f"{self.provider_id} is not a calendar event")
        ev = self.event
        attendees = [{"email": a, "responseStatus": "accepted",
                      **({"self": True} if a.lower() == self.owner.lower() else {})}
                     for a in ev.get("attendees", ())]
        out: dict[str, Any] = {
            "id": self.provider_id, "summary": ev.get("summary", ""),
            "start": {"dateTime": ev["start"]}, "end": {"dateTime": ev["end"]},
            "status": ev.get("status", "confirmed"),
            "organizer": {"email": ev.get("organizer", self.owner),
                          **({"self": True} if ev.get("organizer", self.owner).lower()
                             == self.owner.lower() else {})},
            "attendees": attendees, "updated": self.occurred_at.isoformat()}
        for key in ("description", "location", "recurringEventId"):
            if ev.get(key):
                out[key] = ev[key]
        return out


@dataclass(frozen=True)
class CardExpectation:
    """What the founder must — or must never — see about one subject.

    A card is ABOUT this expectation when any `about` term appears in what the founder reads
    (whole word, any case). `min`/`max` bound how many distinct cards there are, over every sweep
    — so "the same card updates, it does not multiply" is `max: 1` across a multi-sweep case.
    """

    about: tuple[str, ...]
    min: int
    max: int
    mentions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Witness:
    """The stage a must-abstain case must show it reached, so its silence is a decision."""

    stage: str
    objects: tuple[str, ...] = ()
    about: tuple[str, ...] = ()


@dataclass(frozen=True)
class FounderCase:
    case_id: str
    title: str
    kind: str
    label_row: int
    labelled_by: str
    replays: tuple[str, ...]
    founder: Founder
    sweeps: tuple[datetime, ...]
    objects: tuple[CaseObject, ...]
    expected_gate: Mapping[str, str]
    expected_memory: Mapping[str, bool]
    cards: tuple[CardExpectation, ...]
    expected_other: Mapping[str, str]            # workstream / stage / lane / brief, as written
    forbidden_names: tuple[str, ...]
    forbidden_phrases: tuple[str, ...]
    witness: Witness | None
    not_expressible: Mapping[str, str]
    #: Case-level answers for sites that read a situation rather than one object (the decider,
    #: R-1, the narrator, resolution). Served by `ideal_reader.py`.
    model: Mapping[str, Any] = field(default_factory=dict)
    #: Why the engine fails this case today — a finding or a step, named. Set only after the case
    #: was measured, and never an edit to what the case expects: the case still expects the right
    #: card. `test_founder_cases` turns it into a strict xfail, so the day the gap closes the case
    #: passes, the xfail fails, and this line has to go.
    blocked_on: str = ""
    source: str = field(default="", compare=False)

    def expressible(self, key: str) -> bool:
        return key not in self.not_expressible

    def object(self, object_id: str) -> CaseObject:
        return next(o for o in self.objects if o.object_id == object_id)

    def objects_in(self, sweep: int) -> tuple[CaseObject, ...]:
        return tuple(o for o in self.objects if o.sweep == sweep)


# =================================================================================================
# what a run of a case reports — written by `engine_runner.py`, read by `marking.py`
# =================================================================================================
@dataclass(frozen=True)
class Landed:
    """What Layer 1 did with one provider object (an email can land as several events)."""

    object_id: str
    source_object_id: str
    event_id: str | None
    outcome: str
    reason: str | None
    sweep: int


@dataclass(frozen=True)
class SituationView:
    situation_id: str
    situation_type: str
    domain: str
    status: str
    anchor: str                                 # the anchor node's display name


@dataclass(frozen=True)
class CardView:
    card_id: str
    state: str
    level: str
    #: Everything the founder reads on the card, joined: headline, situation, why, actions,
    #: subject, unresolved item, why-now. Forbidden terms and `about` terms are matched on this.
    text: str
    output_lane: str | None
    sweeps: tuple[int, ...]                     # the sweeps after which the card existed


@dataclass(frozen=True)
class CaseRun:
    case_id: str
    org_id: str
    landed: tuple[Landed, ...]
    memory: Mapping[str, int]                   # object id → graph facts carrying its events
    situations: tuple[SituationView, ...]
    cards: tuple[CardView, ...]
    funnel: tuple[Mapping[str, int], ...]       # per sweep: stage → n
    chain_ok: tuple[bool, ...]                  # per sweep: `_run_l2_chain`'s own answer
    model_calls: tuple[tuple[str, str], ...]    # (site, cassette key), in call order
    misses: tuple[tuple[str, str], ...]


# =================================================================================================
# parsing
# =================================================================================================
_CASE_KEYS = {"case_id", "title", "kind", "label_row", "labelled_by", "replays", "founder",
              "sweeps", "objects", "expected", "forbidden", "witness", "not_expressible",
              "model", "notes", "blocked_on"}
_GMAIL_KEYS = {"id", "source", "sweep", "occurred_at", "from", "to", "cc", "thread", "subject",
               "body", "labels", "headers", "attachments", "read"}
_GCAL_KEYS = {"id", "source", "sweep", "occurred_at", "summary", "start", "end", "organizer",
              "attendees", "status", "description", "location", "recurringEventId", "read"}
_CARD_KEYS = {"about", "min", "max", "mentions"}
_ID = re.compile(r"^F\d{2}$")


def parse_case(raw: dict[str, Any], *, source: str = "") -> FounderCase:
    """One case from its JSON, every rule checked. Raises `CaseError` naming the rule."""
    where = source or str(raw.get("case_id", "?"))
    _no_unknown(raw, _CASE_KEYS, where)
    _no_real_name(raw, where)

    case_id = str(raw.get("case_id", ""))
    if not _ID.match(case_id):
        raise CaseError(f"{where}: case_id {case_id!r} is not F<two digits>")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise CaseError(f"{where}: kind {kind!r} is not one of {KINDS}")
    labelled_by = raw.get("labelled_by")
    if labelled_by not in LABELLERS:
        raise CaseError(f"{where}: labelled_by {labelled_by!r} is not one of {LABELLERS}")
    label_row = raw.get("label_row")
    if not isinstance(label_row, int) or label_row < 1:
        raise CaseError(f"{where}: label_row must name a row of golden-labels.md")
    title = str(raw.get("title") or "").strip()
    if not title:
        raise CaseError(f"{where}: a case needs a title")

    f = raw.get("founder") or {}
    _no_unknown(f, {"name", "email", "company", "timezone", "also", "domains"}, f"{where}.founder")
    also = tuple(str(a).strip().lower() for a in f.get("also") or ())
    for address in also:
        if not _EMAIL.fullmatch(address):
            raise CaseError(f"{where}.founder.also: {address!r} is not an address")
    domains = tuple(str(d).strip().lower().lstrip("@").strip(".") for d in f.get("domains") or ())
    from genios_engine.platform.self_identity import PUBLIC_MAIL_DOMAINS
    for domain in domains:
        if not domain or "." not in domain or "@" in domain:
            raise CaseError(f"{where}.founder.domains: {domain!r} is not a domain")
        if domain in PUBLIC_MAIL_DOMAINS:
            raise CaseError(f"{where}.founder.domains: {domain} is a public mail domain — never "
                            "the company's own")
    founder = Founder(name=str(f.get("name", "")), email=str(f.get("email", "")).lower(),
                      company=str(f.get("company", "")), timezone=str(f.get("timezone", "UTC")),
                      also=also, domains=domains)
    if not (founder.name and _EMAIL.fullmatch(founder.email) and founder.company):
        raise CaseError(f"{where}: the founder needs a name, an address and a company")

    sweeps = tuple(_instant(s, f"{where}.sweeps") for s in raw.get("sweeps") or ())
    if not sweeps:
        raise CaseError(f"{where}: a case runs at least one sweep")
    if list(sweeps) != sorted(sweeps) or len(set(sweeps)) != len(sweeps):
        raise CaseError(f"{where}: sweeps are out of order or repeated")

    objects = tuple(_object(o, case_id, founder.email, sweeps, where)
                    for o in raw.get("objects") or ())
    if not objects:
        raise CaseError(f"{where}: a case hands the chain at least one object")
    ids = [o.object_id for o in objects]
    if len(set(ids)) != len(ids):
        raise CaseError(f"{where}: object ids repeat: {ids}")

    expected = raw.get("expected") or {}
    _no_unknown(expected, set(EXPECTATION_KEYS), f"{where}.expected")
    gate = dict(expected.get("gate") or {})
    for oid, verdict in gate.items():
        _known_object(oid, ids, where, "expected.gate")
        if str(verdict).split(":", 1)[0] not in GATE_OUTCOMES:
            raise CaseError(f"{where}: gate verdict {verdict!r} for {oid!r} is not one of "
                            f"{GATE_OUTCOMES} (optionally `:<code>`)")
    memory = dict(expected.get("memory") or {})
    for oid, reached in memory.items():
        _known_object(oid, ids, where, "expected.memory")
        if not isinstance(reached, bool):
            raise CaseError(f"{where}: expected.memory[{oid!r}] must be true or false")
    cards = tuple(_card(c, f"{where}.expected.cards") for c in expected.get("cards") or ())
    if kind == "must_detect" and not any(c.min >= 1 for c in cards):
        raise CaseError(f"{where}: a must_detect case expects at least one card (min >= 1)")
    if kind == "must_abstain" and not any(c.max == 0 for c in cards):
        raise CaseError(f"{where}: a must_abstain case names the card that must not exist "
                        "(max 0)")
    other = {k: str(expected[k]) for k in NOT_EXPRESSIBLE_TODAY if k in expected}

    not_expressible = {str(k): str(v) for k, v in (raw.get("not_expressible") or {}).items()}
    for key, reason in not_expressible.items():
        if key not in EXPECTATION_KEYS:
            raise CaseError(f"{where}: not_expressible names {key!r}, which is no expectation")
        if not reason.strip():
            raise CaseError(f"{where}: not_expressible[{key!r}] gives no reason")
    for key in other:
        if key not in not_expressible:
            raise CaseError(
                f"{where}: expects {key!r}, which the engine cannot express today "
                f"({NOT_EXPRESSIBLE_TODAY[key]}) — declare it in not_expressible with the reason")

    forbidden = raw.get("forbidden") or {}
    _no_unknown(forbidden, {"names", "phrases"}, f"{where}.forbidden")

    witness = None
    if raw.get("witness") is not None:
        w = raw["witness"]
        _no_unknown(w, {"stage", "objects", "about"}, f"{where}.witness")
        if w.get("stage") not in WITNESS_STAGES:
            raise CaseError(f"{where}: witness stage {w.get('stage')!r} is not one of "
                            f"{WITNESS_STAGES}")
        for oid in w.get("objects") or ():
            _known_object(oid, ids, where, "witness.objects")
        witness = Witness(stage=w["stage"], objects=tuple(w.get("objects") or ()),
                          about=tuple(w.get("about") or ()))
        if not (witness.objects or witness.about):
            raise CaseError(f"{where}: a witness names the objects or the subject it watches")
    if kind == "must_abstain" and witness is None:
        raise CaseError(f"{where}: a must_abstain case needs a witness — without one, 'no card' "
                        "passes on a chain that produced nothing at all")

    model = raw.get("model") or {}
    if not isinstance(model, dict):
        raise CaseError(f"{where}: model must be a mapping of site to answers")
    blocked_on = str(raw.get("blocked_on") or "").strip()
    if raw.get("blocked_on") is not None and len(blocked_on) < 20:
        raise CaseError(f"{where}: blocked_on names the finding or step that blocks the case, in "
                        "a sentence")

    return FounderCase(
        case_id=case_id, title=title, kind=kind, label_row=label_row, labelled_by=labelled_by,
        replays=tuple(str(r) for r in raw.get("replays") or ()), founder=founder, sweeps=sweeps,
        objects=objects, expected_gate=gate, expected_memory=memory, cards=cards,
        expected_other=other, forbidden_names=tuple(forbidden.get("names") or ()),
        forbidden_phrases=tuple(forbidden.get("phrases") or ()), witness=witness,
        not_expressible=not_expressible, model=model, blocked_on=blocked_on, source=source)


def load_cases(folder: Path = FOUNDER_DIR) -> tuple[FounderCase, ...]:
    """Every founder case under `folder`, in id order. Missing or empty is an error."""
    if not folder.is_dir():
        raise AssertionError(f"founder case folder missing: {folder}")
    files = sorted(folder.glob("*.json"))
    if not files:
        raise AssertionError(f"no founder cases under {folder} — an empty exam passes nothing")
    cases: dict[str, FounderCase] = {}
    for path in files:
        case = parse_case(json.loads(path.read_text(encoding="utf-8")), source=path.name)
        if case.case_id in cases:
            raise CaseError(f"{case.case_id} is claimed by both {cases[case.case_id].source} "
                            f"and {path.name}")
        cases[case.case_id] = case
    return tuple(cases[k] for k in sorted(cases))


def real_names_in(value: Any) -> list[str]:
    """Every deny-listed name in any string inside `value` (used on cassettes too)."""
    found: list[str] = []
    for text in _strings(value):
        found += [m.group(0) for m in _REAL.finditer(text)]
    return found


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────
def _object(raw: Any, case_id: str, owner: str, sweeps: tuple[datetime, ...],
            where: str) -> CaseObject:
    if not isinstance(raw, dict):
        raise CaseError(f"{where}: an object must be a mapping")
    oid = str(raw.get("id") or "")
    at = f"{where}.objects[{oid or '?'}]"
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", oid):
        raise CaseError(f"{at}: object id {oid!r} must be lower-case letters, digits, - or _")
    source = raw.get("source")
    if source not in SOURCES:
        raise CaseError(f"{at}: source {source!r} is not one of {SOURCES}")
    _no_unknown(raw, _GMAIL_KEYS if source == "gmail" else _GCAL_KEYS, at)
    sweep = raw.get("sweep")
    if not isinstance(sweep, int) or not 0 <= sweep < len(sweeps):
        raise CaseError(f"{at}: sweep {sweep!r} is not an index into the case's sweeps")
    occurred = _instant(raw.get("occurred_at"), f"{at}.occurred_at")
    if occurred > sweeps[sweep]:
        raise CaseError(f"{at}: occurred at {occurred.isoformat()}, after the sweep that reads "
                        f"it ({sweeps[sweep].isoformat()})")
    read = raw.get("read") or {}
    _no_unknown(read, set(READ_SITES), f"{at}.read")
    common = dict(object_id=oid, source=source, sweep=sweep, occurred_at=occurred,
                  case_id=case_id, owner=owner, read=read)
    if source == "gcal":
        for key in ("summary", "start", "end"):
            if not raw.get(key):
                raise CaseError(f"{at}: a calendar event needs {key!r}")
        for key in ("start", "end"):
            _instant(raw[key], f"{at}.{key}")
        event = {k: raw[k] for k in _GCAL_KEYS - {"id", "source", "sweep", "occurred_at", "read"}
                 if k in raw}
        return CaseObject(event=event, **common)
    for key in ("from", "subject", "body"):
        if not str(raw.get(key) or "").strip():
            raise CaseError(f"{at}: a Gmail message needs {key!r}")
    if not raw.get("to"):
        raise CaseError(f"{at}: a Gmail message needs at least one recipient")
    attachments = []
    for a in raw.get("attachments") or ():
        _no_unknown(a, {"filename", "mime", "fetch", "text"}, f"{at}.attachments")
        if a.get("fetch") not in FETCHES:
            raise CaseError(f"{at}: attachment fetch {a.get('fetch')!r} is not one of {FETCHES}")
        if a["fetch"] == "ok" and not str(a.get("text") or "").strip():
            raise CaseError(f"{at}: an attachment that downloads carries its text")
        attachments.append(Attachment(filename=str(a.get("filename") or ""),
                                      mime=str(a.get("mime") or ""), fetch=a["fetch"],
                                      text=str(a.get("text") or "")))
    headers = raw.get("headers") or {}
    if not isinstance(headers, dict):
        raise CaseError(f"{at}: headers must be a mapping of name to value")
    return CaseObject(
        sender=str(raw["from"]), to=tuple(raw.get("to") or ()), cc=tuple(raw.get("cc") or ()),
        thread=str(raw.get("thread") or ""), subject=str(raw["subject"]), body=str(raw["body"]),
        labels=tuple(raw.get("labels") or ()), headers=dict(headers),
        attachments=tuple(attachments), **common)


def _card(raw: Any, where: str) -> CardExpectation:
    if not isinstance(raw, dict):
        raise CaseError(f"{where}: a card expectation must be a mapping")
    _no_unknown(raw, _CARD_KEYS, where)
    about = tuple(str(t) for t in raw.get("about") or ())
    if not about:
        raise CaseError(f"{where}: a card expectation names its subject in `about`")
    lo, hi = raw.get("min"), raw.get("max")
    if not (isinstance(lo, int) and isinstance(hi, int) and 0 <= lo <= hi):
        raise CaseError(f"{where}: min and max must be integers with 0 <= min <= max")
    return CardExpectation(about=about, min=lo, max=hi,
                           mentions=tuple(str(t) for t in raw.get("mentions") or ()))


def _instant(value: Any, where: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as e:
        raise CaseError(f"{where}: {value!r} is not an ISO 8601 instant") from e
    if dt.tzinfo is None:
        raise CaseError(f"{where}: {value!r} has no timezone — a replay instant must be absolute")
    return dt


def _known_object(oid: str, ids: list[str], where: str, field_name: str) -> None:
    if oid not in ids:
        raise CaseError(f"{where}: {field_name} names {oid!r}, which is not an object of the case")


def _no_unknown(raw: Any, allowed: set[str], where: str) -> None:
    if not isinstance(raw, dict):
        raise CaseError(f"{where}: expected a mapping")
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise CaseError(f"{where}: unknown key(s) {unknown} — allowed: {sorted(allowed)}")


def _no_real_name(raw: Any, where: str) -> None:
    found = real_names_in(raw)
    if found:
        raise CaseError(f"{where}: real name(s) from the founder's mailbox {sorted(set(found))} "
                        "— a case is synthetic: invent the name")


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for k, v in value.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")
