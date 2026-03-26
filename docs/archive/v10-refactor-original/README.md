# V10 重构计划

> SQL Optimizer V10 五阶段架构重构

---

## 📁 目录结构

```
v10-refactor/
├── README.md              # 本文件 - 总索引
├── SUMMARY.md             # 简要总结
├── ARCHITECTURE.md        # 总体架构设计
├── EXECUTION_PLAN.md      # 🚀 执行计划（空壳先行）
├── MIGRATION.md           # 代码迁移计划（核心逻辑后续迁移）
├── TEST_DESIGN.md         # 测试设计文档
├── STANDARDS.md           # Python 代码规范 (ruff + mypy)
│
├── STAGES/                # 各阶段详细设计
│   ├── init.md           # Init 阶段：扫描 XML，提取 SQL 单元
│   ├── parse.md          # Parse 阶段：展开动态标签，检测风险
│   ├── recognition.md     # Recognition 阶段：EXPLAIN 采集性能基线
│   ├── optimize.md        # Optimize 阶段：生成优化建议（含验证）
│   └── result.md         # Result 阶段：汇总输出（Patch 或 Report）
│
├── COMMON/                # 公共模块
│   └── overview.md        # Common 模块总览
│
└── CONTRACTS/            # 数据契约
    ├── overview.md        # 契约总览
    └── data-flow.md       # 阶段间数据流详解
```

---

## 🎯 快速导航

### 🚀 想开始实施？先看执行计划！
→ [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) - **空壳先行，逻辑后填**

### 想了解整体架构？
→ [ARCHITECTURE.md](./ARCHITECTURE.md)

### 想了解某个阶段的具体实现？
→ [STAGES/init.md](./STAGES/init.md) 等

### 想了解数据怎么在阶段间传递？
→ [CONTRACTS/data-flow.md](./CONTRACTS/data-flow.md)

### 想了解哪些代码可以共享？
→ [COMMON/overview.md](./COMMON/overview.md)

### 想了解哪些代码需要迁移/重写？
→ [MIGRATION.md](./MIGRATION.md)

### 想了解测试策略？
→ [TEST_DESIGN.md](./TEST_DESIGN.md)

### 想了解 Python 代码规范？
→ [STANDARDS.md](./STANDARDS.md) - **必读！ruff + mypy 配置**

### 想开始写代码？
→ [EXECUTION_PLAN.md](./EXECUTION_PLAN.md)

---

## 🔑 核心理念

1. **阶段自治** - 每个阶段代码放自己目录，不与其他阶段混在一起
2. **契约驱动** - 阶段间通过 JSON 契约传递数据，不直接调用
3. **严格审计** - Common 只放被 2+ 阶段使用的代码
4. **CLI 简洁** - 用户只需指定配置和起始阶段

---

## 📋 CLI 设计

```bash
# 完整流程
sqlopt run --config sqlopt.yml

# 从指定阶段开始
sqlopt run --config sqlopt.yml init
sqlopt run --config sqlopt.yml parse
sqlopt run --config sqlopt.yml recognition
sqlopt run --config sqlopt.yml optimize
sqlopt run --config sqlopt.yml result
```

---

*最后更新：2026-03-23*
