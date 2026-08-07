#!/usr/bin/env python3
"""Regenerate domain.yaml `planned_objects` from the reference graph.

Real expertise has to say "Decision Maker approves Proposal" on the day Proposal does not
exist yet. Without a declared plan every honest forward reference becomes a dead link, and a
validator that cries wolf three hundred times is a validator nobody runs.

So: an id referenced somewhere and authored nowhere becomes a tracked WARNING by landing in
this list. An id that appears in neither stays an ERROR — that is a typo, or a rename that
broke the graph, and it is exactly what you want to hear about.

Run after authoring, to retire entries that now exist:

    python "Domain Expertise/_tools/plan.py"
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import domains, knowledge_refs, load_set, walk  # noqa: E402

BLOCK = re.compile(r"^planned_objects:.*?(?=^\S)", re.M | re.S)


def main() -> int:
    for droot in domains():
        files = list(walk(droot))
        # Objects AND knowledge artifacts. Both are referenced by id, both can be referenced
        # before they exist, and both must be retired from the plan once authored.
        authored = {d["identity"]["id"] for k, _, d in files
                    if k in ("object", "artifact") and (d.get("identity") or {}).get("id")}

        # The prefix is read from domain.yaml, never hardcoded. A second domain arriving is
        # the normal case, and a tool that silently plans nothing for it is worse than one
        # that crashes — it reports "0 still planned" and looks like success.
        #
        # It stops at the domain segment rather than including `.obj.`, because an artifact id
        # is sales.mm.core.meddicc. Filtering on `.obj.` silently dropped every artifact
        # reference and wiped the pinned roster on the next run.
        domain_doc = next((d for k, _, d in files if k == "domain"), {})
        prefix = f"{(domain_doc.get('identity') or {}).get('id', droot.name)}."

        referenced: dict[str, set[str]] = defaultdict(set)

        def note(ref, where, _prefix=prefix):
            if ref and ref.startswith(_prefix):
                referenced[ref].add(where)

        for kind, path, data in files:
            if kind == "__parse_error__":
                continue
            where = path.parent.name if kind != "object" else path.stem
            # Artifact references count too. A capability's knowledge.yaml naming MEDDICC
            # before MEDDICC is authored is the same honest forward reference as an object
            # relationship, and if this tool ignores it the pinned roster gets wiped on the
            # next run and every reference to it turns into an error.
            if kind == "capability_knowledge":
                for r in knowledge_refs(data):
                    note(r, where)
            if kind == "artifact":
                for r in (data.get("objects_used") or []) + \
                         ((data.get("rule") or {}).get("spans") or []):
                    note(r, where)
            if kind == "capability_objects":
                ls = load_set(data)
                for r in ls["required"] + ls["optional"] + (data.get("never_load") or []):
                    note(r, where)
            if kind == "situation":
                o = data.get("objects") or {}
                for key in ("load", "optional", "never_load"):
                    for r in o.get(key) or []:
                        note(r, where)
            if kind == "object":
                for rel in data.get("relationships") or []:
                    note(rel.get("target"), where)
                for prop in (data.get("attributes") or []) + (data.get("properties") or []):
                    if isinstance(prop, dict):
                        note(prop.get("ref"), where)
            if kind in ("model", "offering"):
                for ext in (data.get("objects") or {}).get("extends") or []:
                    note(ext.get("object"), where)

        pending = sorted(set(referenced) - authored)
        lines = ["planned_objects:"]
        if not pending:
            lines = ["planned_objects: []"]
        else:
            for pid in pending:
                scope = pid.split(".")[2]
                users = len(referenced[pid])
                lines.append(f"  - {{id: {pid}, scope: {scope}, referenced_by: {users}}}")

        dom = droot / "domain.yaml"
        text = dom.read_text()
        new_block = "\n".join(lines) + "\n\n"
        if BLOCK.search(text):
            text = BLOCK.sub(new_block, text, count=1)
        else:
            text += "\n" + new_block
        dom.write_text(text)

        retired = sorted(authored & set(referenced))
        print(f"{droot.name}")
        print(f"  authored objects   {len(authored)}")
        print(f"  referenced ids     {len(referenced)}")
        print(f"  still planned      {len(pending)}")
        print(f"  resolved           {len(retired)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
