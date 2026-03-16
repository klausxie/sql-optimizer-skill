"""SQL Optimizer Scripting Module.

This module provides utilities for generating and manipulating SQL branches
in dynamic MyBatis mapper templates.
"""

from sqlopt.scripting.branch_generator import BranchGenerator
from sqlopt.scripting.branch_context import BranchContext
from sqlopt.scripting.branch_strategy import (
    BranchGenerationStrategy,
    AllCombinationsStrategy,
    PairwiseStrategy,
    BoundaryStrategy,
    create_strategy,
)
from sqlopt.scripting.dynamic_context import DynamicContext
from sqlopt.scripting.expression_evaluator import ExpressionEvaluator
from sqlopt.scripting.fragment_registry import FragmentRegistry, build_fragment_registry
from sqlopt.scripting.mutex_branch_detector import MutexBranchDetector
from sqlopt.scripting.sql_node import (
    SqlNode,
    StaticTextSqlNode,
    TextSqlNode,
    MixedSqlNode,
    IfSqlNode,
    WhenSqlNode,
    OtherwiseSqlNode,
    ChooseSqlNode,
    TrimSqlNode,
    WhereSqlNode,
    SetSqlNode,
    ForEachSqlNode,
    VarDeclSqlNode,
    IncludeSqlNode,
)
from sqlopt.scripting.xml_script_builder import XMLScriptBuilder

__all__ = [
    "BranchGenerator",
    "BranchContext",
    "BranchGenerationStrategy",
    "AllCombinationsStrategy",
    "PairwiseStrategy",
    "BoundaryStrategy",
    "create_strategy",
    "DynamicContext",
    "ExpressionEvaluator",
    "FragmentRegistry",
    "build_fragment_registry",
    "MutexBranchDetector",
    "SqlNode",
    "StaticTextSqlNode",
    "TextSqlNode",
    "MixedSqlNode",
    "IfSqlNode",
    "WhenSqlNode",
    "OtherwiseSqlNode",
    "ChooseSqlNode",
    "TrimSqlNode",
    "WhereSqlNode",
    "SetSqlNode",
    "ForEachSqlNode",
    "VarDeclSqlNode",
    "IncludeSqlNode",
    "XMLScriptBuilder",
]
