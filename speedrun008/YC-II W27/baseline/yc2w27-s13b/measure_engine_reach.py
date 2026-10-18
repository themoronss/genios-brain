"""What the GeniOS Engine could put in front of the expert, file by file — and what the expert's answers cite today.

    .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s13b/measure_engine_reach.py" [live-pass folder]

STEP-13b §8 (the check of 12 Oct). No database, no model: it reads

  * the golden set's 94 authored expert answers (`tests/replays/specs/founder/F*.json`, `model.expert`) and maps each
    to its file by the file key its `when` names (`tests/replays/expert_files.json`, the dossiers the answers were
    written against: every id each printed);
  * each file's situations as its dossier printed them (`tests/replays/expert_citations.json`: the `sit:` line —
    "<type> (<L2 domain>)") and whether its kind's playbook was printed (`pb:` ids, stages);
  * the shipped corpus (`packs/compiler/authoring.ExpertBrainCatalog`) — for each situation type, every corpus
    domain whose registry routes it, the corpus situations and capabilities on that route (owner and `also_serves`,
    no predicate evaluated: the dossier has no context slice), each capability's doctrine (question, outcomes,
    failure modes) and knowledge manifest (playbooks, heuristics, rules, mental models, decision frameworks); and
    for the file's kind, its capability (`playbook_reader.KIND_CAPABILITY`) — whose playbooks and heuristics the
    dossier ALREADY prints as `pb:` — and that capability's doctrine, which it does not.

and, given a live pass's folder (`scores/<date>-<model>-expert/`), what the live answers cite.

It prints the per-case table and the totals STEP-13b §8.1 quotes.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

ACTIVATED = ("admin", "founder_office")       # the golden founder's switched-on corpora (STEP-11, `06` D2)
_SIT = re.compile(r"^- \[#\] (?P<type>[\w]+) \((?P<domain>[\w]+)\)")
_PREFIX = re.compile(r"^([a-z_]+):")


def prefix(ref: str) -> str:
    m = _PREFIX.match(str(ref))
    if m:
        return m.group(1)
    return "evt" if str(ref).startswith("evt_") else ("fact" if str(ref).startswith("fact") else f"?{ref}")


def corpus():
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
    return ExpertBrainCatalog(default_authoring_root())


def doctrine(cap_content) -> int:
    """The doctrine lines a capability could print: its question, each outcome, each failure mode."""
    return (1 if cap_content.get("question") else 0) + len(cap_content.get("outcomes") or ()) \
        + len(cap_content.get("failure_modes") or ())


def knowledge(domain, cap_id) -> Counter:
    km = domain.knowledge_manifests.get(cap_id)
    out: Counter = Counter()
    if km is None:
        return out
    for key in ("playbooks", "heuristics", "rules", "mental_models", "decision_frameworks"):
        block = km.content.get(key) or {}
        out[key] += sum(len(block.get(p) or ()) for p in ("core", "scoped"))
    return out


def route(cat, situation_type: str, *, owner_only: bool = False, unconditional: bool = False):
    """Every (domain, corpus situation, capability) the registries route this L2 type to — or only each corpus
    situation's OWNER capability, or only the corpus situations with no `matches.when` predicate (which apply
    to every situation of the type, so no context slice is needed to know they do)."""
    out = []
    for did, dom in cat.domains.items():
        r = dom.routes.get(situation_type)
        if not r:
            continue
        for sid in r.get("situations") or ():
            s = dom.situations[sid].content
            if unconditional and (s.get("matches") or {}).get("when"):
                continue
            caps = [(s.get("identity") or {}).get("owner_capability")]
            if not owner_only:
                caps += list(s.get("also_serves") or ())
            for cap in caps:
                if cap:
                    out.append((did, sid, cap))
    return out


def main(argv: list[str]) -> int:
    from genios_engine.packs.compiler.playbook_reader import KIND_CAPABILITY
    files = json.loads((REPO / "tests/replays/expert_files.json").read_text())
    cites = json.loads((REPO / "tests/replays/expert_citations.json").read_text())
    cat = corpus()

    def sit_lines(case: str, key: str):
        out = []
        for ref in files[case][key]["evidence"]:
            if ref.startswith("sit:"):
                for shape, _i in cites.get(case, {}).get(ref, ()):
                    m = _SIT.match(shape)
                    if m:
                        out.append((m.group("type"), m.group("domain")))
                        break
        return sorted(set(out))

    def kind_of(case: str, key: str):
        pbs = [e for e in files[case][key]["evidence"] if e.startswith("pb:")]
        for kind, cap in KIND_CAPABILITY.items():
            if cap is None:
                continue
            dom = cat.domains.get(cap.split(".", 1)[0])
            km = dom.knowledge_manifests.get(cap) if dom else None
            ids = set()
            if km is not None:
                for k in ("playbooks", "heuristics"):
                    block = km.content.get(k) or {}
                    ids |= {f"pb:{i}" for p in ("core", "scoped") for i in (block.get(p) or ())}
            if pbs and set(pbs) & ids:
                return kind, cap
        return None, None

    # ── the files ──────────────────────────────────────────────────────────────────────────────────
    per_file = {}
    for case, by_key in files.items():
        for key in by_key:
            kind, kcap = kind_of(case, key)
            sits = sit_lines(case, key)
            routed = []
            for t, _d in sits:
                routed += route(cat, t)
            caps_live = sorted({c for d, _s, c in routed if d in ACTIVATED})
            caps_off = sorted({c for d, _s, c in routed if d not in ACTIVATED} - set(caps_live))
            lines = Counter()
            for cap in caps_live + ([kcap] if kcap and kcap not in caps_live else []):
                dom = cat.domains[cap.split(".", 1)[0]]
                content = dom.capabilities[cap].content
                lines["cap_doctrine"] += doctrine(content)
                kn = knowledge(dom, cap)
                if cap == kcap:          # the kind's playbooks and heuristics are printed today (`pb:`)
                    kn["playbooks"] = kn["heuristics"] = 0
                for k, v in kn.items():
                    lines[k] += v
            csits = sorted({s for d, s, _c in routed if d in ACTIVATED})
            sig = 0
            for sid in csits:
                dom = cat.domains[sid.split(".", 1)[0]]
                s = dom.situations[sid].content
                sig += len(s.get("signals_of_progress") or ()) + len(s.get("signals_of_decay") or ())
            lines["situation_signals"] = sig
            per_file[(case, key)] = {"kind": kind, "situations": sits, "caps_live": caps_live,
                                     "caps_off": caps_off, "lines": lines,
                                     "pb_printed": sum(e.startswith("pb:") for e in by_key[key]["evidence"]),
                                     "stages": len(by_key[key].get("stages") or ())}

    # The bounds: the owner capability of a corpus situation with no predicate (lower), every route (upper).
    for (case, key), f in per_file.items():
        lower = sorted({c for t, _d in f["situations"]
                        for d, _s, c in route(cat, t, owner_only=True, unconditional=True) if d in ACTIVATED})
        owners = sorted({c for t, _d in f["situations"]
                         for d, _s, c in route(cat, t, owner_only=True) if d in ACTIVATED})
        f["caps_unconditional"], f["caps_owner"] = lower, owners

    # ── the 94 authored answers ────────────────────────────────────────────────────────────────────
    answers = []
    for path in sorted(glob.glob(str(REPO / "tests/replays/specs/founder/F*.json"))):
        spec = json.loads(Path(path).read_text())
        for a in (spec.get("model") or {}).get("expert") or ():
            key = next(k for k in files.get(spec["case_id"], {}) if any(k in w for w in a["when"]))
            answers.append((spec["case_id"], key, a["answer"]))

    def cites_of(ans):
        out = Counter()
        for f in ans.get("facts") or ():
            for e in f.get("evidence") or ():
                out["fact:" + prefix(e)] += 1
        for part in ("inferences", "patterns"):
            for i in ans.get(part) or ():
                for e in i.get("based_on") or ():
                    out[part[:-1] + ":" + prefix(e)] += 1
        return out

    total = Counter()
    pat = Counter()
    rows = []
    for case, key, ans in answers:
        c = cites_of(ans)
        total.update(c)
        for p in ans.get("patterns") or ():
            refs = [prefix(e) for e in p.get("based_on") or ()]
            pat[p.get("kind")] += 1
            pat["cites_pb" if "pb" in refs else ("facts_only" if set(refs) <= {"fact"} else "data")] += 1
        f = per_file[(case, key)]
        engine_today = c["fact:pb"] + c["inference:pb"] + c["pattern:pb"]
        new_lines = sum(v for k, v in f["lines"].items())
        rows.append((case, key, ans.get("mode"), engine_today, len(ans.get("patterns") or ()),
                     f["kind"], f["pb_printed"], new_lines, f["caps_live"], f["caps_off"],
                     f["situations"]))

    print(f"{'case':<5} {'file':<26} {'mode':<9} {'pb cited':>8} {'pats':>4} {'kind':<10} "
          f"{'pb shown':>8} {'new eng':>7}  situations → live capabilities  [switched-off]")
    for r in rows:
        print(f"{r[0]:<5} {r[1][:26]:<26} {str(r[2]):<9} {r[3]:>8} {r[4]:>4} {str(r[5]):<10} {r[6]:>8} "
              f"{r[7]:>7}  {','.join(t for t, _ in r[10])} → {','.join(c.split('.')[-1] for c in r[8])}"
              + (f"  [{','.join(c.split('.')[-1] for c in r[9])}]" if r[9] else ""))
    n = len(rows)
    print(f"\n{n} authored answers over {len({r[0] for r in rows})} cases, {len({(r[0], r[1]) for r in rows})} files")
    print("citations by line and prefix:", dict(sorted(total.items())))
    print("patterns:", dict(pat))
    print("answers citing a pb: line today:", sum(r[3] > 0 for r in rows))
    print("answers whose file printed the kind's playbook (pb:):", sum(r[6] > 0 for r in rows))
    print("answers whose file would gain >=1 engine line (doctrine, rules, frameworks, the routed "
          "capabilities' playbooks and heuristics, situation signals):", sum(r[7] > 0 for r in rows))
    print("answers whose file has a situation routed only to a switched-off corpus:",
          sum(bool(r[9]) and not r[8] for r in rows))
    print("answers whose file has neither the kind's playbook nor a routed live capability:",
          sum(r[6] == 0 and not r[8] for r in rows))
    lines = Counter()
    for f in {(r[0], r[1]): per_file[(r[0], r[1])] for r in rows}.values():
        lines.update(f["lines"])
    print("engine lines the answered files would gain, summed over files:", dict(lines))
    files_of = [per_file[(r[0], r[1])] for r in rows]
    print("answers whose file gains the KIND's capability doctrine (its playbook already printed):",
          sum(f["kind"] is not None for f in files_of))
    print("answers whose file has a situation routed to a corpus situation with NO predicate (lower bound):",
          sum(bool(f["caps_unconditional"]) for f in files_of))
    print("answers whose file has a situation routed to an OWNER capability in a live corpus (predicates aside):",
          sum(bool(f["caps_owner"]) for f in files_of))
    print("answers gaining an engine line, lower bound (the kind's doctrine or an unconditional route):",
          sum(f["kind"] is not None or bool(f["caps_unconditional"]) for f in files_of))
    print("answers with an investor situation whose file prints no playbook (the brief names no kind):",
          sum(any(t.startswith("investor") for t, _ in f["situations"]) and f["kind"] is None for f in files_of))
    by_case: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for r, f in zip(rows, files_of):
        c = by_case[r[0]]
        c[0] += 1
        c[1] += r[3] > 0
        c[2] += f["kind"] is not None or bool(f["caps_unconditional"])
        c[3] += f["kind"] is not None or bool(f["caps_owner"])
    print("BY CASE — answers · cite an engine line today · could, lower bound · could, upper bound:")
    print("  " + "  ".join(f"{k} {v[0]}·{v[1]}·{v[2]}·{v[3]}" for k, v in sorted(by_case.items())))
    kinds = Counter(per_file[(r[0], r[1])]["kind"] for r in rows)
    print("answers by kind of work (from the pb: printed):", dict(kinds))
    types = Counter(t for r in rows for t, _d in r[10])
    print("situation types on the answered files:", dict(types))

    # ── a live pass's answers ──────────────────────────────────────────────────────────────────────
    if argv:
        live = Counter()
        lpat = Counter()
        modes = Counter()
        n_live = 0
        bad = Counter()
        for path in sorted(glob.glob(str(Path(argv[0]) / "F*.json"))):
            for entry in json.loads(Path(path).read_text()).values():
                if entry.get("site") != "expert" or not isinstance(entry.get("parsed"), dict):
                    continue
                ans = entry["parsed"]
                if not ans.get("facts"):
                    continue
                n_live += 1
                modes[ans.get("mode")] += 1
                live.update(cites_of(ans))
                for f in ans.get("facts") or ():
                    for e in f.get("evidence") or ():
                        if prefix(e).startswith("?"):
                            bad[str(e)[:40]] += 1
                for p in ans.get("patterns") or ():
                    refs = [prefix(e) for e in p.get("based_on") or ()]
                    lpat[p.get("kind")] += 1
                    lpat["cites_pb" if "pb" in refs else ("facts_only" if set(refs) <= {"fact"} else "data")] += 1
        print(f"\nLIVE: {n_live} answers; modes {dict(modes)}")
        print("LIVE citations by line and prefix:", dict(sorted(live.items())))
        print("LIVE patterns:", dict(lpat))
        print("LIVE facts citing something that is no id (top):", bad.most_common(12))
        print("AUTHORED modes:", dict(Counter(a.get("mode") for _c, _k, a in answers)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
