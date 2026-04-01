# SQL Optimizer 当前规格

本文档只描述当前实现的稳定边界。更细的内部实现以代码和 `contracts/**/*.schema.json` 为准。

## 1. 系统目标

SQL Optimizer 用于扫描 MyBatis XML mapper，生成 SQL 优化候选，做数据库验证，并输出可审阅的 XML patch。

支持平台：
- PostgreSQL
- MySQL 5.6+

不支持：
- MariaDB

## 2. 主流程

固定阶段顺序：

`preflight -> scan -> optimize -> validate -> patch_generate -> report`

阶段约束：
- 阶段之间只通过 run 目录产物衔接
- 阶段输出必须是结构化 JSON/JSONL
- 除 `report` 外，已完成阶段默认不重跑
- 动态模板 statement 不允许直接用扁平 SQL 覆盖 XML

## 3. CLI 与运行语义

统一入口：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py <command>
```

稳定命令：
- `run`
- `status`
- `resume`
- `verify`
- `apply`

运行语义：
- `run` 默认推进到主流程结束
- `resume` 在同一 `run_id` 上继续推进
- `status.next_action=report-rebuild` 表示主流程已完成，仅需重建 `report.json`
- `status/resume/apply` 省略 `--run-id` 时默认选择最新 run

## 4. Run 目录

当前唯一 canonical layout：

```text
runs/<run-id>/
├── report.json
├── control/
│   ├── state.json
│   ├── plan.json
│   └── manifest.jsonl
├── artifacts/
│   ├── scan.jsonl
│   ├── fragments.jsonl
│   ├── proposals.jsonl
│   ├── acceptance.jsonl
│   └── patches.jsonl
└── sql/
    ├── catalog.jsonl
    └── <sql-key>/
        └── index.json
```

职责边界：
- `control/state.json`：唯一运行状态源
- `control/plan.json`：固定输入计划与 resolved config
- `control/manifest.jsonl`：执行历史事件流
- `report.json`：极简摘要，不驱动恢复逻辑
- `artifacts/*.jsonl`：阶段直接输出，可删除后重算
- `sql/*`：SQL 下钻导航，不定义运行状态

## 5. 核心契约

稳定主干：
- `SqlUnit`
- `FragmentRecord`
- `OptimizationProposal`
- `AcceptanceResult`
- `PatchResult`
- `RunReport`

对应 schema：
- `contracts/stages/sqlunit.schema.json`
- `contracts/stages/fragment_record.schema.json`
- `contracts/stages/optimization_proposal.schema.json`
- `contracts/stages/acceptance_result.schema.json`
- `contracts/stages/patch_result.schema.json`
- `contracts/run/run_report.schema.json`

原则：
- schema 是最高优先级
- 对外稳定契约只做加法兼容
- 不允许同名字段换语义

## 6. 阶段输出

`scan`
- 输出 `artifacts/scan.jsonl`
- 可选输出 `artifacts/fragments.jsonl`
- 同时保留 `templateSql` 和 `sql` 两种视图

`optimize`
- 输出 `artifacts/proposals.jsonl`
- 只产出优化候选，不直接产出 XML patch

`validate`
- 输出 `artifacts/acceptance.jsonl`
- 写入语义、性能、安全判断，以及补丁可交付判定

`patch_generate`
- 输出 `artifacts/patches.jsonl`
- 优先消费 validate 已选定的 patch 目标

`report`
- 输出顶层 `report.json`
- 输出 `sql/catalog.jsonl` 和 `sql/<sql-key>/index.json`

## 7. Verification

verification 不再有独立 ledger 目录。

当前规则：
- verification 记录嵌入阶段产物本身
- `verify` 命令按 run 目录和阶段产物组装证据链
- `report.json` 只保留摘要和 blocker，不保留大列表

## 8. 配置边界

用户配置根键：
- `config_version`
- `project`
- `scan`
- `db`
- `llm`
- `report`

已移除的旧根键会被忽略，不再作为公开配置边界：
- `validate`
- `policy`
- `apply`
- `patch`
- `diagnostics`
- `runtime`
- `verification`

更多字段说明见 [CONFIG.md](CONFIG.md)。

## 9. 失败与恢复

失败分类：
- `fatal`
- `retryable`
- `degradable`

恢复约束：
- 已完成 statement 不重复执行
- 失败 statement 可在 `resume` 中继续推进
- `report` 是唯一允许重建的阶段

## 10. 重要约束

1. 阶段不能直接互调，只能通过 orchestrator 和 run 目录衔接。
2. 所有输出都必须是结构化对象，不能只产出自然语言结论。
3. 模板级 patch 必须以 template-aware 路径落地，不能用扁平 SQL 直接覆盖动态 XML。
4. `report.json` 只做摘要，不再承担索引和排障账本职责。
