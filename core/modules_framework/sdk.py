"""Module contract + strict validation.

Per MD g-i-5 §5.1.1 — the SDK MUST reject modules that:
- Contain executable reasoning code (engine.py, reasoner.py, etc.)
- Contain model weights (LoRA, .ckpt, .safetensors, .pt)
- Reference unknown scopes
- Have auto-causal edges (status != "asserted") in graph fragment
- Have rules referencing unknown fact types

These rejections happen at LOAD time — before any rule fires, before any
graph fragment merges. Fail-loud, fail-early.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ─────────────────────────────────────────────────────────────────────────────
# Manifest schema
# ─────────────────────────────────────────────────────────────────────────────


class ModuleProvides(BaseModel):
    """What the module brings to the engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rules: list[str] = Field(
        default_factory=list, description="Names of rules/*.yaml files (no extension)"
    )
    graphFragment: str | None = Field(
        default=None,
        description="Path within module to asserted graph JSON (must use status='asserted')",
    )
    simulationTemplates: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)


class Manifest(BaseModel):
    """Module manifest. Loaded from manifest.json at the root of a module package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., min_length=1, max_length=64)
    version: str = Field(..., description="Semver, e.g. 1.0.0")
    requiredScopes: list[str] = Field(default_factory=list)
    engineVersion: str = Field(..., description="Core engine version requirement (semver range)")
    provides: ModuleProvides
    goldenSet: str = Field(..., description="Path within module to evaluator.py")
    # Optional rule metadata — read by the proactive pipeline (rule
    # priority + display title) and by the threshold tuner
    # (tunable_knobs). Open-shape on purpose so modules can add new
    # presentation/metadata keys without bumping the SDK.
    rule_metadata: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Per-rule metadata: title, priority, tunable_knobs",
    )
    # Plan keeps predicates open-vocabulary, but each module must declare
    # the verbs its rules reference. SDK then validates every fact: in
    # every rule YAML is present here — catches typos + drift at load
    # time instead of at first decision when the rule silently never
    # fires. Empty list = module doesn't reference predicates yet (e.g.
    # a pure benchmarks-only module).
    consumed_predicates: list[str] = Field(
        default_factory=list,
        description="Closed set of predicates this module's rules expect; "
                    "validated at module load against rule YAML `fact:` keys.",
    )

    @field_validator("version")
    @classmethod
    def _valid_semver(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError(f"version must be semver MAJOR.MINOR.PATCH; got {v!r}")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────


# File patterns the SDK refuses to load a module that contains them.
# Spec: "validate(module): assert no executable reasoning/engine code in module"
_REJECTED_FILE_NAMES = {
    "engine.py",
    "reasoner.py",
    "rule_engine.py",
    "csp_solver.py",
    "gateway.py",
    "fusion.py",
    "confidence.py",
}

_REJECTED_FILE_SUFFIXES = {
    # Model weight artifacts (LoRA / fine-tuned models)
    ".ckpt",
    ".safetensors",
    ".pt",
    ".pth",
    ".bin",
    ".onnx",
    ".h5",
    ".lora",
}


class ModuleValidationError(Exception):
    """Module failed SDK validation. Loud, blocking error."""


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    errors: list[str]


def load_manifest(module_root: Path) -> Manifest:
    """Read manifest.json from the module root. Pydantic-validates."""
    manifest_path = module_root / "manifest.json"
    if not manifest_path.exists():
        raise ModuleValidationError(f"Module at {module_root} is missing manifest.json (required)")
    try:
        data = json.loads(manifest_path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        raise ModuleValidationError(f"manifest.json parse error: {e}") from e
    try:
        return Manifest.model_validate(data)
    except Exception as e:  # pydantic ValidationError
        raise ModuleValidationError(f"manifest.json schema error: {e}") from e


def validate_module(
    module_root: Path,
    *,
    valid_scopes: Iterable[str],
    known_fact_types: Iterable[str] | None = None,
) -> ValidationReport:
    """Run all SDK rejection rules over a module package.

    Args:
        module_root: filesystem path to the module dir (contains manifest.json)
        valid_scopes: scopes the engine recognizes (rejects unknown scopes in manifest)
        known_fact_types: optional whitelist; if provided, rules referencing fact types
                          outside this set are rejected
    """
    errors: list[str] = []

    # 1. Manifest must load + validate
    try:
        manifest = load_manifest(module_root)
    except ModuleValidationError as e:
        return ValidationReport(ok=False, errors=[str(e)])

    # 2. No executable engine code in module
    engine_files = _find_rejected_engine_files(module_root)
    if engine_files:
        errors.append(
            "Module contains executable engine code (forbidden per g-i-5 §0): "
            + ", ".join(str(p.relative_to(module_root)) for p in engine_files)
        )

    # 3. No model-weight artifacts
    weight_files = _find_weight_files(module_root)
    if weight_files:
        errors.append(
            "Module contains model-weight artifacts (forbidden — opaque, contradicts "
            "explainability moat): "
            + ", ".join(str(p.relative_to(module_root)) for p in weight_files)
        )

    # 4. Required scopes must be in the engine's known set
    valid_scope_set = set(valid_scopes)
    unknown_scopes = [s for s in manifest.requiredScopes if s not in valid_scope_set]
    if unknown_scopes:
        errors.append(
            f"Manifest requires unknown scopes: {unknown_scopes}. "
            f"Engine knows: {sorted(valid_scope_set)}"
        )

    # 5. Graph fragment edges must be 'asserted' (no auto-causal)
    if manifest.provides.graphFragment:
        graph_path = module_root / manifest.provides.graphFragment
        non_asserted = _find_non_asserted_edges(graph_path)
        if non_asserted:
            errors.append(
                f"Graph fragment at {graph_path.relative_to(module_root)} contains "
                f"non-asserted edges: {non_asserted}. "
                "Per MD g-i-3 §3.2.2, only 'asserted' status allowed in module data."
            )

    # 6. Rule YAML files must parse + reference only known fact types.
    #    Whitelist precedence: caller-supplied known_fact_types > manifest's
    #    consumed_predicates. Either is a closed set the rules must stay
    #    inside; a module that declares neither gets the legacy lenient
    #    behaviour (rules parse but predicates aren't checked).
    rules_dir = module_root / "reasoning" / "rules"
    if rules_dir.exists():
        effective_known = (
            set(known_fact_types) if known_fact_types
            else (set(manifest.consumed_predicates) if manifest.consumed_predicates else None)
        )
        rule_errors = _validate_rule_files(
            rules_dir,
            known_fact_types=effective_known,
        )
        errors.extend(rule_errors)

    # 7. goldenSet path must exist
    golden_path = module_root / manifest.goldenSet
    if not golden_path.exists():
        errors.append(f"Manifest.goldenSet path not found: {manifest.goldenSet}")

    return ValidationReport(ok=not errors, errors=errors)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _find_rejected_engine_files(root: Path) -> list[Path]:
    """Find any .py file whose basename matches a reserved engine name."""
    found: list[Path] = []
    for p in root.rglob("*.py"):
        if p.name in _REJECTED_FILE_NAMES:
            found.append(p)
    return found


def _find_weight_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in _REJECTED_FILE_SUFFIXES:
            found.append(p)
    return found


def _find_non_asserted_edges(graph_path: Path) -> list[dict[str, Any]]:
    """Scan the module's graph fragment JSON for any edge with status != 'asserted'."""
    if not graph_path.exists():
        return []
    try:
        data = json.loads(graph_path.read_text("utf-8"))
    except json.JSONDecodeError:
        return [{"error": "graph fragment is not valid JSON"}]

    edges = data.get("edges", []) if isinstance(data, dict) else []
    bad: list[dict[str, Any]] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        status = e.get("status", "asserted")  # default 'asserted' is fine
        if status != "asserted":
            bad.append({"from": e.get("from"), "to": e.get("to"), "status": status})
    return bad


def _validate_rule_files(
    rules_dir: Path,
    *,
    known_fact_types: set[str] | None,
) -> list[str]:
    """Parse every rules/*.yaml. Report parse + fact-type errors as strings."""
    from core.reasoning.rule_loader import RuleLoadError, load_rules

    yaml_files = sorted(rules_dir.rglob("*.yaml"))
    if not yaml_files:
        return []

    errors: list[str] = []
    try:
        ruleset = load_rules(yaml_files)
    except RuleLoadError as e:
        return [f"Rule YAML invalid: {e}"]

    if known_fact_types is None:
        return errors

    # Check every rule's fact references are in the known set
    for rule in ruleset.rules:
        conditions = (rule.when.all or []) + (rule.when.any or [])
        for cond in conditions:
            if cond.fact not in known_fact_types:
                errors.append(
                    f"Rule '{rule.id}' references unknown fact '{cond.fact}'. "
                    f"Known facts for module: {sorted(known_fact_types)}"
                )
    return errors
