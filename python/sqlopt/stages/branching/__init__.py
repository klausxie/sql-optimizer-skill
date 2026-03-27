"""SQL Optimizer Scripting Module.

This module provides utilities for generating and manipulating SQL branches
in dynamic MyBatis mapper templates.
"""

from sqlopt.stages.branching.branch_context import BranchContext
from sqlopt.stages.branching.branch_generator import BranchGenerator
from sqlopt.stages.branching.branch_strategy import (
    AllCombinationsStrategy,
    BoundaryStrategy,
    BranchGenerationStrategy,
    LadderSamplingStrategy,
    PairwiseStrategy,
    create_strategy,
)
from sqlopt.stages.branching.dynamic_context import DynamicContext
from sqlopt.stages.branching.expression_evaluator import ExpressionEvaluator
from sqlopt.stages.branching.fragment_registry import (
    FragmentRegistry,
    build_fragment_registry,
)
from sqlopt.stages.branching.mutex_branch_detector import MutexBranchDetector
from sqlopt.stages.branching.sql_node import (
    ChooseSqlNode,
    ForEachSqlNode,
    IfSqlNode,
    IncludeSqlNode,
    MixedSqlNode,
    OtherwiseSqlNode,
    SetSqlNode,
    SqlNode,
    StaticTextSqlNode,
    TextSqlNode,
    TrimSqlNode,
    VarDeclSqlNode,
    WhenSqlNode,
    WhereSqlNode,
)
from sqlopt.stages.branching.xml_script_builder import XMLScriptBuilder

__all__ = [
    "AllCombinationsStrategy",
    "BoundaryStrategy",
    "BranchContext",
    "BranchGenerationStrategy",
    "BranchGenerator",
    "ChooseSqlNode",
    "DynamicContext",
    "ExpressionEvaluator",
    "ForEachSqlNode",
    "FragmentRegistry",
    "IfSqlNode",
    "IncludeSqlNode",
    "LadderSamplingStrategy",
    "MixedSqlNode",
    "MutexBranchDetector",
    "OtherwiseSqlNode",
    "PairwiseStrategy",
    "SetSqlNode",
    "SqlNode",
    "StaticTextSqlNode",
    "TextSqlNode",
    "TrimSqlNode",
    "VarDeclSqlNode",
    "WhenSqlNode",
    "WhereSqlNode",
    "XMLScriptBuilder",
    "build_fragment_registry",
    "create_strategy",
]
