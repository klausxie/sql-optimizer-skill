# V9 阶段开发指南

> 版本：V9 | 更新日期：2026-03-20

---

## 一、指南概述

本文档提供 V9 五个阶段的独立开发示例，包括可运行的 Python 代码、测试数据路径、预期输出格式和验证方法。

### 前提条件

- Python 3.10+
- 项目依赖已安装: `pip install -e .`
- 契约 Schema 已验证

### 阶段列表

| 阶段 | 主要功能 | 输入 | 输出 |
|------|---------|------|------|
| Init | XML 解析、SQL 提取 | MyBatis XML | `init/sql_units.json` |
| Parse | 分支展开、风险检测 | `init/sql_units.json` | `parse/sql_units_with_branches.json` + `risks.json` |
| Recognition | EXPLAIN 采集 | `parse/sql_units_with_branches.json` | `recognition/baselines.json` |
| Optimize | 规则 + LLM + 验证 | `recognition/baselines.json` | `optimize/proposals.json` |
| Patch | 补丁生成 | `optimize/proposals.json` | `patch/patches.json` |

---

## 二、Init 阶段

### 2.1 阶段职责

解析 MyBatis XML 映射文件，提取 SQL 语句单元。

### 2.2 独立开发示例

```python
"""Init 阶段独立开发示例"""

from pathlib import Path
from datetime import datetime, timezone

# 导入核心模块
from sqlopt.stages.discovery.execute_one import execute_one as discovery_execute_one
from sqlopt.contracts import ContractValidator
from sqlopt.run_paths import canonical_paths
from sqlopt.io_utils import ensure_dir

def run_init_stage(
    mapper_path: str | Path,
    run_dir: str | Path,
) -> dict:
    """
    独立运行 Init 阶段
    
    Args:
        mapper_path: MyBatis Mapper XML 文件路径
        run_dir: 运行目录
    
    Returns:
        包含执行结果的字典
    """
    mapper_path = Path(mapper_path)
    run_dir = Path(run_dir)
    
    # 确保目录结构存在
    ensure_dir(run_dir)
    paths = canonical_paths(run_dir)
    paths.ensure_layout()
    
    # 创建验证器
    validator = ContractValidator(Path(__file__).parent.parent.parent / "contracts")
    
    # 生成运行 ID
    run_id = f"dev_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    # 执行 Init 阶段
    result = discovery_execute_one(
        run_id=run_id,
        mapper_path=mapper_path,
        run_dir=run_dir,
        validator=validator,
        config={},
    )
    
    return result

# 示例用法
if __name__ == "__main__":
    # 测试 Mapper 文件
    test_mapper = Path("tests/fixtures/project/mapper/UserMapper.xml")
    
    # 创建临时运行目录
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = run_init_stage(test_mapper, tmp_dir)
        print(f"解析到 {result['totalCount']} 个 SQL 单元")
        print(f"命名空间: {result['namespace']}")
```

### 2.3 测试数据

```xml
<!-- 测试用 MyBatis Mapper: tests/fixtures/project/mapper/UserMapper.xml -->

<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" 
    "http://mybatis.org/dtd/mybatis-3-mapper.dtd">

<mapper namespace="com.example.UserMapper">
    
    <select id="selectById" resultType="User">
        SELECT id, name, email, status
        FROM users
        WHERE id = #{id}
    </select>
    
    <select id="selectByExample" resultType="User">
        SELECT *
        FROM users
        <where>
            <if test="name != null">
                AND name = #{name}
            </if>
            <if test="status != null">
                AND status = #{status}
            </if>
        </where>
    </select>
    
    <select id="searchLike" resultType="User">
        SELECT *
        FROM users
        WHERE name LIKE '%' || #{name} || '%'
    </select>
    
</mapper>
```

### 2.4 预期输出格式

```json
{
  "mapperPath": "/path/to/UserMapper.xml",
  "namespace": "com.example.UserMapper",
  "sqlUnits": [
    {
      "sqlKey": "com.example.UserMapper.selectById",
      "xmlPath": "/path/to/UserMapper.xml",
      "namespace": "com.example.UserMapper",
      "statementId": "selectById",
      "statementType": "SELECT",
      "sql": "SELECT id, name, email, status FROM users WHERE id = #{id}",
      "parameterMappings": [
        {"name": "id", "jdbcType": "BIGINT"}
      ],
      "riskFlags": []
    }
  ],
  "totalCount": 3,
  "executionTimeMs": 12.5
}
```

### 2.5 输出文件

- 路径: `init/sql_units.json`
- 格式: JSONL (每行一个 SQL 单元)

### 2.6 验证方法

```python
import json

def validate_init_output(run_dir: Path) -> bool:
    """验证 Init 阶段输出"""
    paths = canonical_paths(run_dir)
    
    # 检查输出文件存在
    assert paths.init_sql_units_path.exists(), "sql_units.json 不存在"
    
    # 读取并验证每个 SQL 单元
    with open(paths.init_sql_units_path) as f:
        for line in f:
            unit = json.loads(line)
            # 验证必填字段
            assert "sqlKey" in unit
            assert "statementType" in unit
            assert "sql" in unit
    
    print(f"✅ Init 输出验证通过: {paths.init_sql_units_path}")
    return True
```

---

## 三、Parse 阶段

### 3.1 阶段职责

展开动态 SQL 生成分支路径，同时进行风险检测。

### 3.2 独立开发示例

```python
"""Parse 阶段独立开发示例"""

from pathlib import Path
from datetime import datetime, timezone

from sqlopt.stages.branching.execute_one import execute_one as branching_execute_one
from sqlopt.stages.pruning.execute_one import execute_one as pruning_execute_one
from sqlopt.contracts import ContractValidator
from sqlopt.run_paths import canonical_paths
from sqlopt.io_utils import ensure_dir, write_json

def run_parse_stage(
    run_dir: str | Path,
) -> dict:
    """
    独立运行 Parse 阶段 (分支 + 风险)
    
    Args:
        run_dir: 运行目录
    
    Returns:
        包含分支和风险的字典
    """
    run_dir = Path(run_dir)
    paths = canonical_paths(run_dir)
    paths.ensure_layout()
    
    # 创建验证器
    validator = ContractValidator(Path(__file__).parent.parent.parent / "contracts")
    
    # 读取 Init 阶段输出
    with open(paths.init_sql_units_path) as f:
        sql_units = [json.loads(line) for line in f if line.strip()]
    
    branched_units = []
    all_risks = []
    
    # 3.1 分支展开
    for unit in sql_units:
        branched = branching_execute_one(
            sql_unit=unit,
            run_dir=run_dir,
            validator=validator,
            config={"branching": {"strategy": "all_combinations", "max_branches": 100}},
        )
        branched_units.append(branched)
        
        # 3.2 风险检测
        risks = pruning_execute_one(
            sql_unit=branched,
            run_dir=run_dir,
            validator=validator,
            config={},
        )
        if risks.get("risks"):
            all_risks.append(risks)
    
    # 写入分支结果
    with open(paths.parse_sql_units_with_branches_path, "w") as f:
        for unit in branched_units:
            f.write(json.dumps(unit) + "\n")
    
    # 写入风险结果
    write_json(paths.parse_risks_path, all_risks)
    
    return {
        "branched_units": branched_units,
        "risks": all_risks,
        "total_branches": sum(u.get("branchCount", 0) for u in branched_units),
    }

# 示例用法
if __name__ == "__main__":
    import tempfile
    import shutil
    
    # 准备测试数据
    test_dir = Path(tempfile.mkdtemp())
    try:
        # 复制测试 Mapper
        shutil.copytree(
            Path("tests/fixtures/project"),
            test_dir / "project"
        )
        
        # 运行 Init
        init_result = run_init_stage(
            test_dir / "project/mapper/UserMapper.xml",
            test_dir
        )
        
        # 运行 Parse
        parse_result = run_parse_stage(test_dir)
        print(f"生成了 {parse_result['total_branches']} 个分支")
        print(f"检测到 {len(parse_result['risks'])} 个风险")
    finally:
        shutil.rmtree(test_dir)
```

### 3.3 分支展开示例

对于以下动态 SQL：

```xml
<select id="search" resultType="User">
    SELECT * FROM users
    <where>
        <if test="name != null">AND name = #{name}</if>
        <if test="status != null">AND status = #{status}</if>
    </where>
</select>
```

Parse 阶段会展开为：

| branch_id | 条件 | SQL |
|-----------|------|-----|
| 0 | (无) | `SELECT * FROM users` |
| 1 | name IS NOT NULL | `SELECT * FROM users WHERE name = #{name}` |
| 2 | status IS NOT NULL | `SELECT * FROM users WHERE status = #{status}` |
| 3 | name AND status | `SELECT * FROM users WHERE name = #{name} AND status = #{status}` |

### 3.4 风险检测示例

```python
# 风险类型定义
RISK_TYPES = {
    "PREFIX_WILDCARD": {
        "severity": "HIGH",
        "pattern": r"LIKE\s+['\"]%",
        "description": "前缀通配符导致全表扫描"
    },
    "FUNCTION_WRAP": {
        "severity": "MEDIUM",
        "pattern": r"(UPPER|LOWER|TRIM)\s*\(",
        "description": "函数包裹可能导致索引失效"
    },
    "CONCAT_WILDCARD": {
        "severity": "HIGH",
        "pattern": r"CONCAT\s*\(\s*['\"]%",
        "description": "CONCAT 通配符导致全表扫描"
    },
}
```

### 3.5 预期输出格式

**parse/sql_units_with_branches.json:**

```json
{
  "sqlKey": "com.example.UserMapper.search",
  "branches": [
    {
      "id": 0,
      "conditions": [],
      "sql": "SELECT * FROM users",
      "type": "static"
    },
    {
      "id": 1,
      "conditions": ["name IS NOT NULL"],
      "sql": "SELECT * FROM users WHERE name = #{name}",
      "type": "conditional"
    }
  ],
  "branchCount": 2
}
```

**parse/risks.json:**

```json
[
  {
    "sqlKey": "com.example.UserMapper.searchLike",
    "risk_type": "PREFIX_WILDCARD",
    "severity": "HIGH",
    "location": {"line": 3, "column": 15},
    "suggestion": "Remove leading wildcard"
  }
]
```

### 3.6 验证方法

```python
def validate_parse_output(run_dir: Path) -> bool:
    """验证 Parse 阶段输出"""
    paths = canonical_paths(run_dir)
    
    # 检查分支文件存在
    assert paths.parse_sql_units_with_branches_path.exists()
    
    # 检查风险文件存在
    assert paths.parse_risks_path.exists()
    
    # 验证分支结构
    with open(paths.parse_sql_units_with_branches_path) as f:
        for line in f:
            unit = json.loads(line)
            assert "branches" in unit
            assert "branchCount" in unit
            assert len(unit["branches"]) == unit["branchCount"]
    
    # 验证风险结构
    risks = json.loads(paths.parse_risks_path.read_text())
    for risk in risks:
        assert "sqlKey" in risk
        assert "risk_type" in risk
        assert "severity" in risk
    
    print("✅ Parse 输出验证通过")
    return True
```

---

## 四、Recognition 阶段

### 4.1 阶段职责

采集当前 SQL 的执行计划作为性能基准。

### 4.2 独立开发示例

```python
"""Recognition 阶段独立开发示例"""

from pathlib import Path
from datetime import datetime, timezone

from sqlopt.stages.baseline.execute_one import execute_one as baseline_execute_one
from sqlopt.contracts import ContractValidator
from sqlopt.run_paths import canonical_paths
from sqlopt.platforms.db_connector import create_db_engine

def run_recognition_stage(
    run_dir: str | Path,
    dsn: str,
) -> dict:
    """
    独立运行 Recognition 阶段
    
    Args:
        run_dir: 运行目录
        dsn: 数据库连接字符串
    
    Returns:
        基线结果字典
    """
    run_dir = Path(run_dir)
    paths = canonical_paths(run_dir)
    paths.ensure_layout()
    
    validator = ContractValidator(Path(__file__).parent.parent.parent / "contracts")
    
    # 创建数据库引擎
    engine = create_db_engine(dsn)
    
    # 读取分支 SQL
    with open(paths.parse_sql_units_with_branches_path) as f:
        units = [json.loads(line) for line in f if line.strip()]
    
    baselines = []
    
    # 为每个分支执行 EXPLAIN
    for unit in units:
        for branch in unit.get("branches", []):
            sql = branch["sql"]
            sql_key = f"{unit['sqlKey']}:branch:{branch['id']}"
            
            baseline = baseline_execute_one(
                sql_unit=unit,
                branch=branch,
                run_dir=run_dir,
                engine=engine,
                validator=validator,
                config={},
            )
            baselines.append(baseline)
    
    # 写入基线结果
    import json
    with open(paths.recognition_results_path, "w") as f:
        for baseline in baselines:
            f.write(json.dumps(baseline) + "\n")
    
    return {
        "baselines": baselines,
        "count": len(baselines),
    }

# 示例用法
if __name__ == "__main__":
    dsn = "postgresql://user:pass@localhost:5432/testdb"
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 假设 Parse 阶段已完成
        result = run_recognition_stage(tmp_dir, dsn)
        print(f"采集了 {result['count']} 个基线")
```

### 4.3 预期输出格式

```json
{
  "sql_key": "com.example.UserMapper.selectByExample:branch:1",
  "execution_time_ms": 12.5,
  "rows_scanned": 1520,
  "execution_plan": {
    "node_type": "Seq Scan",
    "index_used": null,
    "cost": 43.21
  },
  "result_hash": "a1b2c3d4e5f6",
  "rows_returned": 20,
  "database_platform": "postgresql",
  "sample_params": {"status": 1},
  "actual_execution_time_ms": 12.9,
  "buffer_hit_count": 110,
  "buffer_read_count": 7,
  "trace": {
    "stage": "recognition",
    "sql_key": "com.example.UserMapper.selectByExample:branch:1",
    "executor": "baseline_collector",
    "timestamp": "2026-03-20T10:30:00Z"
  }
}
```

### 4.4 EXPLAIN 平台差异

**PostgreSQL:**

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT * FROM users WHERE status = 1;
```

**MySQL:**

```sql
EXPLAIN SELECT * FROM users WHERE status = 1;
-- 或带成本分析
EXPLAIN FORMAT=JSON SELECT * FROM users WHERE status = 1;
```

### 4.5 验证方法

```python
def validate_recognition_output(run_dir: Path) -> bool:
    """验证 Recognition 阶段输出"""
    paths = canonical_paths(run_dir)
    
    assert paths.recognition_results_path.exists()
    
    with open(paths.recognition_results_path) as f:
        for line in f:
            baseline = json.loads(line)
            # 验证必填字段
            assert "sql_key" in baseline
            assert "execution_plan" in baseline
            assert "result_hash" in baseline
            # 验证执行计划结构
            plan = baseline["execution_plan"]
            assert "node_type" in plan
    
    print("✅ Recognition 输出验证通过")
    return True
```

---

## 五、Optimize 阶段

### 5.1 阶段职责

生成优化建议并进行语义验证，支持迭代重试。

### 5.2 独立开发示例

```python
"""Optimize 阶段独立开发示例"""

from pathlib import Path
from datetime import datetime, timezone

from sqlopt.stages.optimize.execute_one import execute_one as optimize_execute_one
from sqlopt.stages.optimize.rule_engine import RuleEngine
from sqlopt.stages.optimize.llm_optimizer import LLMOptimizer
from sqlopt.contracts import ContractValidator
from sqlopt.run_paths import canonical_paths
from sqlopt.io_utils import write_jsonl

def run_optimize_stage(
    run_dir: str | Path,
    config: dict | None = None,
) -> dict:
    """
    独立运行 Optimize 阶段
    
    Args:
        run_dir: 运行目录
        config: 配置字典
    
    Returns:
        优化提案字典
    """
    run_dir = Path(run_dir)
    config = config or {}
    paths = canonical_paths(run_dir)
    paths.ensure_layout()
    
    validator = ContractValidator(Path(__file__).parent.parent.parent / "contracts")
    
    # 读取基线结果
    with open(paths.recognition_results_path) as f:
        baselines = [json.loads(line) for line in f if line.strip()]
    
    proposals = []
    
    for baseline in baselines:
        proposal = optimize_execute_one(
            baseline_result=baseline,
            run_dir=run_dir,
            validator=validator,
            config=config,
        )
        proposals.append(proposal)
    
    # 写入提案结果
    write_jsonl(paths.proposals_path, proposals)
    
    return {
        "proposals": proposals,
        "count": len(proposals),
        "actionable": sum(1 for p in proposals if p.get("verdict") == "ACTIONABLE"),
    }

# 示例用法
if __name__ == "__main__":
    config = {
        "optimize": {
            "max_iterations": 3,
            "rules": ["select_minimize", "index_hint", "or_to_union"],
        },
        "llm": {
            "enabled": True,
            "provider": "opencode_run",
        },
    }
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = run_optimize_stage(tmp_dir, config)
        print(f"生成了 {result['count']} 个提案")
        print(f"其中 {result['actionable']} 个可操作")
```

### 5.3 优化规则示例

```python
# 规则引擎示例
RULES = {
    "select_minimize": {
        "name": "SELECT 列最小化",
        "check": lambda sql: "SELECT *" in sql.upper(),
        "rewrite": lambda sql: sql.replace("SELECT *", "SELECT id, name, status"),
    },
    "index_hint": {
        "name": "索引提示",
        "check": lambda sql: "WHERE" in sql.upper() and "INDEX" not in sql.upper(),
        "rewrite": lambda sql: sql + " USE INDEX (idx_primary)",
    },
    "or_to_union": {
        "name": "OR 改写为 UNION",
        "check": lambda sql: " OR " in sql.upper(),
        "rewrite": lambda sql: sql.replace(" OR ", " UNION "),
    },
    "limit_pushdown": {
        "name": "LIMIT 下推",
        "check": lambda sql: "LIMIT" not in sql.upper() and "SELECT" in sql.upper(),
        "rewrite": lambda sql: sql + " LIMIT 1000",
    },
}
```

### 5.4 迭代验证流程

```python
def optimize_with_iteration(
    baseline: dict,
    config: dict,
) -> dict:
    """
    带迭代验证的优化流程
    """
    max_iterations = config.get("optimize", {}).get("max_iterations", 3)
    candidates = []
    
    for iteration in range(max_iterations):
        # 1. 应用规则生成候选
        candidate = apply_rules(baseline, iteration)
        
        # 2. 语义验证
        validated = semantic_check(candidate)
        
        if validated:
            candidate["validated"] = True
            candidate["iterations"] = iteration + 1
            return candidate
        
        # 3. 验证失败，保存候选继续迭代
        candidates.append(candidate)
    
    # 4. 达到最大迭代，选择最佳候选
    return select_best_candidate(candidates)
```

### 5.5 预期输出格式

```json
{
  "sqlKey": "com.example.UserMapper.search:branch:0",
  "issues": ["FULL_SCAN", "PREFIX_WILDCARD"],
  "dbEvidenceSummary": {
    "rowsScanned": 1520,
    "nodeType": "Seq Scan",
    "indexUsed": null
  },
  "planSummary": {
    "before": "Seq Scan on users",
    "cost": 43.21
  },
  "suggestions": [
    {
      "id": "rule-1",
      "source": "rule",
      "title": "Remove leading wildcard",
      "originalSql": "SELECT * FROM users WHERE name LIKE '%' || #{name} || '%'",
      "rewrittenSql": "SELECT * FROM users WHERE name LIKE #{name} || '%'",
      "benefit": "Enable index usage",
      "risk": "LOW"
    }
  ],
  "verdict": "ACTIONABLE",
  "confidence": "HIGH",
  "estimatedBenefit": "HIGH",
  "validated": true,
  "iterations": 2
}
```

### 5.6 验证方法

```python
def validate_optimize_output(run_dir: Path) -> bool:
    """验证 Optimize 阶段输出"""
    paths = canonical_paths(run_dir)
    
    assert paths.proposals_path.exists()
    
    with open(paths.proposals_path) as f:
        for line in f:
            proposal = json.loads(line)
            # 验证必填字段
            assert "sqlKey" in proposal
            assert "suggestions" in proposal
            assert "verdict" in proposal
            # 验证 verdict 值
            assert proposal["verdict"] in ["ACTIONABLE", "NO_ACTION", "BLOCKED"]
    
    print("✅ Optimize 输出验证通过")
    return True
```

---

## 六、Patch 阶段

### 6.1 阶段职责

生成可应用的 XML 补丁。

### 6.2 独立开发示例

```python
"""Patch 阶段独立开发示例"""

from pathlib import Path
from datetime import datetime, timezone

from sqlopt.stages.patch.execute_one import execute_one as patch_execute_one
from sqlopt.stages.patch.patch_generator import PatchGenerator
from sqlopt.contracts import ContractValidator
from sqlopt.run_paths import canonical_paths
from sqlopt.io_utils import write_jsonl

def run_patch_stage(
    run_dir: str | Path,
    config: dict | None = None,
) -> dict:
    """
    独立运行 Patch 阶段
    
    Args:
        run_dir: 运行目录
        config: 配置字典
    
    Returns:
        补丁结果字典
    """
    run_dir = Path(run_dir)
    config = config or {}
    paths = canonical_paths(run_dir)
    paths.ensure_layout()
    
    validator = ContractValidator(Path(__file__).parent.parent.parent / "contracts")
    
    # 读取优化提案
    with open(paths.proposals_path) as f:
        proposals = [json.loads(line) for line in f if line.strip()]
    
    # 读取 SQL 单元
    with open(paths.parse_sql_units_with_branches_path) as f:
        sql_units = {json.loads(line)["sqlKey"]: json.loads(line) for line in f if line.strip()}
    
    patches = []
    
    for proposal in proposals:
        if proposal.get("verdict") != "ACTIONABLE":
            continue
        
        sql_key = proposal["sqlKey"]
        sql_unit = sql_units.get(sql_key)
        
        if not sql_unit:
            continue
        
        patch = patch_execute_one(
            sql_unit=sql_unit,
            acceptance=proposal,  # 在 V9 中直接用 proposal 作为 acceptance
            run_dir=run_dir,
            validator=validator,
            config=config,
        )
        patches.append(patch)
    
    # 写入补丁结果
    write_jsonl(paths.patches_path, patches)
    
    return {
        "patches": patches,
        "count": len(patches),
        "applicable": sum(1 for p in patches if p.get("applicable")),
    }

# 示例用法
if __name__ == "__main__":
    config = {
        "patch": {
            "apply_mode": "manual",
        }
    }
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = run_patch_stage(tmp_dir, config)
        print(f"生成了 {result['count']} 个补丁")
        print(f"其中 {result['applicable']} 个可应用")
```

### 6.3 补丁生成示例

```python
from sqlopt.stages.patch.patch_generator import PatchGenerator

generator = PatchGenerator()

# 生成补丁
patch = generator.generate(
    original_xml="""
        <select id="search" resultType="User">
            SELECT * FROM users WHERE name LIKE '%' || #{name} || '%'
        </select>
    """,
    optimized_sql="SELECT * FROM users WHERE name LIKE #{name} || '%'",
    statement_id="search",
)

print(patch)
# 输出:
# {
#   "before": "<select id=\"search\">...</select>",
#   "after": "<select id=\"search\">...</select>",
#   "diff": "@@ -1,5 +1,5 @@"
# }
```

### 6.4 预期输出格式

```json
{
  "sqlKey": "com.example.UserMapper.search:branch:0",
  "statementKey": "com.example.UserMapper.search",
  "patchFiles": [
    "runs/run_xxx/patch/com.example.UserMapper.search.patch"
  ],
  "diffSummary": {
    "filesChanged": 1,
    "hunks": 2,
    "summary": "Replace LIKE '%x%' with range predicate"
  },
  "applyMode": "manual",
  "rollback": "restore original mapper backup",
  "selectedCandidateId": "rule-1",
  "candidatesEvaluated": 1,
  "applicable": true,
  "applyCheckError": null,
  "gates": {
    "semanticEquivalenceStatus": "PASS",
    "semanticEquivalenceBlocking": false,
    "semanticConfidence": "HIGH"
  }
}
```

### 6.5 验证方法

```python
def validate_patch_output(run_dir: Path) -> bool:
    """验证 Patch 阶段输出"""
    paths = canonical_paths(run_dir)
    
    assert paths.patches_path.exists()
    
    with open(paths.patches_path) as f:
        for line in f:
            patch = json.loads(line)
            # 验证必填字段
            assert "sqlKey" in patch
            assert "patchFiles" in patch
            assert "diffSummary" in patch
            assert "applyMode" in patch
            assert "rollback" in patch
            # 验证 applyMode 值
            assert patch["applyMode"] in ["manual", "auto"]
    
    print("✅ Patch 输出验证通过")
    return True
```

---

## 七、完整流水线示例

### 7.1 端到端运行示例

```python
"""V9 完整流水线示例"""

from pathlib import Path
import tempfile
import shutil

from sqlopt.run_paths import canonical_paths
from sqlopt.contracts import ContractValidator

def run_full_pipeline(
    mapper_paths: list[Path],
    run_dir: Path,
    dsn: str,
    config: dict | None = None,
) -> dict:
    """
    运行完整的 V9 流水线
    
    Args:
        mapper_paths: Mapper XML 文件路径列表
        run_dir: 运行目录
        dsn: 数据库连接字符串
        config: 配置字典
    
    Returns:
        流水线执行结果
    """
    config = config or {}
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    paths = canonical_paths(run_dir)
    paths.ensure_layout()
    validator = ContractValidator(Path(__file__).parent.parent / "contracts")
    
    results = {
        "init": {"count": 0},
        "parse": {"branches": 0, "risks": 0},
        "recognition": {"count": 0},
        "optimize": {"count": 0, "actionable": 0},
        "patch": {"count": 0, "applicable": 0},
    }
    
    # 1. Init
    print("🔄 运行 Init 阶段...")
    from sqlopt.stages.discovery.execute_one import execute_one as init_execute
    
    for mapper_path in mapper_paths:
        result = init_execute(
            run_id="pipeline",
            mapper_path=mapper_path,
            run_dir=run_dir,
            validator=validator,
            config=config,
        )
        results["init"]["count"] += result["totalCount"]
    
    # 2. Parse (分支 + 风险)
    print("🔄 运行 Parse 阶段...")
    from sqlopt.stages.branching.execute_one import execute_one as branch_execute
    from sqlopt.stages.pruning.execute_one import execute_one as risk_execute
    
    with open(paths.init_sql_units_path) as f:
        units = [json.loads(line) for line in f]
    
    branched_units = []
    all_risks = []
    
    for unit in units:
        branched = branch_execute(unit, run_dir, validator, config)
        branched_units.append(branched)
        
        risks = risk_execute(branched, run_dir, validator, config)
        if risks.get("risks"):
            all_risks.append(risks)
    
    results["parse"]["branches"] = sum(u.get("branchCount", 0) for u in branched_units)
    results["parse"]["risks"] = len(all_risks)
    
    # 3. Recognition
    print("🔄 运行 Recognition 阶段...")
    from sqlopt.stages.baseline.execute_one import execute_one as baseline_execute
    from sqlopt.platforms.db_connector import create_db_engine
    
    engine = create_db_engine(dsn)
    baselines = []
    
    for unit in branched_units:
        for branch in unit.get("branches", []):
            baseline = baseline_execute(
                sql_unit=unit,
                branch=branch,
                run_dir=run_dir,
                engine=engine,
                validator=validator,
                config=config,
            )
            baselines.append(baseline)
    
    results["recognition"]["count"] = len(baselines)
    
    # 4. Optimize
    print("🔄 运行 Optimize 阶段...")
    from sqlopt.stages.optimize.execute_one import execute_one as optimize_execute
    
    proposals = []
    for baseline in baselines:
        proposal = optimize_execute(
            baseline,
            run_dir,
            validator,
            config,
        )
        proposals.append(proposal)
    
    results["optimize"]["count"] = len(proposals)
    results["optimize"]["actionable"] = sum(
        1 for p in proposals if p.get("verdict") == "ACTIONABLE"
    )
    
    # 5. Patch
    print("🔄 运行 Patch 阶段...")
    from sqlopt.stages.patch.execute_one import execute_one as patch_execute
    
    patches = []
    sql_units_dict = {u["sqlKey"]: u for u in branched_units}
    
    for proposal in proposals:
        if proposal.get("verdict") != "ACTIONABLE":
            continue
        
        sql_unit = sql_units_dict.get(proposal["sqlKey"])
        if not sql_unit:
            continue
        
        patch = patch_execute(
            sql_unit=sql_unit,
            acceptance=proposal,
            run_dir=run_dir,
            validator=validator,
            config=config,
        )
        patches.append(patch)
    
    results["patch"]["count"] = len(patches)
    results["patch"]["applicable"] = sum(1 for p in patches if p.get("applicable"))
    
    print("✅ 流水线执行完成")
    return results

# 示例用法
if __name__ == "__main__":
    mapper_paths = [
        Path("tests/fixtures/project/mapper/UserMapper.xml"),
    ]
    dsn = "postgresql://user:pass@localhost:5432/testdb"
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        results = run_full_pipeline(mapper_paths, tmp_dir, dsn)
        
        print("\n📊 流水线统计:")
        print(f"  Init: {results['init']['count']} SQL 单元")
        print(f"  Parse: {results['parse']['branches']} 分支, {results['parse']['risks']} 风险")
        print(f"  Recognition: {results['recognition']['count']} 基线")
        print(f"  Optimize: {results['optimize']['count']} 提案, {results['optimize']['actionable']} 可操作")
        print(f"  Patch: {results['patch']['count']} 补丁, {results['patch']['applicable']} 可应用")
```

---

## 八、测试工具

### 8.1 Schema 验证工具

```python
"""Schema 验证工具"""

import json
from pathlib import Path
from jsonschema import validate, ValidationError

from sqlopt.contracts import ContractValidator

def validate_with_schema(
    data: dict,
    schema_name: str,
    schema_dir: Path | None = None,
) -> tuple[bool, str | None]:
    """
    使用 Schema 验证数据
    
    Args:
        data: 待验证的数据
        schema_name: Schema 名称 (不含 .schema.json 后缀)
        schema_dir: Schema 目录
    
    Returns:
        (是否通过, 错误信息)
    """
    if schema_dir is None:
        schema_dir = Path("contracts/schemas")
    
    schema_path = schema_dir / f"{schema_name}.schema.json"
    
    if not schema_path.exists():
        return False, f"Schema 文件不存在: {schema_path}"
    
    with open(schema_path) as f:
        schema = json.load(f)
    
    try:
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e.message)

# 使用示例
data = {"sqlKey": "test", "sql": "SELECT * FROM users"}
valid, error = validate_with_schema(data, "sqlunit")

if valid:
    print("✅ 数据验证通过")
else:
    print(f"❌ 验证失败: {error}")
```

### 8.2 运行状态检查

```python
"""运行状态检查工具"""

from pathlib import Path
import json

from sqlopt.run_paths import canonical_paths

def check_run_status(run_dir: Path) -> dict:
    """
    检查运行状态
    
    Returns:
        状态字典
    """
    run_dir = Path(run_dir)
    paths = canonical_paths(run_dir)
    
    status = {
        "run_dir": str(run_dir),
        "stages": {},
        "complete": False,
    }
    
    # 检查每个阶段
    stage_files = {
        "init": paths.init_sql_units_path,
        "parse_branches": paths.parse_sql_units_with_branches_path,
        "parse_risks": paths.parse_risks_path,
        "recognition": paths.recognition_results_path,
        "optimize": paths.proposals_path,
        "patch": paths.patches_path,
    }
    
    for stage_name, file_path in stage_files.items():
        status["stages"][stage_name] = {
            "exists": file_path.exists(),
            "path": str(file_path),
        }
        
        if file_path.exists():
            if file_path.suffix == ".json":
                try:
                    content = json.loads(file_path.read_text())
                    if isinstance(content, list):
                        status["stages"][stage_name]["count"] = len(content)
                    else:
                        status["stages"][stage_name]["keys"] = list(content.keys())[:5]
                except:
                    pass
    
    # 检查是否完成
    status["complete"] = all(
        s["exists"] for s in status["stages"].values()
    )
    
    return status

# 使用示例
if __name__ == "__main__":
    status = check_run_status(Path("runs/run_20260320_001"))
    print(json.dumps(status, indent=2))
```

---

## 九、调试技巧

### 9.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| `sql_units.json` 为空 | Mapper 文件无 SQL 语句 | 检查 XML 文件格式 |
| 分支展开失败 | 动态标签语法错误 | 检查 `<if>`, `<where>` 标签 |
| EXPLAIN 超时 | SQL 太复杂或数据量大 | 增加 timeout 或采样 |
| 优化提案为空 | 基线数据缺失 | 确保 Recognition 阶段完成 |

### 9.2 日志调试

```python
import logging

# 启用调试日志
logging.basicConfig(level=logging.DEBUG)

# 在关键位置添加日志
logger = logging.getLogger(__name__)

def execute_one(...):
    logger.debug(f"Processing SQL: {sql_key}")
    try:
        result = do_work()
        logger.debug(f"Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing {sql_key}: {e}")
        raise
```

### 9.3 断点调试

```python
# 在 Python 代码中设置断点
import pdb

def execute_one(...):
    # 在返回前设置断点
    pdb.set_trace() if os.environ.get("DEBUG") else None
    
    result = do_work()
    return result

# 运行时启用调试
# DEBUG=1 python your_script.py
```

---

## 十、后续步骤

### 10.1 相关文档

- [V9_ARCHITECTURE_OVERVIEW.md](./V9_ARCHITECTURE_OVERVIEW.md) - 架构总览
- [V9_STAGE_API_CONTRACTS.md](./V9_STAGE_API_CONTRACTS.md) - 阶段 API 契约
- [V9_DATA_CONTRACTS.md](./V9_DATA_CONTRACTS.md) - 数据契约定义

### 10.2 测试验证

```bash
# 运行单元测试
python3 -m pytest tests/test_discovery_module.py -v
python3 -m pytest tests/test_branching_module.py -v
python3 -m pytest tests/test_baseline_module.py -v
python3 -m pytest tests/test_optimize_proposal.py -v

# 运行集成测试
python3 -m pytest tests/test_workflow_v9_integration.py -v

# Schema 验证
python3 scripts/schema_validate_all.py
```

---

*本文档最后更新：2026-03-20*
