# V10 重构：代码迁移计划

> **设计文档** - 仅设计，不实现
>
> 本文档定义从 `ai/refactor-stage-modules` 分支到 V10 架构的代码迁移策略

---

## 1. 迁移原则

| 原则 | 说明 |
|------|------|
| **质量优先** | 只迁移高质量、可维护的代码 |
| **重写简单代码** | 简单代码不迁移，直接重写更高效 |
| **架构匹配** | 迁移时必须适配 V10 五阶段架构 |
| **渐进迁移** | 逐模块迁移，每步可独立验证 |

---

## 2. 代码质量评估标准

### 2.1 适合迁移的代码特征

- ✅ 逻辑复杂，编写困难（如：分支推理、语义等价判断）
- ✅ 经过充分测试，有 80%+ 覆盖率
- ✅ 没有已知 bug 或技术债务
- ✅ 与 V10 架构模块边界清晰

### 2.2 适合重写的代码特征

- ⚠️ 代码简单，逻辑少于 100 行
- ⚠️ 没有测试或测试覆盖率低
- ⚠️ 与旧架构耦合严重，迁移成本高
- ⚠️ 已有更好的实现方式

---

## 3. 可迁移代码清单

### 3.1 高优先级迁移（推荐迁移）

| 模块 | 源文件 | 目标位置 | 迁移理由 |
|------|--------|----------|----------|
| **分支推理引擎** | `stages/branching/branch_generator.py` | `python/sqlopt/stages/recognition/` | 核心算法复杂，重写风险高 |
| **分支策略** | `stages/branching/branch_strategy.py` | `python/sqlopt/stages/recognition/` | 与 branch_generator 紧耦合 |
| **表达式求值器** | `stages/branching/expression_evaluator.py` | `python/sqlopt/stages/recognition/` | 分支条件判断核心组件 |
| **LLM Provider** | `llm/provider.py` | `python/sqlopt/common/llm.py` | 多 stage 共用，必须复用 |
| **LLM Mock 生成器** | `llm/mock_generator.py` | `python/sqlopt/common/llm_mock_generator.py` | 测试基础设施 |

### 3.2 中优先级迁移（选择性迁移）

| 模块 | 源文件 | 目标位置 | 迁移理由 | 建议 |
|------|--------|----------|----------|------|
| **语义等价判断** | `platforms/sql/semantic_equivalence.py` | `python/sqlopt/stages/optimize/` | 优化阶段核心组件 | 评估复杂度后决定 |
| **候选生成器** | `platforms/sql/candidate_generation_v2.py` | `python/sqlopt/stages/optimize/` | 与 semantic_equivalence 配合 | 如已稳定则迁移 |
| **片段注册表** | `stages/branching/fragment_registry.py` | `python/sqlopt/stages/recognition/` | 分支推理辅助 | 可选，看依赖复杂度 |

### 3.3 不建议迁移（重写）

| 模块 | 源文件 | 原因 | 替代方案 |
|------|--------|------|----------|
| **V9 Stage 实现** | `application/v9_stages/*.py` | 架构不兼容，耦合严重 | 重写为 V10 架构 |
| **旧 Config 处理** | `application/config*.py` | V10 采用新配置格式 | 按需重写 |
| **简单工具函数** | `utils/*.py` | 代码简单直接重写 | V10 common 模块实现 |

---

## 4. V10 目标结构映射

```
python/sqlopt/
├── common/                      # Common 模块（2+ stage 共用）
│   ├── __init__.py
│   ├── config.py               # 配置加载（重写）
│   ├── errors.py              # 错误定义（重写）
│   ├── progress.py            # 进度跟踪（重写）
│   ├── run_paths.py           # 路径管理（重写）
│   ├── contracts.py            # 数据契约（重写）
│   ├── db_connector.py        # 数据库连接（重写）
│   ├── llm.py                  # ← 迁移自 llm/provider.py
│   └── llm_mock_generator.py  # ← 迁移自 llm/mock_generator.py
│
├── stages/                      # 各阶段代码（每阶段独立目录）
│   ├── init/                   # Init 阶段
│   │   ├── __init__.py
│   │   ├── stage.py           # 阶段入口（重写）
│   │   └── ...
│   │
│   ├── parse/                 # Parse 阶段
│   │   ├── __init__.py
│   │   ├── stage.py
│   │   └── ...
│   │
│   ├── recognition/            # Recognition 阶段
│   │   ├── __init__.py
│   │   ├── stage.py
│   │   ├── branch_generator.py    # ← 迁移自 stages/branching/
│   │   ├── branch_strategy.py      # ← 迁移自 stages/branching/
│   │   ├── expression_evaluator.py # ← 迁移自 stages/branching/
│   │   ├── fragment_registry.py    # ← 可选迁移
│   │   └── ...
│   │
│   ├── optimize/              # Optimize 阶段
│   │   ├── __init__.py
│   │   ├── stage.py
│   │   ├── semantic_equivalence.py # ← 可迁移自 platforms/sql/
│   │   ├── candidate_generation.py # ← 可迁移自 platforms/sql/
│   │   └── ...
│   │
│   └── result/                # Result 阶段
│       ├── __init__.py
│       ├── stage.py
│       └── ...
│
├── cli/                        # CLI 模块
│   ├── __init__.py
│   └── main.py                # 入口点（重写）
│
└── sqlopt.py                  # 包入口（重写）
```

---

## 5. 迁移执行顺序

### Wave 1: 基础设施迁移

```
1. 创建 common/llm.py
   源: ai/refactor-stage-modules/llm/provider.py
   任务: 适配 V10 配置格式，提取为通用 Provider

2. 创建 common/llm_mock_generator.py
   源: ai/refactor-stage-modules/llm/mock_generator.py
   任务: 适配 V10 contracts

3. 创建 common/config.py, errors.py, progress.py
   任务: 重写（简单模块，直接实现）
```

### Wave 2: Recognition 阶段核心迁移

```
4. 创建 stages/recognition/branch_generator.py
   源: ai/refactor-stage-modules/stages/branching/branch_generator.py
   任务: 迁移核心逻辑，保持接口不变

5. 创建 stages/recognition/branch_strategy.py
   源: ai/refactor-stage-modules/stages/branching/branch_strategy.py
   任务: 与 branch_generator 一起迁移

6. 创建 stages/recognition/expression_evaluator.py
   源: ai/refactor-stage-modules/stages/branching/expression_evaluator.py
   任务: 分支条件表达式求值器
```

### Wave 3: Optimize 阶段可选迁移

```
7. 评估 platforms/sql/semantic_equivalence.py
   任务: 分析代码质量，决定迁移或重写

8. 如迁移: 创建 stages/optimize/semantic_equivalence.py
   任务: 适配 V10 contracts 接口
```

### Wave 4: 阶段实现与集成

```
9. 实现各阶段 stage.py
   任务: 基于 V10 架构重写，使用迁移的组件

10. 实现 CLI
    任务: sqlopt run <stage> 命令
```

---

## 6. 迁移质量门控

| 阶段 | 门控标准 | 验证方式 |
|------|----------|----------|
| **迁移前** | 源代码有测试覆盖 | 查看覆盖率报告 |
| **迁移中** | 保持原有接口不变 | 运行原有测试 |
| **迁移后** | 新位置测试通过 | 执行 pytest |
| **集成后** | V10 架构集成测试通过 | 端到端测试 |

---

## 7. 迁移检查清单

### 7.1 代码层面

- [ ] 源文件读取并理解
- [ ] 依赖关系分析（被谁引用，引用谁）
- [ ] 接口契约确认
- [ ] 测试覆盖确认
- [ ] V10 目标位置确定

### 7.2 架构层面

- [ ] 适配 V10 contracts
- [ ] 使用 common 模块而非重复实现
- [ ] 阶段边界清晰
- [ ] 无循环依赖

### 7.3 测试层面

- [ ] 原有测试迁移
- [ ] 新位置测试通过
- [ ] 集成测试设计

---

## 8. 不迁移代码的处理

对于明确不迁移的代码：

| 类别 | 处理方式 |
|------|----------|
| **V9 Stage 实现** | 归档到 `archive/v9_stages/` |
| **废弃工具函数** | 删除，不保留 |
| **旧配置文件** | 迁移到 V10 格式后删除 |

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 迁移破坏现有功能 | 高 | 保持接口不变，迁移后运行全量测试 |
| 架构不匹配 | 中 | 分阶段迁移，每步可回滚 |
| 依赖缺失 | 低 | 迁移前完整分析依赖图 |

---

## 10. 总结

### 迁移范围

| 类别 | 数量 | 比例 |
|------|------|------|
| **迁移** | 5-7 个核心模块 | ~30% |
| **重写** | 10+ 个模块 | ~70% |

### 迁移原则

1. **复杂逻辑迁移**：分支推理、LLM Provider 等核心算法
2. **简单代码重写**：配置、错误处理、工具函数等
3. **V9 Stage 不迁移**：架构差异太大，重写更高效

### 下一步行动

1. 按 Wave 1-4 顺序执行迁移
2. 每步迁移后运行测试验证
3. 集成测试在所有迁移完成后执行
