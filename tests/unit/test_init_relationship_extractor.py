"""Unit tests for relationship_extractor module - extract_inter_table_relationships and hotspot scoring."""

import pytest
from sqlopt.contracts.init import SQLUnit
from sqlopt.stages.init.relationship_extractor import (
    _compute_confidence,
    _infer_fk_direction,
    _normalize_sql_for_analysis,
    extract_inter_table_relationships,
)


class TestInferFkDirection:
    """Tests for _infer_fk_direction function."""

    def test_user_id_to_id(self):
        direction, via_col, tgt_col = _infer_fk_direction("user_id", "id")
        assert direction == "one-to-many"
        assert via_col == "user_id"
        assert tgt_col == "id"

    def test_order_id_to_id(self):
        direction, via_col, tgt_col = _infer_fk_direction("order_id", "id")
        assert direction == "one-to-many"
        assert via_col == "order_id"
        assert tgt_col == "id"

    def test_id_to_user_id_reversed(self):
        direction, via_col, tgt_col = _infer_fk_direction("id", "user_id")
        assert direction == "many-to-one"
        assert via_col == "id"
        assert tgt_col == "user_id"

    def test_id_to_pk(self):
        direction, via_col, tgt_col = _infer_fk_direction("user_id", "pk")
        assert direction == "one-to-many"

    def test_uuid_target(self):
        direction, via_col, tgt_col = _infer_fk_direction("product_id", "uuid")
        assert direction == "one-to-many"

    def test_non_fk_columns(self):
        direction, via_col, tgt_col = _infer_fk_direction("name", "email")
        assert direction == "many-to-many"


class TestComputeConfidence:
    """Tests for _compute_confidence function."""

    def test_explicit_join_high_confidence(self):
        conf = _compute_confidence(True, "user_id", "id", 3)
        assert conf >= 0.99

    def test_implicit_fk_naming(self):
        conf = _compute_confidence(False, "order_id", "id", 1)
        assert conf == 0.5

    def test_explicit_join_no_fk_naming(self):
        conf = _compute_confidence(True, "name", "email", 1)
        assert conf == 0.4

    def test_single_sql_low_confidence(self):
        conf = _compute_confidence(False, "user_id", "id", 1)
        assert conf == 0.5


class TestNormalizeSqlForAnalysis:
    """Tests for _normalize_sql_for_analysis function."""

    def test_removes_mybatis_tags(self):
        sql = "<if test='id != null'>SELECT * FROM users</if>"
        result = _normalize_sql_for_analysis(sql)
        assert "<" not in result
        assert "users" in result

    def test_removes_parameter_placeholders(self):
        sql = "SELECT * FROM users WHERE id = #{id}"
        result = _normalize_sql_for_analysis(sql)
        assert "#{" not in result
        assert "?" in result

    def test_removes_string_literals(self):
        sql = "SELECT * FROM users WHERE name = 'John'"
        result = _normalize_sql_for_analysis(sql)
        assert "'" not in result


class TestExtractInterTableRelationships:
    """Tests for extract_inter_table_relationships main function."""

    def test_explicit_left_join(self):
        sql_units = [
            SQLUnit(
                id="u1",
                mapper_file="TestMapper.xml",
                sql_id="findUsers",
                sql_text="SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id",
                statement_type="SELECT",
            )
        ]
        rels, hotspots = extract_inter_table_relationships(sql_units)
        assert len(rels) == 1
        rel = rels[0]
        assert rel.source_table == "orders"
        assert rel.target_table == "users"
        assert rel.is_explicit_join is True
        assert rel.direction == "one-to-many"

    def test_implicit_where_equality(self):
        sql_units = [
            SQLUnit(
                id="u1",
                mapper_file="TestMapper.xml",
                sql_id="findItems",
                sql_text="SELECT * FROM a, b WHERE a.user_id = b.id AND a.status = 1",
                statement_type="SELECT",
            )
        ]
        rels, hotspots = extract_inter_table_relationships(sql_units)
        assert len(rels) == 1
        rel = rels[0]
        assert rel.source_table == "a"
        assert rel.target_table == "b"
        assert rel.is_explicit_join is False
        assert rel.direction == "one-to-many"

    def test_no_relationship_single_table(self):
        sql_units = [
            SQLUnit(
                id="u1",
                mapper_file="TestMapper.xml",
                sql_id="findUser",
                sql_text="SELECT * FROM users WHERE id = #{id}",
                statement_type="SELECT",
            )
        ]
        rels, hotspots = extract_inter_table_relationships(sql_units)
        assert len(rels) == 0

    def test_hotspot_high_risk(self):
        sql_units = [
            SQLUnit(
                id="u1",
                mapper_file="TestMapper.xml",
                sql_id="findOrders",
                sql_text="SELECT * FROM orders JOIN users ON orders.user_id = users.id JOIN products ON orders.product_id = products.id",
                statement_type="SELECT",
            ),
            SQLUnit(
                id="u2",
                mapper_file="TestMapper.xml",
                sql_id="findUsers",
                sql_text="SELECT * FROM users JOIN orders ON users.id = orders.user_id",
                statement_type="SELECT",
            ),
        ]
        rels, hotspots = extract_inter_table_relationships(sql_units)
        users_hotspot = hotspots.get("users")
        assert users_hotspot is not None
        assert users_hotspot.incoming_ref_count >= 2
        assert users_hotspot.risk_level in ("high", "medium", "low")

    def test_multiple_rels_same_table_merged(self):
        sql_units = [
            SQLUnit(
                id="u1",
                mapper_file="TestMapper.xml",
                sql_id="find1",
                sql_text="SELECT * FROM orders WHERE user_id = #{userId}",
                statement_type="SELECT",
            ),
            SQLUnit(
                id="u2",
                mapper_file="TestMapper.xml",
                sql_id="find2",
                sql_text="SELECT * FROM users WHERE id = #{id}",
                statement_type="SELECT",
            ),
        ]
        rels, hotspots = extract_inter_table_relationships(sql_units)
        assert len(rels) == 0

    def test_hotspot_risk_levels(self):
        sql_units = [
            SQLUnit(
                id="u1",
                mapper_file="TestMapper.xml",
                sql_id="find1",
                sql_text="SELECT * FROM orders JOIN users ON orders.user_id = users.id JOIN products ON orders.product_id = products.id JOIN log ON orders.id = log.order_id JOIN items ON orders.id = items.order_id",
                statement_type="SELECT",
            ),
            SQLUnit(
                id="u2",
                mapper_file="TestMapper.xml",
                sql_id="find2",
                sql_text="SELECT * FROM users JOIN orders ON users.id = orders.user_id JOIN log ON users.id = log.user_id",
                statement_type="SELECT",
            ),
            SQLUnit(
                id="u3",
                mapper_file="TestMapper.xml",
                sql_id="find3",
                sql_text="SELECT * FROM products JOIN orders ON products.id = orders.product_id",
                statement_type="SELECT",
            ),
        ]
        rels, hotspots = extract_inter_table_relationships(sql_units)
        orders_s = hotspots.get("orders")
        assert orders_s is not None
        assert orders_s.risk_level == "high"
        assert orders_s.incoming_ref_count == 2
        assert orders_s.hotspot_score > 10
