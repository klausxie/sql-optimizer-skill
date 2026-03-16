# SQL Optimizer 功能全景图

> 最后更新: 2026-03-16

本文档描述 SQL Optimizer 的完整功能架构和执行流程。

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SQL Optimizer                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │   MyBatis   │───▶│  sqlopt-cli │───▶│   报告与    │                  │
│  │  Mapper XML │    │   (Python)  │    │   补丁      │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│                              │                 ▲                           │
│                              ▼                 │                           │
│                       ┌─────────────┐          │                           │
│                       │   Database  │──────────┘                           │
│                       │ (PostgreSQL │                                          │
│                       │    MySQL)   │                                          │
│                       └─────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. CLI 命令

| 命令 | 功能 | 典型用法 |
|------|------|----------|
| `validate-config` | 验证配置文件和数据库连通性 | `sqlopt-cli validate-config --config sqlopt.yml` |
| `run` | 从头开始执行优化流程（自动包含配置验证） | `sqlopt-cli run --config sqlopt.yml` |
| `resume` | 继续已中断的运行 | `sqlopt-cli resume --run-id <run-id>` |
| `status` | 查看当前运行状态 | `sqlopt-cli status --run-id <run-id>` |
| `apply` | 应用生成的补丁 | `sqlopt-cli apply --run-id <run-id>` |

> **注意**: `run` 命令会在开头自动执行配置验证（等效于 `validate-config`），无需单独运行验证命令。

### 命令选项

- `--config`: 配置文件路径 (默认: `sqlopt.yml`)
- `--run-id`: 指定运行 ID
- `--to-stage`: 目标阶段 (diagnose/optimize/validate/apply/report)
- `--sql-key`: 指定 SQL key (支持完整 key / namespace.statementId / statementId / statementId#vN)
- `--mapper-path`: 指定 mapper 文件路径
- `--max-steps`: 最大步数限制
- `--max-seconds`: 最大时间限制
- `--force` (apply): 强制应用补丁，无需确认

---

## 3. 阶段流水线 (真实架构)

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌────────┐
│ Diagnose │──▶│Optimize │──▶│Validate │──▶│ Apply   │──▶│ Report │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └────────┘
    │            │            │              │               │
    ▼            ▼            ▼              ▼               ▼
┌──────┐   ┌──────┐   ┌────────┐    ┌───────────┐    ┌─────────┐
│诊断SQL│   │LLM   │   │语义验证│    │生成补丁   │    │生成报告 │
│分支   │   │优化建议│   │+性能  │    │文件       │    │+风险   │
└──────┘   └──────┘   └────────┘    └───────────┘    └─────────┘
```

> **注意**: preflight 阶段已移除，配置验证已合并到 run 命令开头自动执行。

### 阶段详解

| 阶段 | 输入 | 输出 | 功能 |
|------|------|------|------|
| **Diagnose** | Mapper XML | SQL单元 | 扫描 MyBatis XML 中的 SQL 语句，分析分支 |
| **Optimize** | SQL单元 | 优化建议 | 通过 LLM 生成优化建议 |
| **Validate** | 优化建议 | 验证结果 | 数据库语义验证 + 性能对比 |
| **Apply** | 验证结果 | 补丁文件 | 生成可应用的 XML 补丁 |
| **Report** | 所有阶段结果 | 报告 | 生成汇总报告和风险评估 |

---

## 4. 核心模块

### 4.1 命令行入口
- `cli.py`: CLI 命令解析和路由

### 4.2 应用层
- `workflow_engine.py`: 工作流引擎，阶段编排
- `run_service.py`: Run 生命周期管理
- `run_repository.py`: Run 状态持久化
- `config_service.py`: 配置加载验证

### 4.3 阶段处理
- `diagnose.py`: SQL 扫描与分支诊断
- `optimize.py`: LLM 优化建议生成
- `validate.py`: 语义验证
- `apply.py`: 补丁生成
- `report.py` / `report_*.py`: 报告生成

### 4.4 脚本 (新增)
- `scripting/branch_generator.py`: 分支推断
- `scripting/sql_node.py`: SQL 节点树

### 4.5 性能基线 (新增)
- `baseline/baseline_service.py`: 性能基线采集

---

## 5. 数据流与产物

### Run 目录结构

```
runs/<run_id>/
├── supervisor/
│   ├── meta.json         # 运行元信息
│   ├── plan.json         # 固定语句列表
│   ├── state.json        # 阶段状态
│   └── results/          # 步骤结果
├── scan.sqlunits.jsonl   # 扫描产物
├── proposals/            # 优化建议
├── acceptance/           # 验证结果
├── patches/             # 补丁产物
├── verification/         # 验证证据链
├── report.json           # JSON 报告
├── report.md             # Markdown 报告
└── report.summary.md     # 摘要报告
```

---

## 6. 配置结构

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql  # 或 mysql
  dsn: postgresql://user:pass@host:5432/db

llm:
  enabled: true
  provider: opencode_run

apply:
  mode: PATCH_ONLY  # 或 APPLY_IN_PLACE
```

---

## 7. 支持的数据库

| 数据库 | 支持版本 | 特殊限制 |
|--------|----------|----------|
| PostgreSQL | 全部 | 无 |
| MySQL | 5.6+ | 不支持 MariaDB |

---

## 8. 风险标记

| 风险类型 | 模式 | 风险等级 |
|----------|------|----------|
| `prefix_wildcard` | `'%'+name+'%'` | 高 |
| `suffix_wildcard_only` | `name+'%'` | 低 |
| `concat_wildcard` | `CONCAT('%',name)` | 高 |
| `function_wrap` | `UPPER(name)` | 中 |

### 数据量感知

规则严重级别会根据表的数据量自动调整：

| 数据量 | FULL_SCAN 风险 |
|--------|----------------|
| < 1000 行 | 跳过 |
| 1000-10000 行 | info |
| > 10000 行 | warn |

---

## 9. 失败原因码

### 验证阶段

| 原因码 | 含义 | 严重级别 |
|--------|------|----------|
| `VALIDATE_SEMANTIC_ERROR` | SQL 语义错误 | fatal |
| `VALIDATE_EQUIVALENCE_MISMATCH` | 语义不等价 | fatal |
| `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION` | 安全：$ 替换 | fatal |
| `VALIDATE_PERF_NOT_IMPROVED_WARN` | 性能未改进 | warn |

### 其他

| 原因码 | 含义 |
|--------|------|
| `DB_CONNECTION_FAILED` | 数据库连接失败 |
| `PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS` | 补丁语义验证未通过 |
| `NEED_MORE_PARAMS` | 需要更多参数 |

---

## 10. 快速开始

```bash
# 1. 验证配置
sqlopt-cli validate-config --config sqlopt.yml

# 2. 运行优化
sqlopt-cli run --config sqlopt.yml

# 3. 查看状态
sqlopt-cli status --run-id <run-id>

# 4. 应用补丁
sqlopt-cli apply --run-id <run-id>
```

---

## 11. 已知限制

1. MySQL 5.6 不支持 `MAX_EXECUTION_TIME`
2. PostgreSQL 方言 (如 `ILIKE`) 不会自动转换 MySQL
3. 模板级补丁需要 `rewriteMaterialization.replayVerified=true`

---

## 12. 相关文档

- [快速入门](QUICKSTART.md)
- [安装指南](INSTALL.md)
- [故障排查](TROUBLESHOOTING.md)
- [系统规格](project/02-system-spec.md)
- [工作流与状态机](project/03-workflow-and-state-machine.md)
- [数据契约](project/04-data-contracts.md)
