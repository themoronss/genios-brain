"""Sales module — THIN wiring. NO reasoning logic (per MD g-i-5 §0).

This file is allowed because it's not in the SDK's rejected names list
(engine.py, reasoner.py, gateway.py, etc.). It contains only:
- A module-version constant
- A small helper that returns the module's root Path (for callers like
  core.modules_framework.loader.load_module_package)

Real reasoning lives in core/. This file MUST NOT import anything from
core.reasoning, core.neural, etc. — those imports would make this module
operationally engine code, which the SDK forbids.
"""

from __future__ import annotations

from pathlib import Path

MODULE_ID = "sales"
MODULE_VERSION = "1.0.0"


def module_root() -> Path:
    """Path to the module's directory (used by the loader to find data files)."""
    return Path(__file__).resolve().parent
