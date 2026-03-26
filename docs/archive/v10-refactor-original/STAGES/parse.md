# Parse 阶段设计文档

> 当前实现版本：V10-Refactor

---

## 1. 阶段概述

Parse 阶段是 SQL 优化流水线的第二个阶段，负责将 MyBatis XML 中的动态 SQL（如 `<if>`, `<choose>`, `<foreach>` 等）展开为多个可执行的分支。

### 1.1 输入输出

| 项目 | 说明 |
|------|------|
| **输入** | `sql_units.json` (Init 阶段输出) |
| **输出** | `sql_units_with_branches.json` |
| **配置** | `parse_strategy`, `parse_max_branches` |

### 1.2 数据流

```
Init 阶段输出
    │
    │ sql_units: List[SQLUnit]
    │   └── SQLUnit(id, sql_text, ...)
    │
    ▼
Parse 阶段
    │
    ├─ BranchExpander.expand(sql_text)
    │       │
    │       ▼
    │   XMLLanguageDriver.create_sql_source()
    │       │
    │       ▼
    │   SqlNode Tree
    │       │
    │       ▼
    │   BranchGenerator.generate()
    │       │
    │       ▼
    │   List[ExpandedBranch]
    │
    ▼
ParseOutput
    │
    └── sql_units_with_branches: List[SQLUnitWithBranches]
```

---

## 2. 文件结构

```
python/sqlopt/
├── stages/
│   ├── parse/                           # Parse 阶段
│   │   ├── __init__.py
│   │   ├── stage.py                    # ParseStage 入口 (93行)
│   │   ├── branch_expander.py          # 核心展开器 (141行)
│   │   └── expander.py                # 向后兼容包装器 (31行)
│   │
│   └── branching/                      # 分支生成核心模块
│       ├── __init__.py
│       ├── branch_generator.py         # 分支生成器 (1459行)
│       ├── branch_strategy.py          # 策略实现 (559行)
│       ├── xml_language_driver.py     # XML → SqlNode
│       ├── sql_node.py               # SqlNode 树结构
│       ├── mutex_branch_detector.py   # Choose/When 互斥检测
│       ├── dynamic_context.py
│       ├── expression_evaluator.py
│       ├── fragment_registry.py
│       └── xml_script_builder.py
│
├── common/
│   └── config.py                      # 配置管理
│
└── contracts/
    └── parse.py                      # Parse 阶段数据契约
```

---

## 3. 核心组件

### 3.1 ParseStage

**文件**: `python/sqlopt/stages/parse/stage.py`

```python
class ParseStage(Stage[None, ParseOutput]):
    def __init__(self, run_id: str | None = None, use_mock: bool = True, config: SQLOptConfig | None = None):
        self.run_id = run_id
        self.use_mock = use_mock
        self.config = config

    def run(self, ...) -> ParseOutput:
        # 1. 从 Init 阶段读取 SQL units
        # 2. 创建 BranchExpander (使用 config.parse_strategy, config.parse_max_branches)
        # 3. 对每个 SQL unit 调用 expander.expand()
        # 4. 组装 ParseOutput 返回
```

**职责**:
- 读取 Init 阶段输出的 `sql_units.json`
- 创建 `BranchExpander` 实例
- 遍历所有 SQL units，调用展开器
- 组装 `ParseOutput` 返回

### 3.2 BranchExpander

**文件**: `python/sqlopt/stages/parse/branch_expander.py`

```python
@dataclass
class ExpandedBranch:
    path_id: str
    condition: str | None
    expanded_sql: str
    is_valid: bool

class BranchExpander:
    def __init__(self, strategy: str = "ladder", max_branches: int = 50):
        self.strategy = strategy
        self.max_branches = max_branches

    def expand(self, sql_text: str) -> List[ExpandedBranch]:
        # 1. 调用 XMLLanguageDriver 解析 XML → SqlNode
        # 2. 调用 BranchGenerator 生成分支
        # 3. 映射结果返回
```

**职责**:
- 封装 XML 解析和分支生成
- 提供统一的 `expand()` 接口
- 错误处理 (XML 解析失败时返回默认分支)

### 3.3 BranchGenerator

**文件**: `python/sqlopt/stages/branching/branch_generator.py`

```python
class BranchGenerator:
    def __init__(self, strategy: str = "all_combinations", max_branches: int = 100):
        self.strategy = strategy
        self.max_branches = max_branches
        self._strategy = create_strategy(strategy)

    def generate(self, sql_node: SqlNode) -> List[Dict[str, Any]]:
        # 返回: List[{branch_id, active_conditions, sql, condition_count, risk_flags}]
```

**职责**:
- 遍历 SqlNode 树，收集所有条件节点
- 检测 choose 节点 (互斥分支)
- 使用策略生成分支组合
- 检测并标记风险 (risk_flags)

### 3.4 LadderSamplingStrategy

**文件**: `python/sqlopt/stages/branching/branch_strategy.py` (第 188-532 行)

```python
class LadderSamplingStrategy(BranchGenerationStrategy):
    def __init__(self, condition_weights: dict | None = None, table_metadata: dict | None = None):
        self.condition_weights = condition_weights or {}
        self.table_metadata = table_metadata or {}

    def generate(self, conditions: List[str], max_branches: int = 100) -> List[List[str]]:
        # 四步采样流程
```

**职责**:
- 实现阶梯采样策略
- 计算条件风险权重
- 优先选择高风险分支组合

---

## 4. 配置项

### 4.1 SQLOptConfig

**文件**: `python/sqlopt/common/config.py`

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `parse_strategy` | str | `"ladder"` | 采样策略 |
| `parse_max_branches` | int | `50` | 每条 SQL 最大分支数 |

### 4.2 可用策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `ladder` | 阶梯采样，平衡覆盖与数量 | **默认**，生产环境 |
| `all_combinations` | 2^n 全组合 | 条件 < 10 |
| `pairwise` | 两两组合 | 条件较多 |
| `boundary` | 边界值 (全 T/全 F) | 快速验证 |

### 4.3 YAML 配置示例

```yaml
# sqlopt.yml
parse_strategy: ladder
parse_max_branches: 50
```

---

## 5. LadderSamplingStrategy 详细设计

### 5.1 四步采样流程

```
输入: N 个条件 → 输出: M 个分支 (M ≤ max_branches)

Step 1: 单因素覆盖 (N+1 分支)
  - All False (基准)
  - [cond1], [cond2], ... [condN] (每条件单独 True)

Step 2: 高权重两两组合 (Top-K pairs)
  - 按 (w_i + w_j) 排序，取 top-10

Step 3: 高权重三三组合 (Top-K triples)
  - 按 (w_i + w_j + w_k) 排序，取 top-5

Step 4: 贪心填充
  - 选择总权重最高的未覆盖组合，填满 max_branches
```

### 5.2 风险权重体系

#### 基础权重
```python
weight = 1.0  # 所有条件的基础风险
```

#### 文本模式匹配 (+1 ~ +3)

| 模式 | 加权 | 代码位置 |
|------|------|----------|
| 大表关键词 (users/orders/logs) | +3 | branch_strategy.py:441-442 |
| JOIN | +2 | branch_strategy.py:443-444 |
| SELECT * | +2 | branch_strategy.py:445-446 |
| 子查询/IN | +2 | branch_strategy.py:447-448 |
| LIKE 含 `%` | +2 | branch_strategy.py:449-450 |
| OR 条件 | +1 | branch_strategy.py:451-452 |
| ORDER BY | +1 | branch_strategy.py:453-454 |
| GROUP BY | +1 | branch_strategy.py:455-456 |

#### 函数包装 (索引杀手) (+2 ~ +3)

**代码位置**: `branch_strategy.py:223-265`

```python
FUNCTION_WRAPPER_PATTERNS = {
    # 日期函数 (+3)
    "year(": 3, "month(": 3, "day(": 3,
    "date_format(": 3, "extract(": 3,
    "dateadd(": 2, "datediff(": 2, "dayofyear(": 2, "weekday(": 2,
    
    # 字符串函数 (+3)
    "concat(": 3, "upper(": 3, "lower(": 3,
    "substring(": 3, "substr(": 3, "trim(": 2,
    "ltrim(": 2, "rtrim(": 2, "lpad(": 2, "rpad(": 2,
    "replace(": 2, "reverse(": 2,
    
    # 类型转换 (+3)
    "cast(": 3, "convert(": 3,
    
    # 空值处理 (+2)
    "coalesce(": 2, "ifnull(": 2, "nvl(": 2, "isnull(": 2,
    
    # 数学函数 (+2)
    "abs(": 2, "round(": 2, "floor(": 2, "ceil(": 2, "ceiling(": 2,
    "mod(": 1, "sqrt(": 1, "pow(": 1, "power(": 1,
    
    # 长度计算 (+2)
    "length(": 2, "char_length(": 2, "character_length(": 2,
    "octet_length(": 1, "bit_length(": 1,
}
```

#### 字段类型风险 (+2 ~ +3)

**代码位置**: `branch_strategy.py:267-277`

```python
FIELD_TYPE_PATTERNS = {
    "text": 3, "blob": 3, "clob": 3,  # 无法建索引
    "json": 2, "xml": 2,  # 解析开销
    "geometry": 2, "geography": 2,  # 空间计算
    "varchar(1000)": 2, "varchar(2000)": 2,  # 超长 varchar
}
```

#### 风险模式正则 (+1 ~ +3)

**代码位置**: `branch_strategy.py:279-300`

```python
RISK_PATTERNS = {
    r"like\s+['\"]%": 3,  # LIKE '%xxx' 前缀通配
    r"not\s+like": 2,  # NOT LIKE
    r"not\s+in": 2, r"not\s+exists": 2,  # NOT 条件
    r"is\s+not\s+null": 1,  # IS NOT NULL
    r"offset\s+\d+": 2,  # 深分页
    r"limit\s+\d+.*offset": 2,  # LIMIT ... OFFSET
    r"in\s*\(\s*\d+\s*(,\s*\d+){10,}": 2,  # 大 IN 列表 (>10个)
    r"=\s*['\"]\d+['\"]": 2,  # 隐式类型转换
    r"like\s+['\"]\d+['\"]": 2,  # LIKE '123' on numeric
    r"where\s+\w+\s*\*\s*[]<>=]": 3,  # 表达式非SARGable
    r"where\s+\w+\s*[+-]\s*\d+\s*[<>]": 2,  # column +/- const
    r"where\s+abs(": 2,  # WHERE ABS(column)
    r"where\s+year(": 3, r"where\s+month(": 3,  # 日期函数在 WHERE
    r"union\s+(?!all)": 2,  # UNION (非 ALL)
    r"distinct\s+": 2,  # DISTINCT 无索引
    r"having\s+\w+\s*[<>]": 2,  # HAVING 非索引列
    r"where\s+\w+\s+in\s*\(\s*select": 3,  # 相关子查询
    r"exists\s*\(\s*select": 2,  # EXISTS 子查询
}
```

#### 非 SARGable 前缀检测 (+2)

**代码位置**: `branch_strategy.py:302-307, 473-478`

```python
NON_SARGABLE_PREFIXES = [
    r"^%",           # LIKE '%xxx'
    r"^not\s+",     # NOT column = value
    r"^\w+\s*\(",   # Function wrapping column
    r"^\d+\s*[<>]", # Leading comparison
]
```

#### 表元数据增强 (+1 ~ +2)

**代码位置**: `branch_strategy.py:480-504`

```python
# table_metadata 格式
{
    "users": {
        "size": "large",  # "large" | "medium" | "small"
        "indexes": ["id", "email", "created_at"]
    },
    "orders": {
        "size": "medium",
        "indexes": ["id", "user_id"]
    }
}

# 权重调整
大表 (size=large) → +2
中表 (size=medium) → +1
列无索引 → +2
```

### 5.3 权重计算流程

**方法**: `_get_condition_weight(condition: str) -> float`

**代码位置**: `branch_strategy.py:425-483`

```python
def _get_condition_weight(self, condition: str) -> float:
    # 1. 自定义权重 (优先)
    if condition in self.condition_weights:
        return self.condition_weights[condition]

    weight = 1.0  # 基础权重
    cond_lower = condition.lower()

    # 2. 文本模式匹配 (+3, +2, +1)
    # 3. 函数包装检测 (FUNCTION_WRAPPER_PATTERNS)
    # 4. 字段类型检测 (FIELD_TYPE_PATTERNS)
    # 5. 风险模式正则检测 (RISK_PATTERNS)
    # 6. 非 SARGable 前缀检测 (NON_SARGABLE_PREFIXES)
    # 7. 表元数据增强 (table_metadata)

    return weight
```

### 5.4 覆盖率估算

| 场景 | 占比 | 覆盖率 |
|------|------|--------|
| 单因素问题 | 60% | 100% (Step 1) |
| 两两组合问题 | 25% | ~40% (Step 2, top pairs) |
| 三三组合问题 | 10% | ~15% (Step 3, top triples) |
| **综合 recall** | | **~62%** |

---

## 6. 数据契约

### 6.1 SQLBranch (Parse 阶段使用)

**文件**: `python/sqlopt/contracts/parse.py`

```python
@dataclass
class SQLBranch:
    path_id: str                    # 分支唯一标识
    condition: str | None           # 激活条件
    expanded_sql: str               # 展开后的 SQL
    is_valid: bool                  # 是否有效
    risk_flags: list[str] = field(default_factory=list)   # 风险标记
    active_conditions: list[str] = field(default_factory=list)  # 激活的条件列表
```

### 6.2 ParseOutput

**文件**: `python/sqlopt/contracts/parse.py`

```python
@dataclass
class ParseOutput:
    sql_units_with_branches: List[SQLUnitWithBranches]

@dataclass
class SQLUnitWithBranches:
    sql_unit_id: str
    branches: List[SQLBranch]
```

---

## 7. 展开流程详解

### 7.1 单条 SQL 展开流程

```
输入: 
  sql_text = '''
    SELECT * FROM users 
    <if test="name != null">WHERE name = #{name}</if>
    <if test="status != null">AND status = #{status}</if>
  '''

Step 1: XMLLanguageDriver.create_sql_source()
  输出: SqlNode Tree

Step 2: BranchGenerator.generate(sql_node)
  - 收集条件: ["name != null", "status != null"]
  - 互斥检测: 无 (if 不是 choose)
  - 策略选择: LadderSamplingStrategy

Step 3: LadderSamplingStrategy.generate(conditions, max_branches=50)
  输出: [["name != null"], ["status != null"], []]

Step 4: BranchExpander._map_branches()
  输出: List[ExpandedBranch]
    - ExpandedBranch(path_id="branch_0", condition="name != null", ...)
    - ExpandedBranch(path_id="branch_1", condition="status != null", ...)
    - ExpandedBranch(path_id="branch_2", condition=None, ...)

输出:
  [
    SQLBranch(path_id="branch_0", condition="name != null", expanded_sql="SELECT * FROM users WHERE name = #{name}", ...),
    SQLBranch(path_id="branch_1", condition="status != null", expanded_sql="SELECT * FROM users AND status = #{status}", ...),
    SQLBranch(path_id="branch_2", condition=None, expanded_sql="SELECT * FROM users", ...)
  ]
```

---

## 8. 错误处理

### 8.1 XML 解析失败

**位置**: `branch_expander.py:80-89`

```python
try:
    sql_node = XMLLanguageDriver.create_sql_source(sql_text)
    # ...
except (ValueError, RuntimeError, TypeError, xml.etree.ElementTree.ParseError):
    # 返回默认分支，不中断流程
    return [ExpandedBranch(
        path_id="default",
        condition=None,
        expanded_sql=self._strip_xml_tags(sql_text),
        is_valid=True,
    )]
```

---

## 9. 向后兼容性

### 9.1 expander.py 包装器

**文件**: `python/sqlopt/stages/parse/expander.py`

```python
# 保留旧的 expand_branches() 接口，内部委托给 BranchExpander
def expand_branches(sql_text: str) -> list[ExpandedBranch]:
    expander = BranchExpander(strategy="ladder", max_branches=50)
    return expander.expand(sql_text)
```

---

## 10. 测试

### 10.1 测试文件

| 测试 | 文件 | 数量 |
|------|------|------|
| BranchExpander 单元测试 | `tests/unit/test_branch_expander.py` | 4 |
| ParseStage 集成测试 | `tests/unit/test_parse_stage.py` | 4 |
| expander 回归测试 | `tests/unit/test_parse_expander.py` | 11 |

### 10.2 运行测试

```bash
# 运行 Parse 阶段相关测试
python -m pytest tests/unit/test_branch_expander.py tests/unit/test_parse_stage.py tests/unit/test_parse_expander.py -v

# 运行所有测试
python -m pytest tests/unit/ -v
```

### 10.3 测试结果

```
============================= 372 passed in 1.54s ==============================
```

---

## 11. 使用示例

### 11.1 直接使用 BranchExpander

```python
from sqlopt.stages.parse.branch_expander import BranchExpander

expander = BranchExpander(strategy="ladder", max_branches=50)
sql = '''SELECT * FROM users 
<if test="name != null">WHERE name = #{name}</if>'''

branches = expander.expand(sql)
for b in branches:
    print(f"{b.path_id}: {b.expanded_sql}")
```

### 11.2 通过 ParseStage 使用

```python
from sqlopt.common.config import SQLOptConfig
from sqlopt.stages.parse.stage import ParseStage

config = SQLOptConfig(
    parse_strategy="ladder",
    parse_max_branches=50
)
stage = ParseStage(run_id="test", config=config)
output = stage.run()
```

### 11.3 通过 YAML 配置使用

```yaml
# sqlopt.yml
parse_strategy: ladder
parse_max_branches: 50
```

```bash
sqlopt run parse --config sqlopt.yml
```

---

## 12. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| BranchExpander 封装 | 新增独立类 | 保持 BranchGenerator 独立可测试 |
| 策略注入方式 | 构造函数注入 | 运行时可切换策略 |
| 错误处理策略 | 返回默认分支 | 单条 SQL 失败不中断整阶段 |
| 向后兼容 | expander.py 委托 | 不破坏现有调用方 |
| 表元数据 | 构造函数注入 | 支持外部提供，表结构可更新 |

---

## 13. 尚待完善的功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| table_metadata 传入 | 目前为空，需从 Init 阶段或配置传入 | 高 |
| risk_flags 传播 | 目前为空列表，未从 BranchGenerator 传递 | 中 |
| active_conditions 传播 | 目前为空列表，未从 BranchGenerator 传递 | 中 |
| 自定义函数白名单 | 用户可配置已知安全的函数 | 低 |

---

## 14. 代码位置索引

### 14.1 Parse 阶段入口
- `python/sqlopt/stages/parse/stage.py` - ParseStage 类

### 14.2 核心展开器
- `python/sqlopt/stages/parse/branch_expander.py` - BranchExpander 类, ExpandedBranch 数据类

### 14.3 向后兼容包装器
- `python/sqlopt/stages/parse/expander.py` - expand_branches() 函数

### 14.4 分支生成核心
- `python/sqlopt/stages/branching/branch_generator.py` - BranchGenerator 类
- `python/sqlopt/stages/branching/branch_strategy.py` - 策略实现 (LadderSamplingStrategy 等)
- `python/sqlopt/stages/branching/xml_language_driver.py` - XMLLanguageDriver 类
- `python/sqlopt/stages/branching/sql_node.py` - SqlNode 树结构

### 14.5 配置与契约
- `python/sqlopt/common/config.py` - SQLOptConfig 类
- `python/sqlopt/contracts/parse.py` - ParseOutput, SQLBranch 等数据类

---

*文档版本: v1.0*
*最后更新: 2026-03-25*
