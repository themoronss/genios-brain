#!/usr/bin/env python3
r"""The founder's review sheet for one kind of work — line by line, then the admission stamp (`06` D45).

    .venv/bin/python scripts/playbook_review_sheet.py sheet --kind program > program.review.yaml
    # the founder marks every line: decision: accept | edit | reject   (and a note for an edit)
    .venv/bin/python scripts/playbook_review_sheet.py apply program.review.yaml --reviewer rohit

WHAT IS ON THE SHEET. Every line a professional would have to stand behind, for the capability a kind
of work reads (`packs/compiler/playbook_reader.KIND_CAPABILITY`): the capability's description,
question, outcomes, failure modes and measures; each playbook's purpose, triggers, steps, STAGES (each
with its typical duration as a prior and that prior's source), success signal, outcome window, what
doing nothing costs and when to stop; each heuristic's claim and why; each situation's description and
do-nothing sentence; each object's purpose. One line, one decision. Each line carries a fingerprint of
its words, so a sheet filled in for yesterday's text cannot accept today's.

WHAT `apply` DOES — AND REFUSES. Nothing is admitted until EVERY line says `accept`: an `edit` or a
`reject` is listed back, with its note, for the author to change, and nothing is written (exit 1). A
sheet whose fingerprints no longer match the corpus is refused whole (exit 2): regenerate it. When
every line is accepted, each reviewed file is marked as the corpus's ceremony asks — `identity.status:
stable`, `metadata.review_status: approved`, `metadata.reviewed_by: <reviewer>`, `metadata.reviewed_at`
— and the capability and its situations are stamped with `_tools/admit.py`'s own hash, the one the
resolver checks. The tool never decides a line; it records the founder's decision and refuses to stamp
on anything less.

Files are edited line by line, never re-serialised, so the authors' comments and layout survive; a file
whose `status`/`review_status`/`reviewed_by` line cannot be found exactly once is refused before
anything is written.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root  # noqa: E402
from genios_engine.packs.compiler.capability_resolver import (  # noqa: E402
    _admission_reason, artifact_admission_reason, situation_admission_reason)
from genios_engine.packs.compiler.playbook_reader import DOMAIN, KIND_CAPABILITY  # noqa: E402

DECISIONS = ("accept", "edit", "reject")


@dataclass(frozen=True, slots=True)
class Line:
    id: str
    file: str            # relative to the corpus root
    artifact: str
    field: str
    text: str

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(f"{self.artifact}\0{self.field}\0{self.text}".encode()).hexdigest()[:16]


def _fold(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _items(values: Any) -> list[Any]:
    return list(values) if isinstance(values, (list, tuple)) else []


def _capability_lines(doc) -> Iterable[tuple[str, str]]:
    c = doc.content
    for key in ("description", "question"):
        if _fold(c.get(key)):
            yield key, _fold(c.get(key))
    for key in ("outcomes", "failure_modes"):
        for i, item in enumerate(_items(c.get(key)), 1):
            yield f"{key}[{i}]", _fold(item)
    for i, kpi in enumerate(_items(c.get("kpis")), 1):
        if isinstance(kpi, Mapping):
            yield f"kpis[{i}]", _fold(f"{kpi.get('name')} ({kpi.get('direction')}): {kpi.get('description')}")


def _stage(stage: Mapping[str, Any]) -> str:
    parts = [f"{stage.get('label') or stage.get('name')} [{stage.get('name')}]: typically "
             f"{stage.get('typical_duration_days')} days — a prior; source: {stage.get('source')}"]
    if stage.get("quiet_means"):
        parts.append(f"quiet means: {stage['quiet_means']}")
    if stage.get("leaves_when"):
        parts.append(f"leaves when: {stage['leaves_when']}")
    return _fold("; ".join(parts))


def _artifact_lines(doc) -> Iterable[tuple[str, str]]:
    c = doc.content
    if _fold((c.get("purpose") or {}).get("statement")):
        yield "purpose", _fold(c["purpose"]["statement"])
    use = c.get("when_to_use") or {}
    for key in ("signals", "do_not_use_when"):
        for i, item in enumerate(_items(use.get(key)), 1):
            yield f"when_to_use.{key}[{i}]", _fold(item)
    for i, step in enumerate(_items(c.get("steps")), 1):
        if isinstance(step, Mapping):
            text = _fold(step.get("name"))
            if step.get("description"):
                text += f" — {_fold(step['description'])}"
            if step.get("done_when"):
                text += f" (done when: {_fold(step['done_when'])})"
            yield f"steps[{i}]", text
    for i, stage in enumerate(_items(c.get("stages")), 1):
        if isinstance(stage, Mapping):
            yield f"stages[{i}]", _stage(stage)
    for key in ("success_signal", "do_nothing_consequence"):
        if _fold(c.get(key)):
            yield key, _fold(c.get(key))
    if c.get("outcome_window_days") is not None:
        yield "outcome_window_days", f"wait {c['outcome_window_days']} days for the success signal"
    stop = c.get("stop")
    if isinstance(stop, Mapping):
        yield "stop", _fold(f"dormant after {stop.get('dormant_after_days')} quiet days — a prior; "
                            f"source: {stop.get('source')}; then: {stop.get('then')}")
    heuristic = c.get("heuristic")
    if isinstance(heuristic, Mapping):
        for key, value in heuristic.items():
            if isinstance(value, str) and _fold(value):
                yield f"heuristic.{key}", _fold(value)


def _situation_lines(doc) -> Iterable[tuple[str, str]]:
    c = doc.content
    for key in ("description", "do_nothing_consequence"):
        if _fold(c.get(key)):
            yield key, _fold(c.get(key))


def _object_lines(doc) -> Iterable[tuple[str, str]]:
    c = doc.content
    for key in ("description",):
        if _fold(c.get(key)):
            yield key, _fold(c.get(key))
    if _fold((c.get("purpose") or {}).get("statement") if isinstance(c.get("purpose"), Mapping)
             else c.get("purpose")):
        purpose = c.get("purpose")
        yield "purpose", _fold(purpose.get("statement") if isinstance(purpose, Mapping) else purpose)


def scope(catalog: ExpertBrainCatalog, capability_id: str) -> dict[str, list]:
    """The documents a review of this capability covers, by kind, in a stable order."""
    record = catalog.domain(DOMAIN)
    capability = record.capabilities[capability_id]
    knowledge = record.knowledge_manifests[capability_id].content
    artifact_ids = sorted({str(i) for key in ("playbooks", "heuristics", "mental_models", "rules",
                                              "decision_frameworks")
                           for part in ("core", "scoped")
                           for i in ((knowledge.get(key) or {}).get(part) or ())})
    manifest = record.object_manifests[capability_id].content
    object_ids = sorted({str(i) for part in ("core", "scoped") for key in ("required", "optional")
                         for i in ((manifest.get(part) or {}).get(key) or ())})
    situations = sorted((doc for doc in record.situations.values()
                         if (doc.content.get("identity") or {}).get("owner_capability") == capability_id),
                        key=lambda d: d.id)
    return {"capability": [capability],
            "artifact": [record.artifacts[i] for i in artifact_ids if i in record.artifacts],
            "situation": situations,
            "object": [record.objects[i] for i in object_ids if i in record.objects]}


def lines_for(catalog: ExpertBrainCatalog, capability_id: str) -> list[Line]:
    readers = {"capability": _capability_lines, "artifact": _artifact_lines,
               "situation": _situation_lines, "object": _object_lines}
    out: list[Line] = []
    for kind, docs in scope(catalog, capability_id).items():
        for doc in docs:
            for field, text in readers[kind](doc):
                out.append(Line(id=f"L{len(out) + 1:03d}", file=doc.relative_path, artifact=doc.id,
                                field=field, text=text))
    return out


def sheet(catalog: ExpertBrainCatalog, kind: str) -> dict[str, Any]:
    capability_id = KIND_CAPABILITY.get(kind)
    if not capability_id:
        raise SystemExit(f"no capability reads the kind {kind!r}")
    return {"kind": kind, "capability": capability_id,
            "how": "For every line set decision to accept, edit or reject; give an edit or a reject a "
                   "note. Nothing is admitted until every line is accepted (06 D45).",
            "lines": [{"id": l.id, "artifact": l.artifact, "field": l.field, "text": l.text,
                       "fingerprint": l.fingerprint, "decision": "", "note": ""}
                      for l in lines_for(catalog, capability_id)]}


def _mark(text: str, path: Path, reviewer: str, today: str) -> str:
    """The file with its review recorded, edited line by line. Refuses a file it cannot edit exactly."""
    out = text.splitlines(keepends=True)
    block = None
    seen = {"status": 0, "review_status": 0, "reviewed_by": 0, "reviewed_at": 0}
    metadata_end = None
    for i, line in enumerate(out):
        stripped = line.rstrip("\n")
        if stripped and not stripped.startswith((" ", "#")):
            block = stripped.split(":", 1)[0]
            if block == "metadata":
                metadata_end = i + 1
            continue
        if block == "metadata" and stripped.startswith("  "):
            metadata_end = i + 1
        key = stripped.strip().split(":", 1)[0]
        if block == "identity" and stripped.startswith("  status:"):
            out[i] = "  status: stable\n"; seen["status"] += 1
        elif block == "metadata" and key in ("review_status", "reviewed_by", "reviewed_at") \
                and stripped.startswith(f"  {key}:"):
            value = {"review_status": "approved", "reviewed_by": reviewer,
                     "reviewed_at": f'"{today}"'}[key]
            out[i] = f"  {key}: {value}\n"; seen[key] += 1
    if seen["status"] != 1 or seen["review_status"] != 1 or metadata_end is None:
        raise SystemExit(f"refused: {path} has no single identity.status and metadata.review_status "
                         "line to record the review on — nothing was written")
    extra = []
    if seen["reviewed_by"] == 0:
        extra.append(f"  reviewed_by: {reviewer}\n")
    if seen["reviewed_at"] == 0:
        extra.append(f'  reviewed_at: "{today}"\n')
    if seen["reviewed_by"] > 1 or seen["reviewed_at"] > 1:
        raise SystemExit(f"refused: {path} names its reviewer twice — nothing was written")
    return "".join(out[:metadata_end] + extra + out[metadata_end:])


def apply(catalog: ExpertBrainCatalog, root: Path, filled: Mapping[str, Any], reviewer: str,
          today: str | None = None) -> int:
    reviewer = str(reviewer or "").strip()
    if not reviewer:
        raise SystemExit("a review needs a named reviewer (--reviewer)")
    capability_id = str(filled.get("capability") or "")
    current = {l.fingerprint: l for l in lines_for(catalog, capability_id)}
    given = {str(row.get("fingerprint")): row for row in (filled.get("lines") or [])}
    if set(current) != set(given):
        print(f"STALE: the corpus changed since this sheet was made ({len(set(current) - set(given))} "
              f"lines new or edited, {len(set(given) - set(current))} gone) — regenerate it.")
        return 2
    open_lines = [row for row in given.values() if row.get("decision") != "accept"]
    if open_lines:
        for row in sorted(open_lines, key=lambda r: str(r.get("id"))):
            decision = row.get("decision") or "(no decision)"
            print(f"  {row.get('id')}  {decision:<14} {row.get('artifact')} · {row.get('field')}"
                  f"{' — ' + str(row['note']) if row.get('note') else ''}")
        print(f"NOT ADMITTED: {len(open_lines)} of {len(given)} lines are not accepted; nothing written.")
        return 1
    if any(row.get("decision") not in DECISIONS for row in given.values()):
        print("refused: a decision outside accept | edit | reject")
        return 1
    today = today or date.today().isoformat()
    docs = [doc for docs in scope(catalog, capability_id).values() for doc in docs]
    rewritten = {root / doc.relative_path: _mark((root / doc.relative_path).read_text(),
                                                 root / doc.relative_path, reviewer, today)
                 for doc in docs}
    for path, text in rewritten.items():
        path.write_text(text)
    sys.path.insert(0, str(default_authoring_root() / "_tools"))
    import admit                                            # noqa: E402 — the corpus's own stamp
    marked = ExpertBrainCatalog(root)
    record = marked.domain(DOMAIN)
    stamped = [record.capabilities[capability_id]] + [
        record.situations[d.id] for d in scope(marked, capability_id)["situation"]]
    for doc in stamped:
        admit.stamp(root / doc.relative_path, admit.expected(dict(doc.content)))
    final = ExpertBrainCatalog(root).domain(DOMAIN)
    problems = [capability_id] if _admission_reason(final.capabilities[capability_id]) else []
    for sid in (d.id for d in scope(marked, capability_id)["situation"]):
        if situation_admission_reason(final.situations[sid].content):
            problems.append(sid)
    for doc in scope(ExpertBrainCatalog(root), capability_id)["artifact"]:
        if artifact_admission_reason(doc.content):
            problems.append(doc.id)
    if problems:
        print(f"refused after writing: {problems} still do not pass admission — inspect them")
        return 3
    print(f"ADMITTED: {capability_id} — {len(given)} lines accepted by {reviewer}; "
          f"{len(rewritten)} files marked, {len(stamped)} stamped.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=None, help="the corpus root (default: the shipped one)")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sheet", help="write the review sheet for one kind of work")
    s.add_argument("--kind", required=True, choices=sorted(k for k, v in KIND_CAPABILITY.items() if v))
    s.add_argument("--out", type=Path, default=None)
    a = sub.add_parser("apply", help="admit, only when every line is accepted")
    a.add_argument("sheet", type=Path)
    a.add_argument("--reviewer", required=True)
    args = ap.parse_args(argv)
    root = (args.root or default_authoring_root()).resolve()
    catalog = ExpertBrainCatalog(root)
    if args.command == "sheet":
        text = yaml.safe_dump(sheet(catalog, args.kind), sort_keys=False, allow_unicode=True,
                              width=100)
        if args.out:
            args.out.write_text(text)
        else:
            sys.stdout.write(text)
        return 0
    return apply(catalog, root, yaml.safe_load(args.sheet.read_text()) or {}, args.reviewer)


if __name__ == "__main__":
    raise SystemExit(main())
