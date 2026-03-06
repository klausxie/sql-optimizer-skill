# SQL Optimizer 快速入门指南

本指南将帮助你在 10 分钟内完成 SQL Optimizer 的首次运行。

## 前置条件

- Python 3.9 或更高版本
- PostgreSQL 或 MySQL 5.6+ 数据库（含 5.7、8.0+；真实验证时需要；首轮离线 smoke 可先禁用）
- MyBatis XML mapper 文件

## 快速开始（5 分钟）

### 1. 安装 SQL Optimizer

```bash
# 解压 skill bundle
cd /path/to/sql-optimizer-skill-bundle-v<version>

# 安装到你的项目
python3 install/install_skill.py --project /path/to/your/project
```

安装脚本会：
- 将 skill 安装到 `~/.opencode/skills/sql-optimizer`
- 创建 Python 虚拟环境并安装依赖
- 在你的项目中创建 `sqlopt.yml` 配置文件模板

### 2. 配置数据库连接

编辑项目根目录下的 `sqlopt.yml`：

```yaml
# 最小化配置示例
project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml  # MyBatis mapper 文件路径

db:
  platform: postgresql  # 或 mysql
  dsn: postgresql://user:password@localhost:5432/mydb

llm:
  enabled: true
  provider: opencode_run  # 使用 opencode 外部命令
```

**重要配置项说明：**
- `project.root_path`: 项目根目录（通常是 `.`）
- `scan.mapper_globs`: MyBatis XML 文件的匹配模式
- `db.dsn`: 数据库连接字符串
- `llm.provider`: LLM 提供商（推荐使用 `opencode_run`）

MySQL 示例：

```yaml
db:
  platform: mysql
  dsn: mysql://user:password@127.0.0.1:3306/mydb
```

当前边界：
- MySQL 支持 5.6+（含 5.7、8.0+）
- 不支持 MariaDB
- MySQL 5.6 不支持 `MAX_EXECUTION_TIME` 时会自动降级，不阻塞 evidence / compare
- 若原 SQL 或候选 SQL 带 PostgreSQL 方言（例如 `ILIKE`），当前不会自动兼容；MySQL evidence / compare 会按语法错误处理，并上报 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`

**如果只是先验证安装链路**，建议先改成：

```yaml
llm:
  provider: opencode_builtin
  enabled: true
```

这样可以先完成一次离线 smoke run，再切回真实 DB / 外部 LLM。

### 3. 验证安装

```bash
python3 install/doctor.py --project /path/to/your/project
```

Doctor 会检查：
- ✓ Python 版本
- ✓ 配置文件有效性
- ✓ Java scanner JAR 存在
- ✓ 数据库连接
- ✓ Mapper 文件可访问

### 4. 运行第一次优化

```bash
# 使用 skill 命令（推荐）
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli run --config sqlopt.yml

# 或使用 Python 脚本
python3 scripts/sqlopt_cli.py run --config sqlopt.yml
```

你会看到类似的输出：

```
▶ Starting phase: preflight - Checking configuration and environment
✓ Completed phase: preflight
▶ Starting phase: scan - Scanning MyBatis mapper files
✓ Completed phase: scan
ℹ Found 15 SQL statements to analyze
  Processing statement 1/15 (com.example.UserMapper.selectById)
  Processing statement 2/15 (com.example.UserMapper.selectAll)
...
{"run_id": "run_20260301_123456", "result": {"complete": false, "phase": "optimize"}}
```

### 5. 继续运行直到完成

由于每次调用有时间限制（120 秒），你可能需要多次调用 `resume` 命令：

```bash
# 继续运行
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli resume --run-id run_20260301_123456
```

重复执行直到看到 `"complete": true`。

如果 `status` 返回的 `next_action` 是 `report-rebuild`，说明主流程已经完成，只需要重建 report：

```bash
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli run --config sqlopt.yml --to-stage report --run-id run_20260301_123456
```

### 6. 查看结果

```bash
# 查看运行状态
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli status --run-id run_20260301_123456

# 查看某条 SQL 的验证证据链
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli verify --run-id run_20260301_123456 --sql-key com.example.UserMapper.selectById#v1

# 只看压缩诊断（包含 warnings / why_now / recommended_next_step）
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli verify --run-id run_20260301_123456 --sql-key com.example.UserMapper.selectById#v1 --summary-only --format json

# 查看详细报告
cat runs/run_20260301_123456/report.md
```

`status` 里的 `next_action` 含义：
- `resume`：继续推进未完成阶段
- `report-rebuild`：上游阶段已完成，只需重建 `report.json` / `report.md` / `ops/*.json`
- `none`：当前目标阶段已完成，无需继续

与当前实现一致的告警出口：
- `report.json.validation_warnings`
- `report.summary.md` 中的 `## Warnings`
- `sqlopt-cli verify --summary-only` 返回的 `warnings`

### 7. 应用优化补丁（可选）

**警告：应用补丁会修改源文件，请先备份或提交到版本控制！**

```bash
# 应用生成的补丁
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli apply --run-id run_20260301_123456
```

## 完整示例：端到端工作流

```bash
# 1. 安装
python3 install/install_skill.py --project ~/my-project

# 2. 进入项目目录
cd ~/my-project

# 3. 编辑配置（使用你喜欢的编辑器）
vim sqlopt.yml

# 4. 验证配置
python3 ~/.opencode/skills/sql-optimizer/install/doctor.py --project .

# 5. 开始优化
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli run --config sqlopt.yml

# 6. 继续运行（如果需要）
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli resume --run-id <run_id>

# 6b. 如果 status 提示 report-rebuild，则只重建 report
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli run --config sqlopt.yml --to-stage report --run-id <run_id>

# 7. 查看报告
cat runs/<run_id>/report.md

# 8. 查看某条 SQL 的验证证据（可选）
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey>

# 9. 应用补丁（可选）
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli apply --run-id <run_id>
```

## 常见问题

### Q: 如何禁用进度消息？

使用 `--quiet` 或 `-q` 标志：

```bash
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli --quiet run --config sqlopt.yml
```

### Q: 数据库连接失败怎么办？

1. 检查数据库是否运行：`psql <connection_string>`
2. 验证 `db.dsn` 配置是否正确
3. 如果只做离线 smoke，可先使用测试 DSN 并将 `llm.provider` 设为 `opencode_builtin` 或 `heuristic`

### Q: 找不到 Java scanner JAR？

重新安装 skill：

```bash
python3 install/install_skill.py --project /path/to/your/project
```

或手动构建：

```bash
cd java/scan-agent
mvn clean package
```

### Q: 如何使用自己的 LLM API？

修改配置：

```yaml
llm:
  enabled: true
  provider: direct_openai_compatible
  api_base: https://api.openai.com/v1
  api_key: sk-your-api-key
  api_model: gpt-4o-mini
  api_timeout_ms: 30000
```

### Q: 如何只扫描不优化？

使用 `--to-stage` 参数：

```bash
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli run --config sqlopt.yml --to-stage scan
```

如果你要验证仓库内置的扫描覆盖样例，可直接使用：

```bash
python3 scripts/run_until_budget.py \
  --config tests/fixtures/project/sqlopt.scan.local.yml \
  --to-stage scan \
  --max-steps 10 \
  --max-seconds 30
```

这份样例当前覆盖：
- `bind`
- `choose/when/otherwise`
- `where`
- `if`
- `foreach`
- `include`
- `trim`
- `set`

并且会额外锁住：
- `includeTrace` 与 fragment catalog 对齐后不再误报 `SCAN_INCLUDE_TRACE_PARTIAL`

### Q: 如何在本地准备 MySQL 测试库？

仓库内置了 MySQL 5.6+ fixture schema（含 5.7、8.0+）：

```bash
mysql -h 127.0.0.1 -u root -p sqlopt_test < tests/fixtures/sql_local/schema.mysql.sql
```

这会创建并填充 `users / orders / shipments`，用于 MySQL smoke 和 compare 验证。
- `UPDATE + trim + set` 结构不会再产出重复 `SET SET`

### Q: 运行失败了怎么办？

1. 查看错误消息中的建议
2. 检查 `runs/<run_id>/manifest.jsonl` 获取详细日志
3. 运行 doctor 检查环境：
   ```bash
   python3 install/doctor.py --project .
   ```
4. 查看故障排查文档：`docs/TROUBLESHOOTING.md`

## 配置选项速查

### 最小化配置（仅必填项）

```yaml
project:
  root_path: .
scan:
  mapper_globs: ["src/main/resources/**/*.xml"]
db:
  platform: postgresql
  dsn: postgresql://user:pass@localhost:5432/db
llm:
  enabled: true
  provider: opencode_run
```

### 推荐配置（包含常用选项）

```yaml
project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:pass@localhost:5432/db

llm:
  enabled: true
  provider: opencode_run
  timeout_ms: 80000

report:
  enabled: true
```

## 下一步

- 📖 阅读完整文档：`docs/INDEX.md`
- 🔧 了解配置选项：`docs/project/05-config-and-conventions.md`
- 🐛 故障排查：`docs/TROUBLESHOOTING.md`
- 📊 理解报告：`docs/project/02-system-spec.md`
- 🔄 升级指南：`docs/UPGRADE.md`

## 获取帮助

- 查看命令帮助：`sqlopt-cli --help`
- 查看子命令帮助：`sqlopt-cli run --help`
- 报告问题：https://github.com/your-org/sql-optimizer/issues
- 查看文档：`docs/` 目录

---

**提示：** 首次运行建议使用 `--to-stage scan` 先扫描文件，确认配置正确后再进行完整优化。
