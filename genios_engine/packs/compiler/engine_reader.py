"""What the GeniOS Engine knows about ONE file — the Domain Expertise of its situations and its kind (STEP-13b).

`speedrun008/YC-II W27/` STEP-13b §8.4 item 1, tree `yc2_w27_s13b` M37.C2.L-logic.V1.U01 (`engine_for`).
Measured 12 Oct: the expert reads only its KIND's playbook (`playbook_reader.playbook_for`, 22 of 94 authored
answers' files); 26 answers' files hold an investor situation and print no playbook (`03` s13b-F8); no
capability's doctrine — its question, its failure modes — is printed anywhere (s13b-F9); and the compiled
lane never reaches a covered or a held file (s13b-F7: 3 of 33 admission decisions admitted on six cases).

READ BY ROUTE, NOT THROUGH THE PUBLISHER. A held situation is still the file's. For each of the file's
situations (its type and its Layer 2 domain), the corpus situations the authored registries route it to —
narrowed by its domain exactly as `capability_resolver.CapabilityResolver.resolve` narrows it (`DOMAIN_
ALIASES`; an unclassified domain looks everywhere) — in the corpora the tenant switched ON. Each one's
`matches.when` is read by the compiler's own three-state evaluator (`ContextAdapter.matches`) over the
file ANCHOR's facts:

  TRUE     its owner capability's question and failure modes (`cap:`), its signals of progress and decay
           (`sig:`), the capability's playbooks and heuristics (`pb:`), its rules (`rule:`) and each rule's
           compiled constraint with the verdict its `when` reads on this anchor (`cons:` holds · fails ·
           unknown), its mental models and decision frameworks (`frame:`);
  UNKNOWN  named as MAY APPLY, with what it could not read — never shown unchecked;
  FALSE    nothing.

With no anchor read at all, every conditional predicate is UNKNOWN (the risk STEP-13b §8.7 names): only
the unconditional routes print. A situation routed only to a switched-off corpus, a type no registry
routes and a domain no corpus authors are each named (`NotRead`).

THE KIND. For the file's kind of work (`06` D31), the kind's capability (`playbook_reader.KIND_CAPABILITY`)
is read whatever is switched on — the dossier already reads its playbook so — and its playbooks and
heuristics are NOT repeated: they are the dossier's WHAT A PROFESSIONAL KNOWS (`pb:`), printed once.

READ, NEVER GATED (`06` D3, D-s13b-6). Admission gates what may carry authority on a card, not what the
expert may read: every line says whether a named human reviewed it, by the corpus's own ceremony
(`_admission_reason` for a capability, `situation_admission_reason`, `artifact_admission_reason`), and an
unreviewed one is labelled. Bounded per family (`LIMITS`), each line at `LINE_CHARS`, every cut counted.

THE ROUTE KEY (`route_key`) — the content hashes of every corpus situation, capability and artifact the
file's routes reach, no predicate read — is cheap, so a file's fingerprint can name the engine it reads
without reading it (M37.C5). Pure over the catalog: no database, no clock, no model.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from sqlalchemy import text

from genios_engine.contracts import engine_read as E
from genios_engine.contracts.domain_expertise import BrainKind
from genios_engine.platform.canonical import semantic_hash

from .authoring import ExpertBrainCatalog
from .capability_resolver import (DOMAIN_ALIASES, UNCLASSIFIED_DOMAINS, _admission_reason,
                                  artifact_admission_reason, situation_admission_reason)
from .context_adapter import ContextAdapter, PredicateState
from .playbook_reader import KIND_CAPABILITY, _shipped_catalog, _steps, _text
from .runtime_brains import _entry_from_l6_row, _entry_from_lease_row

#: The most lines a family shows for one file; the rest are counted in `EngineRead.cut`.
LIMITS: Mapping[str, int] = MappingProxyType({
    E.CAPABILITY: 28, E.SIGNALS: 6, E.PLAYBOOK: 16, E.RULE: 8, E.CONSTRAINT: 8, E.FRAME: 8})
#: The most characters one line carries, cut on a word.
LINE_CHARS = 360
#: The route key of a file whose routes reach nothing.
ROUTE_NONE = "none"

#: The predicate inputs a constraint names when no anchor was read at all.
NO_ANCHOR = "the anchor's facts were not read"

_FRAME_KEYS = ("mental_models", "decision_frameworks")

#: Which `EngineRead` family a published brain kind becomes (`contracts.engine_read.FAMILIES`).
_BRAIN_FAMILY: Mapping[BrainKind, str] = MappingProxyType({
    BrainKind.ORGANIZATION: E.ORGANIZATION, BrainKind.BEHAVIOR: E.BEHAVIOUR,
    BrainKind.ADAPTIVE: E.ADAPTIVE})



@dataclass(frozen=True, slots=True)
class FileSituation:
    """One of the file's situations as the dossier has it: its type and its Layer 2 domain."""
    situation_type: str
    domain: str
    situation_id: str | None = None


@dataclass(frozen=True, slots=True)
class Anchor:
    """The file anchor's facts as the reasoning context holds them (`reason/runner._load_context`) —
    what a corpus predicate is read over. A fact is its record (`{"value": …}`) or its bare value."""
    facts: Mapping[str, Any] = field(default_factory=dict)
    neighbor_facts: Mapping[str, Any] = field(default_factory=dict)
    observations: tuple[str, ...] = ()
    neighbor_observations: tuple[str, ...] = ()
    edge_count: int | None = None
    evaluation_time: datetime | None = None


@dataclass(frozen=True, slots=True)
class FileEngine:
    """The engine one file reads, the key of its routes, and what applied."""
    read: E.EngineRead
    route_key: str
    capabilities: tuple[str, ...] = ()     # the capabilities read, the kind's first
    situations: tuple[str, ...] = ()       # the corpus situations that applied


class _AnchorFacts:
    """The anchor in the one shape `ContextAdapter` reads with no context slice: its `metadata`. No
    published situation is needed to ask a predicate (STEP-13b §8.7)."""

    def __init__(self, anchor: Anchor) -> None:
        self.org_id = "file"
        self.entities: tuple = ()
        self.metadata = {
            "facts": dict(anchor.facts), "neighbor_facts": dict(anchor.neighbor_facts),
            "observations": list(anchor.observations),
            "neighbor_observations": list(anchor.neighbor_observations),
            "edge_count": anchor.edge_count, "evaluation_time": anchor.evaluation_time}


def _cut(words: Any) -> str:
    text = " ".join(str(words or "").split())
    if len(text) <= LINE_CHARS:
        return text
    head = text[:LINE_CHARS]
    if text[LINE_CHARS] != " " and " " in head:
        head = head.rsplit(" ", 1)[0]
    return head.rstrip(" ,;:") + "…"


def _ids(manifest: Mapping[str, Any] | None, key: str) -> list[str]:
    block = (manifest or {}).get(key) or {}
    return sorted({str(i) for part in ("core", "scoped") for i in (block.get(part) or ())})


def _name(content: Mapping[str, Any], fallback: str) -> str:
    return _text((content.get("identity") or {}).get("name")) or fallback


class _Lines:
    """The lines of one read, per family, each ref once, bounded, the cut counted."""

    def __init__(self, limits: Mapping[str, int]) -> None:
        self.limits = {**LIMITS, **limits}
        self.by_family: dict[str, list[E.EngineLine]] = {f: [] for f in E.FAMILIES}
        self.cut: dict[str, int] = dict.fromkeys(E.FAMILIES, 0)
        self.seen: set[str] = set()

    def add(self, family: str, ref: str, words: Any, *, source: str, version: str, reviewed: bool,
            verdict: str | None = None) -> None:
        text = _cut(words)
        if ref in self.seen or not text:
            return
        self.seen.add(ref)
        if len(self.by_family[family]) >= self.limits.get(family, 10 ** 6):
            self.cut[family] += 1
            return
        self.by_family[family].append(E.EngineLine(ref=ref, family=family, words=text, source=source,
                                                   source_version=version, reviewed=reviewed,
                                                   verdict=verdict))

    def lines(self) -> tuple[E.EngineLine, ...]:
        return tuple(line for family in E.FAMILIES for line in self.by_family[family])


def _route(catalog: ExpertBrainCatalog, situation: FileSituation, activated: frozenset[str] | None):
    """`(live routes, not read)` for one situation: each live route a `(domain, corpus situation id)`."""
    hint = DOMAIN_ALIASES.get(situation.domain, situation.domain)
    if situation.domain in UNCLASSIFIED_DOMAINS:
        domains = sorted(catalog.domains)
    elif hint not in catalog.domains:
        return [], E.NotRead(situation_type=situation.situation_type, domain=situation.domain,
                             reason=E.UNKNOWN_DOMAIN)
    else:
        domains = [hint]
    routed = [d for d in domains if isinstance(catalog.domain(d).routes.get(situation.situation_type),
                                               Mapping)]
    if not routed:
        return [], E.NotRead(situation_type=situation.situation_type, domain=situation.domain,
                             reason=E.NO_ROUTE)
    live = [d for d in routed if activated is None or d in activated]
    if not live:
        return [], E.NotRead(situation_type=situation.situation_type, domain=situation.domain,
                             reason=E.SWITCHED_OFF, corpora=tuple(routed))
    return [(d, str(sid)) for d in live
            for sid in (catalog.domain(d).routes[situation.situation_type].get("situations") or ())], None


def _capability(catalog: ExpertBrainCatalog, capability_id: str | None):
    if not capability_id:
        return None, None
    domain = catalog.domains.get(capability_id.split(".", 1)[0])
    capability = domain.capabilities.get(capability_id) if domain is not None else None
    if capability is None or (capability.content.get("identity") or {}).get("stub"):
        return None, None
    return domain, capability


def _verdict(adapter: ContextAdapter | None, conditions) -> tuple[PredicateState, tuple[str, ...]]:
    if not conditions:
        return PredicateState.TRUE, ()
    if adapter is None:
        return PredicateState.UNKNOWN, (NO_ANCHOR,)
    verdict = adapter.matches(conditions)
    return verdict.state, tuple(verdict.missing)


def _read_capability(out: _Lines, domain, capability, adapter: ContextAdapter | None, *,
                     playbooks: bool) -> None:
    content, cid = capability.content, capability.id
    reviewed = _admission_reason(capability) is None
    if content.get("question"):
        out.add(E.CAPABILITY, f"cap:{cid}#q", content.get("question"), source=cid,
                version=capability.content_hash, reviewed=reviewed)
    for n, failure in enumerate(content.get("failure_modes") or (), start=1):
        out.add(E.CAPABILITY, f"cap:{cid}#f{n}", failure, source=cid,
                version=capability.content_hash, reviewed=reviewed)
    manifest = domain.knowledge_manifests[cid].content if cid in domain.knowledge_manifests else {}
    if playbooks:
        for pid in _ids(manifest, "playbooks"):
            doc = domain.artifacts.get(pid)
            if doc is not None:
                steps = "; ".join(_steps(doc.content))
                out.add(E.PLAYBOOK, f"pb:{pid}", _name(doc.content, pid) + (f": {steps}" if steps else ""),
                        source=pid, version=doc.content_hash,
                        reviewed=artifact_admission_reason(doc.content) is None)
        for hid in _ids(manifest, "heuristics"):
            doc = domain.artifacts.get(hid)
            heuristic = (doc.content.get("heuristic") or {}) if doc is not None else {}
            statement, why = _text(heuristic.get("statement")), _text(heuristic.get("why"))
            if statement:
                out.add(E.PLAYBOOK, f"pb:{hid}", statement + (f" — why: {why}" if why else ""),
                        source=hid, version=doc.content_hash,
                        reviewed=artifact_admission_reason(doc.content) is None)
    for rid in _ids(manifest, "rules"):
        doc = domain.artifacts.get(rid)
        rule = (doc.content.get("rule") or {}) if doc is not None else {}
        statement = _text(rule.get("statement"))
        if not statement:
            continue
        reviewed_rule = artifact_admission_reason(doc.content) is None
        out.add(E.RULE, f"rule:{rid}", statement, source=rid, version=doc.content_hash,
                reviewed=reviewed_rule)
        if rule.get("when"):
            state, missing = _verdict(adapter, rule.get("when"))
            then = _text(rule.get("then"))
            words = {PredicateState.TRUE: "its condition holds on this file" + (f" — then: {then}" if then
                                                                                else ""),
                     PredicateState.FALSE: "its condition does not hold on this file",
                     PredicateState.UNKNOWN: "this file's facts cannot say whether its condition holds"
                                             + (f" — not read: {', '.join(missing)}" if missing else "")}
            out.add(E.CONSTRAINT, f"cons:{rid}", words[state], source=rid, version=doc.content_hash,
                    reviewed=reviewed_rule,
                    verdict={PredicateState.TRUE: E.HOLDS, PredicateState.FALSE: E.FAILS,
                             PredicateState.UNKNOWN: E.UNKNOWN}[state])
    for key in _FRAME_KEYS:
        for fid in _ids(manifest, key):
            doc = domain.artifacts.get(fid)
            if doc is None:
                continue
            statement = _text((doc.content.get("purpose") or {}).get("statement"))
            out.add(E.FRAME, f"frame:{fid}", _name(doc.content, fid) + (f": {statement}" if statement else ""),
                    source=fid, version=doc.content_hash,
                    reviewed=artifact_admission_reason(doc.content) is None)


def _signals(out: _Lines, document) -> None:
    content = document.content
    progress = [str(s) for s in content.get("signals_of_progress") or ()]
    decay = [str(s) for s in content.get("signals_of_decay") or ()]
    if not (progress or decay):
        return
    words = "; ".join(part for part in (
        f"progress: {', '.join(progress)}" if progress else "",
        f"decay: {', '.join(decay)}" if decay else "") if part)
    out.add(E.SIGNALS, f"sig:{document.id}", f"{_name(content, document.id)} — {words}",
            source=document.id, version=document.content_hash,
            reviewed=situation_admission_reason(content) is None)


def engine_for(situations: Iterable[FileSituation], *, kind: str | None,
               activated: frozenset[str] | None, anchor: Anchor | None = None,
               catalog: ExpertBrainCatalog | None = None,
               limits: Mapping[str, int] | None = None) -> FileEngine:
    """The Domain Expertise one file reads — see the module docstring. `activated` is the tenant's
    switched-on corpora (`None`: every authored corpus, for a measurement with no tenant behind it)."""
    catalog = catalog or _shipped_catalog()
    situations = tuple(situations)
    adapter = ContextAdapter(_AnchorFacts(anchor)) if anchor is not None else None
    out = _Lines(limits or {})
    not_read: list[E.NotRead] = []
    may_apply: list[E.MayApply] = []
    applied: list[str] = []
    capabilities: list[str] = []
    kind_capability = KIND_CAPABILITY.get(kind) if kind else None
    domain, capability = _capability(catalog, kind_capability)
    if capability is not None:
        capabilities.append(capability.id)
    reads: list[tuple[Any, Any, bool]] = ([(domain, capability, False)] if capability is not None else [])
    for situation in situations:
        routes, missed = _route(catalog, situation, activated)
        if missed is not None:
            not_read.append(missed)
        for domain_id, sid in routes:
            if sid in applied or any(m.situation == sid for m in may_apply):
                continue
            document = catalog.domain(domain_id).situations[sid]
            owner = (document.content.get("identity") or {}).get("owner_capability")
            state, missing = _verdict(adapter, (document.content.get("matches") or {}).get("when"))
            if state is PredicateState.UNKNOWN:
                may_apply.append(E.MayApply(situation=sid, capability=owner, missing=missing))
                continue
            if state is not PredicateState.TRUE:
                continue
            applied.append(sid)
            _signals(out, document)
            dom, cap = _capability(catalog, owner)
            if cap is not None and cap.id not in capabilities:
                capabilities.append(cap.id)
                reads.append((dom, cap, cap.id != kind_capability))
    for dom, cap, playbooks in reads:
        _read_capability(out, dom, cap, adapter, playbooks=playbooks)
    read = E.EngineRead(lines=out.lines(), cut=out.cut, may_apply=tuple(may_apply),
                        not_read=tuple(not_read))
    return FileEngine(read=read, route_key=route_key(situations, kind=kind, activated=activated,
                                                     catalog=catalog),
                      capabilities=tuple(capabilities), situations=tuple(applied))


def route_key(situations: Sequence[FileSituation], *, kind: str | None, activated: frozenset[str] | None,
              catalog: ExpertBrainCatalog | None = None) -> str:
    """The content hashes of everything the file's routes and kind can reach — no predicate read, so it
    is cheap for every file. `ROUTE_NONE` when they reach nothing."""
    catalog = catalog or _shipped_catalog()
    reached: dict[str, str] = {}
    owners: list[str | None] = [KIND_CAPABILITY.get(kind) if kind else None]
    for situation in situations:
        routes, _missed = _route(catalog, situation, activated)
        for domain_id, sid in routes:
            document = catalog.domain(domain_id).situations[sid]
            reached[sid] = document.content_hash
            owners.append((document.content.get("identity") or {}).get("owner_capability"))
    for owner in owners:
        domain, capability = _capability(catalog, owner)
        if capability is None:
            continue
        reached[capability.id] = capability.content_hash
        manifest = domain.knowledge_manifests.get(capability.id)
        for key in ("playbooks", "heuristics", "rules", *_FRAME_KEYS):
            for aid in _ids(manifest.content if manifest is not None else None, key):
                doc = domain.artifacts.get(aid)
                if doc is not None:
                    reached[aid] = doc.content_hash
    if not reached:
        return ROUTE_NONE
    return "route-" + semantic_hash(sorted(reached.items()))[:12]


def _learned_words(entry) -> str:
    """The producer's own sentence (`statement`, or Behaviour's `pattern_statement`), its
    confidence and since when it has stood. Never the module's own words about the entry — a
    learned line is the company's own history, not a reading of it."""
    statement = _text(entry.value.get("statement")) or _text(entry.value.get("pattern_statement"))
    words = statement or entry.subject_key
    pct = entry.confidence_bp / 100
    tail = f"confidence {pct:g}%, since {entry.effective_at.date().isoformat()}"
    return f"{words} — {tail}"


def learned_for(connection, *, org_id: str, tokens: Iterable[str],
                eval_time: datetime | None = None, limits: Mapping[str, int] | None = None) -> E.EngineRead:
    """What the tenant's Organization, Behaviour and Adaptive brains hold for a file — see the
    module docstring's family table (`org:`, `pat:`, `pref:`) and STEP-13b §8.4 item 1.

    `tokens` are the file's own address tokens (`contracts/brain_address`) — the vocabulary a
    published entry's `value.address.tokens` speaks, not a `BusinessSituationObject`'s: a file is
    not a compiled situation and has none to build one from. An Organization rule is tenant-wide
    and is read whatever tokens are given (`06` D3: an approved policy binds everywhere); a
    Behaviour pattern or an Adaptive entry binds only where a token matches its address, or, for a
    row published before an address existed, its raw `subject` (the same legacy fallback
    `PostgresRuntimeBrains.snapshot` keeps, for the same reason).

    `eval_time` gates the Adaptive LEASE store (`temporary_memories`) alone, pinned to the
    caller's own frozen clock, never `now()`: with none given, no lease is read at all, exactly as
    `PostgresRuntimeBrains` already refuses to invent one rather than fall back to the wall clock.

    Read, never gated (`06` D3, D-s13b-6): every line is `reviewed=True` — the company's own
    history is not a corpus draft awaiting one — though `EngineLine.label` carries the
    `NOT_REVIEWED` word to no family but `AUTHORED`, so this changes nothing a reader sees. Issues
    no insert, update or delete (`tests/packs/test_the_engine_reader_writes_nothing.py`).
    """
    out = _Lines(limits or {})
    token_list = sorted({str(t) for t in tokens})
    rows = connection.execute(text(
        "select org_id, brain, subject, version, value, learning_id, created_at, visibility "
        "from learned_brain_entries "
        "where org_id=:o and active and brain in ('organization','behavior','adaptive') "
        "and (brain='organization' or subject=any(cast(:tokens as text[])) "
        "or jsonb_exists_any(coalesce(value->'address'->'tokens', '[]'::jsonb), cast(:tokens as text[]))) "
        "order by brain, subject, version"),
        {"o": org_id, "tokens": token_list}).mappings().all()
    for row in rows:
        entry = _entry_from_l6_row(row)
        family = _BRAIN_FAMILY[entry.brain]
        out.add(family, f"{E.PREFIX[family]}{entry.entry_id}", _learned_words(entry),
                source=entry.entry_id, version=str(entry.version), reviewed=True)
    if eval_time is not None and token_list:
        lease_rows = connection.execute(text(
            "select memory_id, subject, value, learning_id, created_at, visibility, expires_at "
            "from temporary_memories "
            "where org_id=:o and active and expires_at > :at "
            "and (subject=any(cast(:tokens as text[])) "
            "or jsonb_exists_any(coalesce(value->'address'->'tokens', '[]'::jsonb), cast(:tokens as text[])))"
            "order by subject, memory_id"),
            {"o": org_id, "tokens": token_list, "at": eval_time}).mappings().all()
        for row in lease_rows:
            entry = _entry_from_lease_row(row, org_id=org_id)
            out.add(E.ADAPTIVE, f"{E.PREFIX[E.ADAPTIVE]}{entry.entry_id}", _learned_words(entry),
                    source=entry.entry_id, version=str(entry.version), reviewed=True)
    return E.EngineRead(lines=out.lines(), cut=out.cut)


__all__ = ["Anchor", "FileEngine", "FileSituation", "LIMITS", "LINE_CHARS", "NO_ANCHOR", "ROUTE_NONE",
           "engine_for", "learned_for", "route_key"]
