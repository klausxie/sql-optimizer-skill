"""UNION Collapse Strategy 集成测试"""

import pytest
from sqlopt.platforms.sql.union_collapse_strategy import SafeUnionCollapseStrategy


class TestSafeUnionCollapseStrategy:
    def test_plan_returns_none_when_no_union(self):
        """没有 UNION 时应返回 None"""
        strategy = SafeUnionCollapseStrategy()

        sql_unit = {
            "sqlKey": "test.UserMapper.findAll",
            "xmlPath": "test.xml",
            "templateSql": "SELECT * FROM users",
        }

        result = strategy.plan(
            sql_unit=sql_unit,
            rewritten_sql="SELECT * FROM users WHERE status = 1",
            fragment_catalog={},
            enable_fragment_materialization=False,
            fallback_from=None,
            dynamic_candidate_intent=None,
        )

        assert result is None

    def test_plan_returns_none_when_nested_union(self):
        """嵌套 UNION 时应返回 None"""
        strategy = SafeUnionCollapseStrategy()

        sql_unit = {
            "sqlKey": "test.UserMapper.findAll",
            "xmlPath": "test.xml",
            "templateSql": "SELECT * FROM (SELECT a FROM t1 UNION SELECT b FROM t2 UNION SELECT c FROM t3) tmp",
        }

        result = strategy.plan(
            sql_unit=sql_unit,
            rewritten_sql="SELECT a FROM t1 UNION SELECT b FROM t2 UNION SELECT c FROM t3",
            fragment_catalog={},
            enable_fragment_materialization=False,
            fallback_from=None,
            dynamic_candidate_intent=None,
        )

        assert result is None

    def test_strategy_type(self):
        """验证策略类型"""
        strategy = SafeUnionCollapseStrategy()
        assert strategy.strategy_type == "SAFE_UNION_COLLAPSE"

    def test_required_capability(self):
        """验证所需 capability"""
        strategy = SafeUnionCollapseStrategy()
        assert strategy.required_capability == "SAFE_UNION_COLLAPSE"

    def test_plan_returns_none_when_for_update(self):
        """FOR UPDATE 时应返回 None"""
        strategy = SafeUnionCollapseStrategy()

        sql_unit = {
            "sqlKey": "test.UserMapper.findAll",
            "xmlPath": "test.xml",
            "templateSql": "SELECT * FROM (SELECT a FROM t1 UNION ALL SELECT b FROM t2) tmp",
        }

        result = strategy.plan(
            sql_unit=sql_unit,
            rewritten_sql="SELECT a FROM t1 UNION ALL SELECT b FROM t2 FOR UPDATE",
            fragment_catalog={},
            enable_fragment_materialization=False,
            fallback_from=None,
            dynamic_candidate_intent=None,
        )

        assert result is None

    def test_plan_returns_none_when_distinct(self):
        """DISTINCT 时应返回 None"""
        strategy = SafeUnionCollapseStrategy()

        sql_unit = {
            "sqlKey": "test.UserMapper.findAll",
            "xmlPath": "test.xml",
            "templateSql": "SELECT * FROM (SELECT a FROM t1 UNION ALL SELECT b FROM t2) tmp",
        }

        result = strategy.plan(
            sql_unit=sql_unit,
            rewritten_sql="SELECT DISTINCT a FROM t1 UNION ALL SELECT b FROM t2",
            fragment_catalog={},
            enable_fragment_materialization=False,
            fallback_from=None,
            dynamic_candidate_intent=None,
        )

        assert result is None