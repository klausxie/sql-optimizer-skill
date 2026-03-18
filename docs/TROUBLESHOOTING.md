# SQL Optimizer V8 故障排查

本文档提供 V8 七阶段流水线常见问题的诊断与解决方案。

## 通用诊断命令

```bash
# 查看运行状态
sqlopt-cli status --run-id <run-id>

# 验证配置
sqlopt-cli validate-config --config sqlopt.yml

# 环境诊断
python3 install/doctor.py --project .

# 技能验证
python3 install/install_skill.py --verify
```

---

## 1. 配置验证问题

### PREFLIGHT_CONFIG_INVALID

**现象**：配置校验失败

**诊断**：

```bash
sqlopt-cli validate-config --config sqlopt.yml
```

**原因与解决**：

| 原因 | 修复方式 |
|------|----------|
| `config_version` 缺失或错误 | 确保为 `config_version: v1` |
| `db.platform` 值非法 | 只支持 `postgresql` 或 `mysql` |
| `scan.mapper_globs` 为空 | 至少指定一个 glob 模式 |
| YAML 语法错误 | 使用 `yamllint` 检查格式 |

---

### PREFLIGHT_SCANNER_MISSING

**现象**：Preflight 阶段提示 scanner 缺失

**诊断**：

```bash
sqlopt-cli validate-config --config sqlopt.yml
```

**修复**：

V8 使用 Python 内置 scanner，无需 Java scanner。检查配置中是否残留旧版本配置：

```yaml
# 删除以下旧配置（如果存在）
scan:
  java_scanner:
    jar_path: ...
```

---

## 2. 数据库连接问题

### PREFLIGHT_DB_UNREACHABLE

**现象**：Preflight 阶段报数据库不可达

**诊断**：

```bash
python3 install/doctor.py --project .
psql "<dsn>"   # PostgreSQL
mysql "<dsn>"   # MySQL
```

**原因与解决**：

| 原因 | 修复方式 |
|------|----------|
| DSN 包含占位符 | 替换 `<user>`、`<password>`、`<database>` 等占位符 |
| 数据库地址/端口错误 | 确认数据库监听地址与配置一致 |
| 认证信息错误 | 检查用户名、密码、库名 |
| 网络不通 | 确认防火墙/网络策略允许连接 |
| 数据库未启动 | 启动数据库服务 |

---

### DB_CONNECTION_FAILED

**现象**：Validate 或 Baseline 阶段数据库连接失败

**诊断**：

```bash
sqlopt-cli validate-config --config sqlopt.yml
```

**原因与解决**：

| 原因 | 修复方式 |
|------|----------|
| `db.platform` 与实际数据库不符 | MySQL 配置写 `mysql`，PostgreSQL 配置写 `postgresql` |
| 连接超时 | 检查网络延迟，增加超时配置 |
| 密码过期 | 更新数据库密码 |

**MySQL 注意事项**：

- V8 支持 MySQL 5.6+，不支持 MariaDB
- 不支持 `MAX_EXECUTION_TIME`（MySQL 5.6 限制）

---

### OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR

**现象**：PostgreSQL 方言在 MySQL 平台报错

**诊断**：

```bash
sqlopt-cli status --run-id <run-id>
# 查看 validate 阶段日志
```

**原因与解决**：

某些 PostgreSQL 特有语法（如 `ILIKE`）在 MySQL 平台不兼容。需手动修改 SQL 或在报告中标记为已知限制。

---

## 3. Run 中断恢复

### RUN_NOT_FOUND

**现象**：`status`、`resume`、`apply` 报找不到 run

**诊断**：

```bash
sqlopt-cli status
ls runs/
cat runs/index.json
```

**修复**：

- 在原 run 所在 workspace 目录执行命令
- 显式指定 `--run-id <run-id>`
- 使用 `--project <path>` 指定项目路径

---

### RUNTIME_STAGE_TIMEOUT

**现象**：阶段执行超时

**诊断**：

```bash
sqlopt-cli status --run-id <run-id>
tail -n 80 runs/<run-id>/supervisor/state.json
```

**修复**：

```bash
# 恢复运行
sqlopt-cli resume --run-id <run-id>

# 或使用时间片执行脚本
python3 scripts/run_until_budget.py --config ./sqlopt.yml --max-seconds 95
```

---

### RUNTIME_RETRY_EXHAUSTED

**现象**：重试次数耗尽

**诊断**：

```bash
sqlopt-cli status --run-id <run-id>
cat runs/<run-id>/supervisor/state.json
```

**修复**：

1. 确认外部依赖（DB/LLM）稳定性
2. 使用 `resume` 继续推进
3. 如需重新开始，创建新 run

---

### Run 恢复流程

```bash
# 1. 查看中断的 run
sqlopt-cli status

# 2. 恢复执行
sqlopt-cli resume --run-id <run-id>

# 3. 持续恢复直到完成
sqlopt-cli resume --run-id <run-id>
sqlopt-cli resume --run-id <run-id>
```

**说明**：每个 `resume` 调用推进一个语句步骤，需多次调用直到所有 SQL 处理完成。

---

## 4. SQL 解析错误

### SCAN_XML_PARSE_FATAL

**现象**：XML 解析失败

**诊断**：

```bash
tail -n 100 runs/<run-id>/supervisor/state.json
```

**原因与解决**：

| 原因 | 修复方式 |
|------|----------|
| XML 语法错误 | 使用 xmllint 验证并修复 XML |
| 编码问题 | 确保文件编码为 UTF-8 |
| MyBatis 标签不完整 | 检查 `<mapper>`、`<select>` 等标签配对 |

---

### SCAN_MAPPER_NOT_FOUND

**现象**：未找到 mapper 文件

**诊断**：

```bash
sqlopt-cli validate-config --config sqlopt.yml
```

**修复**：

- 确认 `scan.mapper_globs` 匹配正确的 XML 文件
- 检查 glob 模式路径是否正确

```yaml
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
```

---

### SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD

**现象**：解析覆盖率低于阈值（当前阈值 90%）

**诊断**：

```bash
wc -l runs/<run-id>/sqlmap_catalog/sqlunits.jsonl
tail -n 100 runs/<run-id>/supervisor/state.json
```

**原因与修复**：

| 原因 | 修复方式 |
|------|----------|
| mapper 缺少 `namespace` | 添加 `namespace="..."` 属性 |
| XML 非 MyBatis mapper | 从 glob 中排除非 mapper 文件 |
| SQL 语句语法错误 | 修复 SQL 语法 |

---

### SCAN_SELECTION_SQL_KEY_NOT_FOUND / SCAN_SELECTION_SQL_KEY_AMBIGUOUS

**现象**：`--sql-key` 参数匹配失败或匹配多个 SQL

**诊断**：

```bash
sqlopt-cli run --config sqlopt.yml --sql-key <partial-name>
```

**修复**：

`--sql-key` 支持以下格式：

- 完整 `sqlKey`：`com.example.UserMapper.findById`
- `namespace.statementId`：`com.example.UserMapper.findById`
- `statementId`：`findById`
- `statementId#vN`：指定版本

如果只给方法名且匹配多个，改用更具体的 `namespace.statementId`。

---

## 5. LLM Provider 问题

### PREFLIGHT_LLM_UNREACHABLE

**现象**：Preflight 阶段报 LLM 不可达

**诊断**：

```bash
opencode run --format json --variant minimal "ping"
python3 install/doctor.py --project .
```

**原因与修复**：

| Provider | 检查项 |
|----------|--------|
| `opencode_run` | 检查 `~/.opencode/opencode.json` 的 provider/model/baseURL/apiKey |
| `direct_openai_compatible` | 检查 api_base/api_key/api_model 配置 |

其他可能原因：

- 代理/防火墙拦截
- 企业网络策略限制
- API Key 过期或无效

---

### LLM_RESPONSE_PARSE_ERROR

**现象**：LLM 返回格式解析失败

**诊断**：

```bash
cat runs/<run-id>/proposals/<sql-key>/prompt.json
cat runs/<run-id>/proposals/<sql-key>/raw_response.json
```

**修复**：

- 检查 LLM provider 可用性
- 降低 `optimize.max_candidates` 减少响应长度
- 重试当前 SQL

---

### VALIDATE_LLM_TIMEOUT

**现象**：LLM 调用超时

**修复**：

- 检查网络连接
- 降低 `optimize.max_candidates`
- 重试当前 SQL

---

## 6. 性能问题

### PERFORMANCE_SLOW_BASELINE

**现象**：Baseline 阶段执行缓慢

**诊断**：

```bash
# 检查单个 SQL 的基线采集时间
cat runs/<run-id>/baseline/<sql-key>.json
```

**原因与修复**：

| 原因 | 修复方式 |
|------|----------|
| 表数据量大 | 减少 `baseline.sample_size` |
| 网络延迟 | 检查数据库网络路径 |
| 缺少索引 | 在报告中查看缺失索引建议 |

---

### PERFORMANCE_LLM_HIGH_LATENCY

**现象**：LLM 调用响应慢

**修复**：

- 检查网络到 LLM provider 的延迟
- 考虑切换到延迟更低的 provider
- 减少并发请求数

---

## 7. 阶段特定错误

### Discovery 阶段

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| PREFLIGHT_DB_UNREACHABLE | 数据库不可达 | 检查 db.dsn 和网络连通性 |
| SCAN_MAPPER_NOT_FOUND | mapper 文件未找到 | 检查 mapper_globs 配置 |
| SCAN_XML_PARSE_FATAL | XML 解析失败 | 修复 XML 语法 |

---

### Branching 阶段

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| BRANCH_EXPANSION_ERROR | 分支展开失败 | 检查动态 SQL 标签完整性 |
| BRANCH_LIMIT_EXCEEDED | 分支数超限 | 调整 branching.max_branches |

---

### Pruning 阶段

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| PRUNE_STATIC_ANALYSIS_ERROR | 静态分析错误 | 检查 SQL 语法 |

---

### Baseline 阶段

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| DB_CONNECTION_FAILED | 数据库连接失败 | 检查 db.dsn |
| BASELINE_EXPLAIN_ERROR | EXPLAIN 执行失败 | 检查 SQL 语法和索引 |

---

### Optimize 阶段

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| PREFLIGHT_LLM_UNREACHABLE | LLM 不可达 | 检查 llm 配置 |
| LLM_RESPONSE_PARSE_ERROR | LLM 响应解析失败 | 重试或检查 provider |

---

### Validate 阶段

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| VALIDATE_DB_UNREACHABLE | 数据库不可达 | 检查 db.dsn |
| VALIDATE_TIMEOUT | 验证超时 | 增加超时时间或减少数据量 |
| VALIDATE_SEMANTIC_ERROR | 语义错误 | 检查优化建议是否改变了 SQL 语义 |
| VALIDATE_EQUIVALENCE_MISMATCH | 结果集不等价 | 优化建议可能导致结果不一致 |

---

### Patch 阶段

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| PATCH_GENERATION_ERROR | 补丁生成失败 | 重试 |
| PATCH_LOCATOR_AMBIGUOUS | 定位器模糊 | 手动定位并修复 |
| PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE | 动态 XML 需要模板感知重写 | 手动处理或确认 rewriteMaterialization.replayVerified=true |

---

## 8. 错误分类速查

| 分类 | 含义 | 处理方式 |
|------|------|----------|
| `retryable` | 可重试后恢复 | 使用 `resume` 继续 |
| `degradable` | 可继续但结果降级 | 检查日志，确认影响范围 |
| `fatal` | 需要修复后继续 | 修复问题后重新 run |

---

## 9. 平台特定问题

### Windows

**问题**：`sqlopt-cli` not recognized

**修复**：

```powershell
python install/install_skill.py --verify
# 或使用全路径
%USERPROFILE%\.opencode\skills\sql-optimizer\bin\sqlopt-cli.cmd
```

**问题**：UnicodeDecodeError

**修复**：升级到最新版本，已包含 byte-capture + fallback decode。

---

## 10. 获取帮助

```bash
# 查看完整状态
sqlopt-cli status --run-id <run-id>

# 查看阶段日志
cat runs/<run-id>/supervisor/state.json

# 查看 LLM prompt
cat runs/<run-id>/proposals/<sql-key>/prompt.json

# 查看原始响应
cat runs/<run-id>/proposals/<sql-key>/raw_response.json
```

---

*本文档基于 V8 架构*
