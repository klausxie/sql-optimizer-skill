# SQL Optimizer 快速入门（15 分钟）

目标：在项目里完成一轮可恢复的 SQL 优化运行，并拿到报告与补丁。

## 1. 前置条件

- Python 3.9+
- MyBatis XML mapper 文件
- 数据库（PostgreSQL 或 MySQL 5.6+）  
  仅安装链路 smoke 时可先使用离线配置（`llm.provider=opencode_builtin`）

## 2. 安装并自检

```bash
python3 install/install_skill.py
python3 install/install_skill.py --verify
python3 install/doctor.py --project .
```

如果 `sqlopt-cli` 不可用，先按 `install_skill.py --verify` 输出修复 PATH。

## 3. 准备最小配置

在项目根目录创建或确认 `sqlopt.yml`：

```yaml
project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:pass@127.0.0.1:5432/db?sslmode=disable

llm:
  enabled: true
  provider: opencode_run
```

离线 smoke 推荐：

```yaml
llm:
  enabled: true
  provider: opencode_builtin
```

## 4. 跑通主流程

```bash
sqlopt-cli validate-config --config sqlopt.yml
sqlopt-cli run --config sqlopt.yml
sqlopt-cli status
```

说明：
- `validate-config` 会同时检查 `db.dsn`、mapper 命中情况，以及数据库是否可连。
- `run` 默认持续推进到完成（除非失败/中断）。
- `status/resume/apply` 省略 `--run-id` 时会自动选择最新 run。

如果 `status.next_action=report-rebuild`：

```bash
sqlopt-cli run --config sqlopt.yml --to-stage report --run-id <run-id>
```

## 4.1 架构说明：CLI 与 Skill 分工

SQL Optimizer 采用 CLI + Skill 双层架构，V8 七阶段流水线：

- **CLI (sqlopt-cli)**：负责工程化能力
  - Discovery：连接数据库、采集表结构、解析 XML
  - Branching：分支展开（3种策略）
  - Pruning：静态分析、风险标记、聚合剪枝
  - Baseline：EXPLAIN、采集性能基线
  - Validate：语义验证、性能对比、结果集验证
  - Patch：生成补丁、用户确认、应用补丁

- **Skill**：负责 AI/LLM 能力
  - Optimize：调用 LLM 生成优化建议
  - 读取 CLI 输出的 prompt
  - 做出优化决策

完整流程：CLI Discovery → CLI Branching → CLI Pruning → CLI Baseline → Skill Optimize → CLI Validate → CLI Patch

## 5. 查看产物并应用补丁

```bash
sqlopt-cli status --run-id <run-id>
cat runs/<run-id>/overview/report.summary.md
cat runs/<run-id>/overview/report.md
sqlopt-cli apply --run-id <run-id>
```

重点产物：
- `runs/<run-id>/supervisor/state.json`
- `runs/<run-id>/report.json`
- `runs/<run-id>/report.summary.md`（摘要）
- `runs/<run-id>/report.md`（详细版）
- `runs/<run-id>/patches/`

## 6. 常见分支

- 只想先验证扫描（Discovery 阶段）：

```bash
sqlopt-cli run --config sqlopt.yml --to-stage discovery
```

- 只知道方法名，不知道完整 key：

```bash
sqlopt-cli run --config sqlopt.yml --sql-key findUsers
```

`--sql-key` 支持完整 `sqlKey`、`namespace.statementId`、`statementId`、`statementId#vN`；如果一个方法名匹配多个 SQL，CLI 会返回候选 full key。

- MySQL 方言边界（例如 `ILIKE`）不会自动兼容；语法问题会在 report 的 warnings 体现。

## 7. 下一步文档

- 安装细节：[`INSTALL.md`](INSTALL.md)
- 故障排查：[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
- 配置约定：[`project/05-config-and-conventions.md`](project/05-config-and-conventions.md)
- 命令与状态机：[`project/03-workflow-and-state-machine.md`](project/03-workflow-and-state-machine.md)
