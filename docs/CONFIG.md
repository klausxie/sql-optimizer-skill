# SQL Optimizer 配置参考（v1）

本文档是配置边界的单一事实来源。

## 1. 用户可配置边界

### 1.1 主根键（稳定）

用户配置文件（`sqlopt.yml`）主根键如下：

1. `config_version`
2. `project`
3. `scan`
4. `db`
5. `llm`
6. `report`

### 1.2 命名约束

1. 全部使用 `snake_case`
2. 非 snake_case 视为配置错误

### 1.3 已移除根键（兼容忽略）

以下根键在 v1 已移除，加载时会被自动忽略（并由内部默认值注入）：

- `validate`
- `policy`
- `apply`
- `patch`
- `diagnostics`
- `runtime`
- `verification`
- `rules`
- `prompt_injections`

## 2. 主根键字段

### 2.1 `project`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `root_path` | string | 是 | 项目根目录，支持相对路径 |

### 2.2 `scan`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `mapper_globs` | string[] | 是 | MyBatis XML 匹配模式，必须非空 |

### 2.3 `db`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `platform` | string | 是 | `postgresql` 或 `mysql` |
| `dsn` | string | 是 | 数据库连接串 |
| `schema` | string/null | 否 | PostgreSQL 非默认 schema 时建议显式设置 |

边界说明：

- MySQL 支持 5.6+（含 5.7、8.0+），不支持 MariaDB
- MySQL 5.6 不支持 `MAX_EXECUTION_TIME` 时会自动降级，不阻塞 evidence / compare
- MySQL 场景遇 PostgreSQL 方言（如 `ILIKE`）时，不做自动改写，会按语法错误上报

### 2.4 `llm`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `provider` | string | 是 | `opencode_run` / `direct_openai_compatible` / `opencode_builtin` / `heuristic` |
| `enabled` | bool | 否 | 默认 `true` |
| `timeout_ms` | int | 否 | 请求超时（毫秒） |
| `opencode_model` | string/null | 否 | `opencode_run` 可选模型名 |
| `api_base` | string/null | 条件必填 | 仅 `direct_openai_compatible` |
| `api_key` | string/null | 条件必填 | 仅 `direct_openai_compatible` |
| `api_model` | string/null | 条件必填 | 仅 `direct_openai_compatible` |
| `api_timeout_ms` | int/null | 否 | 仅 `direct_openai_compatible` |
| `api_headers` | object/null | 否 | 仅 `direct_openai_compatible` |

约束：

- `direct_openai_compatible` 必须配置 `api_base/api_key/api_model`
- `opencode_run` 与 `direct_openai_compatible` 保持严格失败语义

### 2.5 `report`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `enabled` | bool | 否 | 默认 `true` |

## 3. 内部注入配置（用户声明会被忽略）

运行时会在 `config.resolved.json` 注入内部节：

- `apply`
- `policy`
- `validate`
- `patch`
- `diagnostics`
- `runtime`
- `verification`

这些节是执行层实现细节，不是用户配置边界。即使用户配置里声明了它们，也会被兼容层忽略。

## 4. 内置固定策略

以下配置已收敛为内部固定常量，用户不再通过 `sqlopt.yml` 修改：

1. validate 策略（profile / selection / evidence gate）
2. policy 阈值与安全口径
3. runtime 超时与重试
4. apply 模式（默认 `PATCH_ONLY`）
5. diagnostics / verification / patch 辅助策略

## 5. 加载与校验流程

1. 读取 `sqlopt.yml`
2. 校验用户配置根键与字段（已移除键先兼容忽略）
3. 补齐默认值
4. 注入内部节
5. 写入 `runs/<run-id>/config.resolved.json`

## 6. 示例

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
  provider: opencode_run

report:
  enabled: true
```

## 7. 运行目录规范

统一路径：`<project.root_path>/runs/<run-id>/`

分层主路径（canonical）：

1. `report.json`
2. `control/state.json`
3. `control/plan.json`
4. `control/manifest.jsonl`
5. `artifacts/scan.jsonl`
6. `artifacts/fragments.jsonl`
7. `artifacts/proposals.jsonl`
8. `artifacts/acceptance.jsonl`
9. `artifacts/patches.jsonl`
10. `sql/catalog.jsonl`
11. `sql/<sql-key>/index.json`

兼容策略：

- 不再保留 legacy 路径写入
- 运行目录读取默认仅认 canonical 路径

## 8. 补丁与回滚约定

1. 默认 `PATCH_ONLY`，`apply` 不会隐式修改源码
2. 每个 `PatchResult` 必须提供 `rollback`
3. 生成 patch 文件应可通过 `git apply --check`

## 9. 架构分层约定

当前默认分层：

1. `models`：只定义内部文档对象与稳定导出 facade，不负责流程编排
2. `policy / selection / builder / loader`：负责规则、聚合、读取，不直接持久化稳定契约
3. `writer / stage`：负责 `to_contract()`、schema 校验和最终落盘

依赖方向：

1. `models` 不能反向依赖 `builder / writer / stage / policy`
2. facade 模块只做 re-export，不承载业务逻辑
3. 新增模型对外导出统一使用 `to_contract()`

## 10. 相关文档

- [快速入门](QUICKSTART.md)
- [安装指南](INSTALL.md)
- [故障排查](TROUBLESHOOTING.md)
- [命令与状态机](project/03-workflow-and-state-machine.md)
