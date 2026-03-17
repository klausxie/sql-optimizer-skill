"""
Unit tests for Branching module (brancher.py)
"""

import unittest
from sqlopt.stages.branching.brancher import Brancher, Branch


class BranchDataclassTest(unittest.TestCase):
    """Test Branch dataclass fields and structure."""

    def test_branch_dataclass_fields(self):
        """Test Branch dataclass has all required fields."""
        branch = Branch(
            branch_id="test_branch",
            active_conditions=["condition1", "condition2"],
            sql="SELECT * FROM users WHERE id = 1",
            condition_count=2,
            risk_flags=["prefix_wildcard"],
        )

        self.assertEqual(branch.branch_id, "test_branch")
        self.assertEqual(branch.active_conditions, ["condition1", "condition2"])
        self.assertEqual(branch.sql, "SELECT * FROM users WHERE id = 1")
        self.assertEqual(branch.condition_count, 2)
        self.assertEqual(branch.risk_flags, ["prefix_wildcard"])

    def test_branch_dataclass_default_risk_flags(self):
        """Test Branch dataclass has default empty risk_flags."""
        branch = Branch(
            branch_id="default_branch",
            active_conditions=[],
            sql="SELECT 1",
            condition_count=0,
        )

        self.assertEqual(branch.risk_flags, [])


class BrancherGenerateTest(unittest.TestCase):
    """Test Brancher.generate() method."""

    def test_generate_returns_single_branch_for_static_sql(self):
        """No dynamic conditions returns single default branch."""
        brancher = Brancher()
        static_sql = "SELECT * FROM users WHERE id = 1"

        branches = brancher.generate(static_sql)

        self.assertEqual(len(branches), 1)
        self.assertEqual(branches[0].branch_id, "default")
        self.assertEqual(branches[0].active_conditions, [])
        self.assertEqual(branches[0].sql, static_sql)
        self.assertEqual(branches[0].condition_count, 0)

    def test_generate_returns_single_branch_for_none_conditions(self):
        """None conditions returns single default branch."""
        brancher = Brancher()
        sql = "SELECT * FROM users"

        branches = brancher.generate(sql, None)

        self.assertEqual(len(branches), 1)
        self.assertEqual(branches[0].branch_id, "default")

    def test_generate_all_combinations_strategy(self):
        """Test all combinations generation strategy."""
        brancher = Brancher(strategy="all_combinations")
        sql = "SELECT * FROM users WHERE 1=1"
        conditions = [
            {"condition": "name = 'test'"},
            {"condition": "status = 'active'"},
        ]

        branches = brancher.generate(sql, conditions)

        # 2 conditions = 2^2 = 4 combinations
        self.assertEqual(len(branches), 4)

        # Verify all branch_ids are unique
        branch_ids = [b.branch_id for b in branches]
        self.assertEqual(len(set(branch_ids)), 4)

    def test_generate_pairwise_strategy(self):
        """Test pairwise generation strategy."""
        brancher = Brancher(strategy="pairwise")
        sql = "SELECT * FROM users WHERE 1=1"
        conditions = [
            {"condition": "name = 'test'"},
            {"condition": "status = 'active'"},
            {"condition": "type = 'admin'"},
        ]

        branches = brancher.generate(sql, conditions)

        # Pairwise: 1 default + 3 individual = 4 branches
        self.assertEqual(len(branches), 4)

        # First branch should be default with no conditions
        self.assertEqual(branches[0].branch_id, "default")
        self.assertEqual(branches[0].active_conditions, [])

        # Remaining branches should have single conditions
        for i in range(1, len(branches)):
            self.assertEqual(branches[i].condition_count, 1)

    def test_generate_respects_max_branches_limit(self):
        """Test max_branches limit is respected."""
        brancher = Brancher(strategy="all_combinations", max_branches=3)
        sql = "SELECT * FROM users WHERE 1=1"
        conditions = [
            {"condition": "cond1"},
            {"condition": "cond2"},
            {"condition": "cond3"},
            {"condition": "cond4"},
        ]

        branches = brancher.generate(sql, conditions)

        # Should be limited to max_branches
        self.assertEqual(len(branches), 3)

    def test_generate_detects_prefix_wildcard_risk(self):
        """Test detection of prefix wildcard risk."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE name LIKE '%' + ? + '%'"

        branches = brancher.generate(sql)

        self.assertEqual(len(branches), 1)
        self.assertIn("prefix_wildcard", branches[0].risk_flags)

    def test_generate_detects_suffix_wildcard_risk(self):
        """Test detection of suffix wildcard risk."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE name LIKE ? + '%'"

        branches = brancher.generate(sql)

        self.assertEqual(len(branches), 1)
        self.assertIn("suffix_wildcard", branches[0].risk_flags)

    def test_generate_detects_function_wrap_risk(self):
        """Test detection of function wrap risk."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE UPPER(name) = ?"

        branches = brancher.generate(sql)

        self.assertEqual(len(branches), 1)
        self.assertIn("function_wrap", branches[0].risk_flags)

    def test_generate_detects_multiple_risks(self):
        """Test detection of multiple risks."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE UPPER(name) LIKE '%' + ?"

        branches = brancher.generate(sql)

        self.assertEqual(len(branches), 1)
        self.assertIn("prefix_wildcard", branches[0].risk_flags)
        self.assertIn("function_wrap", branches[0].risk_flags)

    def test_apply_conditions_basic(self):
        """Test condition application returns SQL."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE 1=1"
        active_conditions = ["name = 'test'", "status = 'active'"]

        result = brancher._apply_conditions(sql, active_conditions)

        # Currently returns SQL as-is (simplified implementation)
        self.assertEqual(result, sql)

    def test_bool_combinations(self):
        """Test boolean combination generation."""
        brancher = Brancher()

        # 2 conditions = 4 combinations
        combos = list(brancher._bool_combinations(2))
        self.assertEqual(len(combos), 4)

        # 3 conditions = 8 combinations
        combos = list(brancher._bool_combinations(3))
        self.assertEqual(len(combos), 8)

        # Verify all combinations are valid boolean tuples
        for combo in combos:
            self.assertIsInstance(combo, tuple)
            self.assertTrue(all(isinstance(x, bool) for x in combo))

    def test_bool_combinations_exhaustive(self):
        """Test bool combinations generate all possibilities."""
        brancher = Brancher()
        n = 3
        combos = list(brancher._bool_combinations(n))

        # Should have exactly 2^n combinations
        self.assertEqual(len(combos), 2**n)

        # All possible combinations of n booleans
        expected = []
        for i in range(2**n):
            expected.append(tuple(bool(i & (1 << j)) for j in range(n)))

        self.assertEqual(sorted(combos), sorted(expected))


class BrancherConfigTest(unittest.TestCase):
    """Test Brancher configuration options."""

    def test_default_strategy(self):
        """Test default strategy is all_combinations."""
        brancher = Brancher()
        self.assertEqual(brancher.strategy, "all_combinations")

    def test_custom_strategy(self):
        """Test custom strategy configuration."""
        brancher = Brancher(strategy="pairwise")
        self.assertEqual(brancher.strategy, "pairwise")

    def test_default_max_branches(self):
        """Test default max_branches is 100."""
        brancher = Brancher()
        self.assertEqual(brancher.max_branches, 100)

    def test_custom_max_branches(self):
        """Test custom max_branches configuration."""
        brancher = Brancher(max_branches=50)
        self.assertEqual(brancher.max_branches, 50)


class RiskPatternsTest(unittest.TestCase):
    """Test risk pattern detection."""

    def test_prefix_wildcard_pattern_single_quote(self):
        """Test prefix wildcard with single quotes."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE name LIKE '%' + ?"

        branches = brancher.generate(sql)
        self.assertIn("prefix_wildcard", branches[0].risk_flags)

    def test_prefix_wildcard_pattern_double_quote(self):
        """Test prefix wildcard with double quotes."""
        brancher = Brancher()
        sql = 'SELECT * FROM users WHERE name LIKE "%" + ?'

        branches = brancher.generate(sql)
        self.assertIn("prefix_wildcard", branches[0].risk_flags)

    def test_suffix_wildcard_pattern(self):
        """Test suffix wildcard pattern."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE name LIKE ? + '%'"

        branches = brancher.generate(sql)
        self.assertIn("suffix_wildcard", branches[0].risk_flags)

    def test_function_wrap_upper(self):
        """Test UPPER function wrap detection."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE UPPER(name) = ?"

        branches = brancher.generate(sql)
        self.assertIn("function_wrap", branches[0].risk_flags)

    def test_function_wrap_lower(self):
        """Test LOWER function wrap detection."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE LOWER(name) = ?"

        branches = brancher.generate(sql)
        self.assertIn("function_wrap", branches[0].risk_flags)

    def test_function_wrap_trim(self):
        """Test TRIM function wrap detection."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE TRIM(name) = ?"

        branches = brancher.generate(sql)
        self.assertIn("function_wrap", branches[0].risk_flags)

    def test_no_risk_for_simple_sql(self):
        """Test no risk flags for simple SQL."""
        brancher = Brancher()
        sql = "SELECT * FROM users WHERE id = 1"

        branches = brancher.generate(sql)
        self.assertEqual(branches[0].risk_flags, [])


class EdgeCasesTest(unittest.TestCase):
    """Test edge cases."""

    def test_empty_sql(self):
        """Test with empty SQL string."""
        brancher = Brancher()
        branches = brancher.generate("")
        self.assertEqual(len(branches), 1)
        self.assertEqual(branches[0].sql, "")

    def test_single_condition(self):
        """Test with single condition."""
        brancher = Brancher(strategy="all_combinations")
        sql = "SELECT * FROM users WHERE 1=1"
        conditions = [{"condition": "name = 'test'"}]

        branches = brancher.generate(sql, conditions)

        # 1 condition = 2 combinations (true/false)
        self.assertEqual(len(branches), 2)

    def test_many_conditions_with_limit(self):
        """Test many conditions with strict limit."""
        brancher = Brancher(strategy="all_combinations", max_branches=2)
        sql = "SELECT * FROM users WHERE 1=1"
        conditions = [{"condition": f"cond{i}"} for i in range(10)]

        branches = brancher.generate(sql, conditions)

        self.assertEqual(len(branches), 2)


if __name__ == "__main__":
    unittest.main()
