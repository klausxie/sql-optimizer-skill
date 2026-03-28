"""JOIN 重排单元测试"""

import pytest
from sqlopt.platforms.sql.join_utils import get_join_order, can_reorder_joins


class TestGetJoinOrder:
    def test_simple_joins(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id JOIN c ON b.id = c.id"
        result = get_join_order(sql)
        assert len(result) >= 2


class TestCanReorderJoins:
    def test_can_reorder(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id JOIN c ON b.id = c.id"
        assert can_reorder_joins(sql) is True

    def test_cannot_reorder_with_union(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id UNION SELECT * FROM c"
        assert can_reorder_joins(sql) is False

    def test_cannot_reorder_with_group_by(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id GROUP BY a.id"
        assert can_reorder_joins(sql) is False