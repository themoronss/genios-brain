"""The GeniOS Engine, read for ONE file — what its dossier is handed beside the data (STEP-13b).

`speedrun008/YC-II W27/` STEP-13b §8.4 item 1, tree `yc2_w27_s13b` M37.C2.L-integration.V3.U05. The three readers
this unit joins were built bottom-up and each is pure or read-only on its own: the Domain Expertise by ROUTE
(`packs/compiler/engine_reader.engine_for`), what the tenant's brains learned (`engine_reader.learned_for`) and the
Reasoning Expertise in SHADOW (`file_units.units_for`). This is the one place that hands them a FILE:

  * the file's SITUATIONS (their type and Layer 2 domain, from its lifecycle) and its KIND of work;
  * its ANCHOR's facts, as `reason/runner._load_context` reads them — and, because a company anchor holds almost no
    fact of its own (everything is extracted onto its people and threads), its people's facts BESIDE them, a 1-hop
    borrow that only fills what the anchor lacks, ROOT FIRST (`context_adapter._fact`'s own rule);
  * the tenant's switched-on corpora (`platform/l3_activation.activated_domains`) — a situation routed only to a
    corpus that is off is named so, not read.

THE ROUTE KEY IS CHEAP AND FOR EVERY FILE (no predicate, no unit, no database): the content hashes of what the file's
routes reach, for its fingerprint (M37.C5). THE READ ITSELF is for a file DUE for review only. A read that cannot be
made is "the engine could not be read for this file", counted by the caller, never a failed review: the expert is
then shown the data alone, as before.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from genios_engine.contracts import engine_read as E
from genios_engine.contracts.brain_address import token
from genios_engine.contracts.reasoning import ContextSnapshot
from genios_engine.packs.compiler import engine_reader as R
from genios_engine.platform.logging import get_logger
from genios_engine.reason.runner import _load_context

from .file_units import _sanitized_facts, units_for

_log = get_logger("genios.reason.expert.file_engine")

#: At most this many of the file's people are read for the facts the anchor lacks.
PEOPLE_READ = 10
#: What a dossier says of a file whose engine could not be read.
UNREAD = "the engine could not be read for this file"


@dataclass(frozen=True, slots=True)
class FileEngineParts:
    """What one file's dossier carries of the engine: the route key (always), and — for a due file whose read
    succeeded — the Domain Expertise with what the brains learned (`engine`), the units' readings (`units`)."""
    route_key: str
    engine: E.EngineRead | None = None
    units: E.EngineRead | None = None
    capabilities: tuple[str, ...] = ()
    error: str | None = None                 # `UNREAD` when the read was due and failed


def situations_of(lifecycle: Any) -> tuple[R.FileSituation, ...]:
    """The file's situations as the engine routes them: their type and Layer 2 domain."""
    return tuple(R.FileSituation(situation_type=s.situation_type, domain=s.domain, situation_id=s.situation_id)
                 for s in getattr(lifecycle, "situations", ()) or ())


def route_key_of(work: Any, lifecycle: Any, *, domains_on: frozenset[str] | None = None) -> str:
    """The file's route key — every file's, cheap. `none` when its routes reach nothing, or cannot be read."""
    try:
        return R.route_key(situations_of(lifecycle), kind=getattr(work, "work_kind", None), activated=domains_on)
    except Exception:      # noqa: BLE001 — a fingerprint input that cannot be computed names nothing
        _log.exception("could not compute the engine route key for file=%s", getattr(work, "file_id", None))
        return R.ROUTE_NONE


def _one_connection(conn: Any) -> Any:
    """`_load_context` opens `store.engine.connect()`; the dossier reads on ONE connection, so it is handed that."""
    return SimpleNamespace(engine=SimpleNamespace(connect=lambda: nullcontext(conn)))


def _anchor(conn: Any, org_id: str, work: Any) -> tuple[Any, dict[str, Any], tuple[str, ...]]:
    """The anchor's node context, the facts its people add beside it (the anchor's own win), and their kinds."""
    store = _one_connection(conn)
    node = _load_context(store, org_id, work.file_id, work.counterparty_type)
    borrowed: dict[str, Any] = {}
    seen_obs: set[str] = set()
    people = sorted(str(p) for p in (work.people or ()) if str(p) != str(work.file_id))[:PEOPLE_READ]
    for person in people:
        ctx = _load_context(store, org_id, person, "person")
        for field, record in ctx.facts.items():
            borrowed.setdefault(field, record)
        seen_obs.update(str(o.get("kind")) for o in ctx.obs if o.get("kind"))
    return node, borrowed, tuple(sorted(seen_obs))


def learned_tokens(work: Any, capabilities: Iterable[str]) -> tuple[str, ...]:
    """The file's own address tokens (`contracts/brain_address`): the file's node, its people, its counterparty's
    address, and the capabilities its engine read — what a published brain entry is addressed by."""
    out: list[str] = []
    candidates = [("node", work.file_id), *(("person", p) for p in (work.people or ())),
                  *((("company", work.file_id),) if work.counterparty_type == "company" else ()),
                  *((("email", work.counterparty_key),) if "@" in str(work.counterparty_key or "") else ()),
                  *(("capability", c) for c in capabilities)]
    for kind, value in candidates:
        try:
            tok = token(kind, value)
        except ValueError:
            continue
        if tok not in out:
            out.append(tok)
    return tuple(out)


def _merged(authored: E.EngineRead, learned: E.EngineRead) -> E.EngineRead:
    """The authored read and what the brains learned, one read: families in their one order, the cuts summed."""
    lines = sorted((*authored.lines, *learned.lines), key=lambda line: E.FAMILIES.index(line.family))
    cut = {family: authored.cut.get(family, 0) + learned.cut.get(family, 0) for family in E.FAMILIES}
    return E.EngineRead(lines=tuple(lines), cut=cut, may_apply=authored.may_apply, not_read=authored.not_read)


def read_file_engine(conn: Any, org_id: str, work: Any, lifecycle: Any, *, now: datetime,
                     domains_on: frozenset[str] | None = None) -> FileEngineParts:
    """The engine read for one DUE file, on the dossier's connection. Never raises: a failure is `UNREAD`."""
    key = route_key_of(work, lifecycle, domains_on=domains_on)
    try:
        node, borrowed, borrowed_obs = _anchor(conn, org_id, work)
        anchor = R.Anchor(facts=node.facts, neighbor_facts=borrowed, observations=tuple(
            sorted({str(o.get("kind")) for o in node.obs if o.get("kind")})), neighbor_observations=borrowed_obs,
            edge_count=len(work.people or ()), evaluation_time=now)
        authored = R.engine_for(situations_of(lifecycle), kind=getattr(work, "work_kind", None),
                                activated=domains_on, anchor=anchor)
        learned = R.learned_for(conn, org_id=org_id, tokens=learned_tokens(work, authored.capabilities),
                                eval_time=now)
        merged_facts: Mapping[str, Any] = {**borrowed, **node.facts}      # root first: the anchor's own win
        context = ContextSnapshot(
            org_id=org_id, graph_version=0, root_entity_id=work.file_id, root_entity_type=work.counterparty_type,
            evaluation_time=now, selector_version="shadow-v1", facts=_sanitized_facts(merged_facts),
            observations=tuple(node.obs), neighbor_observations=borrowed_obs,
            edge_count=len(work.people or ()))
        return FileEngineParts(route_key=key, engine=_merged(authored.read, learned),
                               units=units_for(context), capabilities=authored.capabilities)
    except Exception:      # noqa: BLE001 — a file whose engine cannot be read is reviewed on its data alone
        _log.exception("could not read the engine for org=%s file=%s", org_id, getattr(work, "file_id", None))
        return FileEngineParts(route_key=key, error=UNREAD)


__all__ = ["FileEngineParts", "PEOPLE_READ", "UNREAD", "learned_tokens", "read_file_engine", "route_key_of",
           "situations_of"]
