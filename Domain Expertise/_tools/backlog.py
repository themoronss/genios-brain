#!/usr/bin/env python3
"""Turn every `needs_signal` inference pattern into a Layer 1 / Layer 2 requirements list.

This is the by-product that may be worth more than the objects themselves. Authoring domain
expertise forces you to name exactly what the pipeline would have to observe for that
expertise to run — and each of those names is a concrete, prioritised connector or extractor
task, ranked by how many authored patterns it unblocks.

Writes registry/signal-backlog.md and prints a summary.

    python "Domain Expertise/_tools/backlog.py"
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import domains, load_vocabulary, patterns_of, walk  # noqa: E402


def main() -> int:
    vocab = load_vocabulary()
    sub = vocab["substrate"]

    for droot in domains():
        all_files = list(walk(droot))
        files = [(k, p, d) for k, p, d in all_files if k == "object"]
        sits = [(k, p, d) for k, p, d in all_files if k == "situation"]

        # (kind, name) -> {owner_layer, notes[], blocks[(object, pattern, confidence_bp)]}
        need: dict[tuple[str, str], dict] = defaultdict(
            lambda: {"owner": set(), "notes": [], "blocks": []})
        executable = needs = 0

        for _, path, obj in files:
            oname = obj["identity"]["name"]
            for _kind, pat in patterns_of(obj):
                if pat.get("status") == "executable":
                    executable += 1
                    continue
                needs += 1
                for rs in pat.get("requires_signals") or []:
                    key = (rs["kind"], rs["name"])
                    need[key]["blocks"].append(
                        (oname, pat["id"], pat.get("yields", {}).get("confidence_bp", 0)))
                    if rs.get("owner_layer"):
                        need[key]["owner"].add(rs["owner_layer"])
                    if rs.get("note"):
                        need[key]["notes"].append(f"{oname}: {rs['note']}")

        # Situations blocked on a missing L2 type. These outrank most pattern-level asks:
        # a blocked pattern degrades one object's confidence, whereas a blocked situation
        # means an entire capability never compiles and nothing anywhere logs why.
        blocked_situations = 0
        for _, path, sit in sits:
            sname = sit["identity"]["name"]
            for p in (sit.get("matches") or {}).get("pending_l2_situation_types") or []:
                if not p.get("type"):
                    continue
                blocked_situations += 1
                key = ("l2_situation_type", p["type"])
                # 10000 so a blocked situation sorts above blocked patterns at equal count.
                need[key]["blocks"].append((f"[situation] {sname}", sit["identity"]["id"], 10000))
                need[key]["owner"].add(p.get("owner_layer") or "L2")
                if p.get("note"):
                    need[key]["notes"].append(f"{sname}: {p['note']}")
                if p.get("nearest_today"):
                    need[key]["notes"].append(
                        f"{sname}: closest type emitted today is `{p['nearest_today']}` — "
                        f"close enough to be tempting, not close enough to be true")

        ranked = sorted(need.items(),
                        key=lambda kv: (-len(kv[1]["blocks"]),
                                        -max((b[2] for b in kv[1]["blocks"]), default=0),
                                        kv[0][1]))

        md = [f"# {droot.name} — signal backlog",
              "",
              "> GENERATED — `python \"Domain Expertise/_tools/backlog.py\"`",
              "",
              "Every row is a signal the authored expertise needs and the pipeline does not",
              "emit. Ranked by how many inference patterns it unblocks, then by the confidence",
              "of the strongest pattern waiting on it.",
              "",
              "Rows marked `l2_situation_type` are the expensive ones. A blocked *pattern*",
              "lowers one object's confidence; a blocked *situation* means the capability",
              "behind it never compiles at all, and nothing errors or logs when it doesn't.",
              "",
              "## Where the brain stands",
              "",
              f"- **{executable}** patterns executable against the pipeline today",
              f"- **{needs}** patterns blocked, waiting on **{len(need)}** distinct signals",
              f"- **{blocked_situations}** situation binding(s) waiting on an L2 type no pack "
              f"emits",
              f"- Substrate today: **{len(sub['fact_paths'])}** fact paths · "
              f"**{len(sub['obs_kinds'])}** observation kinds · "
              f"**{len(sub['baselines'])}** baselines",
              "",
              "## The backlog",
              "",
              "| # | Signal | Kind | Owner | Unblocks | Top conf | Objects |",
              "|---|---|---|---|---|---|---|"]

        for i, ((kind, name), info) in enumerate(ranked, 1):
            objs = sorted({b[0] for b in info["blocks"]})
            top = max((b[2] for b in info["blocks"]), default=0)
            owner = "/".join(sorted(info["owner"])) or "—"
            md.append(f"| {i} | `{name}` | {kind} | {owner} | {len(info['blocks'])} | "
                      f"{top} | {', '.join(objs)} |")

        md += ["", "## Why each one matters", ""]
        for (kind, name), info in ranked:
            md.append(f"### `{name}` · {kind}")
            md.append("")
            for oname, pid, conf in sorted(info["blocks"]):
                md.append(f"- blocks **{oname}** / `{pid}` (would yield {conf} bp)")
            for n in dict.fromkeys(info["notes"]):
                md.append(f"- {n}")
            md.append("")

        out = droot / "registry" / "signal-backlog.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(md) + "\n")

        print(f"{droot.name}")
        print(f"  wrote {out.relative_to(droot.parent)}")
        print(f"  {executable} executable / {needs} blocked patterns · "
              f"{len(need)} distinct signals needed")
        print()
        print("  top asks:")
        for i, ((kind, name), info) in enumerate(ranked[:8], 1):
            owner = "/".join(sorted(info["owner"])) or "—"
            print(f"   {i}. {name:<38} {kind:<10} {owner:<4} unblocks {len(info['blocks'])}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
