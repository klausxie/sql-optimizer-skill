# SQL Optimize 重构交接文档

本目录用于把当前项目的有效需求与可验证规格，整理为可直接交接给下一位开发者的重构输入。

## 🚀 快速开始

**新用户？** 查看 [快速入门指南](docs/QUICKSTART.md) - 10 分钟完成首次运行

**查找文档？** 访问 [文档导航](docs/INDEX.md) - 按角色和主题查找所需文档

**开发验证？** 在仓库根目录直接运行 `python3 -m pytest -q`

**数据库平台？** 当前一等支持 `postgresql` 与 `mysql`（MySQL 5.6+，含 5.7、8.0+，不含 MariaDB）
**MySQL 方言边界？** 若 SQL 或候选带 PostgreSQL 方言（如 `ILIKE`），当前不会自动兼容，会在 optimize DB evidence 阶段按语法错误处理，并以 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR` 暴露到 report / verify

**扫描覆盖验证？** 直接运行
`python3 scripts/run_until_budget.py --config tests/fixtures/project/sqlopt.scan.local.yml --to-stage scan --max-steps 10 --max-seconds 30`

## 📖 文档定位

- 面向"完全重写"而非"在旧代码上小修小补"。
- 目标规格优先，当前实现仅作为事实基线与差距参考。

## 📚 阅读顺序

1. `docs/QUICKSTART.md` - **从这里开始！**
2. `docs/project/01-product-requirements.md`
3. `docs/project/02-system-spec.md`
4. `docs/project/03-workflow-and-state-machine.md`
5. `docs/project/04-data-contracts.md`
6. `docs/project/05-config-and-conventions.md`
7. `docs/project/06-delivery-checklist.md`
8. `docs/project/08-artifact-governance.md`

## 🔧 判定规则（冲突时优先级）

1. `contracts/*.schema.json`
2. 当前代码可验证行为（`python/sqlopt`、`scripts/sqlopt_cli.py`）
3. 历史说明文档（`docs/*.md`）

## 🧱 当前实现基线（2026-03）

1. `python/sqlopt/cli.py` 仅保留 CLI adapter 与兼容包装层，核心编排已下沉到 `python/sqlopt/application/`
2. 运行编排边界固定为：`run_service -> workflow_engine -> run_repository/stages`
3. `preflight` 与 `validate` 已使用策略层做 capability gating，不再把平台差异散落在 stage 主流程里
4. `report` 产物与 `supervisor/state.json` 的 phase coverage 已做一致性修复，`report=DONE` 不再出现报告内滞后
5. 文档模型边界当前固定为：
   - `sqlopt.platforms.sql.models` 是 SQL 侧稳定模型入口
   - `sqlopt.stages.report_interfaces` 是 report 侧稳定模型入口
   - 对外契约统一通过 `to_contract()` 导出
6. 推荐的发布前验收基线：
   - 本仓库根目录执行 `python3 -m pytest -q`
   - 优先执行统一验收入口：`python3 scripts/ci/release_acceptance.py`
   - 复制 `tests/fixtures/project` 到临时目录后做一次离线 smoke run
   - 若只验证 scanner/scan，可直接对 `tests/fixtures/project/sqlopt.scan.local.yml` 做一次 scan-only smoke run
   - 核对 `state.json`、`report.json`、`report.summary.md` 中 `report=DONE`
   - 若 `status.next_action=report-rebuild`，说明主流程已完成，仅需重建 report 派生产物
   - 细分验收仍可单独执行：
     `python3 scripts/ci/opencode_smoke_acceptance.py`
     `python3 scripts/ci/degraded_runtime_acceptance.py`
     `python3 scripts/ci/report_rebuild_acceptance.py`
7. **LLM 增强功能（Phase 1-5）已全部完成**：
   - Phase 1: LLM 输出质量控制层（语法检查、启发式检查）
   - Phase 2: LLM 重试 + 反馈机制（验证失败自动重试）
   - Phase 3: validate 阶段 LLM 语义判断（DB 验证失败时 LLM 介入）
   - Phase 4: 规则引擎 ↔ LLM 双向反馈（反馈日志记录到 `ops/llm_feedback.jsonl`）
   - Phase 5: patch_generate 阶段 LLM 辅助（动态 SQL 模板建议）
   - Phase 6: LLM Trace 完整性增强（完整记录 LLM 交互历史）
   - 测试覆盖：84 个新增测试，全部通过

## 💻 交接使用方式

- 先按 `06-delivery-checklist.md` 创建新仓/新模块骨架。
- 以 `04-data-contracts.md` 作为接口和产物结构的"红线"。
- 以 `03-workflow-and-state-machine.md` 实现命令与恢复语义。

## 🎯 Install As Skill

### 快速安装

```bash
# 1. 打包
python3 install/build_bundle.py

# 2. 安装到项目
python3 install/install_skill.py --project <your_project_path>

# 3. 验证安装
python3 install/doctor.py --project <your_project_path>
```

Windows 用户请使用 `python` 替代 `python3`。

安装后，推荐先用 `llm.provider=opencode_builtin` 做一轮离线 smoke run，再切回真实 LLM/DB 配置。
如果是 MySQL 项目，建议先用 `db.platform=mysql` + 测试 DSN 做一轮 smoke，再打开真实 compare。

### 使用 Skill

```bash
# 查看帮助
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli --help

# 开始优化
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli run --config sqlopt.yml

# 查看状态
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli status --run-id <run_id>

# 继续运行
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli resume --run-id <run_id>

# 仅重建报告（当 status.next_action=report-rebuild 时）
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli run --config sqlopt.yml --to-stage report --run-id <run_id>

# 查看某条 SQL 的验证证据链
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey>

# 只看压缩诊断（包含 warnings / why_now / recommended_next_step）
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey> --summary-only --format json

# 应用补丁
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli apply --run-id <run_id>
```

### Scan-only 样例验证

仓库内置了一份只验证扫描覆盖的 fixture 配置：

```bash
python3 scripts/run_until_budget.py \
  --config tests/fixtures/project/sqlopt.scan.local.yml \
  --to-stage scan \
  --max-steps 10 \
  --max-seconds 30
```

当前样例覆盖并已验证：
- `bind`
- `choose/when/otherwise`
- `where`
- `if`
- `foreach`
- `include`
- `trim`
- `set`

建议检查这些产物：
- `tests/fixtures/project/runs/<run_id>/scan.sqlunits.jsonl`
- `tests/fixtures/project/runs/<run_id>/scan.fragments.jsonl`
- `tests/fixtures/project/runs/<run_id>/verification/ledger.jsonl`

## 🐬 MySQL 本地验证

若要在本地快速准备 MySQL 5.6+ 测试库（含 5.7、8.0+），可使用内置 schema：

```bash
mysql -h 127.0.0.1 -u root -p sqlopt_test < tests/fixtures/sql_local/schema.mysql.sql
```

这份脚本会创建并填充：
- `users`
- `orders`
- `shipments`

如遇 PostgreSQL 方言 SQL（例如 `ILIKE`），当前行为是：
- 不做自动改写
- `dbEvidenceSummary.explainError` 保留原始错误
- `report.json.validation_warnings` / `report.summary.md` / `sqlopt-cli verify --summary-only` 会显示 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`

MySQL 5.6 兼容说明：
- `MAX_EXECUTION_TIME` 不支持时会自动降级，不阻塞 evidence / compare 执行

## 🔌 LLM Provider 选型

与代码一致的 LLM 提供商选项：

1. `opencode_run` - 走 `opencode run` 外部命令（推荐）
2. `direct_openai_compatible` - 直连 OpenAI 兼容 `/chat/completions`
3. `opencode_builtin` - 本地内置策略
4. `heuristic` - 本地简化启发式策略

### 配置最小集（v1）

```yaml
config_version: v1

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

report:
  enabled: true
```

已移除且不再接受的配置根键：`validate`、`policy`、`apply`、`patch`、`diagnostics`、`runtime`、`verification`。  
配置示例见 `templates/sqlopt.example.yml`。

## 📋 详细文档

- **[快速入门](docs/QUICKSTART.md)** - 10 分钟上手指南
- **[文档导航](docs/INDEX.md)** - 完整文档索引
- **[安装指南](docs/INSTALL.md)** - 详细安装步骤
- **[配置说明](docs/project/05-config-and-conventions.md)** - 配置选项详解
- **[产物治理](docs/project/08-artifact-governance.md)** - 运行产物与 source-of-truth 规则
- **[故障排查](docs/TROUBLESHOOTING.md)** - 常见问题解决
- **[升级指南](docs/UPGRADE.md)** - 版本升级步骤
- **[分发指南](docs/DISTRIBUTION.md)** - 打包和分发

## 🆘 获取帮助

- 查看命令帮助：`sqlopt-cli --help`
- 运行诊断工具：`python3 install/doctor.py --project <path>`
- 报告问题：https://github.com/your-org/sql-optimizer/issues
- AI 助手指南：[CLAUDE.md](CLAUDE.md)
