"""L2.3 · Cross Domain — two domains reasoning about one subject, and disagreeing.

**THE LAST OF EIGHT.** Cross Tool and Cross User live in `correlation.py`; Resource, Timeline,
Dependency, Conversation and Organization have their own modules. This is Cross Domain, and with
it the architecture's eight named correlators all exist.

**WHAT IT IS FOR, measured read-only on the pilot before a line of this was written.** Every
situation resolved to the person behind it — anchor, or one hop through `corresponded_with`, or
one through `concerns`:

    people reached by at least one situation            43
    people carrying more than one situation TYPE         4
      x3   admin:awaiting_response  +  support:first_response_overdue
      x1   general:relationship     +  support:first_response_overdue

The first row is not overlap. It is a **contradiction**. `awaiting_response` says *they owe us a
reply*; `first_response_overdue` says *we never answered them*. Both cannot be true of one
counterparty at one time, and on all three — Boardy, Crescere Labs, IIM-A — `thread.ball_in_court`
reads `them`, so admin is right and support is wrong. Nothing in the system noticed. Two cards
would have gone out telling the founder opposite things about the same person.

Seventeen nodes carry situations in more than one domain at the ANCHOR level, most of them
harmlessly: `nsrcel.iimb.ac.in` is an investor relationship, a general relationship and a sales
opportunity at once, which is three true readings of one accelerator. Overlap is normal and this
module does not touch it. Only a declared IMPOSSIBILITY is a finding.

**THE PAIRS ARE DECLARED, NOT DETECTED.** There is no similarity score here and no threshold. A
statistical "these two look like they clash" would fire on the harmless overlaps above and would
be undebuggable from a stored number. `EXCLUSIONS` names each impossible pair, says in a sentence
why it is impossible, and names the FACT that settles it where one exists. Adding a pair is an
authoring act a reviewer can argue with.

**IT DOES NOT DELETE ANYTHING.** It returns findings. Which situation yields — and whether both
should be held while a human looks — is a decision for the layer that publishes, and
`contracts/abstention.py` already carries the vocabulary for it. A correlator that silently
suppressed a domain's work would be the wrongful merge the eight-correlator design warns about,
one layer up.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text


@dataclass(frozen=True, slots=True)
class Exclusion:
    """Two situation types that cannot both be true of one subject."""

    #: The two `<domain>:<situation_type>` keys, in declaration order.
    left: str
    right: str
    #: Why they are impossible together, in one sentence a reviewer can disagree with.
    because: str
    #: The fact that settles it, when the graph holds one. `None` means nothing decides it and
    #: both sides are returned unresolved — which is an honest answer and a reviewable one.
    arbiter: str | None = None
    #: Fact value → which side it favours. Read only when `arbiter` is set.
    favours: Mapping[str, str] = ()

    @property
    def pair(self) -> frozenset[str]:
        return frozenset((self.left, self.right))


#: Where the declared impossibilities live. DATA, IN FILES — adding a contradiction is a file
#: and a review, not a deploy of new logic, which is the same argument `patterns/registry.SEED_DIR`
#: makes for detectable situations and the same route it takes.
#:
#: THIS WAS A PYTHON TUPLE AND THAT WAS THE WRONG SHAPE. One pair, hard-coded, so a second
#: contradiction — and every tenant will have different ones, because every business is a
#: different set of readings over a different substrate — meant editing this module. An
#: exclusion is authored expertise: it says what two claims mean and which fact settles them.
#: Nothing about it is engine logic.
EXCLUSIONS_DIR = Path(__file__).resolve().parent / "exclusions"


class ExclusionError(ValueError):
    """A declared impossibility that could not be read. Carries the filename, so a load of a
    dozen names the one that is wrong rather than failing the set."""


def load_exclusion(data: Mapping[str, object], *, source: str = "<inline>") -> Exclusion:
    """One authored mapping → one `Exclusion`. Every refusal names the file and the field.

    STRICT ON PURPOSE. This data suppresses a domain's work, so a typo in `favours` that
    silently made every finding unresolved would be indistinguishable from a tenant with no
    contradictions — the failure this whole module exists to end, one layer in.
    """
    def need(key: str) -> str:
        value = str(data.get(key) or "").strip()
        if not value:
            raise ExclusionError(f"{source}: `{key}` is required")
        return value

    left, right = need("left"), need("right")
    for side in (left, right):
        domain, _, stype = side.partition(":")
        if not domain or not stype:
            raise ExclusionError(f"{source}: {side!r} must read `<domain>:<situation_type>`")
    if left == right:
        raise ExclusionError(f"{source}: a type cannot contradict itself")

    arbiter = str(data.get("arbiter") or "").strip() or None
    favours_raw = data.get("favours") or {}
    if not isinstance(favours_raw, Mapping):
        raise ExclusionError(f"{source}: `favours` must be a mapping of fact value → side")
    favours = {str(k): str(v) for k, v in favours_raw.items()}
    if arbiter and not favours:
        raise ExclusionError(f"{source}: `arbiter` is set but `favours` names no side")
    if favours and not arbiter:
        raise ExclusionError(f"{source}: `favours` is set but no `arbiter` decides it")
    for value, side in favours.items():
        if side not in (left, right):
            # The failure mode this catches: `winner` returns a type `loser` cannot subtract
            # from the pair, so every finding answers unresolved and nothing says why.
            raise ExclusionError(
                f"{source}: favours[{value!r}] = {side!r}, which is neither side of this pair")

    return Exclusion(left=left, right=right, because=need("because"),
                     arbiter=arbiter, favours=favours)


def load_exclusions(directory: Path | None = None) -> tuple[Exclusion, ...]:
    """Every `*.yaml` in the directory, in filename order.

    Sorted, so two machines load the same set and a diff of two contradiction reports is a diff
    of behaviour rather than of `readdir` — the reason `patterns.load_directory` sorts too.
    """
    import yaml

    root = directory or EXCLUSIONS_DIR
    if not root.is_dir():
        return ()
    out: list[Exclusion] = []
    for path in sorted(root.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ExclusionError(f"{path.name} could not be read as YAML: {exc}") from exc
        if not isinstance(data, Mapping):
            raise ExclusionError(f"{path.name} is not an exclusion mapping")
        out.append(load_exclusion(data, source=path.name))
    return tuple(out)


@functools.lru_cache(maxsize=1)
def declared_exclusions() -> tuple[Exclusion, ...]:
    """The shipped set. Cached: pure file IO over immutable data, and the sweep would otherwise
    re-parse it per org. `cache_clear()` is available to a test that writes another."""
    return load_exclusions()


#: THE DECLARED IMPOSSIBILITIES, read from `exclusions/`. A pair not authored there is overlap,
#: not contradiction, and this module ignores it. Kept as a module attribute so every caller's
#: default is one thing a reader can find, and so a test can pass its own set explicitly.
EXCLUSIONS: tuple[Exclusion, ...] = declared_exclusions()


@dataclass(frozen=True, slots=True)
class Contradiction:
    """One subject carrying two situations that cannot both be true."""

    subject_node_id: str
    subject: str
    exclusion: Exclusion
    #: `(key, situation_id)` for each side, in the exclusion's declaration order.
    sides: tuple[tuple[str, str], ...]
    #: The arbiter's value on this subject, or `None` when absent.
    arbiter_value: str | None = None

    @property
    def winner(self) -> str | None:
        """The `<domain>:<type>` the evidence favours, or `None` when nothing settles it."""
        if self.arbiter_value is None:
            return None
        return dict(self.exclusion.favours or {}).get(self.arbiter_value)

    @property
    def loser(self) -> str | None:
        won = self.winner
        if won is None:
            return None
        return next(iter(self.exclusion.pair - {won}))

    @property
    def resolved(self) -> bool:
        return self.winner is not None


#: Every situation, resolved to the PERSON it is really about.
#:
#: Three shapes and a caller should not have to know which, for the reason
#: `correlation_organization.resolve_people` records: a situation anchor is almost never a person.
#: 41 `awaiting_response` anchors are `outreach` nodes and 41 `first_response_overdue` anchors are
#: `thread` nodes on the pilot. `union` rather than `union all` — one situation reachable by two
#: routes is one row, and counting it twice would report a subject as contradicting itself.
#:
#: AT MOST TWO HOPS, the same bound and the same reason: `concerns` and `corresponded_with` are
#: dense, and a transitive walk drifts from one subject to another.
#:
#: `status = 'active'`, AND THE FIRST CUT OF THIS SAID `'open'`. There is no such status: the
#: column holds `active` / `dormant` / `resolved` — 183 / 47 / 2 on the pilot — so the read matched
#: nothing and the module reported a CLEAN TENANT while three live contradictions sat in the table.
#: A filter on a value a column never holds is indistinguishable from a healthy result, which is
#: why it was caught by re-running the raw measurement through the module rather than by rereading
#: the query.
#:
#: `dormant` is excluded on its own merits and not merely because `active` was the value at hand:
#: a dormant situation has stopped making its claim, and two claims cannot contradict when only
#: one of them is still being made.
_SITUATIONS_BY_PERSON = (
    "with s as ("
    "  select situation_id, domain, situation_type, anchor_node_id "
    "  from context_situations where org_id = :o and status = 'active'"
    "), direct as ("
    "  select s.situation_id, s.domain, s.situation_type, n.node_id as person from s "
    "  join graph_nodes n on n.org_id = :o and n.node_id = s.anchor_node_id "
    "       and n.node_type = 'person' and n.valid_to is null"
    "), via_thread as ("
    "  select s.situation_id, s.domain, s.situation_type, e.from_node_id as person from s "
    "  join graph_edges e on e.org_id = :o and e.to_node_id = s.anchor_node_id "
    "       and e.edge_type = 'corresponded_with' and e.valid_to is null"
    "), via_concern as ("
    "  select s.situation_id, s.domain, s.situation_type, "
    "         coalesce(p.node_id, q.from_node_id) as person from s "
    "  join graph_edges c on c.org_id = :o and c.from_node_id = s.anchor_node_id "
    "       and c.edge_type = 'concerns' and c.valid_to is null "
    "  left join graph_nodes p on p.org_id = :o and p.node_id = c.to_node_id "
    "       and p.node_type = 'person' and p.valid_to is null "
    "  left join graph_edges q on q.org_id = :o and q.to_node_id = c.to_node_id "
    "       and q.edge_type = 'corresponded_with' and q.valid_to is null"
    ") "
    "select * from ("
    "  select * from direct union select * from via_thread union select * from via_concern"
    ") all_rows where person is not null"
)

#: The arbiter facts, in bulk. One statement for the tenant rather than one per contradiction.
_ARBITER_FACTS = (
    "select f.subject_node_id as person, f.field as field, f.value as value "
    "from graph_facts f "
    "where f.org_id = :o and f.status = 'active' and f.valid_to is null "
    "  and f.field in :fields"
)

#: Display names, so a finding names somebody rather than an id.
_NAMES = (
    "select node_id, coalesce(display_name, canonical_key) as name from graph_nodes "
    "where org_id = :o and valid_to is null"
)


def _plain(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        stripped = raw.strip().strip('"')
        return stripped or None
    return str(raw) or None


def arbiter_fields(exclusions: Sequence[Exclusion] = EXCLUSIONS) -> tuple[str, ...]:
    """The distinct arbiter facts the declared pairs need. Empty when none declares one."""
    return tuple(sorted({e.arbiter for e in exclusions if e.arbiter}))


def find_contradictions(rows: Sequence[Mapping],
                        arbiters: Mapping[str, Mapping[str, object]] | None = None,
                        names: Mapping[str, str] | None = None,
                        *, exclusions: Sequence[Exclusion] = EXCLUSIONS) -> tuple[Contradiction, ...]:
    """Group situations by subject and return the declared impossibilities among them. Pure.

    A subject carrying THREE situations that pairwise exclude produces one finding per pair, not
    one merged finding: each pair has its own reason and its own arbiter, and folding them would
    lose which claim the evidence actually settles.
    """
    arbiters = arbiters or {}
    names = names or {}
    # A SITUATION WITH MORE THAN ONE SUBJECT HAS NONE, and this is the fan-out that made that
    # matter. `pipeline.py` writes one `person --corresponded_with--> thread` edge PER RECIPIENT,
    # so a THREAD-anchored situation — every `first_response_overdue` row on the pilot — resolves
    # to every participant on the thread, not to the one it is about.
    #
    # The harm is specific and it is the kind this module exists to prevent. A five-recipient
    # thread carrying `first_response_overdue` attributes that claim to all five; if any one of
    # them separately carries `awaiting_response`, a contradiction fires between two situations
    # about DIFFERENT people, and the arbiter then settles it by reading a `ball_in_court` that
    # belongs to only one of them. A contradiction attributed to the wrong person is worse than
    # none: it suppresses a correct card to resolve a disagreement that never existed.
    #
    # DROPPED, NOT GUESSED. `_THREAD_COVERED_BY_PARTY` picks a single party for a different
    # question and can, because it is choosing whom to ADDRESS. Here the question is whose turn
    # it is, and picking one of five would be inventing the answer. On the pilot 41 thread
    # anchors resolve to 22 people, so the ambiguous ones are a real slice — and they keep both
    # of their cards, which is the status quo, rather than losing one to a coin toss.
    subjects: dict[str, set[str]] = {}
    for row in rows:
        subjects.setdefault(str(row["situation_id"]), set()).add(str(row["person"]))

    held: dict[str, dict[str, str]] = {}
    for row in rows:
        situation_id = str(row["situation_id"])
        if len(subjects.get(situation_id, ())) > 1:
            continue
        person = str(row["person"])
        key = f'{row["domain"]}:{row["situation_type"]}'
        # FIRST ONE WINS for a repeated key. Two `awaiting_response` situations on one person are
        # not a contradiction with themselves, and either can stand for the claim.
        held.setdefault(person, {}).setdefault(key, situation_id)

    out: list[Contradiction] = []
    for person, present in sorted(held.items()):
        for exclusion in exclusions:
            if not exclusion.pair <= set(present):
                continue
            value = None
            if exclusion.arbiter:
                value = _plain((arbiters.get(person) or {}).get(exclusion.arbiter))
            out.append(Contradiction(
                subject_node_id=person,
                subject=names.get(person, person),
                exclusion=exclusion,
                sides=((exclusion.left, present[exclusion.left]),
                       (exclusion.right, present[exclusion.right])),
                arbiter_value=value,
            ))
    return tuple(out)


def read_contradictions(conn, org_id: str, *,
                        exclusions: Sequence[Exclusion] = EXCLUSIONS) -> tuple[Contradiction, ...]:
    """Every declared impossibility live on this org. Three bulk statements, never one per row."""
    if not exclusions:
        return ()
    rows = conn.execute(text(_SITUATIONS_BY_PERSON), {"o": org_id}).mappings().all()
    if not rows:
        return ()
    names = {str(r["node_id"]): str(r["name"] or r["node_id"])
             for r in conn.execute(text(_NAMES), {"o": org_id}).mappings().all()}
    arbiters: dict[str, dict[str, object]] = {}
    fields = arbiter_fields(exclusions)
    if fields:
        from sqlalchemy import bindparam

        stmt = text(_ARBITER_FACTS).bindparams(bindparam("fields", expanding=True))
        for row in conn.execute(stmt, {"o": org_id, "fields": list(fields)}).mappings().all():
            arbiters.setdefault(str(row["person"]), {})[str(row["field"])] = row["value"]
    return find_contradictions(rows, arbiters, names, exclusions=exclusions)


__all__ = [
    "EXCLUSIONS",
    "EXCLUSIONS_DIR",
    "ExclusionError",
    "Contradiction",
    "Exclusion",
    "arbiter_fields",
    "declared_exclusions",
    "load_exclusion",
    "load_exclusions",
    "find_contradictions",
    "read_contradictions",
]
