#!/usr/bin/env python3
"""Stamp — or verify — the production-admission hash on a capability or situation.

The ceremony the resolver enforces (`capability_resolver._admission_reason`) is:

    identity.status == 'stable'
    metadata.review_status == 'approved', with a non-empty metadata.reviewed_by
    admission.accepted_content_hash == semantic_hash(document MINUS the admission block)

The hash pin is the difference between accepting a FILE and accepting its CONTENT: edit the
document after review and it silently stops carrying authority, which is the point. Until this
tool existed the hash was computed by hand, which is the one way of producing it that cannot be
trusted — a hand-typed hash accepts whatever it happens to match.

Note which documents this actually gates: the resolver calls the ceremony on CAPABILITIES only.
A situation's `admission` block is recorded and verified here but nothing in the compile path
reads it — stated so the block is not mistaken for a gate it is not.

It deliberately does NOT grant review. `--accept` refuses anything the reviewer has not already
marked approved with their name on it; it only records what was accepted, using the SAME hash
function the compiler will check it with.

    python "Domain Expertise/_tools/admit.py" --check
    python "Domain Expertise/_tools/admit.py" --accept sales.post_sale_and_growth.customer_success
    python "Domain Expertise/_tools/admit.py" --accept --all
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from genios_engine.packs.compiler.authoring import (            # noqa: E402
    ExpertBrainCatalog, default_authoring_root,
)
from genios_engine.platform.canonical import semantic_hash      # noqa: E402

_BLOCK = re.compile(r"\nadmission:\n(?:[ \t]+.*\n?)*$")


def expected(content: dict) -> str:
    """The hash the resolver will demand: the document with `admission` removed."""
    return semantic_hash({k: v for k, v in content.items() if k != "admission"})


#: Everything a capability file carries that is EXPERTISE rather than a label. A file with none of
#: these has a name, a sentence and a question — which is a placeholder, not knowledge.
_LABEL_KEYS = frozenset({"identity", "description", "question", "metadata", "admission"})


def hollow(content: dict) -> bool:
    """True when this document is admitted, hash-pinned, and says nothing.

    The ceremony asks three questions — is it stable, did a named human approve it, do the bytes
    still match — and never asked whether there was anything to approve. So 42 of the 47 Sales
    capabilities, all 57 Admin capabilities and 40 of 49 Customer Support capabilities are
    `status: stable`, `review_status: approved` and carry a stamped hash over a file whose own
    notes say "Phase 1 stub — identity, purpose and object load-set only". Three of them are
    reached by every routed situation on the design partner's org.

    Reported, deliberately NOT gated. Refusing them today would un-route `account_admin` entirely
    (all three Admin capabilities behind it are hollow) and take live coverage backwards. A count
    that shows up on every run is what makes the promotion queue visible; a gate that breaks
    routing is what makes it get switched off.
    """
    return not (set(content) - _LABEL_KEYS)


def gate(content: dict) -> str | None:
    """None = the reviewer has done their part. Else why this document may not be stamped."""
    identity = content.get("identity") or {}
    metadata = content.get("metadata") or {}
    if identity.get("stub"):
        return "identity.stub is true"
    if str(identity.get("status") or "") != "stable":
        return f"identity.status is {identity.get('status') or 'absent'!r}, not 'stable'"
    if str(metadata.get("review_status") or "") != "approved":
        return "metadata.review_status is not 'approved'"
    if not str(metadata.get("reviewed_by") or "").strip():
        return "metadata.reviewed_by is empty — admission needs a named human"
    return None


def stamp(path: Path, digest: str) -> None:
    """Rewrite only the admission block, so authored comments and layout survive."""
    text = path.read_text()
    block = f"\nadmission:\n  accepted_content_hash: {digest}\n"
    text = _BLOCK.sub("", text).rstrip("\n") + "\n" + block
    path.write_text(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="capability or situation ids; omit with --all")
    ap.add_argument("--accept", action="store_true", help="write the hash (default is check-only)")
    ap.add_argument("--check", action="store_true", help="explicit no-op; checking is the default")
    ap.add_argument("--all", action="store_true", help="every reviewer-approved document")
    args = ap.parse_args()

    root = default_authoring_root()
    catalog = ExpertBrainCatalog(root)
    docs = {}
    for record in catalog.domains.values():
        for source in (*record.capabilities.values(), *record.situations.values()):
            docs[source.id] = source

    if args.all:
        targets = sorted(docs)
    elif args.ids:
        targets = list(args.ids)
    else:
        targets = sorted(docs)          # --check over everything

    stamped = drifted = blocked = ok = 0
    hollow_ids: list[str] = []
    for identifier in targets:
        source = docs.get(identifier)
        if source is None:
            print(f"  UNKNOWN  {identifier}")
            return 2
        path = root / source.relative_path
        want = expected(source.content)
        have = str((source.content.get("admission") or {}).get("accepted_content_hash") or "")
        reason = gate(source.content)
        if reason is None and hollow(source.content):
            hollow_ids.append(identifier)

        if reason is not None:
            # --all means "everything the reviewer approved", so an unapproved document is
            # skipped silently there and reported when it was named explicitly.
            if not args.all:
                print(f"  BLOCKED  {identifier}: {reason}")
                blocked += 1
            continue
        if have == want:
            ok += 1
            continue
        if not args.accept:
            print(f"  DRIFTED  {identifier}\n           expected {want}\n           found    "
                  f"{have or '(none)'}\n           {source.relative_path}")
            drifted += 1
            continue
        stamp(path, want)
        print(f"  STAMPED  {identifier} -> {want}")
        stamped += 1

    print(f"\n{ok} already admitted, {stamped} stamped, {drifted} drifted, {blocked} blocked, "
          f"{len(hollow_ids)} HOLLOW")
    if hollow_ids:
        print("\nHOLLOW — admitted, hash-pinned, and carrying no expertise beyond a name, a\n"
              "sentence and a question. Each one routes and contributes nothing to the answer.\n"
              "Not blocked: refusing them today would un-route whole situation types (every\n"
              "Admin capability is here). This is the promotion queue.")
        by_domain: dict[str, list[str]] = {}
        for identifier in hollow_ids:
            by_domain.setdefault(str(identifier).split(".")[0], []).append(identifier)
        for domain, ids in sorted(by_domain.items()):
            print(f"  {domain:<18} {len(ids):>3}")
    return 1 if (drifted or blocked) else 0


if __name__ == "__main__":
    raise SystemExit(main())
