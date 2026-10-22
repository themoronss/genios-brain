import json
import sys
from collections import Counter

d = json.load(open(sys.argv[1]))
mode = sys.argv[2] if len(sys.argv) > 2 else "summary"


def rec(c):
    r = c["gold"].get("recommended")
    if isinstance(r, dict):
        return r.get("what") or ""
    return r or ""


if mode == "summary":
    for path in ("today", "l2"):
        v = Counter(); lanes = Counter(); n = 0; filled = Counter(); errs = []
        multi = 0; versions = 0
        for cid, case in d.items():
            r = case[path]
            if "error" in r:
                errs.append((cid, r["error"][:90])); continue
            v[r["verdict"]] += 1
            cards = r["cards"]
            n += len(cards)
            for c in cards:
                lanes[c["lane"]] += 1
                versions += c["versions"] > 1
                for k in ("headline", "subject", "role", "why_now", "what_remains", "recommended",
                          "alternative", "wait_or_stop", "window_days", "confidence", "capability_key"):
                    if c["gold"].get(k) not in (None, "", {}, []):
                        filled[k] += 1
        print(f"== {path}: cases {len(d)} verdicts {dict(v)} cards {n} lanes {dict(lanes)} "
              f"multi-version {versions} errors {len(errs)}")
        print("   field filled:", {k: f"{filled[k]}/{n}" for k in filled})
        for e in errs:
            print("   ERR", e)
elif mode == "cards":
    for cid, case in d.items():
        for path in ("today", "l2"):
            r = case[path]
            print(f"\n### {cid} [{path}] {case['title']} — {r.get('verdict')} {r.get('reason') or ''}"[:220])
            for c in r.get("cards", []):
                g = c["gold"]
                print(f"  - lane={c['lane']} state={c['state']} level={c['level']} versions={c['versions']} ended={c['ended']}")
                print(f"    headline: {g.get('headline')}")
                print(f"    subject/role: {g.get('subject')} / {g.get('role')}")
                print(f"    why_now: {(g.get('why_now') or '')[:200]}")
                print(f"    remains: {(g.get('what_remains') or '')[:200]}")
                print(f"    recommended: {rec(c)[:220]}")
                print(f"    alternative: {str(g.get('alternative') or '')[:160]}")
                print(f"    wait_or_stop: {str(g.get('wait_or_stop') or '')[:160]}")
                print(f"    window_days: {g.get('window_days')} cap: {g.get('capability_key')} conf: {str(g.get('confidence'))[:160]}")
elif mode == "diff":
    for cid, case in d.items():
        t, n = case["today"], case["l2"]
        th = sorted((c["gold"].get("headline") or "") for c in t.get("cards", []))
        nh = sorted((c["gold"].get("headline") or "") for c in n.get("cards", []))
        if th != nh or t.get("verdict") != n.get("verdict"):
            print(f"{cid} {case['title'][:70]}\n   today {t.get('verdict')}: {th}\n   l2    {n.get('verdict')}: {nh}")
