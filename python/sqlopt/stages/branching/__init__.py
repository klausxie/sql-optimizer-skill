"""SQL Optimizer Scripting Module.

This module provides utilities for generating and manipulating SQL branches
in dynamic MyBatis mapper templates.
"""

from sqlopt.stages.branching.branch_generator import BranchGenerator
from sqlopt.stages.branching.branch_context import BranchContext
from sqlopt.stages.branching.branch_strategy import (
    BranchGenerationStrategy,
    AllCombinationsStrategy,
    PairwiseStrategy,
    BoundaryStrategy,
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
from sqlopt.stages.branching.execute_one import BranchingStage, execute_one
from sqlopt.stages.branching.xml_script_builder import XMLScriptBuilder
from sqlopt.stages.base import StageResult

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
    "StageResult",
    "BranchingStage",
    "execute_one",
]
