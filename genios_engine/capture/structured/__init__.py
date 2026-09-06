"""Structured short-circuit — CRM / DB / calendar / billing events whose meaning is
already typed. Mapped to fields WITHOUT an LLM. Mappings are DATA (a registry), not
per-source logic hardcoded in the pipeline — add a source = add a mapping.
"""

# The built-in product-usage mapping (L1.3.9-U3) registers itself on import, exactly as the four
# mappings in `registry.py` do. Imported HERE rather than from `registry.py` because the builder
# reads the source registry to enforce its capability guard, and registry.py must stay importable
# by anything — including the source registry's own tests — without dragging that in.
from . import product_usage as _product_usage  # noqa: E402,F401  (import for side effect)
