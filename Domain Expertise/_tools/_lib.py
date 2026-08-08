"""Shared loading for the Domain Expertise tools. PyYAML is the only hard dependency.

v2 layout:

    <Domain> Expertise/
      domain.yaml
      objects/core/<name>.yaml                       scope: core
      objects/<capability>/<name>.yaml               scope: capability
      capabilities/<NN-subdomain>/<capability>/
        capability.yaml
        objects.yaml                                 the load-set, references only
        situations/<name>.yaml
      models/<model>/model.yaml  + verticals/<v>/vertical.yaml
      offerings/<family>/offering.yaml + <type>/offering.yaml
      registry/                                      GENERATED
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent          # Domain Expertise/
SCHEMA_DIR = ROOT / "_schema"

KIND_BY_FILENAME = {
    "domain.yaml": "domain",
    "model.yaml": "model",
    "vertical.yaml": "model",
    "offering.yaml": "offering",
    "capability.yaml": "capability",
    "objects.yaml": "capability_objects",
    "knowledge.yaml": "capability_knowledge",
}

# Top-level folders holding scoped content, and the kind each yields. All five artifact
# folders share one schema discriminated by `kind`; the folder is checked against it.
SCOPED_DIRS = {
    "objects": "object",
    "playbooks": "artifact",
    "heuristics": "artifact",
    "mental-models": "artifact",
    "rules": "artifact",
    "decision-frameworks": "artifact",
}

# folder -> the identity.kind an artifact in it must declare
ARTIFACT_KIND_BY_DIR = {
    "playbooks": "playbook",
    "heuristics": "heuristic",
    "mental-models": "mental_model",
    "rules": "rule",
    "decision-frameworks": "decision_framework",
}

# identity.kind -> the id prefix it must use
ARTIFACT_ID_PREFIX = {
    "playbook": "pb",
    "heuristic": "heu",
    "mental_model": "mm",
    "rule": "rule",
    "decision_framework": "df",
}


def load_yaml(path: Path):
    with path.open() as fh:
        return yaml.safe_load(fh)


def load_vocabulary() -> dict:
    return load_yaml(SCHEMA_DIR / "vocabulary.yaml")


def load_schema(kind: str) -> dict:
    name = kind.replace("_", "-")
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())


def domains() -> list[Path]:
    return sorted(p for p in ROOT.iterdir()
                  if p.is_dir() and not p.name.startswith("_") and (p / "domain.yaml").exists())


def classify(path: Path, domain_root: Path) -> str | None:
    """Filenames are checked BEFORE directories: a capability's objects.yaml manifest and an
    object definition under objects/ are different things with confusable paths."""
    if path.name in KIND_BY_FILENAME:
        return KIND_BY_FILENAME[path.name]
    rel = path.relative_to(domain_root).parts
    if "situations" in rel:
        return "situation"
    if not rel:
        return None
    if rel[0] == "terminology":
        return "terminology"
    return SCOPED_DIRS.get(rel[0])


def capability_dir_of(path: Path, domain_root: Path) -> Path | None:
    """The capability folder a capability.yaml / objects.yaml / situation lives inside."""
    rel = path.relative_to(domain_root).parts
    if not rel or rel[0] != "capabilities" or len(rel) < 3:
        return None
    return domain_root / rel[0] / rel[1] / rel[2]


def object_scope_of(path: Path, domain_root: Path) -> str | None:
    """The scope folder segment — 'core' or a capability leaf name. Works for objects/ and
    for all five artifact folders, since they share the core/<capability> convention."""
    rel = path.relative_to(domain_root).parts
    if len(rel) >= 3 and rel[0] in SCOPED_DIRS:
        return rel[1]
    return None


def artifact_dir_of(path: Path, domain_root: Path) -> str | None:
    """The top-level folder an artifact sits in — 'playbooks', 'rules', ..."""
    rel = path.relative_to(domain_root).parts
    return rel[0] if rel and rel[0] in ARTIFACT_KIND_BY_DIR else None


def knowledge_refs(knowledge_yaml: dict) -> list[str]:
    """Every artifact id a capability's knowledge.yaml references, core and scoped merged."""
    out: list[str] = []
    for key in ("playbooks", "heuristics", "mental_models", "rules", "decision_frameworks"):
        block = knowledge_yaml.get(key) or {}
        out += list(block.get("core") or [])
        out += list(block.get("scoped") or [])
    if knowledge_yaml.get("primary_framework"):
        out.append(knowledge_yaml["primary_framework"])
    return out


def walk(domain_root: Path):
    """Yield (kind, path, data) for every authored file under one domain, registry excluded."""
    for path in sorted(domain_root.rglob("*.yaml")):
        parts = path.relative_to(domain_root).parts
        if "registry" in parts:
            continue
        kind = classify(path, domain_root)
        if kind is None:
            continue
        try:
            data = load_yaml(path)
        except yaml.YAMLError as exc:
            yield ("__parse_error__", path, str(exc))
            continue
        if isinstance(data, dict):
            yield (kind, path, data)


def load_set(objects_yaml: dict) -> dict[str, list[str]]:
    """Flatten an objects.yaml into {'required': [...], 'optional': [...]}, core and scoped
    merged — most callers want the union, and the split is a placement concern."""
    out = {"required": [], "optional": []}
    for bucket in ("core", "scoped"):
        b = objects_yaml.get(bucket) or {}
        out["required"] += list(b.get("required") or [])
        out["optional"] += list(b.get("optional") or [])
    return out


def iter_predicate_blocks(data, _key_names=(
        "when", "entered_when", "preconditions", "emitted_when", "conditions")):
    """Yield (dotted_location, condition_dict) for every predicate anywhere in a document.

    `preconditions` is overloaded on purpose and both readings are correct: an object's
    top-level preconditions are RECORDS (id · statement · requires · when · if_unmet), while
    an action's preconditions are a bare predicate list. A record is recognised by carrying
    `statement` or `id`, and is recursed into rather than judged — its own `when` is where the
    predicates actually live. Judging the record itself reported every honest precondition as
    an unfireable rule.
    """
    def is_record(d):
        return isinstance(d, dict) and ("statement" in d or "id" in d)

    def rec(node, trail):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _key_names and isinstance(v, list):
                    for i, cond in enumerate(v):
                        if not isinstance(cond, dict):
                            continue
                        if is_record(cond):
                            yield from rec(cond, trail + [k, str(i)])
                        else:
                            yield (".".join(trail + [k, str(i)]), cond)
                else:
                    yield from rec(v, trail + [str(k)])
        elif isinstance(node, list):
            for i, item in enumerate(node):
                yield from rec(item, trail + [str(i)])
    yield from rec(data, [])


def iter_bp_fields(data):
    def rec(node, trail):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str) and k.endswith("_bp") and not isinstance(v, (dict, list)):
                    yield (".".join(trail + [k]), v)
                else:
                    yield from rec(v, trail + [str(k)])
        elif isinstance(node, list):
            for i, item in enumerate(node):
                yield from rec(item, trail + [str(i)])
    yield from rec(data, [])


def patterns_of(obj: dict):
    ip = obj.get("inference_patterns") or {}
    for kind in ("deterministic", "heuristic"):
        for pat in (ip.get(kind) or []):
            if isinstance(pat, dict):
                yield kind, pat


def refs_in_condition(cond: dict) -> tuple[list[str], list[str], list[str]]:
    """(fact_paths, obs_kinds, baselines) named by one predicate."""
    paths, obs, base = [], [], []
    for key in ("exists", "absent"):
        if key in cond:
            paths.append(cond[key])
    for key in ("has_obs", "no_obs", "neighbor_has_obs", "neighbor_no_obs"):
        if key in cond:
            obs.append(cond[key])
    if "neighbor_fact" in cond:
        paths.append(cond["neighbor_fact"])
    if "path" in cond:
        paths.append(cond["path"])
    val = cond.get("value")
    if isinstance(val, dict) and "baseline" in val:
        base.append(val["baseline"])
    return paths, obs, base
