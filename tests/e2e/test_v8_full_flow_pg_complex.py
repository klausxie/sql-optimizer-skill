#!/usr/bin/env python3
"""
V8 Full Flow Test with Real PostgreSQL Database and Complex Dynamic SQL

Tests the complete V8 workflow with:
1. Real PostgreSQL database (100.101.41.123:5432/postgres)
2. Real opencode_run LLM provider
3. Complex dynamic SQL (if/choose/foreach/where tags)

Usage:
    python3 scripts/ci/test_v8_full_flow_pg_complex.py
    python3 -m pytest scripts/ci/test_v8_full_flow_pg_complex.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_config(config_path: Path, project_root: Path) -> None:
    """Write V8 configuration file with real PostgreSQL DB and opencode_run LLM"""
    config = {
        "config_version": "v1",
        "project": {"root_path": str(project_root)},
        "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
        "db": {
            "platform": "postgresql",
            "dsn": "postgresql://postgres:postgres@100.101.41.123:5432/postgres",
        },
        "llm": {"enabled": True, "provider": "opencode_run", "timeout_ms": 80000},
        "report": {"enabled": True},
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def _create_complex_mappers(project_dir: Path) -> None:
    """Create complex MyBatis XML mapper files with dynamic SQL"""
    mapper_dir = project_dir / "src" / "main" / "resources"
    mapper_dir.mkdir(parents=True, exist_ok=True)

    # UserMapper.xml - with dynamic SQL and risks
    user_mapper = mapper_dir / "UserMapper.xml"
    user_mapper.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" 
    "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.UserMapper">
    
    <!-- Risk: prefix wildcard (LIKE '%' || name || '%') -->
    <select id="searchByName" resultType="User">
        SELECT * FROM users 
        WHERE name LIKE '%' || #{name} || '%'
    </select>
    
    <!-- Risk: function wrap (UPPER) -->
    <select id="findByUpperEmail" resultType="User">
        SELECT * FROM users 
        WHERE UPPER(email) = UPPER(#{email})
    </select>
    
    <!-- Safe: suffix wildcard only -->
    <select id="findByNamePrefix" resultType="User">
        SELECT * FROM users 
        WHERE name LIKE #{name} || '%'
    </select>
    
    <!-- Complex: dynamic where with if -->
    <select id="findByConditions" resultType="User">
        SELECT * FROM users
        <where>
            <if test="name != null">
                AND name = #{name}
            </if>
            <if test="email != null">
                AND email = #{email}
            </if>
            <if test="status != null">
                AND status = #{status}
            </if>
        </where>
    </select>
    
    <!-- Complex: choose/when/otherwise -->
    <select id="findByStatus" resultType="User">
        SELECT * FROM users
        <choose>
            <when test="status == 'active'">
                WHERE active = true
            </when>
            <when test="status == 'inactive'">
                WHERE active = false
            </when>
            <otherwise>
                WHERE 1=1
            </otherwise>
        </choose>
    </select>
    
</mapper>
""",
        encoding="utf-8",
    )

    # OrderMapper.xml - with foreach and complex queries
    order_mapper = mapper_dir / "OrderMapper.xml"
    order_mapper.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" 
    "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.OrderMapper">
    
    <!-- Risk: select star -->
    <select id="findAll" resultType="Order">
        SELECT * FROM orders
    </select>
    
    <!-- Risk: concat wildcard (PostgreSQL uses || not CONCAT) -->
    <select id="searchByProduct" resultType="Order">
        SELECT * FROM orders 
        WHERE product_name LIKE '%' || #{product} || '%'
    </select>
    
    <!-- Complex: foreach for IN clause -->
    <select id="findByIds" resultType="Order">
        SELECT * FROM orders
        WHERE id IN
        <foreach item="id" collection="ids" open="(" separator="," close=")">
            #{id}
        </foreach>
    </select>
    
    <!-- Complex: dynamic set with if -->
    <update id="updateIfNecessary" resultType="int">
        UPDATE orders
        <set>
            <if test="status != null">
                status = #{status},
            </if>
            <if test="productName != null">
                product_name = #{productName},
            </if>
        </set>
        WHERE id = #{id}
    </update>
    
    <!-- Complex: nested if conditions -->
    <select id="findComplexSearch" resultType="Order">
        SELECT * FROM orders
        <where>
            <if test="product != null and product != ''">
                AND product_name LIKE '%' || #{product} || '%'
            </if>
            <if test="status != null">
                AND status = #{status}
            </if>
            <if test="minAmount != null">
                AND amount &gt;= #{minAmount}
            </if>
            <if test="maxAmount != null">
                AND amount &lt;= #{maxAmount}
            </if>
        </where>
    </select>
    
</mapper>
""",
        encoding="utf-8",
    )


def test_v8_full_flow_pg_complex():
    """Test complete V8 workflow using real PostgreSQL DB with complex dynamic SQL"""
    code_root = _repo_root()

    python_path = str(code_root / "python")
    if python_path not in sys.path:
        sys.path.insert(0, python_path)

    from sqlopt.application import run_service
    from sqlopt.io_utils import read_json

    with tempfile.TemporaryDirectory(prefix="sqlopt_v8_pg_complex_") as td:
        project_dir = Path(td) / "project"
        project_dir.mkdir(parents=True)

        _create_complex_mappers(project_dir)

        config_path = project_dir / "sqlopt.yml"
        _write_config(config_path, project_dir)

        run_id = f"run_v8_pg_complex_{uuid4().hex[:8]}"
        print(f"\n=== Starting V8 PostgreSQL Complex Dynamic SQL Test ===")
        print(f"Run ID: {run_id}")
        print(f"PostgreSQL: 100.101.41.123:5432/postgres")
        print(f"LLM: opencode_run")
        print(f"SQL Types: if/choose/foreach/where/set")

        actual_run_id, first_result = run_service.start_run(
            config_path,
            to_stage="patch",
            run_id=run_id,
            repo_root=project_dir,
        )

        print(f"\n=== Run Started: {actual_run_id} ===")

        max_resume = 100
        resume_count = 0
        print(f"\n=== Resuming Run ===")
        while not first_result.get("complete") and resume_count < max_resume:
            result = run_service.resume_run(actual_run_id, repo_root=project_dir)

            current = result.get("state", {}).get("current_stage")
            completed = result.get("state", {}).get("completed_stages", [])
            result_data = result.get("result") or {}
            success = result_data.get("success")
            errors = result_data.get("errors", [])

            if current:
                print(
                    f"  Step {resume_count}: stage={current}, success={success}, completed={len(completed)}"
                )
            if errors:
                print(f"    errors: {errors[:2]}")

            if result.get("complete"):
                first_result = result
                print(f"  Step {resume_count + 1}: COMPLETE")
                break

            first_result = result
            resume_count += 1

        if not first_result.get("complete"):
            print(f"  Stopped after {resume_count} resumes, not complete")
        print(f"  Total resumes: {resume_count}")

        # Verify results
        run_dir = project_dir / "runs" / actual_run_id
        assert run_dir.exists(), f"run directory not found: {run_dir}"

        status_payload = run_service.get_status(actual_run_id, repo_root=project_dir)
        completed_stages = status_payload.get("completed_stages", [])
        current_stage = status_payload.get("current_stage", "")
        stage_results = status_payload.get("stage_results", {})

        print(f"\n=== V8 Stage Status ===")
        print(f"  current_stage: {current_stage}")
        print(f"  completed_stages: {completed_stages}")

        # Verify all 5 V9 stages completed
        v9_stages = [
            "init",
            "parse",
            "recognition",
            "optimize",
            "patch",
        ]
        for stage in v9_stages:
            assert stage in completed_stages, f"Stage {stage} not completed"

        # Verify artifacts
        print(f"\n=== V9 Artifacts ===")
        artifact_checks = {}
        for stage in v9_stages:
            if stage == "init":
                artifact_path = run_dir / stage / "sql_units.json"
            elif stage == "parse":
                artifact_path = run_dir / stage / "sql_units_with_branches.json"
            elif stage == "recognition":
                artifact_path = run_dir / stage / "baselines.json"
            elif stage == "optimize":
                artifact_path = run_dir / stage / "proposals.json"
            else:  # patch
                artifact_path = run_dir / stage / "patches.json"

            exists = artifact_path.exists()
            artifact_checks[stage] = exists
            print(f"  {stage}: {'✓' if exists else '✗'} ({artifact_path.name})")

            if exists:
                with open(artifact_path) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        print(f"    items: {len(data)}")
                    elif isinstance(data, dict):
                        print(f"    keys: {list(data.keys())[:5]}")

        # Show parse details
        parse_path = run_dir / "parse" / "sql_units_with_branches.json"
        if parse_path.exists():
            with open(parse_path) as f:
                parse_data = json.load(f)
            print(f"\n=== Parse Details ===")
            total_branches = 0
            for unit in parse_data:
                sql_key = unit.get("sqlKey", "unknown")
                branch_count = unit.get("branchCount", 0)
                total_branches += branch_count
                branches = unit.get("branches", [])
                print(f"  {sql_key}: {branch_count} branches")
                for b in branches[:3]:  # Show first 3 branches
                    sql = (
                        b.get("sql", "")[:60] + "..."
                        if len(b.get("sql", "")) > 60
                        else b.get("sql", "")
                    )
                    print(f"    - {sql}")
            print(f"  Total branches: {total_branches}")

        # Show risks
        risks_path = run_dir / "parse" / "risks.json"
        if risks_path.exists():
            with open(risks_path) as f:
                risks = json.load(f)
            print(f"\n=== Risks Detected: {len(risks)} ===")
            for r in risks[:5]:  # Show first 5
                print(
                    f"  - {r.get('sqlKey')}: {r.get('riskType')} ({r.get('severity')})"
                )

        print(f"\n=== Artifact Summary ===")
        passed = sum(1 for v in artifact_checks.values() if v)
        print(f"  {passed}/{len(artifact_checks)} checks passed")

        # Save evidence
        evidence_dir = code_root / ".sisyphus" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_file = evidence_dir / f"v8-pg-complex-{actual_run_id}.json"
        evidence_file.write_text(
            json.dumps(
                {
                    "ok": True,
                    "run_id": actual_run_id,
                    "run_dir": str(run_dir),
                    "db": "postgresql",
                    "completed_stages": completed_stages,
                    "current_stage": current_stage,
                    "complete": status_payload.get("status") == "completed",
                    "artifact_checks": artifact_checks,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(f"\n=== Final Result ===")
        print(f"  run_id: {actual_run_id}")
        print(f"  complete: {status_payload.get('status') == 'completed'}")
        print(f"  evidence: {evidence_file}")

        assert status_payload.get("status") == "completed", f"Run not completed"
        assert all(artifact_checks.values()), f"Not all artifacts created"


if __name__ == "__main__":
    test_v8_full_flow_pg_complex()
