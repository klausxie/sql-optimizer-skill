"""Branch generator for MyBatis XML dynamic SQL.

This module provides the BranchGenerator class which generates all possible
SQL branches from MyBatis dynamic SQL nodes (if, choose, etc.).
"""

# ruff: noqa: I001, F401, RUF003, RET507, PIE810, SIM102, PERF401, SIM108, SIM114, RUF005

from __future__ import annotations

import copy
from itertools import product
import re
from typing import TYPE_CHECKING, Any, List, Dict, Optional

from sqlopt.common.defaults import DEFAULT_MAX_BRANCHES
from sqlopt.stages.branching.branch_strategy import (
    BranchGenerationStrategy,
    create_strategy,
    AllCombinationsStrategy,
)
from sqlopt.stages.branching.branch_context import BranchContext
from sqlopt.stages.branching.branch_validator import BranchValidator
from sqlopt.stages.branching.dimension_extractor import DimensionExtractor
from sqlopt.stages.branching.mutex_branch_detector import MutexBranchDetector
from sqlopt.stages.branching.dynamic_context import DynamicContext
from sqlopt.stages.branching.planner import DimensionCandidate, RiskGuidedLadderPlanner
from sqlopt.stages.branching.risk_scorer import SQLDeltaRiskScorer

if TYPE_CHECKING:
    from sqlopt.contracts.init import FieldDistribution
    from sqlopt.stages.branching.sql_node import SqlNode


class BranchGenerator:
    """Generates all possible SQL branches from MyBatis SqlNode trees.

    This class walks the SqlNode tree, collects all conditional nodes (if, choose),
    and generates different branch combinations based on the configured strategy.

    Usage:
        generator = BranchGenerator(strategy="all_combinations")
        branches = generator.generate(sql_node)
    """

    def __init__(
        self,
        strategy: str = "all_combinations",
        max_branches: int = DEFAULT_MAX_BRANCHES,
        strategy_seed: int | None = None,
        condition_weights: dict[str, float] | None = None,
        table_metadata: dict[str, dict] | None = None,
        field_distributions: dict[str, list["FieldDistribution"]] | None = None,
    ) -> None:
        """Initialize the branch generator.

        Args:
            strategy: Branch generation strategy name.
                Options: "all_combinations", "pairwise", "boundary"
            max_branches: Maximum number of branches to generate.
            strategy_seed: Seed for reproducibility (not used currently).
        """
        self.strategy: str = strategy
        self.max_branches: int = max_branches
        self.strategy_seed: int | None = strategy_seed
        self.condition_weights = condition_weights
        self.table_metadata = table_metadata
        self.field_distributions = field_distributions or {}
        self._strategy: BranchGenerationStrategy = create_strategy(
            strategy,
            seed=strategy_seed,
            condition_weights=condition_weights,
            table_metadata=table_metadata,
            field_distributions=field_distributions,
        )
        self._mutex_detector: MutexBranchDetector = MutexBranchDetector()
        self.theoretical_branches: int = 0

    @property
    def strategy_instance(self) -> BranchGenerationStrategy:
        """Get the current strategy instance."""
        return self._strategy

    def generate(self, sql_node: SqlNode) -> List[Dict[str, Any]]:
        """Generate all possible branches from a SqlNode tree.

        This is the main entry point. It:
        1. Collects all conditions from the tree
        2. Detects choose nodes (mutex branches)
        3. Generates branch combinations using the strategy

        Args:
            sql_node: The root SqlNode to generate branches from.

        Returns:
            List of branch dictionaries, each containing:
            - branch_id: Unique identifier
            - active_conditions: Conditions that are TRUE
            - sql: The generated SQL string
        """
        conditions = self._collect_conditions(sql_node)
        valid_combinations = self._enumerate_valid_condition_combinations(sql_node)
        theoretical_branches = len(valid_combinations)

        if self.strategy == "ladder":
            selected_combinations = self._plan_ladder_condition_combinations(sql_node)
        else:
            selected_combinations = self._select_condition_combinations(
                valid_combinations,
                conditions,
            )

        branches = self._render_condition_combinations(sql_node, selected_combinations)
        if not branches:
            context = DynamicContext()
            sql_node.apply(context)
            branches = [
                {
                    "branch_id": 0,
                    "active_conditions": [],
                    "sql": self._normalize_sql(context.get_sql()),
                    "condition_count": 0,
                }
            ]

        # Generate additional cardinality bucket variants for foreach clauses
        # by re-rendering the full tree, not by string replacement.
        branches = self._generate_foreach_boundary_branches(branches, sql_node)
        self.theoretical_branches = len(branches)

        # Collect risk_flags from bind conditions with pattern detection
        # First, collect all bind expressions from the sql_node tree
        bind_expressions = self._collect_bind_expressions(sql_node)

        for branch in branches:
            risk_flags = []
            for cond in branch.get("active_conditions", []):
                if cond.startswith("bind:"):
                    bind_name = cond[5:]  # Extract name from "bind:{name}"
                    if bind_name in bind_expressions:
                        expression = bind_expressions[bind_name]

                        # 检测函数包装模式（与通配符无关，独立检测）
                        # 例如: UPPER(name), LOWER(name), TRIM(name), SUBSTRING(name, 1, 10)
                        # 这些函数包装可能导致索引失效
                        import re

                        function_wrappers = [
                            "UPPER",
                            "LOWER",
                            "TRIM",
                            "LTRIM",
                            "RTRIM",
                            "SUBSTRING",
                            "SUBSTR",
                        ]
                        for func in function_wrappers:
                            # 匹配 func( 或 func ( 模式
                            func_pattern = rf"{func}\s*\("
                            if re.search(func_pattern, expression, re.IGNORECASE):
                                risk_flags.append("function_wrap")
                                break

                        # 检测通配符模式
                        # 表达式示例:
                        #   - 前缀通配符: "'%' + name + '%'" → starts with '%', contains '%'
                        #   - 后缀通配符: "name + '%'" → ends with '%' (but not '% at start)

                        # 检查是否有通配符
                        has_percent = "%" in expression
                        if not has_percent:
                            # 没有通配符但有函数包装，已经在上面处理
                            # 没有函数包装则跳过
                            if not risk_flags:
                                continue
                            else:
                                # 有函数包装风险标记，继续添加
                                pass

                        # 分析位置
                        # 前缀通配符特征: 字符串以 '% 开头
                        starts_with_percent = expression.startswith("'%") or expression.startswith('"%')
                        # 后缀通配符特征: 字符串以 %' 结尾
                        ends_with_percent = expression.endswith("%'") or expression.endswith('"%')

                        # 前缀通配符: "'%' + name + '%'" - 两端都有通配符
                        # 后缀通配符: "name + '%'" - 只有结尾有通配符

                        if starts_with_percent and ends_with_percent:
                            # 两端都有通配符 → 前缀通配符
                            risk_flags.append("prefix_wildcard")
                        elif ends_with_percent and not starts_with_percent:
                            # 只有结尾有通配符 → 后缀通配符
                            risk_flags.append("suffix_wildcard_only")
                        elif starts_with_percent and not ends_with_percent:
                            # 只有开头有通配符 → 前缀通配符
                            risk_flags.append("prefix_wildcard")

                        # 检测 CONCAT 函数包装的通配符模式
                        # 例如: CONCAT('%', name) 或 CONCAT('%', name, '%')
                        # CONCAT 函数内的通配符同样会导致全表扫描
                        # 匹配 CONCAT(..., '%', ...) 模式
                        concat_wildcard_pattern = r"CONCAT\s*\([^)]*['\"][%][^)]*['\"][^)]*\)"
                        if re.search(concat_wildcard_pattern, expression, re.IGNORECASE):
                            if "prefix_wildcard" not in risk_flags:
                                risk_flags.append("concat_wildcard")

            if risk_flags:
                branch["risk_flags"] = self._dedupe_list(risk_flags)
            else:
                branch["risk_flags"] = []

        scorer = SQLDeltaRiskScorer(
            table_metadata=self.table_metadata,
            field_distributions=self.field_distributions,
        )
        for branch in branches:
            risk_score, score_reasons = scorer.score_branch(
                branch.get("sql", ""),
                branch.get("active_conditions", []),
                branch.get("risk_flags", []),
            )
            branch["risk_score"] = risk_score
            branch["score_reasons"] = score_reasons

        validator = BranchValidator()
        validated = validator.validate_and_deduplicate(branches, self.max_branches)
        return validated.branches

    def _plan_ladder_condition_combinations(
        self,
        sql_node: SqlNode,
    ) -> List[List[str]]:
        extractor = DimensionExtractor()
        dimensions = extractor.extract(sql_node)
        if not dimensions:
            return [[]]

        scorer = SQLDeltaRiskScorer(
            table_metadata=self.table_metadata,
            field_distributions=self.field_distributions,
        )
        candidates = [
            DimensionCandidate(
                dimension=dimension,
                score=scorer.score_dimension(dimension),
            )
            for dimension in dimensions
        ]

        planner = RiskGuidedLadderPlanner(max_branches=self.max_branches)
        selected = planner.generate(candidates)
        filtered: List[List[str]] = []
        seen: set[tuple[str, ...]] = set()
        for combo in selected:
            if self._is_obviously_mutex_conflict(set(combo)):
                continue
            key = tuple(combo)
            if key in seen:
                continue
            seen.add(key)
            filtered.append(combo)
            if len(filtered) >= self.max_branches:
                break

        return filtered or [[]]

    def _enumerate_valid_condition_combinations(
        self,
        sql_node: SqlNode,
    ) -> List[List[str]]:
        raw_combinations = self._enumerate_valid_condition_combinations_recursive(
            sql_node,
            set(),
        )
        deduped = self._dedupe_condition_combinations(raw_combinations)
        return [combo for combo in deduped if not self._is_obviously_mutex_conflict(set(combo))]

    def _enumerate_valid_condition_combinations_recursive(
        self,
        sql_node: SqlNode,
        include_stack: set[str],
    ) -> List[List[str]]:
        from sqlopt.stages.branching.sql_node import (
            ChooseSqlNode,
            ForEachSqlNode,
            IfSqlNode,
            IncludeSqlNode,
            MixedSqlNode,
            TrimSqlNode,
            WhereSqlNode,
            SetSqlNode,
            VarDeclSqlNode,
        )

        if isinstance(sql_node, IfSqlNode):
            child_combinations = self._enumerate_valid_condition_combinations_recursive(
                sql_node.contents,
                include_stack,
            )
            combinations = [[]]
            for child_combo in child_combinations:
                combinations.append(self._merge_condition_lists([sql_node.test], child_combo))
            return self._dedupe_condition_combinations(combinations)

        if isinstance(sql_node, ChooseSqlNode):
            combinations: List[List[str]] = []
            for when_node in sql_node.if_sql_nodes:
                child_combinations = self._enumerate_valid_condition_combinations_recursive(
                    when_node.contents,
                    include_stack,
                )
                for child_combo in child_combinations:
                    combinations.append(self._merge_condition_lists([when_node.test], child_combo))

            if sql_node.default_sql_node is not None:
                combinations.extend(
                    self._enumerate_valid_condition_combinations_recursive(
                        sql_node.default_sql_node.contents,
                        include_stack,
                    )
                )
            else:
                combinations.append([])

            return self._dedupe_condition_combinations(combinations)

        if isinstance(sql_node, IncludeSqlNode):
            if not sql_node.fragment_registry or sql_node.refid in include_stack:
                return [[]]
            fragment = sql_node.fragment_registry.lookup(sql_node.refid)
            if fragment is None:
                return [[]]
            next_stack = set(include_stack)
            next_stack.add(sql_node.refid)
            return self._enumerate_valid_condition_combinations_recursive(
                fragment,
                next_stack,
            )

        if isinstance(sql_node, MixedSqlNode):
            combinations: List[List[str]] = [[]]
            for child in sql_node.contents:
                child_combinations = self._enumerate_valid_condition_combinations_recursive(
                    child,
                    include_stack,
                )
                merged: List[List[str]] = []
                for base_combo in combinations:
                    for child_combo in child_combinations:
                        merged.append(self._merge_condition_lists(base_combo, child_combo))
                combinations = self._dedupe_condition_combinations(merged)
            return combinations

        if isinstance(sql_node, (TrimSqlNode, WhereSqlNode, SetSqlNode)):
            return self._enumerate_valid_condition_combinations_recursive(
                sql_node.contents,
                include_stack,
            )

        if isinstance(sql_node, ForEachSqlNode):
            if sql_node.contents is None:
                return [[]]
            return self._enumerate_valid_condition_combinations_recursive(
                sql_node.contents,
                include_stack,
            )

        if isinstance(sql_node, VarDeclSqlNode):
            # bind 标签定义变量，将其 name 作为条件标记传播
            # 例如: <bind name="pattern" value="'%' + name + '%'"/>
            # 会添加 "bind:pattern" 到 active_conditions
            return [[f"bind:{sql_node.name}"]]

        return [[]]

    @staticmethod
    def _merge_condition_lists(
        left: List[str],
        right: List[str],
    ) -> List[str]:
        merged: List[str] = []
        seen: set[str] = set()
        for condition in left + right:
            if condition and condition not in seen:
                seen.add(condition)
                merged.append(condition)
        return merged

    @staticmethod
    def _dedupe_condition_combinations(
        combinations: List[List[str]],
    ) -> List[List[str]]:
        deduped: List[List[str]] = []
        seen: set[tuple[str, ...]] = set()
        for combination in combinations:
            key = tuple(combination)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(combination)
        return deduped

    def _select_condition_combinations(
        self,
        valid_combinations: List[List[str]],
        all_conditions: List[str],
    ) -> List[List[str]]:
        if not valid_combinations:
            return []

        if self.strategy == "all_combinations":
            return valid_combinations[: self.max_branches]

        target_combinations = self._strategy.generate(
            all_conditions,
            max(self.max_branches, len(valid_combinations)),
        )

        selected: List[List[str]] = []
        seen: set[tuple[str, ...]] = set()
        for target in target_combinations:
            best = self._match_valid_combination(target, valid_combinations)
            if best is None:
                continue
            key = tuple(best)
            if key in seen:
                continue
            seen.add(key)
            selected.append(best)
            if len(selected) >= self.max_branches:
                break

        return selected or valid_combinations[: self.max_branches]

    @staticmethod
    def _match_valid_combination(
        target: List[str],
        valid_combinations: List[List[str]],
    ) -> List[str] | None:
        target_set = set(target)
        best_combo: List[str] | None = None
        best_score: tuple[int, int, int, int] | None = None

        for index, candidate in enumerate(valid_combinations):
            candidate_set = set(candidate)
            score = (
                len(target_set - candidate_set),
                len(candidate_set - target_set),
                abs(len(candidate) - len(target)),
                index,
            )
            if best_score is None or score < best_score:
                best_score = score
                best_combo = candidate

        return best_combo

    def _render_condition_combinations(
        self,
        sql_node: SqlNode,
        combinations: List[List[str]],
    ) -> List[Dict[str, Any]]:
        branches: List[Dict[str, Any]] = []
        if_nodes = self._collect_if_nodes(sql_node)

        for active_conditions in combinations[: self.max_branches]:
            active_set = set(active_conditions)
            modified_sql_node = self._create_filtered_sql_node(
                sql_node,
                if_nodes,
                active_set,
            )
            context = DynamicContext()
            modified_sql_node.apply(context)
            branches.append(
                {
                    "branch_id": len(branches),
                    "active_conditions": active_conditions,
                    "sql": self._normalize_sql(context.get_sql()),
                    "condition_count": len(active_conditions),
                }
            )

        return branches

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        return " ".join(sql.split())

    def _collect_conditions(self, sql_node: SqlNode) -> List[str]:
        """Recursively collect all if/when test conditions.

        Args:
            sql_node: The node to collect from.

        Returns:
            List of all test expressions found.
        """
        conditions: List[str] = []
        self._collect_conditions_recursive(sql_node, conditions)
        return conditions

    def _collect_conditions_recursive(self, sql_node: SqlNode, conditions: List[str]) -> None:
        """Internal recursive helper for condition collection."""
        from sqlopt.stages.branching.sql_node import (
            IfSqlNode,
            WhenSqlNode,
            MixedSqlNode,
            ChooseSqlNode,
            TrimSqlNode,
            WhereSqlNode,
            SetSqlNode,
            ForEachSqlNode,
            IncludeSqlNode,
        )

        # Handle IfSqlNode and WhenSqlNode
        if isinstance(sql_node, IfSqlNode):
            if sql_node.test:
                conditions.append(sql_node.test)
            if sql_node.contents:
                self._collect_conditions_recursive(sql_node.contents, conditions)
            return

        # Handle ChooseSqlNode - collect when tests
        if isinstance(sql_node, ChooseSqlNode):
            for when_node in sql_node.if_sql_nodes:
                if when_node.test:
                    conditions.append(when_node.test)
                if when_node.contents:
                    self._collect_conditions_recursive(when_node.contents, conditions)
            if sql_node.default_sql_node and sql_node.default_sql_node.contents:
                self._collect_conditions_recursive(sql_node.default_sql_node.contents, conditions)
            return

        if isinstance(sql_node, IncludeSqlNode):
            if sql_node.fragment_registry:
                fragment = sql_node.fragment_registry.lookup(sql_node.refid)
                if fragment:
                    self._collect_conditions_recursive(fragment, conditions)
            return

        # Handle MixedSqlNode - recurse into contents
        if isinstance(sql_node, MixedSqlNode):
            for child in sql_node.contents:
                self._collect_conditions_recursive(child, conditions)
            return

        # Handle TrimSqlNode and subclasses
        if isinstance(sql_node, (TrimSqlNode, WhereSqlNode, SetSqlNode)):
            if sql_node.contents:
                self._collect_conditions_recursive(sql_node.contents, conditions)
            return

        # Handle ForEachSqlNode
        if isinstance(sql_node, ForEachSqlNode):
            if sql_node.contents:
                self._collect_conditions_recursive(sql_node.contents, conditions)
            return

    def _collect_choose_nodes(self, sql_node: SqlNode) -> List:
        """Recursively collect all choose nodes.

        Args:
            sql_node: The node to collect from.

        Returns:
            List of ChooseSqlNode instances found.
        """
        choose_nodes: List = []
        self._collect_choose_nodes_recursive(sql_node, choose_nodes)
        return choose_nodes

    def _collect_choose_nodes_recursive(self, sql_node: SqlNode, choose_nodes: List) -> None:
        """Internal recursive helper for choose node collection."""
        from sqlopt.stages.branching.sql_node import (
            ChooseSqlNode,
            MixedSqlNode,
            TrimSqlNode,
            WhereSqlNode,
            SetSqlNode,
            ForEachSqlNode,
            IfSqlNode,
            IncludeSqlNode,
        )

        if isinstance(sql_node, ChooseSqlNode):
            choose_nodes.append(sql_node)
            return

        if isinstance(sql_node, IncludeSqlNode):
            if sql_node.fragment_registry:
                fragment = sql_node.fragment_registry.lookup(sql_node.refid)
                if fragment:
                    self._collect_choose_nodes_recursive(fragment, choose_nodes)
            return

        if isinstance(sql_node, MixedSqlNode):
            for child in sql_node.contents:
                self._collect_choose_nodes_recursive(child, choose_nodes)
            return

        if isinstance(sql_node, (TrimSqlNode, WhereSqlNode, SetSqlNode)):
            if sql_node.contents:
                self._collect_choose_nodes_recursive(sql_node.contents, choose_nodes)
            return

        if isinstance(sql_node, ForEachSqlNode):
            if sql_node.contents:
                self._collect_choose_nodes_recursive(sql_node.contents, choose_nodes)
            return

        if isinstance(sql_node, IfSqlNode):
            if sql_node.contents:
                self._collect_choose_nodes_recursive(sql_node.contents, choose_nodes)
            return

    def _generate_mutex_branches(
        self,
        sql_node: SqlNode,
        choose_nodes: List,
    ) -> List[Dict[str, Any]]:
        """Generate branches for SQL with choose nodes.

        Args:
            sql_node: Root SqlNode.
            choose_nodes: List of ChooseSqlNode instances.

        Returns:
            List of branch dictionaries.
        """
        # For choose nodes, we need to generate separate branches
        # Each branch activates only ONE when (or otherwise)

        # Get the first choose node (simplify: handle one level)
        choose_node = choose_nodes[0]
        when_count = len(choose_node.if_sql_nodes)
        has_otherwise = choose_node.default_sql_node is not None

        branches: List[Dict[str, Any]] = []

        # Generate one branch per when node
        for i, when_node in enumerate(choose_node.if_sql_nodes):
            active_conds = [when_node.test] if when_node.test else []

            # Create a modified SQL that only includes this when branch
            modified_sql = self._create_mutex_branch_sql(sql_node, choose_node, i)

            context = DynamicContext()
            modified_sql.apply(context)

            sql = context.get_sql()
            branches.append(
                {
                    "branch_id": i,
                    "active_conditions": active_conds,
                    "sql": sql.strip(),
                    "condition_count": len(active_conds),
                }
            )

        # Generate otherwise branch if exists
        if has_otherwise:
            context = DynamicContext()
            modified_sql = self._create_otherwise_branch_sql(sql_node, choose_node)
            modified_sql.apply(context)
            sql = context.get_sql()
            branches.append(
                {
                    "branch_id": when_count,
                    "active_conditions": [],
                    "sql": sql.strip(),
                    "condition_count": 0,
                }
            )

        # If no branches generated (edge case), add static branch
        if not branches:
            branches = [self._create_branch(0, [], sql_node)]

        return branches

    @staticmethod
    def _create_mutex_branch_sql(
        sql_node: SqlNode,
        choose_node,
        when_index: int,
    ) -> SqlNode:
        """Create a modified SqlNode tree that only activates one when branch.

        Args:
            sql_node: Root SqlNode.
            choose_node: The ChooseSqlNode to modify.
            when_index: Which when branch to activate.

        Returns:
            Modified SqlNode tree.
        """
        from sqlopt.stages.branching.sql_node import (
            MixedSqlNode,
            StaticTextSqlNode,
            ChooseSqlNode,
            WhenSqlNode,
        )

        # For now, return a simplified version
        # In production, we'd create a deep copy and modify the choose node
        when_node = choose_node.if_sql_nodes[when_index]

        # Create a choose that only has this when
        modified_choose = ChooseSqlNode(
            if_sql_nodes=[WhenSqlNode(when_node.test, when_node.contents)],
            default_sql_node=None,
        )

        # Wrap in MixedSqlNode
        return MixedSqlNode([modified_choose])

    @staticmethod
    def _create_otherwise_branch_sql(
        sql_node: SqlNode,
        choose_node,
    ) -> SqlNode:
        """Create a modified SqlNode tree for otherwise branch.

        Args:
            sql_node: Root SqlNode.
            choose_node: The ChooseSqlNode to modify.

        Returns:
            Modified SqlNode tree for otherwise.
        """
        from sqlopt.stages.branching.sql_node import (
            MixedSqlNode,
            ChooseSqlNode,
            OtherwiseSqlNode,
        )

        # Create a choose with only otherwise
        modified_choose = ChooseSqlNode(
            if_sql_nodes=[],
            default_sql_node=OtherwiseSqlNode(choose_node.default_sql_node.contents),
        )

        return MixedSqlNode([modified_choose])

    def _generate_combination_branches(
        self,
        sql_node: SqlNode,
        conditions: List[str],
    ) -> List[Dict[str, Any]]:
        """Generate branches using the configured strategy.

        Args:
            sql_node: Root SqlNode.
            conditions: List of condition expressions.

        Returns:
            List of branch dictionaries.
        """
        # Use strategy to generate combinations
        combinations = self._strategy.generate(conditions, self.max_branches)

        branches: List[Dict[str, Any]] = []

        # Build a mapping from test expression to IfSqlNode
        if_nodes = self._collect_if_nodes(sql_node)

        for i, active_conds in enumerate(combinations):
            # Create a new SqlNode tree with only active conditions
            active_set = set(active_conds)
            if self._is_obviously_mutex_conflict(active_set):
                continue
            modified_sql_node = self._create_filtered_sql_node(sql_node, if_nodes, active_set)

            # Apply the modified SqlNode
            context = DynamicContext()
            modified_sql_node.apply(context)
            sql = context.get_sql().strip()

            branches.append(
                {
                    "branch_id": i,
                    "active_conditions": active_conds,
                    "sql": sql,
                    "condition_count": len(active_conds),
                }
            )

        return branches

    def _collect_if_nodes(self, sql_node: SqlNode) -> dict:
        """Collect all IfSqlNode from the tree.

        Args:
            sql_node: Root SqlNode.

        Returns:
            Dictionary mapping test expression to IfSqlNode.
        """
        if_nodes = {}
        self._collect_if_nodes_recursive(sql_node, if_nodes)
        return if_nodes

    def _collect_if_nodes_recursive(self, sql_node: SqlNode, if_nodes: dict) -> None:
        """Recursively collect IfSqlNode instances."""
        from sqlopt.stages.branching.sql_node import (
            IfSqlNode,
            MixedSqlNode,
            ChooseSqlNode,
            OtherwiseSqlNode,
            WhenSqlNode,
            TrimSqlNode,
            WhereSqlNode,
            SetSqlNode,
            ForEachSqlNode,
            IncludeSqlNode,
        )

        if isinstance(sql_node, IfSqlNode):
            if sql_node.test:
                if_nodes[sql_node.test] = sql_node
            if sql_node.contents:
                self._collect_if_nodes_recursive(sql_node.contents, if_nodes)
            return

        if isinstance(sql_node, IncludeSqlNode):
            if sql_node.fragment_registry:
                fragment = sql_node.fragment_registry.lookup(sql_node.refid)
                if fragment:
                    self._collect_if_nodes_recursive(fragment, if_nodes)
            return

        if isinstance(sql_node, MixedSqlNode):
            for child in sql_node.contents:
                self._collect_if_nodes_recursive(child, if_nodes)
            return

        if isinstance(sql_node, (TrimSqlNode, WhereSqlNode, SetSqlNode)):
            if sql_node.contents:
                self._collect_if_nodes_recursive(sql_node.contents, if_nodes)
            return

        if isinstance(sql_node, ForEachSqlNode):
            if sql_node.contents:
                self._collect_if_nodes_recursive(sql_node.contents, if_nodes)
            return

        if isinstance(sql_node, ChooseSqlNode):
            for when_node in sql_node.if_sql_nodes:
                self._collect_if_nodes_recursive(when_node, if_nodes)
            return

    def _create_filtered_sql_node(
        self,
        sql_node: SqlNode,
        if_nodes: dict,
        active_conditions: set,
    ) -> SqlNode:
        return self._create_filtered_sql_node_recursive(
            sql_node,
            if_nodes,
            active_conditions,
            set(),
        )

    def _create_filtered_sql_node_recursive(
        self,
        sql_node: SqlNode,
        if_nodes: dict,
        active_conditions: set,
        include_stack: set[str],
    ) -> SqlNode:
        """Create a new SqlNode tree with filtering based on active conditions.

        Args:
            sql_node: Original root SqlNode.
            if_nodes: Dictionary of IfSqlNode instances.
            active_conditions: Set of conditions that should be TRUE.

        Returns:
            New SqlNode tree with filtering applied.
        """
        from sqlopt.stages.branching.sql_node import (
            IfSqlNode,
            MixedSqlNode,
            ChooseSqlNode,
            OtherwiseSqlNode,
            WhenSqlNode,
            TrimSqlNode,
            WhereSqlNode,
            SetSqlNode,
            ForEachSqlNode,
            IncludeSqlNode,
            VarDeclSqlNode,
        )

        if isinstance(sql_node, IfSqlNode):
            # Create a new IfSqlNode with active_conditions set
            filtered_contents = self._create_filtered_sql_node_recursive(
                sql_node.contents,
                if_nodes,
                active_conditions,
                include_stack,
            )
            return IfSqlNode(sql_node.test, filtered_contents, active_conditions)

        if isinstance(sql_node, MixedSqlNode):
            filtered_contents = [
                self._create_filtered_sql_node_recursive(
                    child,
                    if_nodes,
                    active_conditions,
                    include_stack,
                )
                for child in sql_node.contents
            ]
            return MixedSqlNode(filtered_contents)

        if isinstance(sql_node, (TrimSqlNode, WhereSqlNode, SetSqlNode)):
            filtered_contents = self._create_filtered_sql_node_recursive(
                sql_node.contents,
                if_nodes,
                active_conditions,
                include_stack,
            )
            return TrimSqlNode(
                filtered_contents,
                prefix=sql_node.prefix,
                suffix=sql_node.suffix,
                prefix_overrides=sql_node.prefix_overrides.copy(),
                suffix_overrides=sql_node.suffix_overrides.copy(),
            )

        if isinstance(sql_node, ForEachSqlNode):
            filtered_contents = None
            if sql_node.contents:
                filtered_contents = self._create_filtered_sql_node_recursive(
                    sql_node.contents,
                    if_nodes,
                    active_conditions,
                    include_stack,
                )
            return ForEachSqlNode(
                collection=sql_node.collection,
                item=sql_node.item,
                index=sql_node.index,
                open=sql_node.open,
                close=sql_node.close,
                separator=sql_node.separator,
                contents=filtered_contents,
                sample_size=sql_node.sample_size,
            )

        if isinstance(sql_node, ChooseSqlNode):
            filtered_whens = []
            for when_node in sql_node.if_sql_nodes:
                filtered_when = WhenSqlNode(
                    when_node.test,
                    self._create_filtered_sql_node_recursive(
                        when_node.contents,
                        if_nodes,
                        active_conditions,
                        include_stack,
                    ),
                    active_conditions,  # Pass active_conditions for mutex handling
                )
                filtered_whens.append(filtered_when)

            filtered_otherwise = None
            if sql_node.default_sql_node:
                filtered_otherwise = ChooseSqlNode(
                    if_sql_nodes=filtered_whens,
                    default_sql_node=OtherwiseSqlNode(
                        self._create_filtered_sql_node_recursive(
                            sql_node.default_sql_node.contents,
                            if_nodes,
                            active_conditions,
                            include_stack,
                        )
                    ),
                )
            else:
                filtered_otherwise = ChooseSqlNode(
                    if_sql_nodes=filtered_whens,
                    default_sql_node=None,
                )
            return filtered_otherwise

        if isinstance(sql_node, IncludeSqlNode):
            if not sql_node.fragment_registry or sql_node.refid in include_stack:
                return sql_node
            fragment = sql_node.fragment_registry.lookup(sql_node.refid)
            if fragment is None:
                return sql_node
            next_stack = set(include_stack)
            next_stack.add(sql_node.refid)
            return self._create_filtered_sql_node_recursive(
                fragment,
                if_nodes,
                active_conditions,
                next_stack,
            )

        if isinstance(sql_node, VarDeclSqlNode):
            # bind 节点透传，保留在过滤后的树中
            return sql_node

        # StaticTextSqlNode - return as is
        return sql_node

    def _create_context(self, active_conditions: List[str]) -> DynamicContext:
        """Create a DynamicContext with bindings for the conditions.

        Args:
            active_conditions: List of conditions to activate.

        Returns:
            Configured DynamicContext.
        """
        context = DynamicContext()

        # Bind each condition to True for active ones
        # This allows the SQL to be generated with the condition "active"
        for cond in active_conditions:
            # 处理 bind 变量绑定
            if cond.startswith("bind:"):
                bind_name = cond[5:]  # 去掉 "bind:" 前缀
                # 绑定一个占位符值，让 SQL 中的 #{pattern} 能够渲染
                context.bind(bind_name, f"#{{{bind_name}}}")
                continue

            # 原有逻辑：提取变量名并绑定
            var_name = self._extract_var_name(cond)
            if var_name:
                context.bind(var_name, True)

        return context

    @staticmethod
    def _extract_var_name(condition: str) -> str | None:
        """Extract a variable name from a condition.

        This is a simplified heuristic - in reality OGNL is more complex.

        Args:
            condition: The OGNL expression.

        Returns:
            Extracted variable name or None.
        """
        # Simple patterns like "name != null", "age > 18"
        match = re.match(r"^(\w+)", condition)
        if match:
            return match.group(1)
        return None

    def _is_obviously_mutex_conflict(self, active_conditions: set[str]) -> bool:
        """Check if active conditions contain obvious mutual exclusions.

        This intentionally handles only simple patterns (no OGNL evaluation):
        - same variable equals two different literals
        - variable equals and not-equals same literal
        - variable == null and variable != null
        - boolean style: `x` and `!x`
        """
        per_var: dict[str, dict[str, set[str] | bool]] = {}

        for condition in active_conditions:
            atom = self._parse_simple_condition(condition)
            if atom is None:
                continue

            var, op, value = atom
            slot = per_var.setdefault(
                var,
                {
                    "eq": set(),
                    "neq": set(),
                    "truthy": False,
                    "falsy": False,
                },
            )

            if op == "eq":
                cast = slot["eq"]
                assert isinstance(cast, set)
                cast.add(value)
            elif op == "neq":
                cast = slot["neq"]
                assert isinstance(cast, set)
                cast.add(value)
            elif op == "truthy":
                slot["truthy"] = True
            elif op == "falsy":
                slot["falsy"] = True

        for slot in per_var.values():
            eq_set = slot["eq"]
            neq_set = slot["neq"]
            truthy = slot["truthy"]
            falsy = slot["falsy"]

            assert isinstance(eq_set, set)
            assert isinstance(neq_set, set)
            assert isinstance(truthy, bool)
            assert isinstance(falsy, bool)

            non_null_eq = {v for v in eq_set if v != "null"}
            if len(non_null_eq) > 1:
                return True

            if "null" in eq_set and "null" in neq_set:
                return True

            if eq_set & neq_set:
                return True

            if truthy and falsy:
                return True

        return False

    @staticmethod
    def _parse_simple_condition(condition: str) -> tuple[str, str, str] | None:
        cond = " ".join(condition.strip().split())
        if not cond:
            return None

        m = re.match(r"^(!)\s*([A-Za-z_]\w*)$", cond)
        if m:
            return m.group(2), "falsy", "true"

        m = re.match(r"^([A-Za-z_]\w*)$", cond)
        if m:
            return m.group(1), "truthy", "true"

        m = re.match(
            r"^([A-Za-z_]\w*)\s*(==|!=|=)\s*(null|\d+(?:\.\d+)?|'[^']*'|\"[^\"]*\")$",
            cond,
        )
        if not m:
            return None

        var = m.group(1)
        op = m.group(2)
        raw_value = m.group(3)

        if raw_value.startswith(("'", '"')) and raw_value.endswith(("'", '"')):
            value = raw_value[1:-1]
        else:
            value = raw_value
        value = value.lower() if value == "null" else value

        normalized_op = "eq" if op in ("==", "=") else "neq"
        return var, normalized_op, value

    def _create_branch(
        self,
        branch_id: int,
        active_conditions: List[str],
        sql_node: SqlNode,
        context: DynamicContext | None = None,
    ) -> Dict[str, Any]:
        """Create a branch dictionary by applying the SqlNode.

        Args:
            branch_id: Unique branch identifier.
            active_conditions: Conditions that are TRUE.
            sql_node: The SqlNode to apply.
            context: Optional pre-created context.

        Returns:
            Branch dictionary with sql and metadata.
        """
        if context is None:
            context = self._create_context(active_conditions)

        # Apply the SqlNode to generate SQL
        sql_node.apply(context)

        # Get the generated SQL
        sql = context.get_sql()

        return {
            "branch_id": branch_id,
            "active_conditions": active_conditions,
            "sql": sql.strip(),
            "condition_count": len(active_conditions),
        }

    def set_strategy(self, strategy_name: str) -> None:
        """Change the branch generation strategy.

        Args:
            strategy_name: New strategy name.
        """
        self.strategy = strategy_name
        self._strategy = create_strategy(
            strategy_name,
            self.strategy_seed,
            condition_weights=self.condition_weights,
            table_metadata=self.table_metadata,
            field_distributions=self.field_distributions,
        )

    def set_max_branches(self, max_branches: int) -> None:
        """Change the maximum number of branches.

        Args:
            max_branches: New maximum.
        """
        self.max_branches = max_branches

    def _generate_mutex_branches_new(
        self,
        sql_node: SqlNode,
        choose_nodes: List,
    ) -> List[Dict[str, Any]]:
        if_nodes = self._collect_if_nodes(sql_node)
        all_conditions = self._collect_conditions(sql_node)

        choose_condition_set = set()
        for choose_node in choose_nodes:
            for when_test in choose_node.if_sql_nodes:
                if when_test.test:
                    choose_condition_set.add(when_test.test)

        non_choose_conditions = [c for c in all_conditions if c not in choose_condition_set]

        if non_choose_conditions:
            non_choose_combinations = self._strategy.generate(non_choose_conditions, self.max_branches)
        else:
            non_choose_combinations = [[]]

        # Build per-choose options and enumerate across all choose nodes together.
        # Each choose contributes N when-options (+ default option if otherwise exists).
        # Then we perform cartesian product across choose nodes so multi-choose coverage
        # is complete.
        choose_options: List[List[set[str]]] = []
        for choose_node in choose_nodes:
            options: List[set[str]] = []
            for when_node in choose_node.if_sql_nodes:
                if when_node.test:
                    options.append({when_node.test})
            if choose_node.default_sql_node is not None:
                options.append(set())
            if options:
                choose_options.append(options)

        choose_combinations: List[set[str]]
        if choose_options:
            choose_combinations = [set().union(*combo) for combo in product(*choose_options)]
        else:
            choose_combinations = [set()]

        branches = []
        seen_signatures: set[tuple[str, ...]] = set()

        for non_choose_active in non_choose_combinations:
            non_choose_set = set(non_choose_active)
            for choose_set in choose_combinations:
                active_set = non_choose_set | choose_set
                if self._is_obviously_mutex_conflict(active_set):
                    continue
                signature = tuple(sorted(active_set))
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)

                modified_node = self._create_filtered_sql_node(sql_node, if_nodes, active_set)
                context = DynamicContext()
                modified_node.apply(context)
                sql = context.get_sql().strip()

                branches.append(
                    {
                        "branch_id": len(branches),
                        "active_conditions": sorted(active_set),
                        "sql": sql,
                        "condition_count": len(active_set),
                    }
                )

                if len(branches) >= self.max_branches:
                    break

        # Generate foreach boundary branches (0, 1, 2 items)
        branches = self._generate_foreach_boundary_branches(branches, sql_node)

        return branches[: self.max_branches]

    @staticmethod
    def _collect_foreach_nodes(
        sql_node: SqlNode,
    ) -> List[Any]:
        """Recursively collect all ForEachSqlNode nodes from the tree.

        Args:
            sql_node: The root SqlNode to collect from.

        Returns:
            List of ForEachSqlNode nodes found in the tree.
        """
        from sqlopt.stages.branching.sql_node import (
            ForEachSqlNode,
            MixedSqlNode,
            StaticTextSqlNode,
        )

        foreach_nodes = []

        def collect_recursive(node: SqlNode) -> None:
            if isinstance(node, ForEachSqlNode):
                foreach_nodes.append(node)
            # MixedSqlNode has a 'contents' attribute that is a list
            elif isinstance(node, MixedSqlNode) and hasattr(node, "contents"):
                if node.contents:
                    if isinstance(node.contents, list):
                        for child in node.contents:
                            collect_recursive(child)
                    else:
                        collect_recursive(node.contents)
            # For other node types that have contents as attribute
            elif hasattr(node, "contents") and node.contents:
                if isinstance(node.contents, list):
                    for child in node.contents:
                        collect_recursive(child)
                else:
                    collect_recursive(node.contents)

        collect_recursive(sql_node)
        return foreach_nodes

    @staticmethod
    def _collect_bind_expressions(
        sql_node: SqlNode,
    ) -> Dict[str, str]:
        """Recursively collect all VarDeclSqlNode expressions from the tree.

        Args:
            sql_node: The root SqlNode to collect from.

        Returns:
            Dictionary mapping bind name to expression value.
        """
        from sqlopt.stages.branching.sql_node import (
            VarDeclSqlNode,
            MixedSqlNode,
            IfSqlNode,
            ChooseSqlNode,
            TrimSqlNode,
            WhereSqlNode,
            SetSqlNode,
            ForEachSqlNode,
            IncludeSqlNode,
        )

        bind_expressions: Dict[str, str] = {}

        def collect_recursive(node: SqlNode) -> None:
            if isinstance(node, VarDeclSqlNode):
                bind_expressions[node.name] = node.expression
            elif isinstance(node, MixedSqlNode) and hasattr(node, "contents"):
                if node.contents:
                    if isinstance(node.contents, list):
                        for child in node.contents:
                            collect_recursive(child)
                    else:
                        collect_recursive(node.contents)
            elif isinstance(node, IfSqlNode) and node.contents:
                collect_recursive(node.contents)
            elif isinstance(node, ChooseSqlNode):
                for when_node in node.if_sql_nodes:
                    if when_node.contents:
                        collect_recursive(when_node.contents)
                if node.default_sql_node and node.default_sql_node.contents:
                    collect_recursive(node.default_sql_node.contents)
            elif isinstance(node, (TrimSqlNode, WhereSqlNode, SetSqlNode)):
                if node.contents:
                    collect_recursive(node.contents)
            elif isinstance(node, ForEachSqlNode):
                if node.contents:
                    collect_recursive(node.contents)
            elif isinstance(node, IncludeSqlNode):
                if node.fragment_registry:
                    fragment = node.fragment_registry.lookup(node.refid)
                    if fragment:
                        collect_recursive(fragment)
            elif hasattr(node, "contents") and node.contents:
                if isinstance(node.contents, list):
                    for child in node.contents:
                        collect_recursive(child)
                else:
                    collect_recursive(node.contents)

        collect_recursive(sql_node)
        return bind_expressions

    def _generate_foreach_boundary_branches(
        self,
        branches: List[Dict[str, Any]],
        sql_node: SqlNode,
    ) -> List[Dict[str, Any]]:
        """Generate additional branches for safe foreach cardinality buckets.

        We keep the base branch render (sample_size=2) as the small-list case,
        then add singleton and large-list variants by re-rendering the filtered
        SqlNode tree. Empty-collection variants are intentionally skipped here
        because they frequently produce invalid SQL such as ``IN ()`` and are
        better modeled as the surrounding guard condition being false.

        Args:
            branches: Initial branches generated from condition combinations.
            sql_node: The root SqlNode.

        Returns:
            Extended list of branches including foreach cardinality variants.
        """
        if not self._collect_foreach_nodes(sql_node):
            return branches

        if_nodes = self._collect_if_nodes(sql_node)
        boundary_branches: List[Dict[str, Any]] = []
        seen_signatures = {
            self._branch_signature(branch["sql"], branch.get("active_conditions", [])) for branch in branches
        }

        for branch in branches:
            if len(branches) + len(boundary_branches) >= self.max_branches:
                break

            active_conditions = list(branch.get("active_conditions", []))
            filtered_node = self._create_filtered_sql_node(
                sql_node,
                if_nodes,
                set(active_conditions),
            )
            filtered_foreach_nodes = self._collect_foreach_nodes(filtered_node)

            for foreach_index, foreach_node in enumerate(filtered_foreach_nodes):
                if len(branches) + len(boundary_branches) >= self.max_branches:
                    break
                for sample_size, bucket_name in ((1, "singleton"), (8, "large")):
                    if len(branches) + len(boundary_branches) >= self.max_branches:
                        break
                    if getattr(foreach_node, "sample_size", 2) == sample_size:
                        continue

                    variant_node = copy.deepcopy(filtered_node)
                    variant_foreach_nodes = self._collect_foreach_nodes(variant_node)
                    if foreach_index >= len(variant_foreach_nodes):
                        continue

                    variant_foreach_nodes[foreach_index].sample_size = sample_size
                    context = DynamicContext()
                    variant_node.apply(context)
                    variant_sql = self._normalize_sql(context.get_sql())
                    if not variant_sql or self._contains_empty_in_clause(variant_sql):
                        continue

                    variant_conditions = active_conditions + [f"foreach_{foreach_index}_{bucket_name}"]
                    signature = self._branch_signature(variant_sql, variant_conditions)
                    if signature in seen_signatures:
                        continue
                    seen_signatures.add(signature)

                    boundary_branches.append(
                        {
                            "branch_id": len(branches) + len(boundary_branches),
                            "active_conditions": variant_conditions,
                            "sql": variant_sql,
                            "condition_count": len(variant_conditions),
                        }
                    )

        return branches + boundary_branches

    @staticmethod
    def _branch_signature(
        sql: str,
        active_conditions: List[str],
    ) -> tuple[str, tuple[str, ...]]:
        return sql, tuple(active_conditions)

    @staticmethod
    def _contains_empty_in_clause(sql: str) -> bool:
        return bool(re.search(r"\b(?:NOT\s+)?IN\s*\(\s*\)", sql, re.IGNORECASE))

    @staticmethod
    def _dedupe_list(values: List[str]) -> List[str]:
        deduped: List[str] = []
        seen: set[str] = set()
        for value in values:
            if value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped
