# V10 总体架构设计

## 1. 设计原则

### 1.1 阶段自治
- 每个阶段代码放**自己目录**，不与其他阶段混在一起
- 阶段内部分为 `api.py`（对外接口）和私有实现
- 阶段可**独立调测**，不依赖其他阶段

### 1.2 契约驱动
- 阶段间通信唯一方式：**JSON 文件**
- 契约优先：代码行为与文档冲突时，以 `contracts/schemas/` 为准
- 每个阶段输出前必须通过 `ContractValidator` 验证

### 1.3 严格审计
- Common 只放被 **2+ 阶段**使用的公共基础设施
- 禁止将业务逻辑代码放入 Common
- 禁止阶段间直接调用（只通过 JSON 文件）

---

## 2. 数据流总览

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              V10 五阶段数据流                                          │
│                                                                                     │
│   ┌─────────┐     ┌─────────┐     ┌────────────┐     ┌──────────┐     ┌───────┐  │
│   │  Init   │────▶│  Parse  │────▶│Recognition │────▶│ Optimize │────▶│Result │  │
│   └─────────┘     └─────────┘     └────────────┘     └──────────┘     └───┬───┘  │
│        │               │                │                 │              │        │
│        ▼               ▼                ▼                 ▼              ▼        │
│   init/           parse/          recognition/        optimize/      ┌────────┐ │
│   ├─sql_units.json   ├─sql_units.json   baselines.json     ├─proposals.json    │        │
│   ├─sql_fragments.json  ├─xml_mappings.json                             │        │
│   ├─xml_mappings.json   └─risks.json           (可验证)  →  Patch       │        │
│   └─table_schemas.json                        └─recommendations.json → Report   │
│   (原始XML+统计)       (include已解析)                                    (用户决策)  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```
python/sqlopt/
├── init/                   # Init 阶段
│   ├── __init__.py
│   ├── api.py            # 阶段 API（必须）
│   ├── run.py            # 入口实现
│   ├── scanner.py        # XML 扫描
│   ├── parser.py         # SQL 解析
│   ├── table_extractor.py # 表结构提取（核心）
│   ├── README.md         # 阶段调测指南
│   └── STAGE.md          # 阶段设计文档
│
├── parse/                 # Parse 阶段
│   ├── __init__.py
│   ├── api.py            # 阶段 API（必须）
│   ├── run.py            # 入口实现
│   ├── branch_generator.py  # 分支展开（核心）
│   ├── risk_detector.py  # 风险检测
│   ├── README.md         # 阶段调测指南
│   └── STAGE.md          # 阶段设计文档
│
├── recognition/           # Recognition 阶段
│   ├── __init__.py
│   ├── api.py            # 阶段 API（必须）
│   ├── run.py            # 入口实现
│   ├── explain_collector.py  # EXPLAIN 采集
│   ├── baseline_runner.py   # 基线执行
│   ├── README.md         # 阶段调测指南
│   └── STAGE.md          # 阶段设计文档
│
├── optimize/              # Optimize 阶段
│   ├── __init__.py
│   ├── api.py            # 阶段 API（必须）
│   ├── run.py            # 入口实现
│   ├── rules_engine.py   # 规则引擎（核心）
│   ├── llm_provider.py   # LLM 调用
│   ├── semantic_check.py # 语义检查
│   ├── README.md         # 阶段调测指南
│   └── STAGE.md          # 阶段设计文档
│
├── result/              # Result 阶段（Patch + Report 汇总）
│   ├── __init__.py
│   ├── api.py            # 阶段 API（必须）
│   ├── run.py            # 入口实现
│   ├── patch_generator.py  # 补丁生成
│   ├── xml_applier.py    # XML 应用
│   ├── report_generator.py  # 用户报告生成
│   ├── README.md         # 阶段调测指南
│   └── STAGE.md          # 阶段设计文档
│
├── common/               # 公共模块（严格审计）
│   ├── __init__.py
│   ├── contracts.py      # 契约验证
│   ├── run_paths.py      # 路径管理
│   ├── progress.py       # 进度报告
│   ├── errors.py         # 错误定义
│   ├── config.py         # 配置加载
│   ├── llm.py            # 统一的大模型调用
│   ├── llm_mock_generator.py  # LLM 生成 Mock 测试数据
│   └── README.md         # Common 调测指南
│
└── cli.py               # CLI 入口

contracts/
└── schemas/              # JSON Schema 契约
    ├── sqlunit.schema.json
    ├── risks.schema.json
    ├── baseline_result.schema.json
    ├── optimization_proposal.schema.json
    ├── recommendation.schema.json
    └── patch_result.schema.json

tests/                      # 测试目录
├── init/                   # Init 阶段测试
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_scanner.py
│   └── mocks/             # Mock 数据（sqlopt mock 生成）
│
├── parse/                  # Parse 阶段测试
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_branch_generator.py
│   └── mocks/
│
├── recognition/            # Recognition 阶段测试
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_explain_collector.py
│   └── mocks/
│
├── optimize/               # Optimize 阶段测试
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_rules_engine.py
│   └── mocks/
│
├── result/                 # Result 阶段测试
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_patch_generator.py
│   └── mocks/
│
├── common/                 # Common 模块测试
│   ├── __init__.py
│   ├── test_contracts.py
│   ├── test_config.py
│   └── mocks/
│
├── integration/            # 整体联调测试
│   ├── __init__.py
│   ├── test_full_pipeline.py   # 完整流程测试
│   ├── test_stage_chain.py     # 阶段链式调用测试
│   └── mocks/
│
└── conftest.py             # pytest 配置和共享 fixtures
```

---

## 4. 测试工具与调测流程

### 4.1 快速调测流程

```bash
# 1. 进入某阶段测试目录
cd tests/init/

# 2. 用 LLM 生成 Mock 数据
sqlopt mock init "生成一个包含多个if和include的SQL"

# 3. 运行测试
python -m pytest test_api.py -v
```

### 4.2 conftest.py 配置

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def mock_data_dir():
    """返回当前阶段的 mock 数据目录"""
    stage = Path(__file__).parent.name
    return Path(f"tests/{stage}/mocks")

@pytest.fixture
def load_mock(stage):
    """加载指定阶段的 mock 数据"""
    def _load(filename):
        mock_dir = Path(f"tests/{stage}/mocks")
        return json.load(open(mock_dir / filename))
    return _load
```

### 4.3 每个阶段测试示例

```python
# tests/init/test_api.py
def test_scan_xml_files(load_mock):
    # 使用 LLM 生成的 mock 数据测试
    mock_input = load_mock("init_sql_units.json")
    
    # 执行被测函数
    result = api.run(config, mock_input)
    
    # 断言
    assert result.success
    assert len(result.sql_units) > 0
```

### 4.4 整体联调测试

```bash
# 完整流程测试
cd tests/integration/
python -m pytest test_full_pipeline.py -v

# 阶段链式调用测试
python -m pytest test_stage_chain.py -v
```

### 4.5 LLM Mock 数据生成

```bash
# 生成指定场景的 mock 数据
sqlopt mock init "生成一个包含多个if和include的SQL"
sqlopt mock parse "生成一个包含include引用和foreach循环的SQL"
sqlopt mock recognition "生成PostgreSQL的完整执行计划"

# 查看生成的 mock 数据
sqlopt mock cat init
sqlopt mock cat parse

# mock 数据存放位置
tests/init/mocks/
tests/parse/mocks/
...
```

---

## 5. 数据契约与版本管理

### 4.1 契约目录结构

```
contracts/
├── schemas/
│   ├── v1/                 # v1 版本完整 schemas
│   │   ├── sqlunit.schema.json
│   │   ├── risks.schema.json
│   │   ├── baseline_result.schema.json
│   │   ├── optimization_proposal.schema.json
│   │   ├── recommendation.schema.json
│   │   └── patch_result.schema.json
│   │
│   ├── v2/                 # v2 版本完整 schemas
│   │   └── ...             # 可能改了某个字段
│   │
│   └── current -> v2       # 软链接指向当前版本
│
├── changelog.md             # 变更日志
└── tools/
    └── migrate.py          # 版本迁移脚本
```

### 4.2 配置文件指定契约版本

```yaml
# sqlopt.yml
config_version: v1

contracts:
  version: "v2"  # 使用哪个版本的契约，默认使用 current

project:
  root_path: .
```

### 4.3 运行时契约验证流程

```
sqlopt run init
    │
    ├── 加载配置（contracts.version，默认 current）
    ├── 从 contracts/schemas/{version}/ 加载对应版本的 schema
    │
    └── Init 输出前
        ├── 用 schema 验证输出
        └── 验证通过 → 写文件
            失败 → 报错退出
```

### 4.4 CLI 契约命令

```bash
# 查看当前契约版本
sqlopt contract version

# 查看变更历史
sqlopt contract log

# 切换契约版本
sqlopt contract use v1

# 验证契约是否正确
sqlopt contract validate

# 更新契约版本
sqlopt contract update --from v1 --to v2
```

### 4.5 代码层面实现

```python
# common/contracts.py
class ContractValidator:
    def __init__(self, version: str = "current"):
        self.version = version
        self.schemas = self._load_schemas(version)
    
    def _load_schemas(self, version: str) -> dict:
        """从 contracts/schemas/{version}/ 加载所有 schema"""
        schema_dir = Path(f"contracts/schemas/{version}")
        return {
            "sqlunit": self._load(f"{schema_dir}/sqlunit.schema.json"),
            "risks": self._load(f"{schema_dir}/risks.schema.json"),
            ...
        }
    
    def validate(self, data: any, schema_name: str) -> list[str]:
        """验证数据是否符合 schema"""
        ...
```

---

## 6. CLI 设计

### 5.1 命令

```bash
# ========== 阶段执行 ==========
# 默认使用 ./sqlopt.yml
sqlopt run init
sqlopt run parse
sqlopt run recognition
sqlopt run optimize
sqlopt run result

# 显式指定 config（仅当默认路径不符时）
sqlopt run init --config /path/to/other.yml

# ========== 工具命令 ==========
# 查看状态
sqlopt status <run_id>

# 应用补丁
sqlopt apply <run_id>

# ========== LLM Mock 数据生成 ==========
# 用 LLM 生成 Mock 测试数据
sqlopt mock init "生成一个复杂的包含多个if标签的SQL单元"
sqlopt mock parse "生成一个包含include和foreach的SQL"
sqlopt mock recognition "生成PostgreSQL的完整执行计划"
sqlopt mock optimize "生成一个语法级优化提案"
sqlopt mock result "生成一个可应用的补丁"

# 查看生成的 Mock 数据
sqlopt mock cat init
```

### 5.2 默认配置查找顺序

1. `./sqlopt.yml`（项目目录下）
2. `~/.sqlopt.yml`（用户 home 目录）
3. 若均不存在，报错提示用户创建

### 5.3 配置文件

```yaml
# sqlopt.yml
config_version: v1

contracts:
  version: "current"  # 契约版本，默认 current

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:password@localhost:5432/dbname

llm:
  enabled: true
  provider: opencode_run
```

### 5.4 禁止的设计

❌ `--to-stage` — 阶段顺序固定
❌ `--from-stage` — 阶段顺序固定
❌ `--skip-stages` — 阶段顺序固定
❌ 每个阶段都要传 `--config` — 默认路径即可

**原因**：阶段顺序是固定的 V9 流程，用户只需指定从哪开始。

---

## 7. Common 模块审计标准

### 6.1 进入 Common 的标准

必须同时满足：
1. 被 **2 个或以上阶段**使用
2. 与业务逻辑**无关**的基础设施
3. 不包含任何 SQL/数据库相关的业务逻辑

### 6.2 允许进入 Common 的模块

| 模块 | 被谁使用 | 理由 |
|------|---------|------|
| `contracts.py` | 所有阶段 | 契约验证基础设施 |
| `run_paths.py` | 所有阶段 | 路径管理基础设施 |
| `progress.py` | 所有阶段 | 进度报告基础设施 |
| `errors.py` | 所有阶段 | 错误定义基础设施 |
| `config.py` | 所有阶段 | 配置加载基础设施 |
| `llm.py` | 所有阶段 | **统一的大模型调用** |
| `llm_mock_generator.py` | 所有阶段 | **LLM 生成 Mock 测试数据** |

### 6.3 禁止进入 Common 的模块

| 模块 | 理由 | 正确位置 |
|------|------|---------|
| `branch_generator.py` | 只被 Parse 使用 | `parse/` |
| `rules_engine.py` | 只被 Optimize 使用 | `optimize/` |
| `llm_provider.py` | 只被 Optimize 使用，调用 common/llm.py | `optimize/` |
| `semantic_check.py` | 只被 Optimize 使用 | `optimize/` |
| `explain_collector.py` | 只被 Recognition 使用 | `recognition/` |
| `patch_generator.py` | 只被 Result 使用 | `result/` |

---

## 8. 实现顺序

1. **Common 模块** - 先实现公共基础设施
2. **Init 阶段** - 独立可运行
3. **Parse 阶段** - 依赖 Init
4. **Recognition 阶段** - 依赖 Parse
5. **Optimize 阶段** - 依赖 Recognition + Parse
6. **Patch 阶段** - 依赖 Optimize
7. **CLI 集成** - 调用各阶段

---

## 9. 成功标准

1. ✅ `sqlopt run --config sqlopt.yml` 完整运行
2. ✅ `sqlopt run --config sqlopt.yml <stage>` 从指定阶段开始
3. ✅ 每个阶段输出通过 `ContractValidator` 验证
4. ✅ Common 模块只包含被 2+ 阶段使用的代码
5. ✅ 无循环依赖：阶段间不直接调用
