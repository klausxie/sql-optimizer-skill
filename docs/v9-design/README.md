# V9 Design Documentation

> SQL Optimizer V9 架构设计文档索引

---

## 文档列表

| 文档 | 说明 |
|------|------|
| [V9_ARCHITECTURE.md](./V9_ARCHITECTURE.md) | 整体架构概览、流程图、各阶段职责 |
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
| `workflow_v8.py` | ✅ 完成 | 支持 V9 5阶段 |
| `run_paths.py` | ✅ 完成 | 添加 init/, parse/ 目录 |
| `contracts.py` | ✅ 完成 | 更新 STAGE_BOUNDARIES |
| `cli/main.py` | ✅ 完成 | cmd_diagnose 更新 |
| Stage 类 | ⚠️ 待更新 | 需要重命名/合并 |
| 单元测试 | ⚠️ 待更新 | 需要适配新阶段名 |

---

## 下一步

1. [ ] 更新 `stages/` 目录下的 Stage 类名和依赖
2. [ ] 更新 `contracts/schemas/` 中的 schema 文件
3. [ ] 编写 V9 单元测试
4. [ ] 更新 README.md 中的架构图

---

*最后更新：2026-03-20*
