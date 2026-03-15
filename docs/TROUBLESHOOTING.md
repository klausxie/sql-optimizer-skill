# SQL Optimizer 故障排查

本页按统一格式给出：`错误码/现象 -> 诊断命令 -> 修复动作`。

## 通用诊断入口

```bash
sqlopt-cli status --run-id <run-id>
python3 install/doctor.py --project .
python3 install/install_skill.py --verify
```

---

## PREFLIGHT_DB_UNREACHABLE

现象：
- preflight 阶段报数据库不可达

诊断命令：

```bash
python3 install/doctor.py --project .
psql "<db_dsn>"
```

修复动作：
- 检查 `sqlopt.yml` 的 `db.dsn`
- 确认数据库监听地址/端口与网络连通
- 修正认证信息（用户名/密码/库名）

---

## PREFLIGHT_LLM_UNREACHABLE

现象：
- preflight 阶段报 LLM 不可达

诊断命令：

```bash
opencode run --format json --variant minimal "ping"
python3 install/doctor.py --project .
```

修复动作：
- `llm.provider=opencode_run`：检查 `~/.opencode/opencode.json` 的 provider/model/baseURL/apiKey
- `llm.provider=direct_openai_compatible`：检查 `api_base/api_key/api_model`
- 检查代理、防火墙、企业网络策略
- Windows 下安装后重开 PowerShell 刷新 PATH

---

## PREFLIGHT_SCANNER_MISSING（仅旧版本/旧 run）

现象：
- 旧版本或历史 run 的 preflight 提示 scanner 检查失败

诊断命令：

```bash
python3 install/doctor.py --project .
sqlopt-cli validate-config --config sqlopt.yml
```

修复动作：
- 当前默认 Python fallback scanner，无需 `scan.java_scanner.jar_path`
- 移除旧配置里的 `scan.java_scanner` 段
- 升级并重装最新 skill 后重试（新版本默认不再做 scanner jar preflight）
- 校验 `scan.mapper_globs` 能匹配到 mapper XML

---

## RUN_NOT_FOUND

现象：
- `status/resume/apply` 报找不到 run

诊断命令：

```bash
sqlopt-cli status --project .
ls runs
cat runs/index.json
```

修复动作：
- 在原 run 所在 workspace 执行命令
- 显式指定 `--run-id <id>` 或 `--project <path>`
- 确认 `runs/<run-id>` 目录存在

---

## SCAN_SELECTION_SQL_KEY_NOT_FOUND / SCAN_SELECTION_SQL_KEY_AMBIGUOUS

现象：
- `--sql-key findUsers` 报未匹配或匹配多个 SQL

诊断命令：

```bash
sqlopt-cli run --config sqlopt.yml --to-stage scan --sql-key findUsers
```

修复动作：
- `--sql-key` 可使用完整 `sqlKey`、`namespace.statementId`、`statementId`、`statementId#vN`
- 如果只给方法名且命中多个 SQL，改用更具体的 `namespace.statementId` 或完整 `sqlKey`
- 必要时配合 `--mapper-path` 缩小扫描范围

---

## DB_CONNECTION_FAILED

现象：
- `validate-config` 或 DB-backed run 在开始前直接报数据库连接失败

诊断命令：

```bash
sqlopt-cli validate-config --config sqlopt.yml
```

修复动作：
- 先检查 `db.platform` 是否与实际数据库一致
- 检查 `db.dsn` 是否仍包含 `<user>`、`<password>`、`<database>` 等占位符
- 修正用户名、密码、主机、端口、库名后重试
- 需要更细的连接确认时，直接用对应客户端手工连接同一个 DSN

---

## RUNTIME_STAGE_TIMEOUT / RUNTIME_RETRY_EXHAUSTED

现象：
- 阶段超时或重试耗尽

诊断命令：

```bash
sqlopt-cli status --run-id <run-id>
tail -n 80 runs/<run-id>/pipeline/manifest.jsonl
python3 scripts/run_until_budget.py --config ./sqlopt.yml --max-seconds 95
```

修复动作：
- 用 `resume` 持续推进，或改用 `run_until_budget.py` 时间片执行
- 优先修复外部依赖（DB/LLM）稳定性
- 对失败 run 用 `status` 先确认是否需要 `report-rebuild`

---

## Windows: sqlopt-cli not recognized

现象：
- `'sqlopt-cli' is not recognized`

诊断命令：

```powershell
python install/install_skill.py --verify
python install/doctor.py --project .
```

修复动作：
- 重新安装：`python install/install_skill.py`
- 按 `--verify` 输出修复 PATH
- 新开 PowerShell 后重试
- 临时可用全路径：`%USERPROFILE%\.opencode\skills\sql-optimizer\bin\sqlopt-cli.cmd`

---

## Windows: doctor UnicodeDecodeError

现象：
- `UnicodeDecodeError: 'gbk' codec can't decode ...`

诊断命令：

```powershell
python install/doctor.py --project .
```

修复动作：
- 升级到最新 bundle（已包含 byte-capture + fallback decode）
- 重新安装后再执行 doctor

---

## Windows: missing SIGALRM

现象：
- `AttributeError: module 'signal' has no attribute 'SIGALRM'`

诊断命令：

```powershell
python install/doctor.py --project .
```

修复动作：
- 升级到最新 bundle（runtime 已支持 Windows 软超时回退）
- 重新安装 skill 后重试

---

## SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD

现象：
- scan 阶段覆盖率低于阈值

诊断命令：

```bash
tail -n 100 runs/<run-id>/pipeline/manifest.jsonl
wc -l runs/<run-id>/pipeline/scan/sqlunits.jsonl
```

修复动作：
- 确认 XML 为有效 mapper（含 `<mapper namespace="...">`）
- 排查被 glob 误匹配的非 mapper XML
- 对照 manifest 的 discovered/parsed 差异修正文件与 glob
