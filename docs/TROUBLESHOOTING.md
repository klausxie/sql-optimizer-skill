# SQL Optimizer 故障排查

先看 3 个入口：

1. `runs/<run-id>/report.json`
2. `runs/<run-id>/control/state.json`
3. `runs/<run-id>/control/manifest.jsonl`

常用命令：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py status --run-id <run-id>
PYTHONPATH=python python3 scripts/sqlopt_cli.py verify --run-id <run-id> --sql-key <sql-key>
PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id <run-id>
```

## Run Not Found

可能原因：
- `run_id` 输入错误
- 当前目录不是创建该 run 的项目目录
- `runs/` 目录被清理或移动

处理方法：
- 先执行 `status` 查看默认选中的最新 run
- 确认当前项目目录正确
- 检查 `runs/<run-id>/control/state.json` 是否存在

## Database Connection

可能原因：
- `db.dsn` 配置错误
- 数据库未启动或网络不可达
- 账号权限不足

处理方法：
- 核对 `sqlopt.yml` 里的 `db.platform` 和 `db.dsn`
- 在命令行手动验证数据库连接
- 数据库恢复后执行 `resume --run-id <run-id>`

## Schema Validation

可能原因：
- 阶段输出与 schema 不匹配
- 代码和契约不一致
- run 中已有旧格式产物

处理方法：
- 先看 `control/manifest.jsonl` 里的失败事件
- 执行 `python3 scripts/schema_validate_all.py`
- 确认当前 run 使用的是新目录结构

## Retry Exhausted

可能原因：
- 外部依赖持续失败
- 某阶段重复超时
- 同一 statement 持续触发同一错误

处理方法：
- 先看 `control/manifest.jsonl`
- 修复数据库或 LLM 可达性后再执行 `resume`
- 若输入已明显变化，重新创建新 run

## LLM Timeout

可能原因：
- LLM 响应过慢
- 网络抖动
- 选中范围过大

处理方法：
- 增大 `llm.timeout_ms`
- 用 `--sql-key` 或更小范围先做局部 run
- 切换到 `opencode_builtin` 或 `heuristic` 做离线 smoke

## LLM Provider

可能原因：
- `llm.provider` 配置不匹配
- `direct_openai_compatible` 缺少 `api_base/api_key/api_model`
- 外部服务限流或不可用

处理方法：
- 对照 [CONFIG.md](CONFIG.md) 检查 LLM 配置
- 先执行 `PYTHONPATH=python python3 scripts/sqlopt_cli.py --help` 确认安装正常
- 需要离线验证时切换到 `opencode_builtin` 或 `heuristic`

## LLM Replay Miss

可能原因：
- `llm.mode=replay`，但这条 optimize request 还没有 cassette
- prompt/version/provider/model 变化导致 fingerprint 改了
- cassette 目录配置错了

处理方法：
- 先看报错里的 `sqlKey`、`fingerprint` 和 cassette 路径
- 确认 `llm.cassette_root` 是否指向 `tests/fixtures/llm_cassettes`
- 如果这条 statement 本来就应该走 LLM，用 `record` 补录
- 如果这条 statement 在 optimize 阶段本来是 `skip`/`blocked`，则不需要补 cassette

常用命令：

```bash
python3 scripts/run_sample_project.py \
  --scope sql \
  --sql-key <sql-key> \
  --to-stage optimize \
  --llm-mode record
```

补充：
- `replay` miss 默认不会 fallback 到 `live`
- 这是故意的，目的是避免测试悄悄退回真实 LLM

## Patch Conflicts

可能原因：
- mapper 文件在扫描后被修改
- 多个 patch 命中同一区域
- 模板结构已变化

处理方法：
- 先看 `artifacts/patches.jsonl`
- 审查 patch 冲突位置
- 如果源码已变化，重新跑一轮新 run

## Verification

可能原因：
- 关键结果缺少 verification 证据
- validate 或 patch 阶段处于降级状态
- `report.json` 中仍有 blocker

处理方法：
- 查看 `artifacts/acceptance.jsonl` 和 `artifacts/patches.jsonl`
- 对单条 SQL 执行 `verify --summary-only`
- 若 `status.next_action=report-rebuild`，只重建 report

## Permissions

可能原因：
- 对 mapper 或 `runs/` 目录没有读写权限
- 文件被其他进程占用

处理方法：
- 检查项目目录和 `runs/` 目录权限
- 确认当前用户可读 mapper、可写 `runs/`
- 关闭占用目标文件的进程后重试
