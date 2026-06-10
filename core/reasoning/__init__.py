"""g-i-2 symbolic reasoning — rules + CSP + proof trees + what-if.

Public API:
    from core.reasoning import (
        # rule loading + types
        Rule, RuleSet, load_rules,
        # engine
        ForwardChainer, BackwardChainer, ChainResult,
        # derivation (proof trees)
        DerivationStep, ProofTree,
        # CSP
        ConstraintSolver, ConstraintCheck,
        # what-if
        whatif,
    )
"""

from core.reasoning.csp_solver import ConstraintCheck, ConstraintSolver, Variable, VarType
from core.reasoning.derivation import DerivationStep, ProofTree, empty_proof
from core.reasoning.rule_engine import BackwardChainer, ChainResult, ForwardChainer
from core.reasoning.rule_loader import Rule, RuleSet, load_rules
from core.reasoning.what_if import PremortemResult, WhatIfResult, premortem, whatif

__all__ = [
    "BackwardChainer",
    "ChainResult",
    "ConstraintCheck",
    "ConstraintSolver",
    "DerivationStep",
    "ForwardChainer",
    "PremortemResult",
    "ProofTree",
    "Rule",
    "RuleSet",
    "VarType",
    "Variable",
    "WhatIfResult",
    "empty_proof",
    "load_rules",
    "premortem",
    "whatif",
]
