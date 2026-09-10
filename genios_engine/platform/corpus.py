"""Where the authored corpus lives, and what it declares — for every layer at once.

    pytest tests/platform/test_the_corpus_is_readable_from_every_layer.py -q

FOUR LAYERS NEED THE SAME THREE LINES OF YAML and none of them may import each other.
`capture` must know which business vocabularies exist (L1 domain hints, coverage requirements),
`context` must know which situation types may be minted, `packs` must know which corpora to
compile, and `platform` must know which domains a tenant may activate. Before this module,
`capture/domain/hints.py` and `capture/coverage/model.py` reached UP into `packs` to find out —
which `tests/test_layer_topology.py` refused, correctly and immediately: *"a package may import
same-or-lower layers only … lower layers never import up."*

`platform` is the answer the architecture already provides. `LAYERS.CROSS_CUTTING` names it
*"config/db/crypto/wiring; the composition root, may import anything"* — so it may read the
corpus and it may be read by capture, and neither direction is upward.

IT ALSO ENDS A THIRD COPY OF THE ROOT PATH. `packs/compiler/authoring.py:232` computed it as
`parents[3]` and `api/expertise_routes.py:30` as `parents[2]`; two hand-counted depths of the
same directory are one refactor away from disagreeing silently.

EVERY READ FAILS SOFT, and that is a rule rather than a convenience. A corpus that cannot be
read is a DEPLOYMENT problem — a volume not mounted, a bad merge, one malformed file. Turning it
into an ImportError would take the admin console, the capture path and the activation table down
over a typo in one situation file that nothing on those paths reads. The shipped defaults in each
caller are what the tenant already had; keeping them is strictly safer than refusing to run.

NOT `ExpertBrainCatalog`, deliberately. That class parses every capability, object, situation and
heuristic in the tree and raises on any integrity fault anywhere in it — right for a compile,
catastrophic for a module-level constant. This reads `domain.yaml` and stops.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any


def corpus_root() -> Path:
    """The authored corpus directory. THE one place this path is computed."""
    return Path(__file__).resolve().parents[2] / "Domain Expertise"


def authored_domains() -> Iterator[tuple[str, dict[str, Any]]]:
    """`(domain_id, domain.yaml contents)` for every authored corpus, in directory order.

    A folder with no `domain.yaml`, an underscore-prefixed folder, a file that will not parse
    and an entry with no `identity.id` are each skipped by themselves. ONE BAD CORPUS MUST NOT
    HIDE THE OTHERS — a tenant whose logistics file has an unbalanced quote should lose
    logistics, not sales.
    """
    try:
        root = corpus_root()
        if not root.is_dir():
            return
        entries = sorted(root.iterdir())
    except OSError:
        return

    for domain_root in entries:
        try:
            if (not domain_root.is_dir() or domain_root.name.startswith("_")
                    or not (domain_root / "domain.yaml").is_file()):
                continue
            import yaml

            data = yaml.safe_load((domain_root / "domain.yaml").read_text()) or {}
            if not isinstance(data, dict):
                continue
            domain_id = str((data.get("identity") or {}).get("id") or "").strip()
            if domain_id:
                yield domain_id, data
        except Exception:      # noqa: BLE001 — see ONE BAD CORPUS above
            continue


def authored_domain_ids() -> tuple[str, ...]:
    """Every authored domain id, sorted and deduplicated."""
    return tuple(sorted({domain_id for domain_id, _ in authored_domains()}))


@lru_cache(maxsize=1)
def engine_domain_aliases() -> dict[str, str]:
    """The engine's own capture-name -> corpus-name table, read without importing upward.

    `packs.compiler.capability_resolver.DOMAIN_ALIASES` stays the single authority — this is a
    lazy read of it from the one package the architecture lets read anything, so `capture` can
    ask "does a shipped domain already speak for this name" without an upward import.

    CACHED because it is a module constant on the other side; it cannot change at runtime.
    """
    try:
        from genios_engine.packs.compiler.capability_resolver import DOMAIN_ALIASES

        return dict(DOMAIN_ALIASES)
    except Exception:      # noqa: BLE001 — an alias lookup, never a reason to fail a caller
        return {}


def speaks_for(domain_id: str, shipped: object) -> bool:
    """Is `domain_id` a name one of `shipped`'s entries already covers?

    A MEMBERSHIP TEST, NOT A REVERSED MAP, and the difference was a live bug. `DOMAIN_ALIASES` is
    MANY-TO-ONE — `{'support': 'customer_support', 'fundraising': 'sales', 'investor': 'sales'}` —
    so inverting it is not a function: `reverse['sales']` gave `'investor'`, `sales` looked like a
    brand-new authored domain, and its real coverage requirements (`communication` + `crm`) were
    overwritten with a bare default. A tenant with a connected CRM would have been told sales
    coverage was complete without one.

    The question is not "what is this called on the other side" but "does a shipped entry already
    speak for it", and both directions of the table answer that.
    """
    if domain_id in shipped:                      # type: ignore[operator]
        return True
    aliases = engine_domain_aliases()
    return (domain_id in set(aliases.values())
            or aliases.get(domain_id, "") in shipped)      # type: ignore[operator]


__all__ = ["authored_domain_ids", "authored_domains", "corpus_root",
           "engine_domain_aliases", "speaks_for"]
