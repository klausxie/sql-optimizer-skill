# V10 执行计划：空壳先行，逻辑后填

> **执行计划** - 可立即开始实施
>
> 核心理念：先搭架子（空壳 + 契约 + 测试），再填内容（核心逻辑迁移）

---

## TL;DR

> **目标**：3-4 周完成一个**可运行的空壳**
> - CLI `sqlopt run <stage>` 可执行
> - 阶段间数据流跑通（契约驱动）
> - 单元测试覆盖空壳代码
> - 核心逻辑先用 mock 填充
>
> **Estimated Effort**: ~4 weeks (Medium-Large)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: CONTRACTS → COMMON → CLI + STUB → TEST

---

## Context

### 用户需求

1. **空壳先行**：先跑起来，逻辑后面填
2. **契约完善**：数据契约是阶段间接口，必须先定
3. **公共模块**：配置、错误、进度、LLM mock 等基础设施
4. **可测试**：每层都要有测试
5. **渐进填充**：核心逻辑（分支推理等）后续迁移

### 设计原则

- **契约优先**：先定义接口，再实现
- **Mock 填充**：核心逻辑先用 mock/stub 替代
- **测试覆盖**：空壳也有测试
- **可运行**：CLI 入口可用
- **代码规范**：遵循 [STANDARDS.md](./STANDARDS.md) - 使用 ruff + mypy

---

## Work Objectives

### 目标 1：可运行的空壳

```
sqlopt run init      # 扫描 XML，输出契约
sqlopt run parse     # 展开分支，输出契约
sqlopt run recognition  # EXPLAIN 基线，输出契约
sqlopt run optimize  # 生成建议，输出契约
sqlopt run result    # 输出报告
```

### 目标 2：完整的数据契约

```
runs/<run_id>/
├── init/
│   └── sql_units.json              # InitOutput
├── parse/
│   ├── sql_units_with_branches.json # ParseOutput
│   └── risks.json                  # RiskOutput
├── recognition/
│   └── baselines.json              # RecognitionOutput
├── optimize/
│   └── proposals.json              # OptimizeOutput
└── result/
    └── report.json                 # ResultOutput
```

### 目标 3：测试覆盖

```
tests/
├── unit/
│   ├── test_contracts.py
│   ├── test_config.py
│   ├── test_progress.py
│   └── test_stages/
│       ├── test_init_stage.py
│       ├── test_parse_stage.py
│       └── ...
├── integration/
│   └── test_stage_flow.py
└── mock/
    ├── mock_llm.py
    └── mock_db.py
```

---

## Execution Strategy

### Wave 1: 数据契约定义（最优先）

```
Wave 1 (Foundation - 必须最先完成):
├── T1: 定义 InitOutput 契约 (contracts/init.py)
├── T2: 定义 ParseOutput 契约 (contracts/parse.py)
├── T3: 定义 RecognitionOutput 契约 (contracts/recognition.py)
├── T4: 定义 OptimizeOutput 契约 (contracts/optimize.py)
├── T5: 定义 ResultOutput 契约 (contracts/result.py)
└── T6: 契约序列化/反序列化工具
```

### Wave 2: 公共模块

```
Wave 2 (After Wave 1 - 依赖契约定义):
├── T7:  配置加载 (config.py)
├── T8:  错误定义 (errors.py)
├── T9:  进度跟踪 (progress.py)
├── T10: 路径管理 (run_paths.py)
├── T11: LLM Mock Provider (llm_mock_generator.py)
├── T12: 数据库连接器 Stub (db_connector.py - stub)
└── T13: 阶段基类 (Stage base class)
```

### Wave 3: CLI + 空壳阶段

```
Wave 3 (After Wave 2 - CLI 依赖公共模块):
├── T14: CLI 入口 (cli/main.py)
├── T15: Init 阶段空壳 (stages/init/stage.py - stub)
├── T16: Parse 阶段空壳 (stages/parse/stage.py - stub)
├── T17: Recognition 阶段空壳 (stages/recognition/stage.py - stub)
├── T18: Optimize 阶段空壳 (stages/optimize/stage.py - stub)
├── T19: Result 阶段空壳 (stages/result/stage.py - stub)
└── T20: 阶段调度器 (stage_runner.py)
```

### Wave 4: 测试基础设施

```
Wave 4 (After Wave 3 - 测试覆盖空壳):
├── T21: 单元测试 - 契约
├── T22: 单元测试 - 公共模块
├── T23: 单元测试 - CLI
├── T24: 单元测试 - 各阶段空壳
├── T25: 集成测试 - 阶段流
└── T26: Mock LLM/DB fixtures
```

### Wave FINAL: 验收

```
Wave FINAL:
├── F1: Plan Compliance Audit
├── F2: Code Quality Review
├── F3: CLI 功能验收
└── F4: 端到端测试 (sqlopt run --config sqlopt.yml)
```

---

## TODOs

### Wave 1: 数据契约定义

- [ ] 1. **定义 InitOutput 契约**

  **What to do**:
  - 创建 `python/sqlopt/contracts/init.py`
  - 定义 `InitInput`, `InitOutput` dataclass
  - 字段：`sql_units: List[SQLUnit]`, `run_id: str`, `timestamp: str`
  - `SQLUnit` dataclass: `id, mapper_file, sql_id, sql_text, statement_type`
  - JSON 序列化/反序列化方法

  **Acceptance Criteria**:
  - [ ] `python/sqlopt/contracts/init.py` 存在
  - [ ] `InitOutput.to_json()` 输出正确格式
  - [ ] `InitOutput.from_json()` 正确还原

  **QA Scenarios**:
  ```
  Scenario: InitOutput 序列化
    Tool: Bash
    Command: cd python && python -c "
      from sqlopt.contracts.init import InitOutput, SQLUnit
      unit = SQLUnit(id='u1', mapper_file='UserMapper.xml', sql_id='findUser', sql_text='SELECT * FROM users', statement_type='SELECT')
      output = InitOutput(sql_units=[unit], run_id='test-123')
      print(output.to_json())
    "
    Expected Result: {"sql_units": [{"id": "u1", "mapper_file": "UserMapper.xml", "sql_id": "findUser", "sql_text": "SELECT * FROM users", "statement_type": "SELECT"}], "run_id": "test-123", "timestamp": "..."}
    Evidence: .sisyphus/evidence/task-1-init-contract.json
  ```

  **Commit**: YES
  - Message: `feat(contracts): define InitOutput contract`
  - Files: `python/sqlopt/contracts/init.py`

---

- [ ] 2. **定义 ParseOutput 契约**

  **What to do**:
  - 创建 `python/sqlopt/contracts/parse.py`
  - 定义 `ParseInput`, `ParseOutput`, `RiskOutput` dataclass
  - `ParseOutput` 字段：`sql_units_with_branches: List[SQLUnitWithBranches]`
  - `SQLUnitWithBranches` 字段：`sql_unit_id, branches: List[SQLBranch]`
  - `SQLBranch` 字段：`path_id, condition, expanded_sql, is_valid`
  - `RiskOutput` 字段：`risks: List[Risk]`

  **Acceptance Criteria**:
  - [ ] `python/sqlopt/contracts/parse.py` 存在
  - [ ] 序列化/反序列化正确

  **Commit**: YES
  - Message: `feat(contracts): define ParseOutput contract`

---

- [ ] 3. **定义 RecognitionOutput 契约**

  **What to do**:
  - 创建 `python/sqlopt/contracts/recognition.py`
  - 定义 `RecognitionInput`, `RecognitionOutput` dataclass
  - `RecognitionOutput` 字段：`baselines: List[PerformanceBaseline]`
  - `PerformanceBaseline` 字段：`sql_unit_id, path_id, plan, estimated_cost, actual_time_ms`

  **Acceptance Criteria**:
  - [ ] `python/sqlopt/contracts/recognition.py` 存在
  - [ ] 序列化/反序列化正确

  **Commit**: YES
  - Message: `feat(contracts): define RecognitionOutput contract`

---

- [ ] 4. **定义 OptimizeOutput 契约**

  **What to do**:
  - 创建 `python/sqlopt/contracts/optimize.py`
  - 定义 `OptimizeInput`, `OptimizeOutput`, `OptimizationProposal` dataclass
  - `OptimizeOutput` 字段：`proposals: List[OptimizationProposal]`
  - `OptimizationProposal` 字段：`sql_unit_id, path_id, original_sql, optimized_sql, rationale, confidence`

  **Acceptance Criteria**:
  - [ ] `python/sqlopt/contracts/optimize.py` 存在
  - [ ] 序列化/反序列化正确

  **Commit**: YES
  - Message: `feat(contracts): define OptimizeOutput contract`

---

- [ ] 5. **定义 ResultOutput 契约**

  **What to do**:
  - 创建 `python/sqlopt/contracts/result.py`
  - 定义 `ResultInput`, `ResultOutput` dataclass
  - `ResultOutput` 字段：`can_patch: bool, report: Report, patches: List[Patch]`
  - `Report` 字段：`summary, details, risks, recommendations`
  - `Patch` 字段：`sql_unit_id, original_xml, patched_xml, diff`

  **Acceptance Criteria**:
  - [ ] `python/sqlopt/contracts/result.py` 存在
  - [ ] 序列化/反序列化正确

  **Commit**: YES
  - Message: `feat(contracts): define ResultOutput contract`

---

- [ ] 6. **契约序列化工具**

  **What to do**:
  - 创建 `python/sqlopt/contracts/__init__.py`
  - 创建 `contracts/base.py` - 基类和工具函数
  - JSON 序列化 helpers
  - 契约验证器

  **Acceptance Criteria**:
  - [ ] `contracts/__init__.py` 导出所有契约
  - [ ] `to_json()` / `from_json()` 一致性测试通过

  **Commit**: YES
  - Message: `feat(contracts): add serialization utilities`

---

### Wave 2: 公共模块

- [ ] 7. **配置加载 (config.py)**

  **What to do**:
  - 创建 `python/sqlopt/common/config.py`
  - `SQLOptConfig` dataclass
  - YAML 加载函数 `load_config(path: str) -> SQLOptConfig`
  - 验证必填字段

  **Acceptance Criteria**:
  - [ ] `sqlopt.yml` 示例文件加载成功
  - [ ] 字段验证正确

  **Commit**: YES
  - Message: `feat(common): add config loading`

---

- [ ] 8. **错误定义 (errors.py)**

  **What to do**:
  - 创建 `python/sqlopt/common/errors.py`
  - 定义 `SQLOptError` 基类
  - `ConfigError`, `StageError`, `ContractError`, `LLMError` 等子类
  - 统一的错误格式

  **Acceptance Criteria**:
  - [ ] 所有错误类定义
  - [ ] 错误可序列化

  **Commit**: YES
  - Message: `feat(common): define error types`

---

- [ ] 9. **进度跟踪 (progress.py)**

  **What to do**:
  - 创建 `python/sqlopt/common/progress.py`
  - `ProgressTracker` 类
  - 阶段进度回调
  - JSON 状态持久化

  **Acceptance Criteria**:
  - [ ] `ProgressTracker` 可跟踪阶段进度
  - [ ] 状态可持久化到 JSON

  **Commit**: YES
  - Message: `feat(common): add progress tracking`

---

- [ ] 10. **路径管理 (run_paths.py)**

  **What to do**:
  - 创建 `python/sqlopt/common/run_paths.py`
  - `RunPaths` 类
  - 各阶段输出目录计算
  - 契约文件路径生成

  **Acceptance Criteria**:
  - [ ] `RunPaths` 正确生成路径
  - [ ] `run_path / "init" / "sql_units.json"` 正确

  **Commit**: YES
  - Message: `feat(common): add run paths management`

---

- [ ] 11. **LLM Mock Provider**

  **What to do**:
  - 创建 `python/sqlopt/common/llm_mock_generator.py`
  - `MockLLMProvider` 类
  - 基于 description 生成 mock 响应
  - `generate_optimization(sql, description) -> str`

  **Acceptance Criteria**:
  - [ ] Mock Provider 可实例化
  - [ ] `generate_optimization()` 返回模拟建议

  **Commit**: YES
  - Message: `feat(common): add LLM mock provider`

---

- [ ] 12. **数据库连接器 Stub**

  **What to do**:
  - 创建 `python/sqlopt/common/db_connector.py`
  - `DBConnector` 抽象基类
  - `PostgreSQLConnector`, `MySQLConnector` stub 实现
  - `execute_explain()` 方法签名

  **Acceptance Criteria**:
  - [ ] `DBConnector` 基类存在
  - [ ] stub 实现可实例化

  **Commit**: YES
  - Message: `feat(common): add DB connector stubs`

---

- [ ] 13. **阶段基类**

  **What to do**:
  - 创建 `python/sqlopt/stages/base.py`
  - `Stage` 抽象基类
  - `Input`, `Output` 类型参数
  - `run(input) -> Output` 抽象方法
  - `validate_input()`, `validate_output()` hooks

  **Acceptance Criteria**:
  - [ ] `Stage` 基类存在
  - [ ] 子类可实现 `run()` 方法

  **Commit**: YES
  - Message: `feat(stages): add stage base class`

---

### Wave 3: CLI + 空壳阶段

- [ ] 14. **CLI 入口**

  **What to do**:
  - 创建 `python/sqlopt/cli/main.py`
  - `sqlopt run [stage]` 命令
  - 默认 stage = `init`
  - 默认 config = `./sqlopt.yml`
  - 阶段调度逻辑

  **Acceptance Criteria**:
  - [ ] `sqlopt run init` 执行不报错
  - [ ] 输出 "Init stage completed"

  **QA Scenarios**:
  ```
  Scenario: CLI run init stage
    Tool: Bash
    Command: cd python && python -m sqlopt.cli.main run init --config ../tests/real/mybatis-test/sqlopt.yml
    Expected Result: Exit code 0, 输出 "Init stage completed"
    Evidence: .sisyphus/evidence/task-14-cli-run-init.json
  ```

  **Commit**: YES
  - Message: `feat(cli): add main entry point`

---

- [ ] 15. **Init 阶段空壳**

  **What to do**:
  - 创建 `python/sqlopt/stages/init/stage.py`
  - 继承 `Stage[InitInput, InitOutput]`
  - `run()` 方法：
    - 读取配置
    - 扫描 XML 文件
    - 调用 `_extract_sql_units()`
    - 输出 InitOutput
  - `_extract_sql_units()` stub：返回空列表或硬编码数据

  **Acceptance Criteria**:
  - [ ] Init stage 可执行
  - [ ] 输出 `runs/<run_id>/init/sql_units.json`

  **Commit**: YES
  - Message: `feat(stages): add init stage stub`

---

- [ ] 16. **Parse 阶段空壳**

  **What to do**:
  - 创建 `python/sqlopt/stages/parse/stage.py`
  - 继承 `Stage[ParseInput, ParseOutput]`
  - `run()` 方法：
    - 读取 InitOutput 契约
    - 调用 `_expand_branches()` (stub)
    - 输出 ParseOutput
  - `_expand_branches()` stub：返回硬编码分支

  **Acceptance Criteria**:
  - [ ] Parse stage 可执行
  - [ ] 输出 `runs/<run_id>/parse/sql_units_with_branches.json`

  **Commit**: YES
  - Message: `feat(stages): add parse stage stub`

---

- [ ] 17. **Recognition 阶段空壳**

  **What to do**:
  - 创建 `python/sqlopt/stages/recognition/stage.py`
  - 继承 `Stage[RecognitionInput, RecognitionOutput]`
  - `run()` 方法：
    - 读取 ParseOutput 契约
    - 调用 `_collect_baselines()` (stub)
    - 输出 RecognitionOutput
  - `_collect_baselines()` stub：返回硬编码基线

  **Acceptance Criteria**:
  - [ ] Recognition stage 可执行
  - [ ] 输出 `runs/<run_id>/recognition/baselines.json`

  **Commit**: YES
  - Message: `feat(stages): add recognition stage stub`

---

- [ ] 18. **Optimize 阶段空壳**

  **What to do**:
  - 创建 `python/sqlopt/stages/optimize/stage.py`
  - 继承 `Stage[OptimizeInput, OptimizeOutput]`
  - `run()` 方法：
    - 读取 RecognitionOutput 契约
    - 调用 `_generate_proposals()` (stub - 使用 MockLLM)
    - 输出 OptimizeOutput
  - `_generate_proposals()` stub：使用 MockLLM 生成建议

  **Acceptance Criteria**:
  - [ ] Optimize stage 可执行
  - [ ] 输出 `runs/<run_id>/optimize/proposals.json`

  **Commit**: YES
  - Message: `feat(stages): add optimize stage stub`

---

- [ ] 19. **Result 阶段空壳**

  **What to do**:
  - 创建 `python/sqlopt/stages/result/stage.py`
  - 继承 `Stage[ResultInput, ResultOutput]`
  - `run()` 方法：
    - 读取 OptimizeOutput 契约
    - 生成报告
    - 输出 ResultOutput
  - 逻辑：can_patch=true 时输出 patches，false 时只输出 report

  **Acceptance Criteria**:
  - [ ] Result stage 可执行
  - [ ] 输出 `runs/<run_id>/result/report.json`

  **Commit**: YES
  - Message: `feat(stages): add result stage stub`

---

- [ ] 20. **阶段调度器**

  **What to do**:
  - 创建 `python/sqlopt/stage_runner.py`
  - `StageRunner` 类
  - `run_stage(stage_name, run_id, config)` 方法
  - 阶段依赖检查
  - 契约文件读写

  **Acceptance Criteria**:
  - [ ] `StageRunner` 可调度各阶段
  - [ ] 阶段间数据流正确

  **Commit**: YES
  - Message: `feat(core): add stage runner`

---

### Wave 4: 测试基础设施

- [ ] 21. **单元测试 - 契约**

  **What to do**:
  - 创建 `tests/unit/test_contracts.py`
  - 各契约序列化/反序列化测试
  - 边界条件测试

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_contracts.py` 通过

  **Commit**: YES
  - Message: `test: add contract unit tests`

---

- [ ] 22. **单元测试 - 公共模块**

  **What to do**:
  - 创建 `tests/unit/test_config.py`
  - 创建 `tests/unit/test_progress.py`
  - 创建 `tests/unit/test_run_paths.py`
  - 各模块单元测试

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_common/` 通过

  **Commit**: YES
  - Message: `test: add common module unit tests`

---

- [ ] 23. **单元测试 - CLI**

  **What to do**:
  - 创建 `tests/unit/test_cli.py`
  - CLI 参数解析测试
  - 命令路由测试

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_cli.py` 通过

  **Commit**: YES
  - Message: `test: add CLI unit tests`

---

- [ ] 24. **单元测试 - 各阶段空壳**

  **What to do**:
  - 创建 `tests/unit/test_stages/`
  - 各阶段空壳的输入输出测试
  - Stub 方法测试

  **Acceptance Criteria**:
  - [ ] `pytest tests/unit/test_stages/` 通过

  **Commit**: YES
  - Message: `test: add stage unit tests`

---

- [ ] 25. **集成测试 - 阶段流**

  **What to do**:
  - 创建 `tests/integration/test_stage_flow.py`
  - 端到端测试：`run init` → `run parse` → ...
  - 使用 mybatis-test 作为真实数据源

  **Acceptance Criteria**:
  - [ ] `pytest tests/integration/test_stage_flow.py` 通过
  - [ ] 所有契约文件正确生成

  **Commit**: YES
  - Message: `test: add stage flow integration tests`

---

- [ ] 26. **Mock Fixtures**

  **What to do**:
  - 创建 `tests/fixtures/mock_llm.py`
  - 创建 `tests/fixtures/mock_db.py`
  - pytest fixtures

  **Acceptance Criteria**:
  - [ ] Fixtures 可复用

  **Commit**: YES
  - Message: `test: add mock fixtures`

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`

  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`

  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [ ] F3. **CLI 功能验收** — `unspecified-high`

  - `sqlopt run init` 可执行
  - `sqlopt run parse` 可执行
  - `sqlopt run --config sqlopt.yml` 完整流程可执行

  Output: `CLI [PASS/FAIL] | Flow [PASS/FAIL] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`

  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Success Criteria

### 可运行验证

```bash
# 1. CLI 可执行
cd python && python -m sqlopt.cli.main --help
# Expected: 显示帮助信息

# 2. Init 阶段可运行
python -m sqlopt.cli.main run init --config ../tests/real/mybatis-test/sqlopt.yml
# Expected: 创建 runs/<run_id>/init/sql_units.json

# 3. 完整流程可运行
python -m sqlopt.cli.main run --config ../tests/real/mybatis-test/sqlopt.yml
# Expected: 所有契约文件生成
```

### 测试验证

```bash
# 单元测试
cd python && python -m pytest ../tests/unit/ -v

# 集成测试
python -m pytest ../tests/integration/ -v
```

### 代码质量验证

> 参考: [STANDARDS.md](./STANDARDS.md) - 完整的 Python 代码规范 + 闭环机制

```bash
# 安装 ruff (如未安装)
pip install ruff

# Lint 检查 (手动)
cd python && ruff check sqlopt/

# 自动修复 (注意: 不修复安全问题和类型问题)
ruff check --fix sqlopt/

# 类型检查 (需要 mypy)
pip install mypy
cd python && mypy sqlopt/ --ignore-missing-imports

# 完整 CI 检查
cd python && ruff check sqlopt/ && mypy sqlopt/ --ignore-missing-imports

# 🔄 闭环: pre-commit hook 自动检查
# 安装: cp .claude/lint/pre-commit.sh .git/hooks/pre-commit
# 或: git config core.hooksPath .claude/lint
```

### 🔄 闭环机制

| 步骤 | 说明 |
|------|------|
| **1. 编写代码** | 按 STANDARDS.md 规范编写 |
| **2. git add** | 添加要提交的文件 |
| **3. git commit** | 触发 pre-commit hook |
| **4. 自动检查** | `.claude/lint/pre-commit.sh` 运行 ruff |
| **5. 失败?** | `exit 1` 阻止提交，查看错误修复 |
| **6. 成功?** | `exit 0` 允许提交 |

---

## Commit Strategy

| Wave | 数量 | 建议 |
|------|------|------|
| Wave 1 | 6 | 按契约文件分开提交 |
| Wave 2 | 7 | 按模块分开提交 |
| Wave 3 | 7 | 按阶段分开提交 |
| Wave 4 | 6 | 按测试类型分组提交 |

---

## 后续：核心逻辑迁移

完成空壳后，下一阶段是迁移核心逻辑：

```
Phase 2 (后续):
├── 迁移分支推理 (stages/branching/*)
├── 迁移语义等价 (platforms/sql/semantic_equivalence.py)
├── 迁移 LLM Provider (llm/provider.py)
└── 填充各阶段核心逻辑
```

---

*最后更新：2026-03-23*
