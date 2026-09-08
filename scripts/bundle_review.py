#!/usr/bin/env python3
"""K4's second command — read the narratives a tenant is actually shipping, as a founder reads them.

    python scripts/bundle_review.py --org <pilot> --sample 25
    python scripts/bundle_review.py --golden                 # the committed 25-bundle review set

**Why a script and not a dashboard row.** K4's last gate is a HUMAN standard: a founder should
understand the card in ten seconds. No assertion can decide that, so this prints the rendered cards
— numbers already substituted, exactly what a customer sees — and reports the machine-checkable
half beside them: the fallback rate, the bare-number count, the citation count, the word counts, and
which of V-1..V-7 refused anything.

Read-only. It opens no model, writes no row, and never touches production unless a URL is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genios_engine.reason.bundle.gauntlet import CHECK_NAMES          # noqa: E402
from genios_engine.reason.bundle.store import BUNDLE_TABLE, BundleStore  # noqa: E402

GLANCE = ("headline", "situation_summary", "why_it_matters", "root_cause",
          "recommendation_rationale", "expected_effect")
HEADINGS = {"situation_summary": "SITUATION", "why_it_matters": "WHY THIS MATTERS",
            "root_cause": "ROOT CAUSE", "recommendation_rationale": "RECOMMENDATION",
            "expected_effect": "EXPECTED EFFECT",
            "alternatives_narrative": "WHY NOT THE ALTERNATIVES"}


def _wrap(text: str, width: int = 92, indent: str = "  ") -> str:
    words, line, out = str(text or "").split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(indent + line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(indent + line)
    return "\n".join(out)


def print_card(rendered: dict, *, generation: str, citations=(), evidence_refs=()) -> int:
    """One card, the way a founder sees it. Returns the glance-card word count."""
    print("\n" + "─" * 96)
    print(rendered.get("headline", "(no headline)").upper())
    words = 0
    for name in GLANCE[1:]:
        text = rendered.get(name)
        if not text:
            continue
        words += len(text.split())
        print(f"\n{HEADINGS[name]}")
        print(_wrap(text))
    if rendered.get("alternatives_narrative"):
        print(f"\n{HEADINGS['alternatives_narrative']}")
        print(_wrap(rendered["alternatives_narrative"]))
    sources = [f"{len(evidence_refs)} evidence items"]
    for citation in citations:
        sources.append(f"{citation.get('artifact_class')} {citation.get('artifact_id')}")
    print(f"\n  Sources: {' · '.join(sources)}")
    print(f"  [generation: {generation}]")
    return words + len(rendered.get("headline", "").split())


def review_golden(limit: int) -> int:
    from tests.reason.l4_golden import load_golden
    doc = load_golden()
    gate = doc["gate"]
    shown = 0
    over = []
    for fixture in doc["fixtures"]:
        rendered = fixture["expect"].get("rendered")
        if not rendered or shown >= limit:
            continue
        shown += 1
        situation = doc["situations"][fixture["situation"]]
        print(f"\n### {fixture['fixture_id']}  ({', '.join(fixture['tags'])})")
        words = print_card(rendered, generation="llm (golden replay)",
                           citations=situation.get("citations") or (),
                           evidence_refs=situation.get("evidence_ids") or ())
        if words > gate["ten_second_max_words_per_card"]:
            over.append((fixture["fixture_id"], words))
    total = len(doc["fixtures"])
    adversarial = sum(1 for f in doc["fixtures"] if "adversarial" in f["tags"])
    print("\n" + "=" * 96)
    print(f"golden set          : {total} fixtures ({adversarial} adversarial, "
          f"{total - adversarial} clean or unanswered)")
    print(f"checks exercised    : "
          f"{sorted({c for f in doc['fixtures'] for c in f['expect']['checks_failed']})}")
    print(f"ten-second breaches : {over or 'none'}")
    return 1 if over else 0


def review_org(org_id: str, limit: int, database_url: str | None) -> int:
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    url = database_url or os.environ.get("GENIOS_TEST_DATABASE_URL") or ""
    if not url:
        print("no database URL: pass --database-url or set GENIOS_TEST_DATABASE_URL",
              file=sys.stderr)
        return 2
    engine = get_engine(url)
    store = BundleStore(engine)
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"select decision_hash, generation, rendered, bundle, gauntlet, attempts, "
            f"cost_micro_usd from {BUNDLE_TABLE} where org_id = :o "
            "order by created_at desc limit :l"), {"o": org_id, "l": limit}).all()
    if not rows:
        print(f"no narratives stored for {org_id} — is `bundle` activated for this tenant?")
        return 1
    refusals: dict[str, int] = {}
    bare = 0
    for row in rows:
        rendered = row.rendered if isinstance(row.rendered, dict) else json.loads(row.rendered)
        payload = row.bundle if isinstance(row.bundle, dict) else json.loads(row.bundle)
        print_card(rendered, generation=row.generation,
                   citations=payload.get("citations") or [],
                   evidence_refs=payload.get("evidence_refs") or [])
        checks = row.gauntlet if isinstance(row.gauntlet, list) else json.loads(row.gauntlet or "[]")
        for check in checks:
            if not check.get("passed"):
                refusals[check["check"]] = refusals.get(check["check"], 0) + 1
        if any("{" in str(value) for value in rendered.values()):
            bare += 1
    stats = store.stats(org_id=org_id)
    print("\n" + "=" * 96)
    print(f"bundles              : {stats['bundles']}")
    print(f"template_fallback    : {stats['template_fallback']} "
          f"({stats['fallback_rate_bp'] / 100:.1f}%)  — K4 gate: under 15%")
    print(f"cache hit rate       : {stats['cache_hit_rate_bp'] / 100:.1f}%  — doc 11 gate: over 60%")
    print(f"narrative spend      : ${stats['cost_micro_usd'] / 1_000_000:.4f}")
    if stats["bundles"]:
        print(f"$ per published card : "
              f"${stats['cost_micro_usd'] / stats['bundles'] / 1_000_000:.4f}  — doc 11 gate: <= $0.02")
    print(f"consult outcomes     : {stats['consults']}")
    print(f"gauntlet refusals    : "
          f"{ {f'{k} {CHECK_NAMES[k]}': v for k, v in sorted(refusals.items())} or 'none'}")
    print(f"unresolved placeholders on a card : {bare}  — K4 gate: 0")
    return 0 if (stats["fallback_rate_bp"] < 1500 and bare == 0) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", help="tenant to review")
    parser.add_argument("--sample", type=int, default=25)
    parser.add_argument("--golden", action="store_true",
                        help="review the committed golden set instead of a tenant")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    if args.golden or not args.org:
        return review_golden(args.sample)
    return review_org(args.org, args.sample, args.database_url)


if __name__ == "__main__":
    raise SystemExit(main())
