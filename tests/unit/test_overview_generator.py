"""Tests for StageOverviewGenerator base class."""

import pytest

from python.sqlopt.application.v9_stages.overview import StageOverviewGenerator


class TestStageOverviewGenerator:
    """Test cases for StageOverviewGenerator base class."""

    def test_render_header(self, tmp_path):
        """Verify header contains stage name and summary."""
        gen = StageOverviewGenerator("init", tmp_path)
        result = gen._render_header("Init", "Scanned 100 SQL units")
        assert "# Init Stage Overview" in result
        assert "## 执行摘要" in result
        assert "Scanned 100 SQL units" in result

    def test_render_table(self, tmp_path):
        """Verify table rendering with headers and rows."""
        gen = StageOverviewGenerator("init", tmp_path)
        headers = ["Name", "Count", "Status"]
        rows = [["SQL Units", 100, "OK"], ["Risks", 5, "Warning"]]
        result = gen._render_table(headers, rows)
        assert "## 关键指标" in result
        assert "| Name | Count | Status |" in result
        assert "| SQL Units | 100 | OK |" in result
        assert "| Risks | 5 | Warning |" in result
        assert "------" in result

    def test_render_table_empty_headers(self, tmp_path):
        """Verify empty headers return empty string."""
        gen = StageOverviewGenerator("init", tmp_path)
        result = gen._render_table([], [["row"]])
        assert result == ""

    def test_render_bullet_list(self, tmp_path):
        """Verify bullet list rendering."""
        gen = StageOverviewGenerator("init", tmp_path)
        items = ["Item 1", "Item 2", "Item 3"]
        result = gen._render_bullet_list(items)
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "- Item 3" in result

    def test_render_bullet_list_empty(self, tmp_path):
        """Verify empty list returns empty string."""
        gen = StageOverviewGenerator("init", tmp_path)
        result = gen._render_bullet_list([])
        assert result == ""

    def test_render_risk_summary_high(self, tmp_path):
        """Verify high severity risks are grouped."""
        gen = StageOverviewGenerator("init", tmp_path)
        risks = [
            {
                "severity": "high",
                "risk_type": "prefix_wildcard",
                "description": "Wildcard at start of LIKE pattern",
            }
        ]
        result = gen._render_risk_summary(risks)
        assert "## 问题与风险" in result
        assert "### 🔴 高风险" in result
        assert "**prefix_wildcard**: Wildcard at start of LIKE pattern" in result

    def test_render_risk_summary_medium(self, tmp_path):
        """Verify medium severity risks are grouped."""
        gen = StageOverviewGenerator("init", tmp_path)
        risks = [
            {
                "severity": "medium",
                "risk_type": "function_wrap",
                "description": "Function wrap on column prevents index usage",
            }
        ]
        result = gen._render_risk_summary(risks)
        assert "## 问题与风险" in result
        assert "### 🟡 中风险" in result
        assert (
            "**function_wrap**: Function wrap on column prevents index usage" in result
        )

    def test_render_risk_summary_low(self, tmp_path):
        """Verify low severity risks are grouped."""
        gen = StageOverviewGenerator("init", tmp_path)
        risks = [
            {
                "severity": "low",
                "risk_type": "suffix_wildcard_only",
                "description": "Suffix wildcard may reduce index efficiency",
            }
        ]
        result = gen._render_risk_summary(risks)
        assert "## 问题与风险" in result
        assert "### 🟢 低风险" in result
        assert (
            "**suffix_wildcard_only**: Suffix wildcard may reduce index efficiency"
            in result
        )

    def test_render_risk_summary_mixed(self, tmp_path):
        """Verify mixed severity risks grouped correctly."""
        gen = StageOverviewGenerator("init", tmp_path)
        risks = [
            {
                "severity": "high",
                "risk_type": "prefix_wildcard",
                "description": "High risk",
            },
            {
                "severity": "low",
                "risk_type": "suffix_wildcard_only",
                "description": "Low risk",
            },
            {
                "severity": "medium",
                "risk_type": "function_wrap",
                "description": "Medium risk",
            },
        ]
        result = gen._render_risk_summary(risks)
        assert "### 🔴 高风险" in result
        assert "### 🟡 中风险" in result
        assert "### 🟢 低风险" in result
        assert "**prefix_wildcard**: High risk" in result
        assert "**function_wrap**: Medium risk" in result
        assert "**suffix_wildcard_only**: Low risk" in result

    def test_render_risk_summary_empty(self, tmp_path):
        """Verify empty risks return empty string."""
        gen = StageOverviewGenerator("init", tmp_path)
        result = gen._render_risk_summary([])
        assert result == ""

    def test_write_creates_file(self, tmp_path):
        """Verify write method creates markdown file."""
        gen = StageOverviewGenerator("init", tmp_path)

        class MockGenerator(StageOverviewGenerator):
            def generate(self, data):
                return "# Mock Report\n\nTest content"

        mock_gen = MockGenerator("init", tmp_path)
        output_path = mock_gen.write({}, "test_report.md")

        assert output_path.exists()
        assert output_path.name == "test_report.md"
        content = output_path.read_text(encoding="utf-8")
        assert "# Mock Report" in content
        assert "Test content" in content

    def test_generate_abstract_raises(self, tmp_path):
        """Verify base class generate() raises NotImplementedError."""
        gen = StageOverviewGenerator("init", tmp_path)
        with pytest.raises(NotImplementedError):
            gen.generate({})
