# V9 Design Documentation

> SQL Optimizer V9 架构设计文档索引

---

## 文档列表

| 文档 | 说明 |
|------|------|
| [V9_ARCHITECTURE_OVERVIEW.md](./V9_ARCHITECTURE_OVERVIEW.md) | 架构总览、与 V8 对比、目录结构 |
| [V9_ARCHITECTURE.md](./V9_ARCHITECTURE.md) | 流水线各阶段详细处理逻辑 |
| [V9_STAGE_API_CONTRACTS.md](./V9_STAGE_API_CONTRACTS.md) | 阶段 API 契约、数据 Schema、JSON 示例 |
| [V9_STAGE_DEV_GUIDE.md](./V9_STAGE_DEV_GUIDE.md) | 各阶段独立开发演示示例 |
| [V9_DATA_CONTRACTS.md](./V9_DATA_CONTRACTS.md) | 数据契约定义、Schema、阶段接口 |
| [V9_CLOSURE_PLAN.md](./V9_CLOSURE_PLAN.md) | V9 收口计划、阶段性开发路线图 |

---

## 快速参考

### V9 流水线 (5 阶段)

```
Init → Parse → Recognition → Optimize → Patch
```

| 阶段 | 输入 | 输出 | 核心功能 |
|------|------|------|----------|
| **Init** | MyBatis XML | `init/sql_units.json` | XML解析、SQL提取 |
| **Parse** | `sql_units.json` | `parse/sql_units_with_branches.json`, `parse/risks.json` | 分支展开+风险检测 |
| **Recognition** | 分支SQL | `recognition/baselines.json` | EXPLAIN采集，性能基线 |
| **Optimize** | `baselines.json` | `optimize/proposals.json` | 优化+验证(迭代循环) |
| **Patch** | `proposals.json` | `patch/patches.json` | XML补丁生成 |

### CLI 命令

```bash
# 完整流程
sqlopt-cli run --config sqlopt.yml

# 诊断模式 (init + parse)
sqlopt-cli run --config sqlopt.yml --to-stage parse

# 单阶段执行
sqlopt-cli run --config sqlopt.yml --to-stage optimize

# 状态查看
sqlopt-cli status --run-id <run_id>

# 恢复执行
sqlopt-cli resume --run-id <run_id>

# 应用补丁
sqlopt-cli apply --run-id <run_id>
```

### 目录结构

```
runs/<run_id>/
├── init/
│   └── sql_units.json
├── parse/
│   ├── sql_units_with_branches.json
│   └── risks.json
├── recognition/
│   └── baselines.json
├── optimize/
│   └── proposals.json
└── patch/
    └── patches.json
```

---

## 与 V8 对比

| V8 | V9 | 变更 |
|-----|-----|------|
| Discovery (7) | Init | 重命名 |
| Branching (7) + Pruning (7) | Parse | 合并 |
| Baseline | Recognition | 重命名 |
| Optimize (7) + Validate (7) | Optimize | 合并为迭代 |
| Patch | Patch | 不变 |

**V8**: 7 阶段  
**V9**: 5 阶段

---

## 开发状态（按当前代码收敛情况）

| 组件 | 状态 | 说明 |
|------|------|------|
| `workflow_v9.py` | ✅ 主干完成 | 已作为默认 workflow engine 导出 |
| `v9_stages/runtime.py` | ✅ 已落地 | 阶段可独立绑定和单独执行 |
| `contracts.py` | ✅ 已更新 | V9 边界与多 Schema 校验已接入 |
| `cli/main.py` | ⚠️ 收口中 | 主流程已 V9 化，但仍有旧命令/帮助语义残留 |
| `run_paths.py` | ⚠️ 收口中 | 仍保留 deprecated legacy 路径常量与 alias |
| `status_resolver.py` | ✅ 主路径已收口 | V9 状态解析已收敛为 `resume / none` |
| `risks.schema.json` | ✅ 已创建 | Parse 风险输出已具备独立 Schema |
| 单元测试 | ✅ 持续补强 | 已覆盖 V9 workflow、runtime、contracts 等关键模块 |

---

## 文档状态

| 文档 | 状态 | 说明 |
|------|------|------|
| V9_ARCHITECTURE_OVERVIEW.md | ✅ 完成 | 架构总览、与 V8 对比、目录结构 |
| V9_STAGE_API_CONTRACTS.md | ✅ 完成 | 阶段 API 契约、数据 Schema、JSON 示例 |
| V9_STAGE_DEV_GUIDE.md | ✅ 完成 | 各阶段独立开发演示示例 |

---

*最后更新：2026-03-20*
