"""Thin loading of module DATA into the engine.

Per MD g-i-5 §0 — loader does NOT execute module code. It:
1. Reads manifest.json
2. Loads YAML rules (via core.reasoning.rule_loader)
3. Reads graph fragment JSON (asserted edges only — already SDK-validated)
4. Reads benchmarks.yaml
5. Reads artifact template configs

Returns a ModulePackage dataclass the engine + g-i-6 can consume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.modules_framework.sdk import Manifest, load_manifest
from core.reasoning.rule_loader import RuleSet, load_rules


@dataclass(frozen=True)
class ModulePackage:
    """Loaded module — pure data, no executable code."""

    root: Path
    manifest: Manifest
    ruleset: RuleSet
    graph_fragment: dict[str, Any] = field(default_factory=dict)
    benchmarks: dict[str, Any] = field(default_factory=dict)
    artifact_templates: dict[str, dict[str, Any]] = field(default_factory=dict)
    simulation_templates: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_module_package(module_root: Path) -> ModulePackage:
    """Load a module's data into a ModulePackage. Caller MUST have run validate_module first."""
    manifest = load_manifest(module_root)

    # Rules: load all YAML files referenced in manifest.provides.rules
    rules_dir = module_root / "reasoning" / "rules"
    rule_files = [rules_dir / f"{name}.rules.yaml" for name in manifest.provides.rules]
    ruleset = load_rules(rule_files) if rule_files else RuleSet(rules=[])

    # Graph fragment
    graph_fragment: dict[str, Any] = {}
    if manifest.provides.graphFragment:
        p = module_root / manifest.provides.graphFragment
        if p.exists():
            graph_fragment = json.loads(p.read_text("utf-8"))

    # Benchmarks (optional)
    benchmarks: dict[str, Any] = {}
    bench_path = module_root / "knowledge" / "benchmarks.yaml"
    if bench_path.exists():
        benchmarks = yaml.safe_load(bench_path.read_text("utf-8")) or {}

    # Artifact templates
    artifact_templates: dict[str, dict[str, Any]] = {}
    for name in manifest.provides.artifacts:
        p = module_root / "artifacts" / f"{name}.yaml"
        if p.exists():
            artifact_templates[name] = yaml.safe_load(p.read_text("utf-8")) or {}

    # Simulation templates
    simulation_templates: dict[str, dict[str, Any]] = {}
    for name in manifest.provides.simulationTemplates:
        p = module_root / "simulation" / "templates" / f"{name}.yaml"
        if p.exists():
            simulation_templates[name] = yaml.safe_load(p.read_text("utf-8")) or {}

    return ModulePackage(
        root=module_root,
        manifest=manifest,
        ruleset=ruleset,
        graph_fragment=graph_fragment,
        benchmarks=benchmarks,
        artifact_templates=artifact_templates,
        simulation_templates=simulation_templates,
    )
