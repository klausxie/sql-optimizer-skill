# SQL Optimizer V8 架构完善计划

> 文档版本：V1.0 | 创建日期：2026-03-19
> 基于深度调研结果生成，指导后续开发方向

> **文档性质**：工作计划书 - 记录待执行任务，不包含已完成的实现代码

---

## 执行状态总览

| 类别 | 状态 | 待完成 |
|------|------|--------|
| **T-001** 修复测试 | 📋 待执行 | 4 个测试的 import 修复 |
| **T-002** 完善 Pruning | 📋 待执行 | 添加 execute_one.py |
| **T-003** 实现 Report | 📋 待执行 | 创建 stages/report/ |
| **T-004** 更新文档 | 📋 待执行 | V8_SUMMARY.md 同步 |
| **T-005** Discovery execute_one | 📋 待执行 | 添加 execute_one.py |
| **T-006** Baseline execute_one | 📋 待执行 | 添加 execute_one.py |
| **T-007** 独立 CLI 命令 | 📋 待执行 | diagnose/optimize/validate |
| **T-008** 架构一致性 | 📋 待执行 | workflow_v8.py 冲突解决 |

---

## 一、调研总结

### 1.1 核心发现

经过 6 个并行探索代理的深度调研，发现以下关键问题：

| 类别 | 状态 | 说明 |
|------|------|------|
| **V8 Stages** | ⚠️ 部分完成 | 7 个阶段中 3 个严重不完整 |
| **Data Contracts** | ✅ 完成 | 15 个 Schema 完整，有验证器 |
| **Workflow Engines** | ⚠️ 清理中 | 旧引擎已删除，V8 正常 |
| **CLI Commands** | ⚠️ 部分实现 | 核心命令正常，独立阶段命令缺失 |
| **Report Modules** | ❌ 严重缺失 | 无 report.py，无 V8 集成 |
| **Tests** | ⚠️ 4 个损坏 | 模块引用问题 |

### 1.2 阶段实现状态详情

| 阶段 | 目录 | 代码行数 | execute_one | 状态 | 关键问题 |
|------|------|----------|------------|------|----------|
| Discovery | `stages/discovery/` | ~900 | ❌ 无 | ⚠️ 简化 | 无 execute_one 入口 |
| Branching | `stages/branching/` | ~3000 | ✅ 有 | ✅ 完成 | - |
| Pruning | `stages/pruning/` | **193** | ❌ 无 | ❌ 严重 | 仅静态分析，无 DB 交互 |
| Baseline | `stages/baseline/` | ~600 | ❌ 无 | ⚠️ 简化 | 无 execute_one 入口 |
| Optimize | `stages/optimize/` | ~700 | ✅ 有 | ✅ 完成 | - |
| Validate | `stages/validate/` | ~800 | ✅ 有 | ✅ 完成 | - |
| Patch | `stages/patch/` | ~600 | ✅ 有 | ✅ 完成 | - |
| **Report** | ❌ 不存在 | - | ❌ 无 | ❌ 缺失 | 无 stages/report.py |

---

## 二、工作方向（5 大方向）

### 方向 1：完善 Pruning 阶段（高优先级）

**问题**：
- 仅 193 行代码，只做静态分析
- 没有数据库交互
- 没有实现 V8 架构要求的 execute_one 入口

**现状功能**：
- ✅ 前缀通配符检测 (`'%'+col`)
- ✅ 后缀通配符检测 (`col+'%'`)
- ✅ CONCAT 通配符检测
- ✅ 函数包裹检测

**缺失功能**：
- ❌ 数据库连接和 EXPLAIN 执行
- ❌ 成本估算
- ❌ 索引利用率分析
- ❌ 执行计划差异对比
- ❌ execute_one 入口点

**建议行动**：
```
1. 创建 stages/pruning/execute_one.py
2. 补充数据库交互能力
3. 添加成本估算逻辑
4. 与 baseline 阶段数据对接
```

---

### 方向 2：补充 Report 报告模块（高优先级）

**问题**：
- `stages/report.py` 不存在
- `stages/report_builder.py` 不存在
- V8 工作流不包含报告生成
- `RunFinalizer` 仅在测试中使用，无生产实现

**当前状态**：
- `run_paths.py` 定义了报告路径：
  - `overview/report.json`
  - `overview/report.md`
  - `overview/report.summary.md`
- `StatusResolver` 有 `report_enabled()` 但无生成逻辑
- 配置文件支持 `report.enabled` 选项

**建议行动**：
```
1. 创建 stages/report/report_generator.py
2. 创建 stages/report/report_builder.py
3. 在 workflow_v8.py 中添加报告阶段
4. 实现 _run_report() 方法
5. 集成到 RunFinalizer 生产代码中
```

---

### 方向 3：完善 Discovery 和 Baseline 阶段（中优先级）

**问题**：
- 无 execute_one 入口点
- 无法与 V8 工作流无缝集成

**建议行动**：
```
1. 创建 stages/discovery/execute_one.py
2. 创建 stages/baseline/execute_one.py
3. 确保与 supervisor 状态管理兼容
```

---

### 方向 4：修复测试（高优先级）

**问题**：4 个测试因模块引用错误失败

**损坏测试**：
```
1. tests/test_scripting_branch_generator.py - 缺少 baseline/ 模块
2. tests/test_adapters_branch_*.py - 缺少 branch_*.py 模块
3. tests/test_application_run_service.py - 缺少 commands/ 模块
```

**建议行动**：
```
1. 修复 import 语句
2. 添加缺失的模块引用
3. 确保测试可独立运行
```

---

### 方向 5：实现独立阶段 CLI 命令（中优先级）

**问题**：
- 文档描述的 `diagnose`、`optimize`、`validate` 命令未实现
- 用户无法单独执行某个阶段

**当前 CLI 状态**：
| 命令 | 状态 | 说明 |
|------|------|------|
| `run` | ✅ | 完整流程 |
| `resume` | ✅ | 恢复运行 |
| `status` | ✅ | 状态查看 |
| `apply` | ✅ | 应用补丁 |
| `verify` | ✅ | 验证证据链 |
| `validate-config` | ✅ | 验证配置 |
| `diagnose` | ❌ | 阶段 1-3 |
| `optimize` | ❌ | 阶段 5 |
| `validate` | ❌ | 阶段 6 |

**建议行动**：
```
1. 实现 diagnose 命令 (discovery + branching + pruning)
2. 实现 optimize 命令 (优化指定 SQL)
3. 实现 validate 命令 (验证指定 SQL)
4. 更新文档确保一致
```

---

## 三、契约和数据状态

### 3.1 数据契约（✅ 完整）

| Schema | 状态 | 验证器 |
|--------|------|--------|
| sqlunit.schema.json | ✅ | ✅ |
| fragment_record.schema.json | ✅ | ✅ |
| branch_record.schema.json | ✅ | ✅ |
| risk_record.schema.json | ✅ | ✅ |
| baseline.schema.json | ✅ | ✅ |
| optimization_proposal.schema.json | ✅ | ✅ |
| acceptance_result.schema.json | ✅ | ✅ |
| patch_result.schema.json | ✅ | ✅ |
| report.schema.json | ✅ | ✅ |
| run_meta.schema.json | ✅ | ✅ |

**结论**：契约层完整，无需修改

### 3.2 文档状态

| 文档 | 状态 | 说明 |
|------|------|------|
| V8_SUMMARY.md | ⚠️ 需更新 | 实现状态表格需要修正 |
| AGENTS.md | ✅ 已同步 | 目录结构已更新 |
| STAGES.md | ❌ 缺失 | 应迁移自 V8_SUMMARY.md |

**建议行动**：
```
1. 更新 V8_SUMMARY.md 的阶段状态表格
2. 创建 docs/V8/STAGES.md
3. 确保文档与代码状态一致
```

---

## 四、优先级矩阵

| 优先级 | 任务 | 工作量 | 风险 |
|--------|------|--------|------|
| P0 | 修复损坏的测试 | 低 | 低 |
| P0 | 完善 Pruning 阶段 | 中 | 中 |
| P0 | 解决 workflow_v8.py 架构不一致 | 低 | 高 |
| P1 | 实现 Report 模块 | 高 | 高 |
| P1 | 修复 V8_SUMMARY.md | 低 | 低 |
| P2 | 完善 Discovery/Baseline execute_one | 中 | 低 |
| P2 | 实现独立阶段 CLI | 中 | 低 |

---

## 五、详细任务分解

### 5.1 P0 - 立即处理

#### T-001：修复测试引用错误

**根本原因**：模块路径迁移不一致
- 旧路径：`sqlopt.baseline`, `sqlopt.commands`, `sqlopt.scripting`
- 新路径：`sqlopt.stages.baseline`, `sqlopt.stages.branching`
- `sqlopt.commands` 模块从未创建

**4 个损坏测试**：

| 测试文件 | 当前 Import | 修复后 Import |
|---------|-----------|--------------|
| `tests/test_baseline_module.py:8` | `from sqlopt.baseline.performance_collector import` | `from sqlopt.stages.baseline.performance_collector import` |
| `tests/test_commands_branch.py:9` | `from sqlopt.commands import branch` | 创建 `sqlopt/commands/` 模块并实现 `branch.py` |
| `tests/test_commands_baseline.py` | `from sqlopt.commands import baseline` | 同上，创建 `baseline.py` |
| `tests/test_scripting_branch_generator.py:6` | `from sqlopt.scripting.branch_generator import BranchGenerator` | `from sqlopt.stages.branching.branch_generator import BranchGenerator` |

**具体修复命令**：

```bash
# 1. 修复 test_scripting_branch_generator.py
sed -i '' 's/from sqlopt.scripting.branch_generator/from sqlopt.stages.branching.branch_generator/' tests/test_scripting_branch_generator.py

# 2. 修复 test_baseline_module.py
sed -i '' 's/from sqlopt.baseline.from sqlopt.stages.baseline/' tests/test_baseline_module.py

# 3. 对于 commands 模块，有两个选择：
# 选项 A：创建空的 commands 模块（如果 CLI 命令需要）
mkdir -p python/sqlopt/commands
touch python/sqlopt/commands/__init__.py

# 选项 B：修改测试使用 stages 下的模块
```

**验证命令**：
```bash
python3 -m pytest tests/test_scripting_branch_generator.py -v
python3 -m pytest tests/test_baseline_module.py -v
python3 -m pytest tests/test_commands_branch.py -v
python3 -m pytest tests/test_commands_baseline.py -v
```

**操作**：
1. 运行上述 sed 命令修复 import
2. 或创建 commands 模块
3. 运行 pytest 验证全部通过

#### T-002：完善 Pruning 阶段

**目标**：实现完整的剪枝逻辑

**文件结构建议**：
```
stages/pruning/
├── __init__.py
├── analyzer.py          # 现有：静态分析
├── cost_estimator.py    # 新增：成本估算
├── db_interactor.py     # 新增：数据库交互
├── execute_one.py       # 新增：V8 入口
└── tests/
```

**execute_one.py 接口**：
```python
def execute_one(run_id: str, sql_key: str, ctx: StageContext) -> PruningResult:
    """对单个 SQL 单元执行剪枝分析"""
    ...
```

### 5.2 P1 - 近期处理

#### T-003：实现 Report 模块

**目标**：生成完整的优化报告

**文件结构**：
```
stages/report/
├── __init__.py
├── report_generator.py   # 核心生成器
├── report_builder.py     # 报告构建器
├── templates/           # 报告模板
│   ├── summary.md
│   └── detail.json
└── execute_one.py       # V8 入口（新增）
```

**execute_one.py 接口**：
```python
# stages/report/execute_one.py
class ReportStage:
    def execute_one(self, run_id: str, ctx: StageContext) -> ReportResult:
        """生成单个 SQL 的报告"""
        ...

    def generate_summary(self, run_id: str) -> SummaryReport:
        """生成汇总报告"""
        ...

    def generate_detail(self, run_id: str, sql_key: str) -> DetailReport:
        """生成单个 SQL 的详细报告"""
        ...
```

**ReportResult 输出结构**：
```json
{
  "run_id": "run_xxx",
  "sql_key": "selectById",
  "summary": {
    "total_risks": 5,
    "high_risk": 2,
    "medium_risk": 1,
    "low_risk": 2,
    "optimization_candidates": 3
  },
  "recommendations": [...]
}
```

**与 workflow_v8.py 集成**：
```python
# 选项 A：将 report 添加到 STAGE_ORDER（如 report 是流水线阶段）
STAGE_ORDER = [
    ...
    "patch",
    "report"  # 新增
]

# 或选项 B：report 作为后处理步骤，不在流水线中
```

**操作步骤**：
1. 创建 `stages/report/` 目录结构
2. 实现 `execute_one.py` 入口
3. 实现 `report_builder.py` 核心逻辑
4. 决定 report 是流水线阶段还是后处理
5. 更新 workflow_v8.py 集成方式
6. 运行测试验证

#### T-004：更新 V8_SUMMARY.md

**修正内容**：
```markdown
# 原：剪枝阶段 ✅ 已实现
# 改：剪枝阶段 ⚠️ 部分实现（缺少 execute_one）

# 原：基线阶段 ✅ 已实现
# 改：基线阶段 ⚠️ 简化实现（无 execute_one）

# 原：补丁阶段 ✅ 已实现
# 改：报告阶段 ❌ 缺失
```

#### T-008：解决 workflow_v8.py 架构不一致

**问题**：`workflow_v8.py` 内部存在冲突

| 位置 | 行号 | 内容 |
|------|------|------|
| `STAGE_ORDER` | 58-66 | 7 个阶段，**不含** `report` |
| `DEFAULT_PHASE_POLICIES` | 76 | 包含 `"report": PhaseExecutionPolicy(...)` |

**冲突详情**：
```python
# Line 58-66
STAGE_ORDER = [
    "discovery",
    "branching", 
    "pruning",
    "baseline",
    "optimize",
    "validate",
    "patch"
]

# Line 76
DEFAULT_PHASE_POLICIES = {
    ...
    "report": PhaseExecutionPolicy(phase="report", allow_regenerate=True),  # 存在于策略但不在执行顺序中
}
```

**决策（需确认）**：
| 选项 | 决策 | 实现方式 |
|------|------|---------|
| A | report 是流水线阶段 | 将 `"report"` 添加到 `STAGE_ORDER` 末尾 |
| B | report 是后处理步骤 | 从 `DEFAULT_PHASE_POLICIES` 中移除 `"report"` |

**推荐决策**：选项 B（report 作为后处理步骤）
- 理由：报告生成不应该是流水线的一部分，应该是运行结束后的总结
- 影响：需要修改 V8_SUMMARY.md 中 "7 阶段" 的描述

**已决策：采用选项 B**
- 报告作为后处理步骤，不在流水线中
- `DEFAULT_PHASE_POLICIES` 中的 `"report"` 条目需删除

**修复步骤**：
```python
# 1. 编辑 workflow_v8.py，删除 DEFAULT_PHASE_POLICIES 中的 "report" 条目
# 位于 DEFAULT_PHASE_POLICIES dict 中的 "report" 键值对

# 2. 更新 V8_SUMMARY.md，将 "7 阶段" 描述改为 "6 阶段 + 后处理"
```

**验证命令**：
```bash
grep -n "report" python/sqlopt/application/workflow_v8.py
# 确认 STAGE_ORDER 中无 "report"，且 DEFAULT_PHASE_POLICIES 中也无 "report"
```

**操作**：
1. 确认 report 的设计意图（选项 A 或 B）
2. 按对应步骤修复
3. 更新 V8_SUMMARY.md 文档
4. 运行测试验证

### 5.3 P2 - 规划中

#### T-005：完善 Discovery execute_one

**目标**：支持 V8 工作流的单步执行

**文件结构建议**：
```
stages/discovery/
├── __init__.py
├── scanner.py           # 现有：XML 扫描
├── parser.py           # 现有：MyBatis 解析
├── execute_one.py      # 新增：V8 入口
└── tests/
```

**execute_one.py 接口**：
```python
# stages/discovery/execute_one.py
class DiscoveryStage:
    def execute_one(self, run_id: str, ctx: StageContext) -> DiscoveryResult:
        """对单个 Mapper XML 执行发现"""
        ...

    def scan_mapper(self, mapper_path: str) -> List[SqlUnit]:
        """扫描单个 Mapper 文件"""
        ...

    def extract_sql_units(self, mapper_content: str) -> List[SqlUnit]:
        """提取 SQL 单元"""
        ...
```

**操作步骤**：
1. 创建 `stages/discovery/execute_one.py`
2. 实现 `DiscoveryStage` 类
3. 实现 `execute_one` 方法
4. 与 supervisor 状态管理集成

#### T-006：完善 Baseline execute_one

**目标**：支持 V8 工作流的单步执行

**文件结构建议**：
```
stages/baseline/
├── __init__.py
├── baseline_collector.py  # 现有：760行
├── explain_parser.py      # 现有
├── execute_one.py         # 新增：V8 入口
└── tests/
```

**execute_one.py 接口**：
```python
# stages/baseline/execute_one.py
class BaselineStage:
    def execute_one(self, run_id: str, sql_key: str, ctx: StageContext) -> BaselineResult:
        """对单个 SQL 执行基线采集"""
        ...

    def collect_baseline(self, sql: str, params: dict) -> BaselineResult:
        """执行 EXPLAIN 并采集基线"""
        ...

    def parse_explain(self, explain_output: str) -> ExecutionPlan:
        """解析 EXPLAIN 输出"""
        ...
```

**BaselineResult 输出结构**：
```json
{
  "sql_key": "selectById",
  "execution_time_ms": 45.2,
  "rows_scanned": 1250,
  "execution_plan": {
    "node_type": "Index Scan",
    "index_used": "idx_user_id",
    "cost": 12.5
  },
  "result_hash": "abc123..."
}
```

**操作步骤**：
1. 创建 `stages/baseline/execute_one.py`
2. 实现 `BaselineStage` 类
3. 复用现有 `baseline_collector.py` 逻辑
4. 实现 `execute_one` 方法
5. 与 supervisor 状态管理集成

#### T-007：实现独立阶段 CLI

**目标**：支持 diagnose、optimize、validate 命令

**命令设计**：

| 命令 | 功能 | 执行的阶段 |
|------|------|-----------|
| `diagnose` | 诊断模式 | discovery + branching + pruning |
| `optimize` | 优化单个 SQL | optimize |
| `validate` | 验证单个 SQL | validate |

**diagnose 命令实现**：
```python
# cli.py - diagnose 子命令
@subcommand("diagnose")
def diagnose_cmd(args):
    """执行诊断模式（阶段 1-3）"""
    # 1. Discovery: 扫描 XML
    # 2. Branching: 生成分支
    # 3. Pruning: 风险检测
    # 输出诊断报告
```

**optimize 命令实现**：
```python
# cli.py - optimize 子命令
@subcommand("optimize")
def optimize_cmd(args):
    """优化指定 SQL"""
    # 需要 --run-id 和 --sql-key 参数
    # 执行 optimize 阶段
    # 输出优化建议
```

**validate 命令实现**：
```python
# cli.py - validate 子命令
def validate_cmd(args):
    """验证指定 SQL"""
    # 需要 --run-id 和 --sql-key 参数
    # 执行 validate 阶段
    # 输出验证结果
```

**操作步骤**：
1. 在 `cli.py` 中添加 `diagnose`、`optimize`、`validate` 子命令
2. 实现各子命令的逻辑
3. 添加参数解析（--run-id, --sql-key 等）
4. 调用对应的 stage execute_one 方法
5. 测试各命令

---

## 六、架构一致性检查

### 6.1 V8 工作流阶段顺序

**文件**：`python/sqlopt/application/workflow_v8.py`

```python
# Line 58-66 - STAGE_ORDER 不包含 report
STAGE_ORDER = [
    "discovery",
    "branching", 
    "pruning",
    "baseline",
    "optimize",
    "validate",
    "patch"
]

# Line 76 - DEFAULT_PHASE_POLICIES 包含 report（冲突）
DEFAULT_PHASE_POLICIES = {
    ...
    "report": PhaseExecutionPolicy(phase="report", allow_regenerate=True),
}
```

**问题**：`report` 在策略中定义但不在执行顺序中

**决策**：
- 选项 A：如果 report 是流水线阶段 → 将 `"report"` 添加到 `STAGE_ORDER`
- 选项 B：如果 report 是后处理步骤 → 从 `DEFAULT_PHASE_POLICIES` 中移除

### 6.2 execute_one 入口点检查

| 阶段 | execute_one | Supervisor 集成 |
|------|------------|----------------|
| discovery | ❌ 缺失 | 需要 |
| branching | ✅ 存在 | ✅ |
| pruning | ❌ 缺失 | 需要 |
| baseline | ❌ 缺失 | 需要 |
| optimize | ✅ 存在 | ✅ |
| validate | ✅ 存在 | ✅ |
| patch | ✅ 存在 | ✅ |

---

## 七、附录

### 7.1 术语对照

| 术语 | 说明 |
|------|------|
| execute_one | V8 架构的单步执行入口 |
| supervisor | 运行状态管理器 |
| StageContext | 阶段执行上下文 |

### 7.2 相关文件路径

```
python/sqlopt/
├── application/
│   ├── workflow_v8.py       # V8 工作流引擎
│   └── run_service.py       # Run 生命周期
├── stages/
│   ├── discovery/           # 发现阶段
│   ├── branching/           # 分支阶段
│   ├── pruning/            # 剪枝阶段 ⚠️
│   ├── baseline/           # 基线阶段 ⚠️
│   ├── optimize/           # 优化阶段 ✅
│   ├── validate/           # 验证阶段 ✅
│   └── patch/             # 补丁阶段 ✅
└── cli.py                  # CLI 入口

contracts/                    # 数据契约 ✅
docs/V8/V8_SUMMARY.md       # 架构文档 ⚠️
tests/                       # 测试 ⚠️
```

---

## 八、文档范围说明

### 本计划涵盖范围

本计划是 **工作计划书**，记录 **待执行** 的开发任务：

| 任务 | 状态 | 说明 |
|------|------|------|
| 6 并行探索代理调研 | ✅ 已完成 | 覆盖 7 阶段、契约、引擎、CLI、报告、测试 |
| 工作计划文档编写 | ✅ 已完成 | T-001 到 T-008 详细规划 |
| 代码实现 | ❌ 待执行 | 所有 T-001 到 T-008 任务 |

### 前期已完成的工作（不在本计划范围内）

| 工作 | 完成日期 | 说明 |
|------|----------|------|
| 清理旧 stages/*.py 文件 | 2026-03-19 | 删除 13 个旧文件 |
| 重命名为 stages/* 目录 | 2026-03-19 | baseline/, optimize/, validate/, patch/ |
| 创建 execute_one.py | 2026-03-19 | optimize/, validate/ 已有 |
| 更新 AGENTS.md | 2026-03-19 | 目录结构同步 |
| 更新 V8_SUMMARY.md | 2026-03-19 | 实现状态表格 |

### 如何使用本计划

1. **优先级顺序**：按 P0 → P1 → P2 顺序执行
2. **每个任务独立**：可分配给不同开发者并行执行
3. **验收标准**：每个任务完成后更新本表格状态

---

*文档生成时间：2026-03-19*
*调研方法：6 并行探索代理 + 代码审查*
