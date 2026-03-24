# SQL Optimizer

SQL 优化工具，用于分析和优化 MyBatis XML 中的 SQL 语句。

## 功能特点

- **SQL 解析**: 自动识别和分析 MyBatis Mapper XML 中的 SQL 语句
- **性能基线**: 生成 SQL 性能基线数据
- **智能优化**: 基于 LLM 的 SQL 优化建议
- **数据库支持**: PostgreSQL / MySQL

---

## 架构概览

### 五阶段流水线

```
┌─────────┐    ┌─────────┐    ┌────────────┐    ┌──────────┐    ┌───────┐
│  Init   │───▶│  Parse  │───▶│ Recognition │───▶│ Optimize │───▶│Result │
└─────────┘    └─────────┘    └────────────┘    └──────────┘    └───────┘
```

| 阶段 | 说明 | 输出 |
|------|------|------|
| **Init** | 扫描 MyBatis XML，提取 SQL 单元 | `sql_units.json` |
| **Parse** | 展开动态标签（if/include/foreach），生成执行分支 | `sql_units_with_branches.json` |
| **Recognition** | 采集 SQL 执行计划，生成性能基线 | `baselines.json` |
| **Optimize** | 基于规则 + LLM 生成优化建议 | `proposals.json` |
| **Result** | 汇总输出补丁或报告 | `report.json` |

### 目录结构

```
python/sqlopt/
├── cli/main.py              # CLI 入口
├── stage_runner.py          # 流水线编排器
├── common/                  # 公共模块
│   ├── config.py           # 配置加载
│   ├── run_paths.py        # 路径管理
│   ├── progress.py         # 进度跟踪
│   ├── errors.py           # 错误定义
│   ├── llm_mock_generator.py  # LLM Mock 数据生成
│   └── db_connector.py     # 数据库连接器
├── stages/
│   ├── init/               # Init 阶段
│   ├── parse/              # Parse 阶段
│   ├── recognition/         # Recognition 阶段
│   ├── optimize/           # Optimize 阶段
│   └── result/             # Result 阶段
└── contracts/              # 数据契约（JSON Schema）
    └── schemas/
```

---

## 快速开始

### 1. 安装

```bash
pip install -e ".[dev]"
```

### 2. 创建配置文件

```bash
# PostgreSQL
cp installer/config/templates/sqlopt.postgresql.yml.template sqlopt.yml

# MySQL
cp installer/config/templates/sqlopt.mysql.yml.template sqlopt.yml
```

编辑 `sqlopt.yml`，填入数据库连接信息。

### 3. 运行

```bash
# 完整流程
sqlopt run init
sqlopt run parse
sqlopt run recognition
sqlopt run optimize
sqlopt run result

# 或分阶段运行
sqlopt run init --config sqlopt.yml
```

### 4. 查看结果

结果保存在 `runs/<run_id>/` 目录下。

---

## 构建

### 构建可执行文件

```bash
# 安装构建依赖
pip install -e ".[dev]"

# 执行构建
python installer/build.py
```

构建完成后，可执行文件位于 `installer/dist/` 目录。

### 分发

将 `installer/` 目录完整提供给用户即可，包含：
- 可执行文件（`sqlopt.exe` 或 `sqlopt`）
- 配置模板
- 初始化脚本

---

## 阶段调测

### Init 阶段

扫描 MyBatis XML 文件，提取 SQL 单元。

```bash
# 运行
sqlopt run init --config sqlopt.yml

# 查看输出
cat runs/<run_id>/init/sql_units.json

# 测试
python -m pytest tests/unit/test_init_stage.py -v
```

### Parse 阶段

展开动态 SQL 标签，生成执行分支。

```bash
# 运行（依赖 Init 阶段输出）
sqlopt run parse --config sqlopt.yml

# 查看输出
cat runs/<run_id>/parse/sql_units_with_branches.json

# 测试
python -m pytest tests/unit/test_parse_stage.py -v
```

### Recognition 阶段

采集 SQL 执行计划，生成性能基线。

```bash
# 运行（依赖 Parse 阶段输出）
sqlopt run recognition --config sqlopt.yml

# 查看输出
cat runs/<run_id>/recognition/baselines.json

# 测试
python -m pytest tests/unit/test_recognition_stage.py -v
```

### Optimize 阶段

基于规则和 LLM 生成优化建议。

```bash
# 运行（依赖 Recognition + Parse 阶段输出）
sqlopt run optimize --config sqlopt.yml

# 查看输出
cat runs/<run_id>/optimize/proposals.json

# 测试
python -m pytest tests/unit/test_optimize_stage.py -v
```

### Result 阶段

汇总输出补丁或报告。

```bash
# 运行（依赖 Optimize 阶段输出）
sqlopt run result --config sqlopt.yml

# 查看输出
cat runs/<run_id>/result/report.json

# 测试
python -m pytest tests/unit/test_result_stage.py -v
```

---

## 测试

```bash
# 运行所有单元测试
python -m pytest tests/unit/ -v

# 运行带覆盖率
python -m pytest tests/unit/ --cov=sqlopt --cov-report=term-missing

# 运行集成测试
python -m pytest tests/integration/ -v
```

### 使用 Mock 模式测试

如无数据库或 LLM，可使用 mock 模式：

```yaml
llm_provider: mock
llm_enabled: true
```

---

## 配置说明

### 完整配置示例

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

### LLM Provider

| Provider | 说明 | 适用场景 |
|----------|------|----------|
| `opencode_run` | 使用本地 opencode（**推荐**） | 生产环境 |
| `openai` | 使用 OpenAI API | 需要 `OPENAI_API_KEY` |
| `mock` | 模拟数据 | 测试 |

---

## 依赖

- Python >= 3.9
- PostgreSQL 或 MySQL（用于实际优化）
- opencode（可选，用于 LLM 优化）

## 许可证

MIT
