# 配置文件说明

## 快速开始

### 1. 选择配置模板

根据您的数据库类型选择对应的模板文件：

| 数据库 | 模板文件 |
|--------|----------|
| PostgreSQL | `config/templates/sqlopt.postgresql.yml.template` |
| MySQL | `config/templates/sqlopt.mysql.yml.template` |
| 仅测试 | `config/templates/sqlopt.example.yml.template` (使用 mock 模式) |

### 2. 创建配置文件

```bash
# PostgreSQL
copy config\templates\sqlopt.postgresql.yml.template sqlopt.yml

# MySQL
copy config\templates\sqlopt.mysql.yml.template sqlopt.yml
```

### 3. 修改配置

编辑 `sqlopt.yml` 文件，填入您的实际数据库连接信息。

## 配置项说明

### 数据库配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `db_platform` | 数据库平台类型 | `postgresql` 或 `mysql` |
| `db_host` | 数据库主机地址 | `localhost`、`127.0.0.1` |
| `db_port` | 数据库端口 | `5432` (PostgreSQL)、`3306` (MySQL) |
| `db_name` | 数据库名称 | `mydb` |
| `db_user` | 数据库用户名 | `admin` |
| `db_password` | 数据库密码 | `secret` |

### LLM 配置

| 配置项 | 说明 | 可选值 |
|--------|------|--------|
| `llm_provider` | LLM 提供者 | `opencode_run` (默认，推荐)、`openai`、`mock` |
| `llm_enabled` | 是否启用 LLM | `true` 或 `false` |

### LLM Provider 对比

| Provider | 说明 | 适用场景 |
|----------|------|----------|
| `opencode_run` | 使用本地 opencode | **生产环境（推荐）** |
| `openai` | 使用 OpenAI API | 需要 OpenAI API Key |
| `mock` | 模拟数据 | 测试、演示 |

## 示例配置

### PostgreSQL + opencode_run（推荐）

```yaml
config_version: v1
db_platform: postgresql
db_host: localhost
db_port: 5432
db_name: myapp
db_user: postgres
db_password: mypassword
llm_provider: opencode_run
llm_enabled: true
project_root_path: .
scan_mapper_globs:
  - "src/main/resources/**/*.xml"
```

### MySQL + openai

```yaml
config_version: v1
db_platform: mysql
db_host: localhost
db_port: 3306
db_name: myapp
db_user: root
db_password: mypassword
llm_provider: openai
llm_enabled: true
project_root_path: .
scan_mapper_globs:
  - "src/main/resources/**/*.xml"
```

## 常见问题

**Q: llm_provider 选哪个好？**
推荐使用 `opencode_run`：无需 API Key，使用本地模型，保护数据隐私。

**Q: 使用 openai 需要什么？**
需要设置环境变量：`export OPENAI_API_KEY=your_api_key_here`

**Q: 如何验证配置是否正确？**
```bash
sqlopt run init --config ./sqlopt.yml
```
