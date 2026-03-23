# Common 模块总览

> 被 2+ 阶段使用的公共基础设施

---

## 1. 设计原则

### 1.1 进入 Common 的标准

必须同时满足：
1. 被 **2 个或以上阶段**使用
2. 与业务逻辑**无关**的基础设施
3. 不包含任何 SQL/数据库相关的业务逻辑

### 1.2 禁止进入 Common 的模块

| 模块 | 理由 | 正确位置 |
|------|------|---------|
| `branch_generator.py` | 只被 Parse 使用 | `parse/` |
| `rules_engine.py` | 只被 Optimize 使用 | `optimize/` |
| `llm_provider.py` | 只被 Optimize 使用 | `optimize/` |
| `semantic_check.py` | 只被 Optimize 使用 | `optimize/` |
| `explain_collector.py` | 只被 Recognition 使用 | `recognition/` |
| `patch_generator.py` | 只被 Result 使用 | `result/` |

---

## 2. 模块清单

```
common/
├── __init__.py
├── contracts.py         # 契约验证
├── run_paths.py         # 路径管理
├── progress.py          # 进度报告
├── errors.py           # 错误定义
├── config.py           # 配置加载
├── db_connector.py     # 数据库连接
├── llm.py              # 统一的大模型调用
├── llm_mock_generator.py # LLM 生成 Mock 测试数据
└── README.md          # 本文档
```

---

## 3. 各模块说明

### 3.1 contracts.py - 契约验证

**职责**：验证 JSON 文件是否符合 Schema 规范

**被谁使用**：所有阶段

**API**：
```python
from common.contracts import ContractValidator

validator = ContractValidator()
errors = validator.validate_file("init/sql_units.json", "sqlunit.schema.json")
# errors = [] 表示验证通过
```

### 3.2 run_paths.py - 路径管理

**职责**：管理运行目录和文件路径

**被谁使用**：所有阶段

**API**：
```python
from common.run_paths import RunPaths

paths = RunPaths(run_id="test-run")
paths.init_dir()  # 创建所有阶段目录
paths.init_sql_units  # init/sql_units.json
paths.parse_sql_units  # parse/sql_units.json
paths.recognition_baselines  # recognition/baselines.json
paths.optimize_proposals  # optimize/proposals.json
paths.patch_patches  # patch/patches.json
```

### 3.3 progress.py - 进度报告

**职责**：报告阶段执行进度

**被谁使用**：所有阶段

**API**：
```python
from common.progress import ProgressReporter

reporter = ProgressReporter(run_id="test-run", total=100)
reporter.start_stage("init")
reporter.update(50)  # 50% 完成
reporter.complete_stage("init")
```

### 3.4 errors.py - 错误定义

**职责**：定义和分类错误

**被谁使用**：所有阶段

**API**：
```python
from common.errors import SqlOptError, ValidationError, DatabaseError

raise SqlOptError("INIT_001", "Failed to scan XML files")
raise ValidationError("PARSE_001", "Invalid sqlunit format")
```

### 3.5 config.py - 配置加载

**职责**：加载和解析配置文件

**被谁使用**：所有阶段

**API**：
```python
from common.config import load_config, validate_config

config = load_config("sqlopt.yml")
errors = validate_config(config)
# errors = [] 表示配置有效
```

### 3.6 db_connector.py - 数据库连接

**职责**：管理数据库连接

**被谁使用**：Init（连接验证）, Recognition（EXPLAIN 执行）

**API**：
```python
from common.db_connector import DbConnector

conn = DbConnector(config["db"])
conn.connect()
result = conn.execute("EXPLAIN SELECT * FROM users")
conn.disconnect()
```

### 3.7 llm.py - 统一的大模型调用

**职责**：统一管理 LLM 调用，提供标准接口

**被谁使用**：Optimize（生成优化建议）、Common（生成 Mock 数据）

**API**：
```python
from common.llm import LLM

llm = LLM(config["llm"])

# 同步调用
response = llm.complete("你的 SQL 有哪些优化建议？")

# 流式调用
for chunk in llm.stream_complete("解释一下执行计划"):
    print(chunk, end="")
```

### 3.8 llm_mock_generator.py - LLM 生成 Mock 测试数据

**职责**：基于阶段数据契约 + 用户描述，用 LLM 生成模拟入餐数据

**被谁使用**：所有阶段（用于独立调测）

**核心价值**：
- 阶段可以**独立调测**，不依赖上游输出
- LLM 根据用户描述 + Schema 生成真实的测试数据
- 可以生成**正向**（valid）和**负向**（invalid）测试用例

**API**：
```python
from common.llm_mock_generator import LLMMockGenerator

generator = FixtureGenerator(llm_config=config["llm"])

# 用户描述想要什么样的测试数据
user_prompt = "生成一个复杂的包含多个if标签和include引用的SQL单元"

# 生成 Init 阶段的 Mock 数据
mock_data = generator.generate("init", user_prompt=user_prompt)
# 返回模拟的 init/sql_units.json

# 生成 Parse 阶段的 Mock 数据
user_prompt = "生成一个包含include引用和foreach循环的SQL"
mock_data = generator.generate("parse", user_prompt=user_prompt)
# 返回模拟的 parse/sql_units.json（带 branches）

# 生成带错误的测试数据（用于测试错误处理）
mock_data = generator.generate("init", user_prompt="生成一个缺少必填字段的无效数据", valid=False)
```

**CLI 使用**：
```bash
# 用户描述想要什么样的测试数据，LLM 生成
sqlopt mock init "生成一个复杂的包含多个if标签的SQL单元"
sqlopt mock parse "生成一个包含include和foreach的SQL"
sqlopt mock recognition "生成PostgreSQL的完整执行计划"
sqlopt mock optimize "生成一个语法级优化提案"
sqlopt mock result "生成一个可应用的补丁"

# 查看生成的 Mock 数据
sqlopt mock cat init
```

---

## 4. 快速调测

### 4.1 测试配置加载

```python
# test_config.py
import sys
sys.path.insert(0, '/path/to/python')

from common.config import load_config, validate_config

config = load_config('/tmp/sqlopt-test/sqlopt.yml')
errors = validate_config(config)
print(f"Errors: {errors}")
print(f"Config: {config}")
```

### 4.2 测试契约验证

```python
# test_contracts.py
import sys
sys.path.insert(0, '/path/to/python')
import json

from common.contracts import ContractValidator

validator = ContractValidator()
with open('/tmp/sqlopt-test/runs/test-run/init/sql_units.json') as f:
    data = json.load(f)

errors = validator.validate(data, "sqlunit.schema.json")
print(f"Validation errors: {errors}")
```

---

## 5. 修改指南

### 5.1 改契约验证逻辑

**文件**：`common/contracts.py`

**原因**：需要支持新的 Schema 或修改验证逻辑

**修改**：编辑 `contracts.py`

### 5.2 改路径逻辑

**文件**：`common/run_paths.py`

**原因**：需要修改目录结构

**修改**：编辑 `run_paths.py`

### 5.3 改配置加载

**文件**：`common/config.py`

**原因**：需要支持新的配置项

**修改**：编辑 `config.py`

---

## 6. 审计清单

添加新模块到 Common 前，必须确认：

- [ ] 被几个阶段使用？（必须是 2+）
- [ ] 是否是基础设施？（不是业务逻辑）
- [ ] 是否包含 SQL/数据库逻辑？（不能包含）

如果不满足，模块应该放在对应阶段目录下。
