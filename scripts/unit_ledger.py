"""The ratchet that turns "skip nothing" into a red bar.

The V2 layer plans promise their own scope twice. Each group doc opens with a **Component
map** whose `Units` column states how many unit specs that component owes, and then further
down the doc those specs are supposed to appear as `L1.4.3-U2 ·` headings. Nothing has ever
compared the two columns, so a component could declare four units, carry two, and read as
finished — the promise and the delivery live 200 lines apart and no human diffs them.

This reads both halves and subtracts. It reports, per layer and per group: components
declared, units promised by the map, unit specs actually written, and the arithmetic gap
with the specific missing unit IDs named — `L1.4.3-U3`, not "two missing".

**The blind spot this had, and how it is closed.** A component map with no `Units` column
promises nothing, so it can never be under-delivered against. Six of Layer 2's seven group docs
have no such column — only L2.4 wrote one — so the ledger read Layer 2's promise as 20 and its gap
as 2 while six groups sat between 25% and 60% specified. A group that never states its promise
reads greener than one that does, which is exactly backwards. Where a plan states its promise
somewhere else, that file is registered in `PROMISE_SUPPLEMENTS`: its promise ledger fills in the
missing `Units` column (never overriding a doc that wrote its own) and the unit specs written in it
count as written. Layer 2's supplement is `docs/plans/L2_MISSING_UNIT_SPECS.md`.

`--check` makes it a ratchet. The gap is frozen into `scripts/unit_ledger.baseline.json` and
the check fails when a layer's gap grows or a missing unit ID appears that the baseline did
not already carry. The gap can shrink freely; it can never widen unnoticed.

No database, no network — it parses markdown and exits.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: One regex family covers all four layers, because the plans share one ID grammar:
#: `L<layer>.<group>.<component>` for a component and `<base>-U<n>` for a unit spec.
#: Anything that does not match is *not* silently skipped — it is counted as an anomaly and
#: printed, because a doc that invents its own IDs is exactly the kind of drift this catches.
COMPONENT_ID = re.compile(r"\bL([1-4])\.(\d+)\.(\d+)\b")
COMPONENT_HEADING = re.compile(r"^(#+)\s+.*?\bL[1-4]\.\d+\.\d+\s+·")
UNIT_HEADING = re.compile(r"^(#+)\s+(L[1-4](?:\.\d+)+)-U(\d+)\s+·")
COMPONENT_MAP_HEADING = re.compile(r"^#+\s*component map\b", re.IGNORECASE)
COMPONENT_ID_CELL = re.compile(r"^L[1-4]\.\d+\.\d+$")
GROUP_DOC = re.compile(r"Group-(L[1-4]\.\d+)-", re.IGNORECASE)
LAYER_DIR = re.compile(r"^0[1-4]-Layer-([1-4])-Plan$")

#: Matches `**ACCEPTANCE**` and the two variants the docs actually use —
#: `**ACCEPTANCE / gate K1**` and `**ACCEPTANCE** — <prose>`.
ACCEPTANCE = re.compile(r"\*\*ACCEPTANCE\b")

#: A unit's spec block ends here even when the heading is deeper than the unit's own, because
#: these are group-scope sections: the gate belongs to every unit at once, and the reverse
#: prompt is the agent brief. Without this a level-1 unit would absorb the group gate's own
#: ACCEPTANCE and read as covered when it states nothing.
BLOCK_BOUNDARY = re.compile(r"^#+\s+.*\b(group acceptance gate|reverse prompt)\b", re.IGNORECASE)

#: L4's group docs number their work `# C1 ·`, `# U1 ·`, `# E1 ·`, `# S1 ·` — component-local
#: counters with no layer/group prefix. They are real specs but they carry no addressable ID,
#: so the ledger cannot tie them to a component map. Detected and reported, never counted.
NON_CANONICAL_SPEC = re.compile(r"^#+\s+\**[A-Z]{1,2}\d+\**\s+·")

#: A `## Promise ledger` heading in a supplement, whose first following table states the `Units`
#: each component owes. Same grammar as a Component map — deliberately, so one parser reads both.
PROMISE_LEDGER_HEADING = re.compile(r"^#+\s*(?:\d+[.)]\s*)?promise ledger\b", re.IGNORECASE)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN_ROOT = REPO_ROOT / "Rohit_Updates (Version 2)" / "Version 2 Updates"
DEFAULT_BASELINE = Path(__file__).resolve().parent / "unit_ledger.baseline.json"

#: Layer number -> the file that states a promise its group docs never wrote. A supplement may
#: only FILL IN an unstated promise; a component whose own map declared a `Units` count keeps it,
#: so L2.4 — the one Layer 2 group that stated its own — is untouched by this.
PROMISE_SUPPLEMENTS: dict[int, Path] = {
    2: REPO_ROOT / "docs" / "plans" / "L2_MISSING_UNIT_SPECS.md",
}


def strip_md(cell: str) -> str:
    """Markdown emphasis is decoration on an ID, not part of it.

    Component maps bold the rows that matter (`| **L2.2.7** | **Version Manager** |`), so the
    first cell has to be unwrapped before it can be matched as an identifier.
    """
    return cell.replace("*", "").replace("`", "").strip()


def sort_key(unit_or_component_id: str) -> tuple:
    """Natural order, so `L1.4.10` sorts after `L1.4.9` instead of after `L1.4.1`."""
    return tuple(int(n) for n in re.findall(r"\d+", unit_or_component_id))


@dataclass
class Component:
    cid: str
    #: Units the component map promises. `None` means the map declared the component but had
    #: no `Units` column at all (L1.7, every L2 group but L2.4, L3.1) — an unstated promise is
    #: reported as unstated, never silently read as zero.
    promised: int | None = None
    written: set[int] = field(default_factory=set)
    accepted: set[int] = field(default_factory=set)
    #: The subset of `written` whose spec lives in a supplement rather than in the group doc.
    #: Reported so "specified" is never mistaken for "specified where the builder will look".
    supplement_written: set[int] = field(default_factory=set)
    #: True when the component only ever appeared as a `## L1.3.4 ·` heading and never as a
    #: row in the map — the reverse drift, spec without a promise.
    heading_only: bool = False
    #: `"map"` when the group doc's own Component map stated the count, `"supplement"` when it
    #: was filled in from `PROMISE_SUPPLEMENTS`, `None` when nobody has stated it. A promise
    #: stated outside the plan is still a promise, but a reader must be able to see that it is.
    promise_source: str | None = None

    @property
    def gap(self) -> int:
        if self.promised is None:
            return 0
        return max(0, self.promised - len(self.written))

    @property
    def missing_ids(self) -> list[str]:
        if self.promised is None:
            return []
        return [f"{self.cid}-U{n}" for n in range(1, self.promised + 1) if n not in self.written]

    @property
    def over_delivered(self) -> int:
        if self.promised is None:
            return 0
        return max(0, len(self.written) - self.promised)


@dataclass
class Group:
    gid: str
    path: Path
    components: dict[str, Component] = field(default_factory=dict)
    #: Units addressed to the group itself (`L1.1-U1`, `L3.1-U2`) rather than to a component.
    #: They are real written specs, so they count as written — but they cannot close a
    #: component's gap, because no component map row claims them.
    group_units: dict[int, bool] = field(default_factory=dict)
    has_component_map: bool = False
    non_canonical_specs: int = 0

    @property
    def promised_from_supplement(self) -> int:
        return sum(c.promised or 0 for c in self.components.values()
                   if c.promise_source == "supplement")

    @property
    def written_in_supplement(self) -> int:
        return sum(len(c.supplement_written) for c in self.components.values())

    @property
    def declared(self) -> int:
        return len(self.components)

    @property
    def promised(self) -> int:
        return sum(c.promised for c in self.components.values() if c.promised is not None)

    @property
    def written(self) -> int:
        return sum(len(c.written) for c in self.components.values()) + len(self.group_units)

    @property
    def written_in_mapped(self) -> int:
        return sum(len(c.written) for c in self.components.values())

    @property
    def accepted(self) -> int:
        return sum(len(c.accepted) for c in self.components.values()) + sum(
            1 for ok in self.group_units.values() if ok
        )

    @property
    def gap(self) -> int:
        return sum(c.gap for c in self.components.values())

    @property
    def missing_ids(self) -> list[str]:
        out: list[str] = []
        for c in sorted(self.components.values(), key=lambda c: sort_key(c.cid)):
            out.extend(c.missing_ids)
        return out


@dataclass
class Layer:
    n: int
    groups: dict[str, Group] = field(default_factory=dict)

    @property
    def lid(self) -> str:
        return f"L{self.n}"

    def _sum(self, attr: str) -> int:
        return sum(getattr(g, attr) for g in self.groups.values())

    @property
    def declared(self) -> int:
        return self._sum("declared")

    @property
    def promised(self) -> int:
        return self._sum("promised")

    @property
    def written(self) -> int:
        return self._sum("written")

    @property
    def accepted(self) -> int:
        return self._sum("accepted")

    @property
    def gap(self) -> int:
        return self._sum("gap")

    @property
    def missing_ids(self) -> list[str]:
        out: list[str] = []
        for g in sorted(self.groups.values(), key=lambda g: sort_key(g.gid)):
            out.extend(g.missing_ids)
        return out


def parse_tables(lines: list[str]) -> list[tuple[int, list[list[str]]]]:
    """Every pipe-table in the doc, as (start_line_index, rows-of-cells)."""
    tables: list[tuple[int, list[list[str]]]] = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            start = i
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            tables.append((start, rows))
        else:
            i += 1
    return tables


def units_column(header: list[str]) -> int | None:
    for idx, cell in enumerate(header):
        if strip_md(cell).lower() == "units":
            return idx
    return None


def read_component_map(lines: list[str], group: Group) -> None:
    """Load the promised unit counts from the group's Component map.

    Primary source is the table under a `## Component map` heading. Where a group never wrote
    one — L2.1 titles its table "The eight views" — the first table whose left column is made
    of component IDs stands in, so the components still get counted as declared even though
    the doc states no unit promise for them.
    """
    tables = parse_tables(lines)
    chosen: list[list[str]] | None = None

    map_line = next((i for i, ln in enumerate(lines) if COMPONENT_MAP_HEADING.match(ln)), None)
    if map_line is not None:
        group.has_component_map = True
        for start, rows in tables:
            if start > map_line:
                chosen = rows
                break
    else:
        for _start, rows in tables:
            ids = [strip_md(r[0]) for r in rows[2:] if r]
            if len(ids) >= 2 and all(COMPONENT_ID_CELL.match(x) for x in ids):
                chosen = rows
                break

    if not chosen or len(chosen) < 2:
        return

    header = chosen[0]
    ucol = units_column(header)
    for row in chosen[1:]:
        if not row or set("".join(row)) <= set("-: "):
            continue                                   # the |---|---| separator
        cid = strip_md(row[0])
        if not COMPONENT_ID_CELL.match(cid):
            continue
        promised: int | None = None
        if ucol is not None and ucol < len(row):
            raw = strip_md(row[ucol])
            if raw.isdigit():
                promised = int(raw)
        group.components[cid] = Component(
            cid=cid, promised=promised, promise_source=None if promised is None else "map")


def read_specs(lines: list[str], group: Group) -> None:
    """Record every component heading and every unit spec, with its ACCEPTANCE state.

    A unit's section runs from its heading to the next *structural* heading: another unit, a
    component, a group-scope section, or any heading shallower than the unit's own. Depth alone
    is not enough — L1.6.7-U1 and L2.7.7-U1 both break their spec into `###` prose subheads at
    the unit's own level (`### The two numbers are different`), and ending on depth would cut
    the block before its ACCEPTANCE and under-report coverage.
    """
    boundaries: list[tuple[int, int, bool]] = []
    for i, ln in enumerate(lines):
        m = re.match(r"^(#+)\s", ln)
        if not m:
            continue
        structural = bool(
            UNIT_HEADING.match(ln) or COMPONENT_HEADING.match(ln) or BLOCK_BOUNDARY.match(ln)
        )
        boundaries.append((i, len(m.group(1)), structural))

    def section_end(start: int, level: int) -> int:
        for i, lvl, structural in boundaries:
            if i > start and (structural or lvl < level):
                return i
        return len(lines)

    for i, line in enumerate(lines):
        if NON_CANONICAL_SPEC.match(line):
            group.non_canonical_specs += 1

        if (m := COMPONENT_HEADING.match(line)) and not UNIT_HEADING.match(line):
            found = COMPONENT_ID.search(strip_md(line))
            if found:
                cid = found.group(0)
                if cid not in group.components:
                    group.components[cid] = Component(cid=cid, heading_only=True)
            continue

        m = UNIT_HEADING.match(line)
        if not m:
            continue
        level, base, n = len(m.group(1)), m.group(2), int(m.group(3))
        has_acceptance = any(
            ACCEPTANCE.search(lines[j]) for j in range(i, section_end(i, level))
        )
        if COMPONENT_ID_CELL.match(base):
            comp = group.components.setdefault(base, Component(cid=base, heading_only=True))
            comp.written.add(n)
            if has_acceptance:
                comp.accepted.add(n)
        else:
            group.group_units[n] = has_acceptance


def read_promise_ledger(lines: list[str]) -> dict[str, int]:
    """A supplement's `## Promise ledger` table -> {component id: units promised}.

    Deliberately the same shape as a Component map: a `Units` column and component ids in the
    first cell. A supplement that states a promise for a component the plan never declared is
    reported by `scan` as an anomaly rather than silently inventing a component.
    """
    start = next((i for i, ln in enumerate(lines) if PROMISE_LEDGER_HEADING.match(ln)), None)
    if start is None:
        return {}
    table = next((rows for line, rows in parse_tables(lines) if line > start), None)
    if not table or len(table) < 2:
        return {}
    ucol = units_column(table[0])
    if ucol is None:
        return {}
    out: dict[str, int] = {}
    for row in table[1:]:
        if not row or set("".join(row)) <= set("-: "):
            continue
        cid = strip_md(row[0])
        if not COMPONENT_ID_CELL.match(cid) or ucol >= len(row):
            continue
        raw = strip_md(row[ucol])
        if raw.isdigit():
            out[cid] = int(raw)
    return out


def apply_supplement(layer: Layer, path: Path) -> list[str]:
    """Fill in the promise a layer's group docs never stated, and count the specs written here.

    Two rules keep this honest. A supplement may only fill a promise that is `None` — a component
    whose own map wrote a `Units` count keeps it, so a supplement can never quietly lower a stated
    promise. And a supplement's unit specs count as WRITTEN, because they are: a spec is a spec
    wherever it lives. Both facts are surfaced separately in the report so neither is invisible.

    Returns the anomalies found, which are reported rather than raised.
    """
    if not path.exists():
        return [f"{layer.lid}: promise supplement not found at {path}"]
    lines = path.read_text(encoding="utf-8").splitlines()
    anomalies: list[str] = []

    for cid, promised in read_promise_ledger(lines).items():
        group = layer.groups.get(cid.rsplit(".", 1)[0])
        if group is None:
            anomalies.append(f"{layer.lid}: {path.name} promises {cid}, a group the plan has no doc for")
            continue
        comp = group.components.get(cid)
        if comp is None:
            anomalies.append(f"{layer.lid}: {path.name} promises {cid}, absent from its Component map")
            comp = group.components.setdefault(cid, Component(cid=cid, heading_only=True))
        if comp.promised is None:
            comp.promised, comp.promise_source = promised, "supplement"
        elif comp.promised != promised:
            anomalies.append(
                f"{layer.lid}: {cid} promises {comp.promised} in its Component map and "
                f"{promised} in {path.name} — the map wins")

    scratch = Group(gid="supplement", path=path)
    read_specs(lines, scratch)
    for cid, found in scratch.components.items():
        if not found.written:
            continue
        group = layer.groups.get(cid.rsplit(".", 1)[0])
        if group is None:
            anomalies.append(f"{layer.lid}: {path.name} specs {cid}, a group the plan has no doc for")
            continue
        comp = group.components.setdefault(cid, Component(cid=cid, heading_only=True))
        comp.written |= found.written
        comp.accepted |= found.accepted
        comp.supplement_written |= found.written
    return anomalies


def scan(plan_root: Path, *, supplements: dict[int, Path] | None = None) -> tuple[dict[int, Layer], list[str]]:
    layers: dict[int, Layer] = {}
    for layer_dir in sorted(plan_root.iterdir()):
        lm = LAYER_DIR.match(layer_dir.name)
        if not layer_dir.is_dir() or not lm:
            continue
        layer = Layer(n=int(lm.group(1)))
        layers[layer.n] = layer
        for doc in sorted(layer_dir.glob("*.md")):
            gm = GROUP_DOC.search(doc.name)
            if not gm:
                continue
            group = Group(gid=gm.group(1), path=doc)
            layer.groups[group.gid] = group
            lines = doc.read_text(encoding="utf-8").splitlines()
            read_component_map(lines, group)
            read_specs(lines, group)
    anomalies: list[str] = []
    for n, path in (supplements or {}).items():
        if n in layers:
            anomalies.extend(apply_supplement(layers[n], path))
        else:
            anomalies.append(f"L{n}: a promise supplement is registered but the layer has no plan dir")
    return layers, anomalies


def to_report(layers: dict[int, Layer], scan_anomalies: list[str] | None = None) -> dict:
    out: dict = {"layers": {}, "totals": {}, "scan_anomalies": list(scan_anomalies or [])}
    for n in sorted(layers):
        layer = layers[n]
        groups: dict[str, dict] = {}
        for gid in sorted(layer.groups, key=sort_key):
            g = layer.groups[gid]
            groups[gid] = {
                "doc": g.path.name,
                "has_component_map": g.has_component_map,
                "components_declared": g.declared,
                "units_promised": g.promised,
                "units_written": g.written,
                "units_written_in_mapped_components": g.written_in_mapped,
                "units_written_at_group_level": len(g.group_units),
                "units_promised_by_supplement": g.promised_from_supplement,
                "units_written_in_supplement": g.written_in_supplement,
                "acceptance_blocks": g.accepted,
                "gap": g.gap,
                "missing_unit_ids": g.missing_ids,
                "non_canonical_specs": g.non_canonical_specs,
                "components": {
                    c.cid: {
                        "promised": c.promised,
                        "written": sorted(c.written),
                        "gap": c.gap,
                        "over_delivered": c.over_delivered,
                        "in_component_map": not c.heading_only,
                        "promise_source": c.promise_source,
                        "written_in_supplement": sorted(c.supplement_written),
                    }
                    for c in sorted(g.components.values(), key=lambda c: sort_key(c.cid))
                },
            }
        out["layers"][layer.lid] = {
            "components_declared": layer.declared,
            "units_promised": layer.promised,
            "units_written": layer.written,
            "acceptance_blocks": layer.accepted,
            "gap": layer.gap,
            "missing_unit_ids": layer.missing_ids,
            "groups": groups,
        }
    out["totals"] = {
        "components_declared": sum(l.declared for l in layers.values()),
        "units_promised": sum(l.promised for l in layers.values()),
        "units_written": sum(l.written for l in layers.values()),
        "acceptance_blocks": sum(l.accepted for l in layers.values()),
        "gap": sum(l.gap for l in layers.values()),
        "units_promised_by_supplement": sum(
            g.promised_from_supplement for l in layers.values() for g in l.groups.values()),
        "units_written_in_supplement": sum(
            g.written_in_supplement for l in layers.values() for g in l.groups.values()),
    }
    return out


def baseline_of(report: dict) -> dict:
    """The frozen part of the report — gaps, promises and the named missing IDs.

    The PROMISE is frozen as well as the gap, and that is not redundant. A gap is
    `promised - written`, so deleting the promise closes the gap: drop a supplement file, or
    remove a row from its promise ledger, and a group that owed five unwritten specs reports a
    perfect zero. Freezing the promise makes that show up as what it is — the promise moved —
    instead of as success.
    """
    return {
        "gap_by_layer": {lid: l["gap"] for lid, l in report["layers"].items()},
        "gap_by_group": {
            gid: g["gap"] for l in report["layers"].values() for gid, g in l["groups"].items()
        },
        "promised_by_group": {
            gid: g["units_promised"]
            for l in report["layers"].values() for gid, g in l["groups"].items()
        },
        "missing_unit_ids": sorted(
            {uid for l in report["layers"].values() for uid in l["missing_unit_ids"]},
            key=sort_key,
        ),
        "total_gap": report["totals"]["gap"],
    }


def pct(num: int, den: int) -> str:
    return f"{(num * 100 // den) if den else 0}%"


def render(report: dict, show_missing: bool) -> str:
    lines: list[str] = []
    w = (6, 7, 10, 10, 10, 8, 9, 8)
    head = (
        f"{'LAYER':<{w[0]}}{'GROUP':<{w[1]}}{'COMPNTS':>{w[2]}}"
        f"{'PROMISD':>{w[3]}}{'WRITTEN':>{w[4]}}{'GAP':>{w[5]}}{'ACCEPT':>{w[6]}}"
        f"{'SUPP':>{w[7]}}"
    )
    lines.append(head)
    lines.append("-" * len(head))

    for lid, layer in report["layers"].items():
        for gid, g in layer["groups"].items():
            promised = str(g["units_promised"]) if g["units_promised"] else "—"
            flag = "  !" if g["gap"] else ""
            supp = (f"{g['units_promised_by_supplement']}/{g['units_written_in_supplement']}"
                    if g["units_promised_by_supplement"] or g["units_written_in_supplement"]
                    else "—")
            lines.append(
                f"{'':<{w[0]}}{gid:<{w[1]}}{g['components_declared']:>{w[2]}}"
                f"{promised:>{w[3]}}{g['units_written']:>{w[4]}}"
                f"{g['gap'] or '—':>{w[5]}}{g['acceptance_blocks']:>{w[6]}}"
                f"{supp:>{w[7]}}{flag}"
            )
        lines.append("-" * len(head))
        lsupp = sum(g["units_promised_by_supplement"] for g in layer["groups"].values())
        lwritten = sum(g["units_written_in_supplement"] for g in layer["groups"].values())
        lsupp_cell = f"{lsupp}/{lwritten}" if lsupp or lwritten else "—"
        lines.append(
            f"{lid:<{w[0]}}{'TOTAL':<{w[1]}}{layer['components_declared']:>{w[2]}}"
            f"{layer['units_promised'] or '—':>{w[3]}}{layer['units_written']:>{w[4]}}"
            f"{layer['gap'] or '—':>{w[5]}}{layer['acceptance_blocks']:>{w[6]}}"
            f"{lsupp_cell:>{w[7]}}"
        )
        lines.append("=" * len(head))

    t = report["totals"]
    tsupp = f"{t['units_promised_by_supplement']}/{t['units_written_in_supplement']}"
    lines.append(
        f"{'ALL':<{w[0]}}{'':<{w[1]}}{t['components_declared']:>{w[2]}}"
        f"{t['units_promised']:>{w[3]}}{t['units_written']:>{w[4]}}"
        f"{t['gap']:>{w[5]}}{t['acceptance_blocks']:>{w[6]}}{tsupp:>{w[7]}}"
    )
    lines.append("")
    lines.append(
        "SUPP = units promised by a registered promise supplement / unit specs written in it. "
        "A group doc with no `Units` column promises nothing and so can never be under-delivered "
        "against — the supplement is what makes its promise countable."
    )
    lines.append(
        f"acceptance coverage: {t['acceptance_blocks']}/{t['units_written']} written units "
        f"carry an **ACCEPTANCE** block ({pct(t['acceptance_blocks'], t['units_written'])})"
    )

    if show_missing:
        for lid, layer in report["layers"].items():
            if not layer["missing_unit_ids"]:
                continue
            lines.append("")
            lines.append(f"{lid} — {layer['gap']} unit specs promised but never written:")
            for gid, g in layer["groups"].items():
                if not g["missing_unit_ids"]:
                    continue
                lines.append(f"  {gid}: " + ", ".join(g["missing_unit_ids"]))

    anomalies: list[str] = list(report.get("scan_anomalies", []))
    for lid, layer in report["layers"].items():
        no_map = [gid for gid, g in layer["groups"].items() if not g["has_component_map"]]
        nc = sum(g["non_canonical_specs"] for g in layer["groups"].values())
        if layer["units_written"] == 0 and nc:
            anomalies.append(
                f"{lid}: 0 canonical unit IDs, but {nc} headings use component-local counters "
                f"(`# C1 ·`, `# U1 ·`, `# E1 ·`, `# S1 ·`). Its specs are unaddressable — "
                f"the ledger cannot tie them to a component map."
            )
        if no_map:
            anomalies.append(f"{lid}: no Component map in {', '.join(no_map)} — promise unstated.")
        unstated = [
            gid for gid, g in layer["groups"].items()
            if any(c["promised"] is None for c in g["components"].values())
        ]
        if unstated:
            anomalies.append(
                f"{lid}: components with NO stated unit promise in {', '.join(unstated)} — "
                f"they cannot be under-delivered against; register a promise supplement or add a "
                f"`Units` column."
            )
        supplemented = [
            gid for gid, g in layer["groups"].items() if g["units_promised_by_supplement"]
        ]
        if supplemented:
            anomalies.append(
                f"{lid}: promise stated OUTSIDE the plan for {', '.join(supplemented)} "
                f"(see PROMISE_SUPPLEMENTS) — the group docs still state no `Units` column."
            )
        unmapped = [
            f"{cid}"
            for g in layer["groups"].values()
            for cid, c in g["components"].items()
            if not c["in_component_map"]
        ]
        if unmapped:
            anomalies.append(
                f"{lid}: specced but absent from the Component map — {', '.join(unmapped)}"
            )
        over = [
            f"{cid} (+{c['over_delivered']})"
            for g in layer["groups"].values()
            for cid, c in g["components"].items()
            if c["over_delivered"]
        ]
        if over:
            anomalies.append(f"{lid}: more units written than promised — {', '.join(over)}")
    if anomalies:
        lines.append("")
        lines.append("ANOMALIES")
        lines.extend(f"  - {a}" for a in anomalies)
    return "\n".join(lines)


def check(report: dict, baseline_path: Path) -> int:
    if not baseline_path.exists():
        print(f"no baseline at {baseline_path} — run with --write-baseline first", file=sys.stderr)
        return 1
    base = json.loads(baseline_path.read_text(encoding="utf-8"))
    now = baseline_of(report)

    failures: list[str] = []
    for lid, gap in now["gap_by_layer"].items():
        was = base["gap_by_layer"].get(lid)
        if was is None:
            failures.append(f"{lid} is not in the baseline (new layer) — gap {gap}")
        elif gap > was:
            failures.append(f"{lid} gap grew {was} -> {gap}")
    for gid, gap in now["gap_by_group"].items():
        was = base["gap_by_group"].get(gid)
        if was is None:
            failures.append(f"{gid} is not in the baseline (new group) — gap {gap}")
        elif gap > was:
            failures.append(f"{gid} gap grew {was} -> {gap}")
    for gid, promised in now["promised_by_group"].items():
        was = base.get("promised_by_group", {}).get(gid)
        if was is not None and promised < was:
            failures.append(
                f"{gid} promise shrank {was} -> {promised} — a gap closed by deleting the "
                f"promise, not by writing the spec")
    appeared = sorted(set(now["missing_unit_ids"]) - set(base["missing_unit_ids"]), key=sort_key)
    if appeared:
        failures.append("newly missing unit specs: " + ", ".join(appeared))

    if failures:
        print("UNIT LEDGER: RATCHET BROKEN")
        for f in failures:
            print(f"  - {f}")
        return 1

    closed = sorted(set(base["missing_unit_ids"]) - set(now["missing_unit_ids"]), key=sort_key)
    print(f"UNIT LEDGER: OK — total gap {now['total_gap']} (baseline {base['total_gap']})")
    if closed:
        print(f"  closed since baseline ({len(closed)}): " + ", ".join(closed))
        print("  the gap shrank — re-run with --write-baseline to tighten the ratchet")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_PLAN_ROOT, help="V2 plan root")
    ap.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    ap.add_argument("--json", action="store_true", help="machine-readable report for CI")
    ap.add_argument("--check", action="store_true", help="fail if the gap grew since baseline")
    ap.add_argument("--write-baseline", action="store_true", help="freeze today's gap")
    ap.add_argument("--no-missing", action="store_true", help="omit the missing-ID listing")
    ap.add_argument("--no-supplement", action="store_true",
                    help="ignore PROMISE_SUPPLEMENTS and report only what the plan docs state")
    args = ap.parse_args(argv)

    if not args.root.is_dir():
        print(f"plan root not found: {args.root}", file=sys.stderr)
        return 2

    layers, scan_anomalies = scan(
        args.root, supplements=None if args.no_supplement else PROMISE_SUPPLEMENTS)
    report = to_report(layers, scan_anomalies)

    if args.write_baseline:
        args.baseline.write_text(
            json.dumps(baseline_of(report), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"baseline written: {args.baseline} (total gap {report['totals']['gap']})")
        return 0
    if args.check:
        return check(report, args.baseline)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(render(report, show_missing=not args.no_missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
