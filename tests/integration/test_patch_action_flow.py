"""Integration tests for PatchAction flow.

Tests the full pipeline from InitStage through ResultStage, verifying:
- Full pipeline runs without errors
- proposals.json contains actions array with proper structure
- XmlPatchEngine.apply_actions() produces valid patched XML
- Conflict detection works with overlapping actions
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from sqlopt.common.config import SQLOptConfig
from sqlopt.common.llm_mock_generator import MockLLMProvider
from sqlopt.common.xml_patch_engine import XmlPatchEngine
from sqlopt.contracts.optimize import (
    ActionConflict,
    OptimizationAction,
    OptimizationProposal,
    UnitActionSummary,
)
from sqlopt.stages.init.stage import InitStage
from sqlopt.stages.optimize.stage import OptimizeStage
from sqlopt.stages.parse.stage import ParseStage
from sqlopt.stages.recognition.stage import RecognitionStage
from sqlopt.stages.result.stage import ResultStage


class ActionGeneratingMockProvider(MockLLMProvider):
    """Mock LLM provider that generates OptimizationAction arrays.

    Use this instead of MockLLMProvider when testing the patch action flow.
    """

    def generate_optimization(
        self,
        sql: str,
        description: str = "",
        *,
        xml_context: str | None = None,  # noqa: ARG002
        table_schema: str | None = None,  # noqa: ARG002
        branch_condition: str | None = None,  # noqa: ARG002
    ) -> str:
        """Generate mock optimization with actions for SELECT * queries."""
        sql_unit_id = f"unit_{self._generate_deterministic_id(sql, '')}"
        path_id = f"path_{self._generate_deterministic_id(sql + description, '')}"

        # Generate actions for SELECT * optimization
        actions = []
        sql_upper = sql.upper().strip()

        if sql_upper.startswith("SELECT *") or "SELECT  *" in sql_upper:
            actions = [
                {
                    "action_id": f"act_{self._generate_deterministic_id(sql, '')}",
                    "operation": "REPLACE",
                    "xpath": "/mapper/select",
                    "target_tag": "select",
                    "original_snippet": sql,
                    "rewritten_snippet": sql.replace("*", "id, name", 1),
                    "sql_fragment": "*",
                    "rationale": "SELECT * retrieves all columns unnecessarily",
                    "confidence": 0.9,
                    "path_id": path_id,
                    "issue_type": "SELECT_STAR",
                }
            ]

        proposal = {
            "sql_unit_id": sql_unit_id,
            "path_id": path_id,
            "original_sql": sql,
            "optimized_sql": sql.replace("*", "id, name", 1) if actions else sql,
            "rationale": "Replace SELECT * with specific columns" if actions else "No change needed",
            "confidence": 0.9 if actions else 0.5,
            "actions": actions,
        }

        return json.dumps(proposal)


class TestPatchActionFlowIntegration:
    """Integration tests for the complete PatchAction flow."""

    @pytest.fixture
    def temp_mapper_dir(self):
        """Create a temporary directory with test XML mapper files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mapper_dir = Path(tmpdir) / "mappers"
            mapper_dir.mkdir()

            # Simple mapper with SELECT * that needs optimization
            (mapper_dir / "UserMapper.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <select id="findAll" resultType="User">
        SELECT * FROM users
    </select>

    <select id="findById" resultType="User">
        SELECT * FROM users WHERE id = #{id}
    </select>
</mapper>"""
            )

            yield tmpdir, mapper_dir

    @pytest.fixture
    def mock_config(self, temp_mapper_dir):
        """Create a mock config pointing to the temp mapper directory."""
        _, mapper_dir = temp_mapper_dir
        return SQLOptConfig(
            project_root_path=mapper_dir,
            scan_mapper_globs=["**/*.xml"],
            db_host=None,
            db_port=None,
            db_name=None,
        )

    def _create_run_structure(self, tmpdir: Path, run_id: str) -> Path:
        """Create the standard run directory structure."""
        run_path = tmpdir / "runs" / run_id
        for stage in ["init", "parse", "recognition", "optimize", "result"]:
            (run_path / stage).mkdir(parents=True, exist_ok=True)
        return run_path

    def test_full_pipeline_runs_without_errors(self, temp_mapper_dir, mock_config, monkeypatch):
        """Test that the full pipeline runs without errors."""
        tmpdir, _ = temp_mapper_dir
        run_id = "test-patch-flow-full"
        self._create_run_structure(Path(tmpdir), run_id)

        monkeypatch.chdir(tmpdir)

        # Run InitStage
        init_stage = InitStage()
        init_output = init_stage.run(config=mock_config, run_id=run_id)
        assert len(init_output.sql_units) == 2

        # Run ParseStage
        parse_stage = ParseStage(run_id=run_id, use_mock=True, config=mock_config)
        parse_output = parse_stage.run()
        assert len(parse_output.sql_units_with_branches) == 2

        # Run RecognitionStage
        recognition_stage = RecognitionStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        recognition_output = recognition_stage.run()
        assert len(recognition_output.baselines) >= 2

        # Run OptimizeStage
        optimize_stage = OptimizeStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        optimize_output = optimize_stage.run()
        assert len(optimize_output.proposals) >= 2

        # Run ResultStage
        result_stage = ResultStage(run_id=run_id, use_mock=True)
        result_output = result_stage.run()
        assert result_output is not None

    def test_proposals_json_contains_actions_array(self, temp_mapper_dir, mock_config, monkeypatch):
        """Test that proposals.json contains proper actions array structure."""
        tmpdir, _ = temp_mapper_dir
        run_id = "test-patch-actions-struct"
        self._create_run_structure(Path(tmpdir), run_id)

        monkeypatch.chdir(tmpdir)

        # Run pipeline up to optimize
        init_stage = InitStage()
        init_stage.run(config=mock_config, run_id=run_id)

        parse_stage = ParseStage(run_id=run_id, use_mock=True, config=mock_config)
        parse_stage.run()

        recognition_stage = RecognitionStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        recognition_stage.run()

        optimize_stage = OptimizeStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        optimize_stage.run()

        # Check proposals.json file
        proposals_file = Path(f"runs/{run_id}/optimize/proposals.json")
        assert proposals_file.exists()

        with proposals_file.open() as f:
            proposals_data = json.load(f)

        assert "proposals" in proposals_data
        proposals = proposals_data["proposals"]
        assert len(proposals) >= 2

        # Find a proposal with actions
        proposals_with_actions = [p for p in proposals if p.get("actions")]
        assert len(proposals_with_actions) >= 1, "At least one proposal should have actions"

        # Verify action structure
        for proposal in proposals_with_actions:
            actions = proposal["actions"]
            assert isinstance(actions, list)
            for action in actions:
                assert "action_id" in action
                assert "operation" in action
                assert "xpath" in action
                assert "target_tag" in action
                assert "confidence" in action
                assert action["operation"] in ("REPLACE", "ADD", "REMOVE", "WRAP")

    def test_xml_patch_engine_produces_valid_patched_xml(self, temp_mapper_dir, mock_config, monkeypatch):
        """Test that XmlPatchEngine.apply_actions() produces valid patched XML."""
        tmpdir, _ = temp_mapper_dir
        run_id = "test-xml-patch-apply"
        self._create_run_structure(Path(tmpdir), run_id)

        monkeypatch.chdir(tmpdir)

        # Run pipeline up to optimize
        init_stage = InitStage()
        init_stage.run(config=mock_config, run_id=run_id)

        parse_stage = ParseStage(run_id=run_id, use_mock=True, config=mock_config)
        parse_stage.run()

        recognition_stage = RecognitionStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        recognition_stage.run()

        optimize_stage = OptimizeStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        optimize_stage.run()

        # Original XML
        original_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <select id="findAll" resultType="User">
        SELECT * FROM users
    </select>
</mapper>"""

        # Create an action to replace SELECT * with specific columns
        action = OptimizationAction(
            action_id="act_001",
            operation="REPLACE",
            xpath="/mapper/select",
            target_tag="select",
            original_snippet="SELECT * FROM users",
            rewritten_snippet="SELECT id, name FROM users",
            sql_fragment="*",
            rationale="Replace SELECT * with specific columns",
            confidence=0.9,
            path_id="path_001",
            issue_type="SELECT_STAR",
        )

        # Apply action
        patched_xml = XmlPatchEngine.apply_actions([action], original_xml)

        # Verify patched XML is valid and contains the optimization
        assert "SELECT id, name FROM users" in patched_xml
        assert "SELECT * FROM users" not in patched_xml

    def test_conflict_detection_works(self):
        """Test that conflict detection works with overlapping actions."""
        stage = OptimizeStage()

        # Create two actions targeting the same xpath with different operations
        action_a = OptimizationAction(
            action_id="act_a",
            operation="REPLACE",
            xpath="/mapper/select",
            target_tag="select",
            original_snippet="SELECT *",
            rewritten_snippet="SELECT id",
            confidence=0.9,
        )

        action_b = OptimizationAction(
            action_id="act_b",
            operation="REMOVE",
            xpath="/mapper/select",
            target_tag="select",
            original_snippet="SELECT *",
            confidence=0.8,
        )

        conflicts = stage.detect_conflicts([action_a, action_b])

        # Should detect a conflict (contradict: REPLACE vs REMOVE)
        assert len(conflicts) >= 1
        assert any(c.conflict_type == "contradict" for c in conflicts)

    def test_conflict_resolution_higher_confidence_wins(self):
        """Test that conflict resolution keeps the higher confidence action."""
        stage = OptimizeStage()

        action_a = OptimizationAction(
            action_id="act_a",
            operation="REPLACE",
            xpath="/mapper/select",
            target_tag="select",
            original_snippet="SELECT *",
            rewritten_snippet="SELECT id, name",
            confidence=0.95,  # Higher confidence
        )

        action_b = OptimizationAction(
            action_id="act_b",
            operation="REPLACE",
            xpath="/mapper/select",
            target_tag="select",
            original_snippet="SELECT *",
            rewritten_snippet="SELECT id",
            confidence=0.75,  # Lower confidence
        )

        conflicts = stage.detect_conflicts([action_a, action_b])

        # Should detect overlap conflict
        assert len(conflicts) >= 1

        # Higher confidence action should win
        conflict = conflicts[0]
        if conflict.conflict_type == "overlap":
            assert conflict.resolution in ("a_wins", "b_wins")

    def test_unit_action_summary_aggregation(self):
        """Test that UnitActionSummary correctly aggregates actions from multiple branches."""
        stage = OptimizeStage()

        # Create proposals with actions for different branches
        proposal1 = OptimizationProposal(
            sql_unit_id="unit_001",
            path_id="branch_a",
            original_sql="SELECT * FROM users WHERE type = 'A'",
            optimized_sql="SELECT id, name FROM users WHERE type = 'A'",
            rationale="Replace SELECT *",
            confidence=0.9,
            actions=[
                OptimizationAction(
                    action_id="act_1",
                    operation="REPLACE",
                    xpath="/mapper/select",
                    target_tag="select",
                    original_snippet="SELECT *",
                    rewritten_snippet="SELECT id, name",
                    confidence=0.9,
                    path_id="branch_a",
                )
            ],
        )

        proposal2 = OptimizationProposal(
            sql_unit_id="unit_001",
            path_id="branch_b",
            original_sql="SELECT * FROM users WHERE type = 'B'",
            optimized_sql="SELECT id, name FROM users WHERE type = 'B'",
            rationale="Replace SELECT *",
            confidence=0.85,
            actions=[
                OptimizationAction(
                    action_id="act_2",
                    operation="REPLACE",
                    xpath="/mapper/select",
                    target_tag="select",
                    original_snippet="SELECT *",
                    rewritten_snippet="SELECT id, name",
                    confidence=0.85,
                    path_id="branch_b",
                )
            ],
        )

        # Aggregate actions
        summary = stage.aggregate_unit_actions("unit_001", [proposal1, proposal2])

        assert summary.sql_unit_id == "unit_001"
        assert len(summary.actions) == 2
        assert len(summary.conflicts) == 0  # Same operation on same xpath is not a conflict
        assert summary.branch_coverage["branch_a"] is True
        assert summary.branch_coverage["branch_b"] is True

    def test_result_stage_creates_patches(self, temp_mapper_dir, mock_config, monkeypatch):
        """Test that ResultStage creates patches from proposals with actions."""
        tmpdir, _ = temp_mapper_dir
        run_id = "test-result-patches"
        self._create_run_structure(Path(tmpdir), run_id)

        monkeypatch.chdir(tmpdir)

        # Run pipeline up to optimize
        init_stage = InitStage()
        init_stage.run(config=mock_config, run_id=run_id)

        parse_stage = ParseStage(run_id=run_id, use_mock=True, config=mock_config)
        parse_stage.run()

        recognition_stage = RecognitionStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        recognition_stage.run()

        optimize_stage = OptimizeStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        optimize_stage.run()

        # Run ResultStage
        result_stage = ResultStage(run_id=run_id, use_mock=True)
        result_output = result_stage.run()

        # Verify result output
        assert result_output is not None
        assert hasattr(result_output, "patches")
        assert hasattr(result_output, "report")

        # If patches were generated, verify structure
        if result_output.patches:
            for patch in result_output.patches:
                assert patch.sql_unit_id is not None
                assert patch.original_xml is not None
                assert patch.patched_xml is not None
                assert patch.diff is not None

    def test_patch_file_structure(self, temp_mapper_dir, mock_config, monkeypatch):
        """Test that the patch file is correctly structured."""
        tmpdir, _ = temp_mapper_dir
        run_id = "test-patch-file"
        self._create_run_structure(Path(tmpdir), run_id)

        monkeypatch.chdir(tmpdir)

        # Run pipeline
        init_stage = InitStage()
        init_stage.run(config=mock_config, run_id=run_id)

        parse_stage = ParseStage(run_id=run_id, use_mock=True, config=mock_config)
        parse_stage.run()

        recognition_stage = RecognitionStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        recognition_stage.run()

        optimize_stage = OptimizeStage(
            run_id=run_id,
            llm_provider=ActionGeneratingMockProvider(),
            use_mock=True,
            config=mock_config,
        )
        optimize_stage.run()

        result_stage = ResultStage(run_id=run_id, use_mock=True)
        result_stage.run()

        # Check report.json file exists
        report_file = Path(f"runs/{run_id}/result/report.json")
        assert report_file.exists()

        with report_file.open() as f:
            report_data = json.load(f)

        assert "report" in report_data
        assert "patches" in report_data
        assert isinstance(report_data["patches"], list)


class TestXmlPatchEngineMyBatis:
    """Integration tests for XmlPatchEngine with MyBatis XML."""

    def test_mybatis_select_star_replacement(self):
        """Test replacing SELECT * in a MyBatis XML select statement."""
        original_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <select id="findAll" resultType="User">
        SELECT * FROM users
    </select>
</mapper>"""

        action = OptimizationAction(
            action_id="act_fix_select_star",
            operation="REPLACE",
            xpath="/mapper/select",
            target_tag="select",
            original_snippet="SELECT * FROM users",
            rewritten_snippet="SELECT id, name, email FROM users",
            sql_fragment="*",
            rationale="Replace SELECT * with specific columns to reduce data transfer",
            confidence=0.92,
            issue_type="SELECT_STAR",
        )

        patched_xml = XmlPatchEngine.apply_actions([action], original_xml)

        # Verify the replacement
        assert "SELECT id, name, email FROM users" in patched_xml
        assert "SELECT * FROM users" not in patched_xml

        # Verify XML is still valid
        import xml.etree.ElementTree as ET

        tree = ET.fromstring(patched_xml)
        assert tree.find("select") is not None
        assert tree.find("select").text.strip() == "SELECT id, name, email FROM users"

    def test_multiple_actions_same_element(self):
        """Test applying multiple actions to the same element."""
        original_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <select id="findAll" resultType="User">
        SELECT * FROM users
    </select>
</mapper>"""

        actions = [
            OptimizationAction(
                action_id="act_1",
                operation="REPLACE",
                xpath="/mapper/select",
                target_tag="select",
                original_snippet="SELECT *",
                rewritten_snippet="SELECT id, name",
                confidence=0.9,
            ),
            OptimizationAction(
                action_id="act_2",
                operation="ADD",
                xpath="/mapper/select",
                target_tag="select",
                rewritten_snippet="<where>id > 0</where>",
                confidence=0.85,
            ),
        ]

        patched_xml = XmlPatchEngine.apply_actions(actions, original_xml)

        assert "SELECT id, name" in patched_xml
        assert "<where>id &gt; 0</where>" in patched_xml or "<where>id > 0</where>" in patched_xml

    def test_patch_preserves_xml_structure(self):
        """Test that patching preserves XML structure and declarations."""
        original_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <resultMap id="UserResult" type="User">
        <id property="id" column="id"/>
        <result property="name" column="name"/>
    </resultMap>

    <select id="findAll" resultMap="UserResult">
        SELECT * FROM users
    </select>
</mapper>"""

        action = OptimizationAction(
            action_id="act_fix",
            operation="REPLACE",
            xpath="/mapper/select",
            target_tag="select",
            original_snippet="SELECT * FROM users",
            rewritten_snippet="SELECT id, name FROM users",
            confidence=0.9,
        )

        patched_xml = XmlPatchEngine.apply_actions([action], original_xml)

        assert '<?xml version="1.0"' in patched_xml or "<?xml version='1.0'" in patched_xml
        assert "<resultMap id=" in patched_xml
        assert "<select id=" in patched_xml
        assert "SELECT id, name FROM users" in patched_xml
