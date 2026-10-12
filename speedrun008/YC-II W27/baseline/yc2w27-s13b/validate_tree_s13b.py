"""Does the proposed STEP-13b block parse, and does every dependency it names exist?

    .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s13b/validate_tree_s13b.py"

Checks, exit code 1 on any failure:
  * the file parses and holds one block, `yc2_w27_s13b`, whose milestones are M37 and M38 — ids no other block
    uses (tree.yaml and every baseline tree);
  * every unit has `what`, `artifact`, `verify` (one line) and `depends_on`; its id is unique and spells where it
    sits (`<milestone>.<category>.L-<layer>.V<level>.U<n>`);
  * every `depends_on` resolves — a bare id inside this block, `<block>/<id>` in tree.yaml or in a proposed
    baseline block (`baseline/yc2w27-s14|s15|s16/tree_s1x.yaml`);
  * the block's own dependencies have no cycle, and each unit's level is at least its depth among them;
and prints the units per milestone and the critical path inside the block.
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BLOCK = "yc2_w27_s13b"
_ID = re.compile(r"^(M\d+)\.(C\d+)\.L-([a-z]+)\.V(\d+)\.U(\d+)$")


def units_of(block: dict):
    for m in block.get("milestones") or ():
        for c in m.get("categories") or ():
            for layer in c.get("layers") or ():
                for level in layer.get("levels") or ():
                    for u in level.get("units") or ():
                        yield m["id"], c["id"], layer["layer"], level["level"], u


def ids_in(path: Path) -> dict[str, set[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, set[str]] = {}
    for name, block in data.items():
        if not isinstance(block, dict):
            continue
        found = {u["id"] for *_r, u in units_of(block)}
        found |= {m["id"] for m in block.get("milestones") or () if isinstance(m, dict)}
        if found:
            out[name] = found
    return out


def main() -> int:
    errors: list[str] = []
    mine = yaml.safe_load((HERE / "tree_s13b.yaml").read_text(encoding="utf-8"))
    if list(mine) != [BLOCK]:
        errors.append(f"the file holds {list(mine)}, not [{BLOCK}]")
    block = mine[BLOCK]
    milestones = [m["id"] for m in block["milestones"]]
    if milestones != ["M37", "M38"]:
        errors.append(f"milestones {milestones}")

    known: dict[str, set[str]] = ids_in(REPO / "tree.yaml")
    for path in glob.glob(str(HERE.parent / "yc2w27-s1*" / "tree_s1*.yaml")):
        if Path(path).name != "tree_s13b.yaml":
            for name, ids in ids_in(Path(path)).items():
                known.setdefault(name, set()).update(ids)
    for name, ids in known.items():
        if name != BLOCK and ids & set(milestones):
            errors.append(f"{sorted(ids & set(milestones))} already used by {name}")

    units = list(units_of(block))
    ids = [u["id"] for *_r, u in units]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"duplicate ids {dupes}")
    deps: dict[str, list[str]] = {}
    level_of: dict[str, int] = {}
    for mid, cid, layer, level, u in units:
        uid = u["id"]
        m = _ID.match(uid)
        if not m or m.group(1) != mid or f"{m.group(1)}.{m.group(2)}" != cid or m.group(3) != layer \
                or int(m.group(4)) != int(level):
            errors.append(f"{uid} does not spell where it sits ({cid}, {layer}, level {level})")
        for key in ("what", "artifact", "verify", "depends_on"):
            if key not in u:
                errors.append(f"{uid} has no {key}")
        if "\n" in str(u.get("verify", "")).strip():
            errors.append(f"{uid}: verify is more than one line")
        level_of[uid] = int(level)
        deps[uid] = []
        for d in u.get("depends_on") or ():
            if "/" in d:
                other, oid = d.split("/", 1)
                if oid not in known.get(other, set()):
                    errors.append(f"{uid} depends on {d}, which no block holds")
            elif d not in ids:
                errors.append(f"{uid} depends on {d}, which is not in this block")
            else:
                deps[uid].append(d)

    depth: dict[str, int] = {}
    path_to: dict[str, list[str]] = {}

    def walk(uid: str, seen: tuple[str, ...] = ()) -> int:
        if uid in seen:
            errors.append(f"a cycle: {' -> '.join(seen + (uid,))}")
            return 0
        if uid not in depth:
            best, via = 0, []
            for d in deps[uid]:
                dd = walk(d, seen + (uid,)) + 1
                if dd > best:
                    best, via = dd, path_to.get(d, [d])
            depth[uid], path_to[uid] = best, via + [uid]
        return depth[uid]

    for uid in deps:
        walk(uid)
        if level_of[uid] < depth[uid]:
            errors.append(f"{uid}: level {level_of[uid]} is below its depth {depth[uid]}")

    per = {m: sum(1 for mid, *_r in units if mid == m) for m in milestones}
    longest = max(path_to.values(), key=len)
    cross = sorted({d for *_r, u in units for d in u.get("depends_on") or () if "/" in d})
    print(f"parsed: block {BLOCK}, {len(units)} units — " + ", ".join(f"{m} {n}" for m, n in per.items()))
    print(f"depends_on: {sum(len(u.get('depends_on') or ()) for *_r, u in units)} named, "
          f"{len(cross)} distinct in other blocks, every one resolved" if not any(
              'which' in e for e in errors) else "depends_on: UNRESOLVED (below)")
    print(f"critical path inside the block ({len(longest)} units): " + " → ".join(longest))
    print("in other blocks: " + ", ".join(cross))
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
