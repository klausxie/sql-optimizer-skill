# 详细设计 2：CLI 工具设计

## 1. 设计目标

设计两个独立的 CLI 工具，分别负责 SQL 优化和数据目录管理。

## 2. CLI 分工

| CLI | 职责 | 场景 |
|-----|------|------|
| `sqlopt-cli` | SQL 优化主流程 | run, resume, status, apply |
| `sqlopt-data` | 数据目录管理 | get, list, set, diff, validate, prune |

**设计思路**：职责分离，优化流程 vs 数据管理独立演进

## 3. sqlopt-cli（SQL 优化）

### 3.1 命令列表

| 命令 | 功能 |
|------|------|
| `run --config <file>` | 开始优化流程 |
| `resume` | 恢复运行 |
| `status` | 查看状态 |
| `apply` | 应用补丁 |
| `validate-config` | 验证配置 |

### 3.2 设计思路

**run 命令**：
- 默认执行完整流程（Discovery → Validate）
- 支持 `--to-stage` 控制执行范围
- 支持 `--max-steps` / `--max-seconds` 控制资源消耗
- 每次调用推进一个 SQL 步骤，支持可恢复执行

**resume 命令**：
- 从中断处恢复运行
- 自动跳过已完成的步骤

**apply 命令**：
- 应用生成的补丁
- 支持 `--force` 跳过确认

## 4. sqlopt-data（数据管理）

### 4.1 命令列表

| 命令 | 功能 |
|------|------|
| `get <path>` | 查询数据 |
| `list <path>` | 列出内容 |
| `set <path> <value>` | 修改数据 |
| `diff <a> <b>` | 版本对比 |
| `validate <path>` | 验证契约 |
| `prune <target>` | 清理数据 |

### 4.2 设计思路

**路径解析**：
- 支持相对路径（相对于项目根目录）
- 支持 `runs/`、`cache/`、`history/` 等路径类型

**JSONPath 查询**：
- 支持类似 `.[?(@.risk=='high')]` 的查询表达式
- 支持多种输出格式：json、table、csv

**版本对比**：
- 支持运行间对比
- 支持阶段间对比
- 支持单项对比

**数据验证**：
- 支持 JSON Schema 验证
- 支持契约完整性检查

**清理策略**：
- 按时间清理缓存
- 按阶段保留运行产物
- 保留最近 N 次历史运行

## 5. 设计原则

- **管道兼容**：支持 stdin/stdout 便于脚本集成
- **人类优先**：默认人类可读输出
- **错误语义**：清晰的退出码和错误信息
- **一致性**：遵循 Unix 惯例
