#!/usr/bin/env python3
"""Validate the authored Expert Brain.

Two passes.

STRUCTURE — each file against its JSON Schema. Needs `jsonschema`; if it is absent the pass
is SKIPPED with a notice rather than silently passing, because a validator that quietly
checks less than you think is worse than none.

SEMANTICS — always runs. These are the checks no schema can express and that keep the brain
honest as it grows past what one person can hold:

  PATTERN HONESTY   A pattern marked `executable` whose fact paths or observation kinds the
                    pipeline does not emit is a lie. Left unchecked the library fills with
                    expertise that looks live and never fires, and nobody finds out until
                    someone asks why the system is quiet.
  SCOPE INTEGRITY   core / capability placement is decided by the REFERENCE GRAPH, not by
                    intent. A scoped object two capabilities load is an error; a core object
                    one capability loads is a warning. Otherwise `core/` decays into
                    "objects we happened to author early".
  LINK INTEGRITY    Every object id referenced anywhere resolves, or is declared planned.
  L2 BINDING        Every situation binds to types Layer 2 actually emits.
  LAYOUT            A capability folder has both required files; a situation sits in the
                    folder its owner_capability names; an object sits in its scope folder.

Exit 1 on any error. --strict promotes warnings to errors.

    python "Domain Expertise/_tools/validate.py" [--strict]
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (ARTIFACT_ID_PREFIX, ARTIFACT_KIND_BY_DIR,  # noqa: E402
                  artifact_dir_of, capability_dir_of, domains, iter_bp_fields,
                  iter_predicate_blocks, knowledge_refs, load_schema, load_set,
                  load_vocabulary, object_scope_of, patterns_of, refs_in_condition, walk)

try:
    import jsonschema
    from referencing import Registry, Resource
except ModuleNotFoundError:
    jsonschema = None

KINDS = ["domain", "object", "artifact", "terminology", "capability", "capability_objects",
         "capability_knowledge", "situation", "model", "offering"]

ERRORS: list[str] = []
WARNINGS: list[str] = []


def err(path: Path, msg: str) -> None:
    ERRORS.append(f"{short(path)}: {msg}")


def warn(path: Path, msg: str) -> None:
    WARNINGS.append(f"{short(path)}: {msg}")


def short(path: Path) -> str:
    p = path.parts
    return "/".join(p[-3:]) if len(p) >= 3 else path.name


def build_validators() -> dict:
    schemas = {k: load_schema(k) for k in KINDS}
    resources = []
    for k, s in schemas.items():
        res = Resource.from_contents(s)
        resources.append((s["$id"], res))
        resources.append((f"{k.replace('_', '-')}.schema.json", res))
    registry = Registry().with_resources(resources)
    return {k: jsonschema.Draft202012Validator(s, registry=registry)
            for k, s in schemas.items()}


# predicate forms, transcribed from engine.py:_eval_condition dispatch order
FORM_KEYS = [
    {"exists"}, {"absent"}, {"has_obs"}, {"no_obs"},
    {"neighbor_has_obs"}, {"neighbor_no_obs"},
    {"neighbor_fact", "op", "value"},
    {"fn", "op", "value"},
    {"fn", "path", "op", "value"},
    {"path", "op", "value"},
]


def check_predicate(path: Path, where: str, cond: dict, vocab: dict) -> None:
    keys = set(cond)
    if keys not in FORM_KEYS:
        err(path, f"{where}: predicate {sorted(keys)} matches no form the engine dispatches "
                  f"on — _eval_condition returns False for it, so it can never fire")
        return
    if "op" in cond and cond["op"] not in vocab["closed"]["predicate_ops"]:
        err(path, f"{where}: op {cond['op']!r} not in {vocab['closed']['predicate_ops']} "
                  f"(IN is uppercase; a lowercase 'in' evaluates False forever)")
    if cond.get("fn") == "edge_count" and "path" in cond:
        err(path, f"{where}: fn=edge_count takes no path")


def main(strict: bool = False) -> int:
    vocab = load_vocabulary()
    sub = vocab["substrate"]
    facts, obs_kinds = set(sub["fact_paths"]), set(sub["obs_kinds"])
    baselines, l2_types = set(sub["baselines"]), set(sub["l2_situation_types"])
    verbs = set(vocab["open"]["relationship_verbs"])
    ev_sources = set(vocab["open"]["evidence_sources"])
    planned_sub = vocab.get("planned_substrate") or {}
    planned_l2 = set(planned_sub.get("l2_situation_types") or [])

    validators = {}
    if jsonschema is None:
        print("NOTICE  jsonschema not installed — STRUCTURE pass skipped.\n"
              "        pip install jsonschema   to enable it.\n")
    else:
        validators = build_validators()

    total = 0
    # Routing is a GLOBAL property, not a per-domain one. Customer Support failing to bind
    # `budget_freeze` is not a defect in Customer Support, and reporting it per domain buries
    # the ~11 genuinely unrouted types under ~40 lines of noise the moment a second domain
    # lands. Accumulate here, report once, after every domain has been read.
    bound_anywhere: set[str] = set()
    pending_anywhere: dict[str, set[str]] = defaultdict(set)

    for droot in domains():
        files = list(walk(droot))
        domain_doc = next((d for k, _, d in files if k == "domain"), {})
        planned = {p["id"] for p in (domain_doc.get("planned_objects") or [])}
        core_roster = {n for group in (domain_doc.get("core_objects") or {}).values()
                       for n in group}

        authored_objects: dict[str, Path] = {}
        authored_artifacts: dict[str, Path] = {}
        object_scope: dict[str, str] = {}
        situations: dict[str, dict] = {}
        capabilities: dict[str, Path] = {}
        terminology_areas: set[str] = set()
        ids_seen: dict[str, Path] = {}
        # object / artifact id -> capability ids that reference it. The scope rule is decided
        # here, from the graph, for BOTH objects and knowledge artifacts — MEDDICC referenced
        # by four capabilities has to be core for the same reason Decision Maker does.
        loaded_by: dict[str, set[str]] = defaultdict(set)

        # ── pass A · structure + census ───────────────────────────────────────────────
        for kind, path, data in files:
            total += 1
            if kind == "__parse_error__":
                ERRORS.append(f"{short(path)}: YAML parse error — {data}")
                continue

            if validators:
                for exc in sorted(validators[kind].iter_errors(data),
                                  key=lambda e: list(e.absolute_path))[:4]:
                    loc = ".".join(str(p) for p in exc.absolute_path) or "<root>"
                    err(path, f"schema[{kind}] at {loc}: {exc.message}")

            ident = data.get("identity") or {}
            oid = ident.get("id")
            if oid:
                if oid in ids_seen:
                    err(path, f"duplicate id {oid!r} — already used by {short(ids_seen[oid])}")
                ids_seen[oid] = path

            if kind == "object" and oid:
                authored_objects[oid] = path
                object_scope[oid] = ident.get("scope", "?")
            elif kind == "artifact" and oid:
                authored_artifacts[oid] = path
                object_scope[oid] = ident.get("scope", "?")
            elif kind == "terminology":
                if data.get("area"):
                    terminology_areas.add(data["area"])
            elif kind == "situation" and oid:
                situations[oid] = data
            elif kind == "capability" and oid:
                capabilities[oid] = path
            elif kind == "capability_objects":
                cap = data.get("capability")
                if cap:
                    for ref in load_set(data)["required"] + load_set(data)["optional"]:
                        loaded_by[ref].add(cap)
            elif kind == "capability_knowledge":
                cap = data.get("capability")
                if cap:
                    for ref in knowledge_refs(data):
                        loaded_by[ref].add(cap)

        # ── pass B · per-file semantics ───────────────────────────────────────────────
        for kind, path, data in files:
            if kind == "__parse_error__":
                continue
            ident = data.get("identity") or {}

            for where, cond in iter_predicate_blocks(data):
                check_predicate(path, where, cond, vocab)

            for where, val in iter_bp_fields(data):
                if not isinstance(val, int) or not 0 <= val <= 10000:
                    err(path, f"{where} = {val!r}: every _bp field is an integer 0-10000 "
                              f"(Atlas Rule 03 — floats do not hash reproducibly)")

            # ---- capability folder layout ----
            if kind == "capability":
                capdir = capability_dir_of(path, droot)
                if capdir is None:
                    err(path, "capability.yaml must live at capabilities/<NN-subdomain>/"
                              "<capability>/")
                    continue
                if not (capdir / "objects.yaml").exists():
                    err(path, "capability folder has no objects.yaml — the load-set is not "
                              "optional; without it nothing compiles")
                declared = ident.get("subdomain")
                match = next((s for s in domain_doc.get("subdomains", [])
                              if s["id"] == declared), None)
                if match is None:
                    err(path, f"subdomain {declared!r} is not declared in domain.yaml")
                elif match["dir"] != capdir.parent.name:
                    err(path, f"subdomain {declared!r} maps to {match['dir']}/ but the folder "
                              f"sits in {capdir.parent.name}/")
                if ident.get("id", "").split(".")[-1] != capdir.name.replace("-", "_"):
                    err(path, f"id leaf does not match folder name {capdir.name!r}")

            # ---- objects.yaml ----
            if kind == "capability_objects":
                capdir = capability_dir_of(path, droot)
                cap = data.get("capability")
                if capdir and cap and cap.split(".")[-1] != capdir.name.replace("-", "_"):
                    err(path, f"capability {cap!r} does not match folder {capdir.name!r}")
                if cap and cap not in capabilities:
                    err(path, f"capability {cap!r} has no capability.yaml")
                for ref in (data.get("core") or {}).get("required", []) + \
                           (data.get("core") or {}).get("optional", []):
                    if ".obj.core." not in ref:
                        err(path, f"{ref} is listed under `core` but is not a core id")
                for ref in (data.get("scoped") or {}).get("required", []) + \
                           (data.get("scoped") or {}).get("optional", []):
                    if ".obj.core." in ref:
                        err(path, f"{ref} is listed under `scoped` but is a core id")
                    elif cap and ref.split(".")[2] != cap.split(".")[-1]:
                        err(path, f"{ref} is scoped to a different capability than {cap!r} — "
                                  f"a scoped object belongs to exactly one")

            # ---- situation ----
            if kind == "situation":
                for t in (data.get("matches") or {}).get("l2_situation_types") or []:
                    if t not in l2_types:
                        err(path, f"matches.l2_situation_types: {t!r} is not a type Layer 2 "
                                  f"emits — the registry lookup can never resolve it. If it "
                                  f"is a type a future pack must emit, move it to "
                                  f"matches.pending_l2_situation_types")
                for p in (data.get("matches") or {}).get("pending_l2_situation_types") or []:
                    t = p.get("type")
                    if t in l2_types:
                        err(path, f"matches.pending_l2_situation_types: {t!r} is ALREADY "
                                  f"emitted by Layer 2 — as written this situation routes "
                                  f"nothing. Move it to matches.l2_situation_types")
                    elif t not in planned_l2:
                        warn(path, f"matches.pending_l2_situation_types: {t!r} is not listed "
                                   f"in vocabulary planned_substrate.l2_situation_types — add "
                                   f"it so the ask stays a census rather than a wish")
                owner = ident.get("owner_capability")
                capdir = capability_dir_of(path, droot)
                if owner and capdir and owner.split(".")[-1] != capdir.name.replace("-", "_"):
                    err(path, f"owner_capability {owner!r} does not match the folder it sits "
                              f"in ({capdir.name})")
                if owner and owner not in capabilities:
                    err(path, f"owner_capability {owner!r} has no capability.yaml")
                for cid in data.get("also_serves") or []:
                    if cid not in capabilities:
                        err(path, f"also_serves references unknown capability {cid!r}")
                    if cid == owner:
                        err(path, f"also_serves repeats the owner {cid!r}")

            # ---- knowledge artifact ----
            if kind == "artifact":
                oid = ident.get("id", "")
                akind = ident.get("kind")
                adir = artifact_dir_of(path, droot)
                parts = oid.split(".")

                if adir and akind and ARTIFACT_KIND_BY_DIR[adir] != akind:
                    err(path, f"kind {akind!r} but the file sits in {adir}/ — that folder "
                              f"holds {ARTIFACT_KIND_BY_DIR[adir]!r}")
                if akind and len(parts) >= 2 and parts[1] != ARTIFACT_ID_PREFIX.get(akind):
                    err(path, f"id prefix {parts[1]!r} does not match kind {akind!r} "
                              f"(expected {ARTIFACT_ID_PREFIX.get(akind)!r})")
                # A rule spanning fewer than two objects is an object's business_rule wearing
                # a coat. The whole reason rules/ exists is edges an object cannot see alone.
                if akind == "rule":
                    spans = (data.get("rule") or {}).get("spans") or []
                    if len(spans) < 2:
                        warn(path, f"rule spans {len(spans)} object(s) — a rule local to one "
                                   f"object belongs in that object's business_rules")
                for ref in (data.get("objects_used") or []) + \
                           ((data.get("rule") or {}).get("spans") or []):
                    if ref and ref not in authored_objects and ref not in planned:
                        err(path, f"references object {ref!r}, which appears nowhere")

            # ---- capability knowledge manifest ----
            if kind == "capability_knowledge":
                capdir = capability_dir_of(path, droot)
                cap = data.get("capability")
                if capdir and cap and cap.split(".")[-1] != capdir.name.replace("-", "_"):
                    err(path, f"capability {cap!r} does not match folder {capdir.name!r}")
                if cap and cap not in capabilities:
                    err(path, f"capability {cap!r} has no capability.yaml")
                for key in ("playbooks", "heuristics", "mental_models", "rules",
                            "decision_frameworks"):
                    block = data.get(key) or {}
                    for ref in block.get("core") or []:
                        if len(ref.split(".")) >= 3 and ref.split(".")[2] != "core":
                            err(path, f"{ref} is listed under {key}.core but is not a core id")
                    for ref in block.get("scoped") or []:
                        p = ref.split(".")
                        if len(p) >= 3 and p[2] == "core":
                            err(path, f"{ref} is listed under {key}.scoped but is a core id")
                        elif cap and len(p) >= 3 and p[2] != cap.split(".")[-1]:
                            err(path, f"{ref} is scoped to a different capability than "
                                      f"{cap!r} — a scoped artifact belongs to exactly one")
                for area in data.get("terminology") or []:
                    if area not in terminology_areas:
                        err(path, f"terminology area {area!r} has no file")
                for ref in knowledge_refs(data):
                    if ref not in authored_artifacts:
                        if ref in planned:
                            warn(path, f"{ref} is planned but not authored yet")
                        else:
                            err(path, f"{ref} appears nowhere — not authored, and not in "
                                      f"domain.yaml planned_objects")

            # ---- object ----
            if kind == "object":
                oid = ident.get("id", "")
                scope = ident.get("scope")
                folder = object_scope_of(path, droot)
                id_scope = oid.split(".")[2] if oid.count(".") >= 3 else None

                if folder and id_scope and folder.replace("-", "_") != id_scope:
                    err(path, f"id scope segment {id_scope!r} does not match folder "
                              f"{folder!r}")
                if scope == "core" and folder != "core":
                    err(path, "scope: core but the file is not in objects/core/")
                if scope == "capability" and folder == "core":
                    err(path, "scope: capability but the file is in objects/core/")
                if scope == "core" and oid.split(".")[-1] not in core_roster:
                    warn(path, f"{oid.split('.')[-1]!r} is not listed in domain.yaml "
                               f"core_objects")
                owner = ident.get("owner_capability")
                if scope == "capability" and owner and owner not in capabilities:
                    err(path, f"owner_capability {owner!r} has no capability.yaml")

                for i, rel in enumerate(data.get("relationships") or []):
                    # The object schema renamed this field `verb` -> `type`. Accept both: the
                    # library is mid-migration and a validator that only understands one shape
                    # reports the other as broken, which is worse than either shape.
                    v = rel.get("type") or rel.get("verb")
                    if v not in verbs:
                        warn(path, f"relationships.{i}: verb {v!r} is outside "
                                   f"the recommended set")
                for e in data.get("evidence") or []:
                    if e.get("source") not in ev_sources:
                        warn(path, f"evidence source {e.get('source')!r} is outside the "
                                   f"recommended set")
                wsum = sum(f.get("weight_bp", 0) for f in data.get("decision_factors") or [])
                if data.get("decision_factors") and wsum != 10000:
                    warn(path, f"decision_factors weight_bp sums to {wsum}, not 10000")

                # PATTERN HONESTY
                for _pkind, pat in patterns_of(data):
                    pid = pat.get("id", "?")
                    if pat.get("status") == "executable":
                        for cond in pat.get("when") or []:
                            p_, o_, b_ = refs_in_condition(cond)
                            for p in p_:
                                if p not in facts:
                                    err(path, f"pattern {pid} is marked executable but names "
                                              f"fact path {p!r}, which the pipeline does not "
                                              f"emit — mark it needs_signal")
                            for o in o_:
                                if o not in obs_kinds:
                                    err(path, f"pattern {pid} is marked executable but names "
                                              f"observation kind {o!r}, which Layer 2 does "
                                              f"not emit — mark it needs_signal")
                            for b in b_:
                                if b not in baselines:
                                    err(path, f"pattern {pid} is marked executable but names "
                                              f"baseline {b!r}, which is not learned")
                    elif pat.get("status") == "needs_signal" and pat.get("when"):
                        ok = True
                        for cond in pat["when"]:
                            p_, o_, b_ = refs_in_condition(cond)
                            ok &= (all(p in facts for p in p_)
                                   and all(o in obs_kinds for o in o_)
                                   and all(b in baselines for b in b_))
                        if ok:
                            warn(path, f"pattern {pid} is marked needs_signal but every "
                                       f"reference resolves — promote it to executable")

            # ---- link integrity, everywhere an object id can appear ----
            targets: list[tuple[str, str]] = []
            for i, rel in enumerate(data.get("relationships") or []):
                targets.append((f"relationships.{i}.target", rel.get("target")))
            # `properties` was renamed `attributes` by the object schema. Walk both, so link
            # integrity keeps holding across the migration instead of silently checking nothing.
            for key in ("properties", "attributes"):
                for i, prop in enumerate(data.get(key) or []):
                    if isinstance(prop, dict) and prop.get("ref"):
                        targets.append((f"{key}.{i}.ref", prop["ref"]))
            if kind == "capability_objects":
                ls = load_set(data)
                for key in ("required", "optional"):
                    for i, ref in enumerate(ls[key]):
                        targets.append((f"{key}.{i}", ref))
                for i, ref in enumerate(data.get("never_load") or []):
                    targets.append((f"never_load.{i}", ref))
            if kind == "situation":
                o = data.get("objects") or {}
                for key in ("load", "optional", "never_load"):
                    for i, ref in enumerate(o.get(key) or []):
                        targets.append((f"objects.{key}.{i}", ref))
            if kind in ("model", "offering"):
                for i, ext in enumerate((data.get("objects") or {}).get("extends") or []):
                    targets.append((f"objects.extends.{i}.object", ext.get("object")))

            # dependencies may point at an artifact as well as an object — "this object cannot
            # be reasoned about without the MEDDICC model" is a real dependency.
            for i, dep in enumerate(data.get("dependencies") or []):
                if isinstance(dep, dict) and dep.get("target"):
                    targets.append((f"dependencies.{i}.target", dep["target"]))

            for where, tgt in targets:
                if not tgt or tgt in authored_objects or tgt in authored_artifacts:
                    continue
                if tgt in planned:
                    warn(path, f"{where}: {tgt} is planned but not authored yet")
                else:
                    err(path, f"{where}: {tgt} appears nowhere — not authored, and not in "
                              f"domain.yaml planned_objects")

        # ── pass C · SCOPE INTEGRITY, decided by the reference graph ──────────────────
        # Objects and knowledge artifacts obey the same rule for the same reason. MEDDICC
        # referenced by four capabilities must be core, or it becomes four copies that drift —
        # which is exactly what happened when it was an inline string on each capability.
        for kindname, home, registry, manifest in (
                ("object", "objects/core/", authored_objects, "objects.yaml"),
                ("artifact", "<kind>/core/", authored_artifacts, "knowledge.yaml")):
            for oid, path in sorted(registry.items()):
                loaders = loaded_by.get(oid, set())
                scope = object_scope.get(oid, "?")
                if scope == "capability" and len(loaders) > 1:
                    err(path, f"scope: capability but {len(loaders)} capabilities reference it "
                              f"({', '.join(sorted(loaders))}) — promote it to {home}")
                if scope == "core" and len(loaders) == 1:
                    warn(path, f"scope: core but only {next(iter(loaders))} references it — "
                               f"consider demoting it to that capability")
                if not loaders:
                    warn(path, f"no capability's {manifest} references this {kindname} — it is "
                               f"authored but unreachable")

        # ── pass D · domain roster agrees with disk, both directions ──────────────────
        on_disk_caps = {c.split(".")[-1] for c in capabilities}
        declared_caps = {c for s in domain_doc.get("subdomains", []) for c in s["capabilities"]}
        for missing in sorted(declared_caps - on_disk_caps):
            err(droot / "domain.yaml", f"capability {missing!r} is declared but has no folder")
        for extra in sorted(on_disk_caps - declared_caps):
            err(droot / "domain.yaml", f"capability folder {extra!r} exists but is not declared")

        on_disk_core = {o.split(".")[-1] for o, s in object_scope.items() if s == "core"}
        for missing in sorted(core_roster - on_disk_core):
            warn(droot / "domain.yaml",
                 f"core object {missing!r} is on the roster but not authored yet")

        # every L2 type the pipeline emits should reach at least one situation, in SOME domain
        for s in situations.values():
            m = s.get("matches") or {}
            bound_anywhere.update(m.get("l2_situation_types") or [])
            for p in m.get("pending_l2_situation_types") or []:
                if p.get("type"):
                    pending_anywhere[p["type"]].add(droot.name)

    for t in sorted(l2_types - bound_anywhere):
        WARNINGS.append(f"<routing>: Layer 2 emits {t!r} and no situation in any domain binds "
                        f"it — no capability will ever compile for it")

    print(f"checked {total} files across {len(domains())} domain(s)")
    if pending_anywhere:
        print(f"{len(pending_anywhere)} situation trigger(s) authored against types no pack "
              f"emits yet — see registry/signal-backlog.md")
    print()
    for w in WARNINGS:
        print(f"  WARN   {w}")
    if WARNINGS:
        print()
    for e in ERRORS:
        print(f"  ERROR  {e}")
    if ERRORS:
        print()

    failed = bool(ERRORS) or (strict and bool(WARNINGS))
    print(f"{len(ERRORS)} error(s), {len(WARNINGS)} warning(s) — {'FAIL' if failed else 'OK'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(strict="--strict" in sys.argv))
