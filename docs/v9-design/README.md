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
sqlopt-cli diagnose --config sqlopt.yml

# 单阶段执行
sqlopt-cli run --config sqlopt.yml --stage optimize

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

## 开发状态

| 组件 | 状态 | 说明 |
|------|------|------|
| `workflow_v8.py` | ✅ 完成 | 支持 V9 5阶段，直接方法调用 |
| `run_paths.py` | ✅ 完成 | 添加 init/, parse/, recognition/ 目录 |
| `contracts.py` | ✅ 完成 | 更新 STAGE_BOUNDARIES |
| `cli/main.py` | ✅ 完成 | cmd_diagnose 更新为 init + parse |
| Stage 类扁平化 | ✅ 完成 | OptimizeStage, PatchStage 已扁平化 |
| V8 死代码清理 | ✅ 完成 | 删除 _run_discovery 等死方法 |
| `risks.schema.json` | ✅ 完成 | 已创建风险检测 Schema |
| DiscoveryStage | ✅ 已移除 | 不再导出，仅代码保留 |
| 单元测试 | ✅ 完成 | 测试通过 |

---

## 文档状态

| 文档 | 状态 | 说明 |
|------|------|------|
| V9_ARCHITECTURE_OVERVIEW.md | ✅ 完成 | 架构总览、与 V8 对比、目录结构 |
| V9_STAGE_API_CONTRACTS.md | ✅ 完成 | 阶段 API 契约、数据 Schema、JSON 示例 |
| V9_STAGE_DEV_GUIDE.md | ✅ 完成 | 各阶段独立开发演示示例 |

---

*最后更新：2026-03-20*
