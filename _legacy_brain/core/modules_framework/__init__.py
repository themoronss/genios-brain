"""g-i-5 Module SDK — modules are DATA packages (no engine code allowed).

Per MD g-i-5 §0 (the architectural law):
- Module supplies: rules + asserted graph fragment + benchmarks + simulation templates +
  artifact configs + evaluator + thin wiring
- Module does NOT ship: reasoning code, model weights, engine
- SDK REJECTS any module that tries to embed engine/LoRA logic

Public API:
    from core.modules_framework import (
        # contract + validation
        Manifest, ModulePackage, load_manifest, validate_module, ModuleValidationError,
        # registry + activation
        Registry, ModuleActivation, activate_module, deactivate_module,
        # isolation
        IsolationGuard, IsolationError,
        # golden gate
        run_golden_test, GoldenResult,
    )
"""

from core.modules_framework.golden import GoldenResult, run_golden_test
from core.modules_framework.isolation import IsolationError, IsolationGuard
from core.modules_framework.loader import ModulePackage, load_module_package
from core.modules_framework.registry import (
    ModuleActivation,
    Registry,
    activate_module,
    deactivate_module,
)
from core.modules_framework.sdk import (
    Manifest,
    ModuleValidationError,
    load_manifest,
    validate_module,
)

__all__ = [
    "GoldenResult",
    "IsolationError",
    "IsolationGuard",
    "Manifest",
    "ModuleActivation",
    "ModulePackage",
    "ModuleValidationError",
    "Registry",
    "activate_module",
    "deactivate_module",
    "load_manifest",
    "load_module_package",
    "run_golden_test",
    "validate_module",
]
