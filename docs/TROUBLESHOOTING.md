# SQL Optimizer Skill 故障排查

## 1. preflight 阶段 DB 不可达

现象：

- `PREFLIGHT_DB_UNREACHABLE`

检查项：

1. 检查 `sqlopt.yml` 中的 `db.dsn`
2. 确认当前机器到 DB 可连通
3. 用 `psql` 或其他 DB 客户端手工验证

## 2. preflight 阶段 LLM 不可达

现象：

- `PREFLIGHT_LLM_UNREACHABLE`

检查项：

1. 执行 `opencode run --format json --variant minimal "ping"`
2. 检查 `~/.opencode/opencode.json` 中的 model/provider/baseURL/apiKey
3. 检查网络、代理、防火墙
4. Windows 场景：安装 `opencode` 后重开 PowerShell，确保 PATH 刷新
5. 若 `llm.provider=direct_openai_compatible`，检查 `api_base/api_key/api_model` 和 endpoint 连通性

Provider 专项检查：
1. `opencode_run`：命令可用，且 opencode profile/model 配置正确。
2. `direct_openai_compatible`：HTTP endpoint 可达，凭据与 model 有效。

## 3. preflight 阶段 scanner 检查失败

现象：

- `PREFLIGHT_SCANNER_MISSING`

检查项：

1. 当前默认使用 Python fallback scanner，不再需要配置 `scan.java_scanner.jar_path`
2. 若你使用的是旧配置，请移除 `scan.java_scanner` 段
3. 确认 `scan.mapper_globs` 能匹配到 mapper XML 文件

## 4. run_id 未找到

现象：

- `RUN_NOT_FOUND`

检查项：

1. 在同一 workspace 执行 `status --run-id <id>`
2. 确认 `<project>/runs/<run_id>` 路径下存在该 run
3. 检查 `<project>/runs/index.json`

## 5. command 超时

现象：

- `RUNTIME_STAGE_TIMEOUT` 或重试耗尽

检查项：

1. 当前运行时参数已内置，不再通过 `sqlopt.yml` 暴露 `runtime.*` 调整项
2. 使用时间片循环命令：`python scripts/run_until_budget.py --config ./sqlopt.yml --max-seconds 95`
3. 或持续执行 `resume`，直到输出出现 `"complete": True`

## 6. Windows 找不到 sqlopt-cli

现象：

- `'sqlopt-cli' is not recognized`

检查项：

1. 使用完整路径执行：`%USERPROFILE%\.opencode\skills\sql-optimizer\bin\sqlopt-cli.cmd`
2. 重新安装：`python install/install_skill.py --project <project>`
3. 执行 doctor：`python install/doctor.py --project <project>`

## 7. Windows doctor 出现 UnicodeDecodeError

现象：

- `UnicodeDecodeError: 'gbk' codec can't decode ...`

检查项：

1. 升级到最新 bundle（当前已使用 byte-capture + fallback decode）
2. 重新执行：`python install/doctor.py --project <project>`

## 8. Windows 运行缺少 SIGALRM

现象：

- `AttributeError: module 'signal' has no attribute 'SIGALRM'`

检查项：

1. 升级到最新 bundle（runtime 已支持 Windows 软超时回退）
2. 重新安装并执行 doctor

## 9. scan 阶段报 SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD

现象：

- `SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD`

检查项：

1. 确认 mapper XML 包含 `<mapper ... namespace="...">`
2. 当前逻辑下，被 glob 匹配到的非 mapper XML 会从 discovered-count 中跳过
3. 结合 `manifest.jsonl` 与 `scan.sqlunits.jsonl` 检查 discovered/parsed 差异
