# V9 架构总览

> 版本：V9 | 更新日期：2026-03-20

---

## 一、V9 架构概述

V9 是 V8 的演进版本，将原来的 7 阶段流水线简化为 **5 阶段**，并采用直接方法调用替代 Stage 类委托模式。

### 核心设计理念

1. **简化阶段划分**：7 阶段 → 5 阶段，降低复杂度
2. **直接方法调用**：不通过 Stage 基类委托，减少抽象层开销
3. **迭代式优化**：Optimize 阶段内集成验证迭代
4. **产物可追溯**：每个阶段产物独立目录，便于审查和回滚

### V9 流水线

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              V9 SQL Optimizer Pipeline                                   │
│                                                                                         │
│  ┌─────────┐    ┌─────────┐    ┌────────────┐    ┌─────────────────┐    ┌─────────┐  │
│  │  Init   │───▶│  Parse  │───▶│ Recognition │───▶│     Optimize     │───▶│  Patch  │  │
│  └─────────┘    └─────────┘    └────────────┘    └─────────────────┘    └─────────┘  │
│                                                                                         │
│                                                 ▲                                       │
│                                                 │ (迭代重试)                              │
│                                                 └─────────────────────────────────────  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、与 V8 架构对比

### 阶段映射表

| V8 阶段 | V9 阶段 | 变更类型 | 说明 |
|---------|---------|----------|------|
| Discovery | **Init** | 重命名 | 更清晰表达初始化职责 |
| Branching | **Parse** | 合并 | 合并 Pruning 减少阶段 |
| Pruning | | | 职责合并到 Parse 阶段 |
| Baseline | **Recognition** | 重命名 | 强调 SQL 模式识别 |
| Optimize | **Optimize** | 合并 | 合并 Validate 为迭代验证 |
| Validate | | | 职责合并到 Optimize 阶段 |
| Patch | Patch | 不变 | 保持不变 |

### 架构差异

| 维度 | V8 | V9 |
|------|-----|-----|
| 阶段数量 | 7 | 5 |
| 阶段调用方式 | Stage 类 + 委托 | 直接方法调用 |
| 优化验证 | 分离两阶段 | Optimize 内迭代 |
| 产物目录 | 分散 | 各自阶段目录 |
| 诊断命令 | scan + branch | diagnose (init + parse) |

---

## 三、目录结构

### 3.1 文档目录 (`docs/`)

```
docs/
├── v9-design/
│   ├── README.md                      # V9 文档索引
│   ├── V9_ARCHITECTURE_OVERVIEW.md   # 本文件：架构总览
│   ├── V9_ARCHITECTURE.md            # 流水线各阶段详细逻辑
│   ├── V9_STAGE_API_CONTRACTS.md     # 阶段 API 契约
│   ├── V9_STAGE_DEV_GUIDE.md         # 各阶段独立开发示例
│   └── V9_DATA_CONTRACTS.md          # 数据契约定义
│
├── V8/                               # V8 架构文档
│   ├── V8_STAGES_OVERVIEW.md
│   └── STAGE_API_CONTRACTS.md
│
├── ARCHITECTURE.md                   # 主架构文档
├── QUICKSTART.md                     # 快速开始
├── INSTALL.md                        # 安装指南
├── CONFIG_NEW.md                     # 配置说明
├── MIGRATION.md                      # V8→V9 迁移指南
└── TROUBLESHOOTING.md               # 故障排查
```

### 3.2 代码目录 (`python/sqlopt/`)

```
python/sqlopt/
├── application/
│   ├── workflow_engine.py           # 核心工作流引擎
│   ├── workflow_v8.py              # V8/V9 兼容工作流
│   └── run_service.py              # Run 生命周期管理
│
├── stages/                          # 阶段实现（V9 使用直接调用）
│   ├── discovery/                   # [已废弃→Init]
│   ├── branching/                   # [已废弃→Parse]
│   ├── pruning/                    # [已废弃→Parse]
│   ├── baseline/                    # [已废弃→Recognition]
│   ├── optimize/
│   │   ├── execute_one.py          # 优化执行单元
│   │   ├── rule_engine.py          # 规则引擎
│   │   └── llm_optimizer.py       # LLM 优化器
│   ├── validate/                    # [已废弃→Optimize 迭代]
│   │   ├── execute_one.py
│   │   └── semantic_checker.py
│   └── patch/
│       ├── execute_one.py          # 补丁执行单元
│       ├── patch_generator.py      # 补丁生成器
│       └── apply.py                # 补丁应用
│
├── scripting/                       # 分支推断
│   ├── branch_generator.py          # 分支生成器
│   ├── sql_node.py                 # SQL 节点树
│   └── ast_utils.py                # AST 工具
│
├── commands/                        # CLI 命令
│   └── main.py
│
└── cli.py                          # CLI 入口
```

### 3.3 Run 产物目录

```
runs/<run_id>/
├── supervisor/
│   ├── meta.json                    # 运行元信息
│   ├── plan.json                   # 固定语句列表
│   ├── state.json                  # 阶段状态
│   └── results/                    # 各阶段结果
│
├── init/                           # [阶段1] Init
│   └── sql_units.json              # SQL 单元列表
│
├── parse/                          # [阶段2] Parse
│   ├── sql_units_with_branches.json # 带分支的 SQL 单元
│   └── risks.json                  # 风险检测结果
│
├── recognition/                     # [阶段3] Recognition
│   └── baselines.json              # 性能基线 (EXPLAIN 结果)
│
├── optimize/                       # [阶段4] Optimize
│   └── proposals.json              # 优化提案 (含验证状态)
│
├── patch/                         # [阶段5] Patch
│   └── patches.json               # 最终补丁
│
├── report.json                     # JSON 报告
├── report.md                       # Markdown 报告
└── report.summary.md              # 摘要报告
```

---

## 四、阶段依赖关系图

### 4.1 执行顺序图

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           V9 阶段依赖关系                                  │
└────────────────────────────────────────────────────────────────────────────┘

  Init
    │
    │ 产出: sql_units.json
    │
    ▼
  Parse ───────────────────────────────────────────────────────────────────┐
    │                                                                   │
    │ 产出: sql_units_with_branches.json + risks.json                    │
    │                                                                   │
    ▼                                                                   │
 Recognition ────────────────────────────────────────────────────────────┤
    │                                                                   │
    │ 产出: baselines.json                                               │
    │                                                                   │
    ▼                                                                   │
 Optimize ───────────────────────────────────────────────────────────────┤
    │                                                                   │
    │  (迭代验证循环)                                                    │
    │  ┌─────────────────────────────────────┐                          │
    │  │  加载候选 → 应用规则 → 语义验证   │                          │
    │  │       ↓         ↓                  │                          │
    │  │    通过？   失败重试               │                          │
    │  │       ↓         ↓                  │                          │
    │  │   接受提案 ← 候选+1 ─→ 达到最大   │                          │
    │  │                         迭代？     │                          │
    │  └─────────────────────────────────────┘                          │
    │                                                                   │
    │ 产出: proposals.json (validated=true 的提案)                       │
    │                                                                   │
    ▼                                                                   │
 Patch ─────────────────────────────────────────────────────────────────┘
    │
    │ 产出: patches.json
    │
    ▼
  结束
```

### 4.2 依赖矩阵

| 阶段 | Init | Parse | Recognition | Optimize | Patch |
|------|------|-------|------------|---------|-------|
| Init | - | ✅ | | | |
| Parse | 依赖 Init | - | ✅ | | |
| Recognition | | 依赖 Parse | - | ✅ | |
| Optimize | | | 依赖 Recognition | - | ✅ |
| Patch | | | | 依赖 Optimize | - |

---

## 五、数据契约概览

### 5.1 阶段契约总表

| 阶段 | 输入 Schema | 输出 Schema | 说明 |
|------|------------|------------|------|
| **Init** | - | `sqlunit.schema.json` | MyBatis XML 解析 |
| **Parse** | `sqlunit.schema.json` | `sqlunit.schema.json` (扩展) + `risks.schema.json` | 分支展开 + 风险检测 |
| **Recognition** | `sqlunit.schema.json` | `baseline_result.schema.json` | EXPLAIN 采集 |
| **Optimize** | `baseline_result.schema.json` | `optimization_proposal.schema.json` | 规则 + LLM + 验证 |
| **Patch** | `optimization_proposal.schema.json` | `patch_result.schema.json` | XML 补丁生成 |

### 5.2 契约文件位置

```
contracts/schemas/
├── sqlunit.schema.json              # SQL 单元定义
├── risks.schema.json                # 风险检测结果
├── baseline_result.schema.json      # 性能基线
├── optimization_proposal.schema.json # 优化提案
├── patch_result.schema.json         # 补丁结果
├── acceptance_result.schema.json    # 验证结果
├── run_report.schema.json          # 运行报告
└── ...                             # 其他契约
```

### 5.3 契约优先级

当代码行为与文档冲突时，按以下优先级处理：

1. `contracts/schemas/*.schema.json` (最高)
2. 当前代码实现 (`python/sqlopt/`)
3. 历史文档 (`docs/`)

---

## 六、CLI 命令参考

### 6.1 完整流程命令

```bash
# 验证配置
sqlopt-cli validate-config --config sqlopt.yml

# 执行完整流程 (阶段 1-5)
sqlopt-cli run --config sqlopt.yml

# 执行完整流程 (指定 SQL)
sqlopt-cli run --config sqlopt.yml --sql-key com.example.UserMapper.selectById
```

### 6.2 分阶段命令

```bash
# 诊断模式 (Init + Parse)
sqlopt-cli diagnose --config sqlopt.yml

# 仅 Init 阶段
sqlopt-cli run --config sqlopt.yml --stage init

# 仅 Parse 阶段
sqlopt-cli run --config sqlopt.yml --stage parse

# 仅 Recognition 阶段
sqlopt-cli recognition --config sqlopt.yml

# 仅 Optimize 阶段
sqlopt-cli run --config sqlopt.yml --stage optimize

# 仅 Patch 阶段
sqlopt-cli run --config sqlopt.yml --stage patch
```

### 6.3 状态与恢复命令

```bash
# 查看运行状态
sqlopt-cli status --run-id <run_id>

# 恢复中断的运行
sqlopt-cli resume --run-id <run_id>

# 查看优化建议
sqlopt-cli verify --run-id <run_id> --sql-key <sql_key>
```

### 6.4 补丁应用命令

```bash
# 应用补丁 (需确认)
sqlopt-cli apply --run-id <run_id>

# 应用补丁 (跳过确认)
sqlopt-cli apply --run-id <run_id> --force

# 仅预览补丁
sqlopt-cli apply --run-id <run_id> --dry-run
```

### 6.5 命令与阶段映射

| CLI 命令 | 执行阶段 | V9 支持 |
|---------|---------|---------|
| `sqlopt-cli run --config sqlopt.yml` | 1-5 全部 | ✅ |
| `sqlopt-cli run --config sqlopt.yml --stage <stage>` | 指定阶段 | ✅ |
| `sqlopt-cli diagnose` | 1-2 (init+parse) | ✅ |
| `sqlopt-cli recognition --config sqlopt.yml` | 3 | ✅ |
| `sqlopt-cli verify --run-id <id> --sql-key <key>` | 4 结果查询 | ✅ |
| `sqlopt-cli apply --run-id <id>` | 5 | ✅ |
| `sqlopt-cli status --run-id <id>` | - | ✅ |
| `sqlopt-cli resume --run-id <id>` | 断点恢复 | ✅ |

---

## 七、后续文档链接

### 7.1 V9 设计文档

| 文档 | 说明 |
|------|------|
| [V9_ARCHITECTURE.md](./V9_ARCHITECTURE.md) | 流水线各阶段详细处理逻辑 |
| [V9_STAGE_API_CONTRACTS.md](./V9_STAGE_API_CONTRACTS.md) | 阶段 API 契约、数据 Schema、JSON 示例 |
| [V9_STAGE_DEV_GUIDE.md](./V9_STAGE_DEV_GUIDE.md) | 各阶段独立开发演示示例 |
| [V9_DATA_CONTRACTS.md](./V9_DATA_CONTRACTS.md) | 数据契约定义、Schema、阶段接口 |

### 7.2 V8 参考文档

| 文档 | 说明 |
|------|------|
| [V8_STAGES_OVERVIEW.md](../V8/V8_STAGES_OVERVIEW.md) | V8 阶段总览与 Stage 架构 |
| [STAGE_API_CONTRACTS.md](../V8/STAGE_API_CONTRACTS.md) | V8 阶段 API 契约规范 |

### 7.3 核心参考文档

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | 主架构文档 |
| [QUICKSTART.md](../QUICKSTART.md) | 快速开始指南 |
| [CONFIG_NEW.md](../CONFIG_NEW.md) | 配置说明 |
| [MIGRATION.md](../MIGRATION.md) | V8→V9 迁移指南 |

---

## 八、关键概念

### 8.1 直接方法调用 vs Stage 委托

V9 采用直接方法调用模式：

```python
# V8 (Stage 委托模式)
stage = OptimizeStage()
result = stage.execute(context)

# V9 (直接方法调用)
from sqlopt.stages.optimize.execute_one import execute_one
result = execute_one(baseline_data, run_dir, config)
```

### 8.2 迭代式验证

V9 将 Validate 合并到 Optimize 阶段：

```python
# V9 Optimize 迭代流程
for iteration in range(max_iterations):
    # 1. 应用优化规则
    candidate = apply_rules(baseline)
    
    # 2. 语义验证
    validated = semantic_check(candidate)
    
    # 3. 通过则接受
    if validated:
        return candidate
    
# 4. 达到最大迭代，使用最佳候选
return best_candidate
```

### 8.3 产物目录隔离

V9 每个阶段产物存储在独立目录：

```
runs/<run_id>/
├── init/sql_units.json          # Init 产出
├── parse/sql_units_with_branches.json  # Parse 产出
├── parse/risks.json             # Parse 风险产出
├── recognition/baselines.json   # Recognition 产出
├── optimize/proposals.json      # Optimize 产出
└── patch/patches.json          # Patch 产出
```

---

*本文档最后更新：2026-03-20*
