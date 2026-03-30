"""JOIN 合并单元测试"""

import pytest
from sqlopt.platforms.sql.join_utils import find_consolidation_candidates


class TestFindConsolidationCandidates:
    def test_candidates_found(self):
        sql = "SELECT * FROM main m LEFT JOIN a ON m.id = a.ref_id LEFT JOIN b ON m.id = b.ref_id LEFT JOIN c ON m.id = c.ref_id"
        result = find_consolidation_candidates(sql)
        assert result is not None
        assert len(result) > 0

    def test_no_candidates(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id"
        result = find_consolidation_candidates(sql)
        assert result is None

    def test_no_join(self):
        sql = "SELECT * FROM users WHERE id = 1"
        result = find_consolidation_candidates(sql)
        assert result is None