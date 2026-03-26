# Python 代码规范

> **V10 SQL Optimizer - 代码规范手册**
>
> 整合 PEP 8、Google Python Style Guide + 项目 Lint 规则

---

## 1. 权威参考

| 标准 | 链接 | 用途 |
|------|------|------|
| **PEP 8** | https://pep8.org/ | 代码布局、命名、注释 |
| **Google Python Style Guide** | https://google.github.io/styleguide/pyguide.html | 类型注解、docstring |
| **PEP 484 (Type Hints)** | https://peps.python.org/pep-0484/ | 类型注解规范 |
| **ruff** | https://docs.astral.sh/ruff/ | Linter + Formatter |

---

## 2. Lint 工具配置

### 2.1 ruff 配置 (pyproject.toml)

```toml
[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "S",      # flake8-bandit (security)
    "YTT",    # flake8-2020
    "ASYNC",  # flake8-async
    "BLE",    # flake8-blind-except
    "FA",     # flake8-future-annotations
    "ISC",    # flake8-implicit-str-concat
    "PIE",    # flake8-pie
    "T20",    # flake8-print
    "PYI",    # flake8-pyi
    "RSE",    # flake8-raise
    "RET",    # flake8-return
    "SLF",    # flake8-self
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "ARG",    # flake8-arguments
    "PTH",    # flake8-use-pathlib
    "PL",     # pylint
    "PERF",   # perflint
    "RUF",    # Ruff-specific rules
]
ignore = [
    "E501",   # line-too-long (handled by formatter)
    "S101",   # assert (allowed in tests)
    "PLR0913", # too-many-arguments (allow for dataclasses)
    "PLR2004", # magic-value-comparison (allow for status codes)
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # unused-imports allowed in __init__
"tests/*" = ["S101", "F401", "F811"]  # tests can have asserts and unused
```

---

## 3. 命名规范 (Naming Conventions)

### 3.1 规则来源

来自 `.claude/lint/rules/naming.toml`

### 3.2 命名风格

| 风格 | 用途 | 示例 |
|------|------|------|
| `snake_case` | 变量、函数、方法、模块 | `sql_unit`, `extract_sql_units()` |
| `PascalCase` | 类、异常、TypeAlias | `SQLUnit`, `ConfigError` |
| `UPPER_CASE` | 常量、枚举值 | `MAX_RETRY_COUNT`, `SQLStatementType.SELECT` |
| `camelCase` | 不使用 (Python 不推荐) | - |

### 3.3 命名禁忌

| 禁止 | 错误示例 | 正确示例 |
|------|----------|----------|
| 单字母变量 (loop index 除外) | `x = get_data()` | `sql_data = get_data()` |
| 匈牙利命名 | `str_name` | `name: str` (用类型注解) |
|| 双下划线前缀 (dunder) | `__private_method()` | `_private_method()` |
| 与内置冲突 | `list = []` | `items = []` |

### 3.4 命名长度原则

| 场景 | 最小长度 | 最大长度 |
|------|----------|----------|
| 循环变量 | `i`, `j`, `k` | - |
| 私有方法 | - | 30 chars |
| 普通变量/函数 | 3 chars | 40 chars |
| 类名 | 3 chars | 40 chars |
| 常量 | 3 chars | 30 chars |

---

## 4. 错误处理规范 (Error Handling)

### 4.1 规则来源

来自 `.claude/lint/rules/error-handling.toml`

### 4.2 核心规则

#### 规则 1: 不许裸 try-except

```python
# ❌ 禁止 - 捕获所有异常
try:
    process(data)
except:
    pass

# ✅ 必须 - 捕获特定异常
try:
    process(data)
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise ConfigurationError(f"Failed to process: {e}") from e

# ✅ 必须 - 至少记录日志
try:
    process(data)
except Exception as e:
    logger.exception("Unexpected error in process()")
    raise
```

#### 规则 2: 不许空 catch 块

```python
# ❌ 禁止
except FileNotFoundError:
    pass  # 丢失错误信息

# ✅ 必须 - 至少记录日志
except FileNotFoundError:
    logger.warning("Config file not found, using defaults")

# ✅ 或者 - 传播给调用者
except FileNotFoundError:
    logger.debug("No override config, skipping")
    # 不需要处理，让调用者知道没有覆盖配置
```

#### 规则 3: 异常类型必须具体

```python
# ❌ 禁止 - 捕获通用异常
except Exception:
    handle_error()

# ✅ 必须 - 捕获具体异常
except (ValueError, TypeError) as e:
    handle_validation_error(e)

# ✅ 允许 - 已知可能失败的外部操作
except (requests.RequestException, json.JSONDecodeError) as e:
    logger.error(f"API request failed: {e}")
    raise APIError("Failed to fetch data") from e
```

#### 规则 4: 错误必须传播或记录

```python
# ❌ 禁止 - 静默吞掉错误
try:
    risky_operation()
except SomeError:
    pass  # 静默

# ✅ 必须 - 传播或记录
try:
    risky_operation()
except SomeError as e:
    logger.error(f"Operation failed: {e}")
    raise  # 传播给调用者

try:
    risky_operation()
except SomeError as e:
    logger.warning(f"Optional operation failed, continuing: {e}")
    # 不影响主流程，可以吞掉
```

#### 规则 5: 使用自定义异常类

```python
# ❌ 禁止 - 使用通用异常
raise RuntimeError("Invalid config")

# ✅ 必须 - 使用项目定义的异常
class ConfigurationError(SQLOptError):
    """配置相关错误"""
    pass

raise ConfigurationError("Database dsn is required")
```

---

## 5. 导入规范 (Import Conventions)

### 5.1 规则来源

来自 `.claude/lint/rules/imports.toml`

### 5.2 核心规则

#### 规则 1: 禁止 wildcard import

```python
# ❌ 禁止
from sqlopt.contracts import *
from typing import *

# ✅ 必须 - 显式导入
from sqlopt.contracts import InitOutput, ParseOutput
from typing import List, Dict, Optional
```

#### 规则 2: 导入顺序 (isort)

```python
# 标准库
import os
import sys
from typing import List, Dict

# 第三方库
import yaml
from rich.console import Console

# 本地应用
from sqlopt.common import config
from sqlopt.contracts import InitOutput
from sqlopt.stages import init
```

#### 规则 3: 禁止循环依赖

```python
# ❌ 禁止 - 循环依赖
# module_a.py
from module_b import b_func
def a_func(): pass

# module_b.py
from module_a import a_func
def b_func(): pass

# ✅ 解决方案 - 使用延迟导入或重构
# module_a.py
def a_func(): pass

def get_b():
    from module_b import b_func
    return b_func
```

#### 规则 4: 无未使用导入

```python
# ❌ 禁止
from sqlopt.common import config, errors, progress  # progress 未使用

# ✅ 必须 - 只导入使用的
from sqlopt.common import config, errors
```

---

## 6. 安全规范 (Security)

### 6.1 规则来源

来自 `.claude/lint/rules/security.toml`

### 6.2 核心规则

#### 规则 1: 禁止硬编码凭证

```python
# ❌ 禁止
dsn = "postgresql://user:password@localhost:5432/db"
api_key = "sk-1234567890abcdef"

# ✅ 必须 - 使用环境变量或配置
dsn = os.environ.get("DATABASE_URL")
api_key = config.secrets.get("api_key")
```

#### 规则 2: SQL 注入防护

```python
# ❌ 禁止 - 字符串拼接 SQL
query = "SELECT * FROM users WHERE id = " + user_id

# ✅ 必须 - 参数化查询
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))
```

#### 规则 3: 禁止 eval()

```python
# ❌ 禁止
code = compile(user_input, '<string>', 'eval')
result = eval(code)

# ✅ 必须 - 使用 ast.literal_eval 或 json.loads
result = ast.literal_eval(user_input)  # 仅支持字面量
result = json.loads(user_input)  # JSON
```

#### 规则 4: 输入验证

```python
# ✅ 必须 - 验证外部输入
def process_sql(sql_text: str) -> None:
    if not isinstance(sql_text, str):
        raise TypeError("sql_text must be str")
    if len(sql_text) > MAX_SQL_LENGTH:
        raise ValueError(f"SQL exceeds max length {MAX_SQL_LENGTH}")
    # process...
```

---

## 7. 类型注解规范 (Type Hints)

### 7.1 PEP 484 + Google Style

```python
# ✅ 函数注解
def process_sql_units(units: List[SQLUnit]) -> ParseOutput:
    ...

# ✅ 复杂类型使用 TypeAlias
SQLUnitMap = Dict[str, SQLUnit]

# ✅ 可选参数
def find_unit_by_id(units: List[SQLUnit], unit_id: str) -> Optional[SQLUnit]:
    ...

# ✅ 不使用 Any
# ❌ def process(x: Any) -> Any
# ✅ def process(x: SQLUnit) -> ParseOutput
```

### 7.2 类型注解规则

| 规则 | 说明 |
|------|------|
| 公开 API 必须注解 | `def` 和 `async def` 的参数和返回值 |
| 局部变量尽量注解 | 提高代码可读性 |
| 禁止使用 `Any` | 使用具体类型或 `Optional[X]` |
| 类型别名用 `TypeAlias` | PEP 613 |

---

## 8. Docstring 规范

### 8.1 Google Style

```python
def process_sql_units(units: List[SQLUnit]) -> ParseOutput:
    """处理 SQL 单元列表，展开分支路径。
    
    Args:
        units: 从 Init 阶段提取的 SQL 单元列表
        
    Returns:
        ParseOutput: 包含展开分支的 SQL 单元和风险列表
        
    Raises:
        ConfigurationError: 当配置无效时
        ParseError: 当 XML 解析失败时
        
    Example:
        >>> units = [SQLUnit(id="u1", ...)]
        >>> output = process_sql_units(units)
        >>> len(output.sql_units_with_branches)
        5
    """
```

---

## 9. 代码布局 (PEP 8)

### 9.1 缩进

```python
# ✅ 4 spaces
def indent_example():
    if condition:
        do_something()
    else:
        do_other()
```

### 9.2 行长度

```python
# ✅ 最大 100 字符 (pyproject.toml line-length = 100)
# 使用括号续行
result = some_function(
    arg1="value1",
    arg2="value2",
)
```

### 9.3 空行

```python
class MyClass:
    def method1(self): ...
    def method2(self): ...
    # 2 空行分隔方法组


class AnotherClass:
    ...
```

### 9.4 import 格式

```python
# 标准库
import os
import sys
from typing import List, Optional

# 第三方
import yaml
from rich.console import Console

# 本地
from sqlopt.common import config
```

---

## 10. 测试规范

### 10.1 命名

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 测试文件 | `test_<module>.py` | `test_config.py` |
| 测试类 | `Test<Module>` | `TestConfig` |
| 测试函数 | `test_<description>` | `test_load_config_valid_yaml` |

### 10.2 测试结构

```python
import pytest
from sqlopt.common.config import load_config

class TestConfig:
    """配置模块测试"""
    
    def test_load_config_valid_yaml(self, tmp_path):
        """测试加载有效 YAML 配置"""
        # Arrange
        config_file = tmp_path / "sqlopt.yml"
        config_file.write_text("db:\n  platform: postgresql\n")
        
        # Act
        config = load_config(str(config_file))
        
        # Assert
        assert config.db.platform == "postgresql"
    
    def test_load_config_missing_required_field(self, tmp_path):
        """测试缺少必填字段时抛出错误"""
        config_file = tmp_path / "sqlopt.yml"
        config_file.write_text("db: {}")  # 缺少 platform
        
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(str(config_file))
        
        assert "platform" in str(exc_info.value)
```

### 10.3 测试规则

| 规则 | 说明 |
|------|------|
| Arrange-Act-Assert | 每个测试三个部分 |
| 一个测试一个断言 | 便于定位问题 |
| 测试文件名匹配 | `test_<module>.py` |
| fixtures 复用 | 使用 `@pytest.fixture` |

---

## 11. 常见错误对照表

| 错误 | 错误写法 | 正确写法 |
|------|----------|----------|
| 裸 except | `except:` | `except SpecificError:` |
| 空 except | `except: pass` | `except: logger.warning(...)` |
| 硬编码密码 | `password="secret"` | `password=os.environ["PASSWORD"]` |
| Wildcard import | `from X import *` | `from X import Y, Z` |
| 使用 Any | `x: Any` | `x: SQLUnit` |
| 行太长 | `x = func(a, b, c, d, e, f, g)` | `x = func(a, b, c, d, e,\n    f, g)` |
| 可变默认参数 | `def f(x=[])` | `def f(x=None): if x is None: x = []` |
| 字符串拼 SQL | `"SELECT * FROM " + table` | `"SELECT * FROM %s"` + params |

---

## 12. Lint 检查命令

```bash
# 运行 ruff 检查
cd python
ruff check sqlopt/

# 自动修复 (不安全，但快速)
ruff check --fix sqlopt/

# 类型检查 (需要 mypy)
mypy sqlopt/ --ignore-missing-imports

# 完整检查 (CI 用)
ruff check sqlopt/ && mypy sqlopt/ --ignore-missing-imports
```

---

## 13. 闭环机制 (Closure)

### 13.1 Pre-commit Hook

项目使用 `.claude/lint/pre-commit.sh` 作为**自动检查机制**：

```bash
# 安装 pre-commit hook (首次设置)
cp .claude/lint/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# 或使用 git config
git config core.hooksPath .claude/lint
```

### 13.2 严格模式 (Strict Mode)

| 行为 | 说明 |
|------|------|
| **Lint 失败** | `exit 1` - 阻止提交 |
| **Lint 通过** | `exit 0` - 允许提交 |
| **无 staged 文件** | `exit 0` - 允许提交 |

### 13.3 触发流程

```
git add <files>
git commit
    ↓
pre-commit.sh 自动运行
    ↓
检测语言 → 运行对应 linter
    ↓
失败? → exit 1 (阻止提交)
成功? → exit 0 (允许提交)
```

### 13.4 人工检查命令

```bash
# 手动运行 lint 检查
.claude/lint/pre-commit.sh

# 或直接用 ruff
cd python && ruff check sqlopt/

# 查看详细错误
cd python && ruff check sqlopt/ --show-source
```

### 13.5 Lint 规则文件

| 文件 | 用途 |
|------|------|
| `.claude/lint/index.toml` | AI 可读的规则索引 |
| `.claude/lint/rules/naming.toml` | 命名规范 |
| `.claude/lint/rules/error-handling.toml` | 错误处理规范 |
| `.claude/lint/rules/imports.toml` | 导入规范 |
| `.claude/lint/rules/security.toml` | 安全规范 |
| `.claude/lint/config/python.toml` | ruff 配置 |
| `.claude/lint/pre-commit.sh` | pre-commit hook |

---

## 14. 阶段报告规范 (Stage Reports)

### 14.1 核心要求

每个阶段执行完成后必须生成 `SUMMARY.md` 报告，包含该阶段的执行情况。

### 14.2 报告内容要求

| 内容 | 说明 |
|------|------|
| 阶段名称 | 如 "INIT 阶段报告" |
| 运行ID | 用于追踪本次执行 |
| 耗时 | 执行时间（秒） |
| 统计信息 | SQL单元数、分支数、文件数、文件大小 |
| 数据契约说明 | 该阶段使用的数据结构解释 |
| 错误列表 | 如有错误，显示错误信息 |
| 警告列表 | 如有警告，显示警告信息 |

### 14.3 语言要求

**所有阶段报告必须使用中文**：
- 标题用中文：如 `# INIT 阶段报告`
- 标签用中文：如 `| SQL单元数 |` 而不是 `| SQL Units |`
- 错误提示用中文

### 14.4 生成约束

| 约束 | 说明 |
|------|------|
| Best-effort | 报告生成失败不阻塞阶段完成 |
| 大小限制 | 单个报告不超过 50KB |
| 原子写入 | 使用 temp+rename 模式 |
| 位置 | `runs/{run_id}/{stage}/SUMMARY.md` |

### 14.5 功能变化必须更新报告

**强制规则**：任何阶段的功能变化（如新增字段、新增输出文件、流程调整等），必须同步更新该阶段的 `SUMMARY.md` 生成逻辑：

```python
# ✅ 正确：在修改功能时同时更新报告
def _generate_summary(self, run_id: str, output: MyOutput) -> None:
    """生成阶段报告。
    
    注意：每次修改阶段功能时，必须同步更新此方法。
    """
    try:
        summary = StageSummary(
            stage_name=self.stage_name,
            run_id=run_id,
            duration_seconds=time.time() - self.start_time,
            # 新增字段必须同步添加到这里
            new_field_count=len(output.new_fields),
            ...
        )
        summary_path.write_text(generate_summary_markdown(summary), encoding="utf-8")
    except Exception as e:
        logger.warning(f"生成阶段报告失败，不影响阶段执行: {e}")

# ❌ 错误：修改功能但不更新报告
def _generate_summary(self, run_id: str, output: MyOutput) -> None:
    # 报告内容与实际功能脱节
    pass
```

### 14.6 报告生成位置

```
runs/
└── {run_id}/
    ├── init/SUMMARY.md        # Init 阶段报告
    ├── parse/SUMMARY.md       # Parse 阶段报告
    ├── recognition/SUMMARY.md # Recognition 阶段报告
    ├── optimize/SUMMARY.md    # Optimize 阶段报告
    └── result/SUMMARY.md     # Result 阶段报告
```

---

## 15. 参考

- [PEP 8](https://pep8.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [ruff docs](https://docs.astral.sh/ruff/)
- [Type Hints cheat sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)
