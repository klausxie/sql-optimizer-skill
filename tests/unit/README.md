# 单元测试

测试单个组件/函数的功能，使用 mock 数据。

## 运行方式

```bash
# 运行所有单元测试
python3 -m pytest tests/unit/ -v

# 运行特定测试
python3 -m pytest tests/unit/test_baseline_module.py -v

# 运行特定测试函数
python3 -m pytest tests/unit/test_baseline_module.py::test_collect_baseline -v
```

## 现有测试

| 测试文件 | 组件 | 说明 |
|----------|------|------|
| test_baseline_module.py | BaselineCollector | 基线采集器 |
| test_baseline_explain_parser.py | EXPLAIN解析器 | MySQL/PG执行计划解析 |
| test_branching_module.py | Brancher | 分支生成器 |
| test_builtin_rules_detection.py | 风险检测规则 | 内置风险规则 |
| test_candidate_*.py | 候选生成 | 优化候选相关 |
| test_apply_mode.py | 应用模式 | 补丁应用模式 |
| test_commands_*.py | CLI命令 | 命令行接口 |

## 添加新单元测试

```python
# tests/unit/test_my_component.py
import pytest
from sqlopt.stages.my_component import MyClass

def test_my_class_basic():
    obj = MyClass()
    result = obj.process("input")
    assert result == "expected"

def test_my_class_edge_case():
    obj = MyClass()
    result = obj.process("")
    assert result is None
```

## Mock 数据

单元测试使用 mock 数据，不连接真实数据库。

如需使用真实数据库连接，使用集成测试 (`tests/integration/`)。
