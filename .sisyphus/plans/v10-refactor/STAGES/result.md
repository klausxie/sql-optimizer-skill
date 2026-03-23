# Result 阶段

> 汇总输出：根据优化类型，分发到 Patch 或 Report

---

## 1. 阶段职责

**核心职责**：
1. 根据 Optimize 的输出类型，分发到不同处理流程
2. **Patch 流程**：对可验证的语法级优化，生成并应用 XML 补丁
3. **Report 流程**：对不可验证的结构级建议，生成用户决策报告

**两条输出路径**：

```
Optimize 输出
    │
    ├── canPatch = true → proposals.json → Patch 流程 → XML 补丁
    │
    └── canPatch = false → recommendations.json → Report 流程 → 用户报告
```

**输入**：
- `optimize/proposals.json` — 可验证的语法级优化
- `optimize/recommendations.json` — 不可验证的结构级建议
- `parse/xml_mappings.json` — 原始 XML 文件位置映射

**输出**：
- `result/patches.json` — 已应用的补丁列表
- `result/reports/*.md` — 用户决策报告

**不做什么**：
- ❌ 不展开动态 SQL（那是 Parse 的职责）
- ❌ 不执行 EXPLAIN（那是 Recognition 的职责）
- ❌ 不生成优化建议（那是 Optimize 的职责）

---

## 2. 数据契约

### 2.1 输入

#### 2.1.1 optimize/proposals.json

```json
// optimize/proposals.json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "originalSql": "SELECT * FROM users WHERE name LIKE '%' || #{name}",
    "validated": true,
    "suggestions": [
      {
        "id": "prefix-like-fix",
        "rewrittenSql": "SELECT id, name FROM users WHERE name LIKE #{name} || '%'"
      }
    ]
  }
]
```

#### 2.1.2 parse/xml_mappings.json

```json
// parse/xml_mappings.json
{
  "files": [
    {
      "xmlPath": "/path/to/UserMapper.xml",
      "statements": [
        {
          "sqlKey": "com.example.UserMapper.search",
          "statementId": "search",
          "startLine": 30,
          "endLine": 42,
          "originalContent": "<select id=\"search\">\n  SELECT * FROM users WHERE name LIKE '%' || #{name}\n</select>"
        }
      ]
    }
  ]
}
```

**关键**：Patch 阶段根据 `xml_mappings.json` 定位原始 XML 文件，根据 `proposals.json` 的 `rewrittenSql` 生成补丁。

### 2.2 输出 Schema

```json
// result/patches.json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "patchFiles": ["runs/xxx/result/UserMapper.xml.patch"],
    "diffSummary": {
      "filesChanged": 1,
      "hunks": 2,
      "summary": "Replace LIKE '%x%' with range predicate"
    },
    "applicable": true,
    "status": "ready"
  }
]
```

### 2.3 关键字段说明

| 字段 | 说明 |
|------|------|
| `sqlKey` | 分支唯一标识 |
| `patchFiles` | 补丁文件路径列表 |
| `diffSummary.filesChanged` | 修改的文件数 |
| `diffSummary.hunks` | diff 块数 |
| `diffSummary.summary` | 修改摘要 |
| `applicable` | 是否可应用 |
| `status` | 状态：`ready`, `applied`, `failed` |

---

## 3. 目录结构

```
result/
├── __init__.py
├── api.py                 # 阶段 API（必须）
│                          # - validate_input()
│                          # - run(proposals_file, config) -> PatchResult
├── run.py                # 入口实现
├── patch_generator.py     # 补丁生成（核心）
├── xml_applier.py        # XML 应用
├── diff_generator.py     # diff 生成
├── README.md            # 本文档
└── STAGE.md             # 阶段设计文档（详细）
```

---

## 4. 快速调测

### 4.1 准备测试环境

```bash
# 1. 创建测试输入文件
mkdir -p /tmp/sqlopt-test/runs/test-run/result
cat > /tmp/sqlopt-test/runs/test-run/optimize/proposals.json << 'EOF'
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "originalSql": "SELECT * FROM users WHERE name LIKE '%' || #{name}",
    "validated": true,
    "suggestions": [
      {
        "id": "prefix-like-fix",
        "rewrittenSql": "SELECT id, name FROM users WHERE name LIKE #{name} || '%'"
      }
    ]
  }
]
EOF

# 2. 创建测试配置
cat > /tmp/sqlopt-test/sqlopt.yml << 'EOF'
config_version: v1
project:
  root_path: /tmp/sqlopt-test
EOF

export SQLOPT_RUN_DIR=/tmp/sqlopt-test/runs/test-run
```

### 4.2 编写测试代码

```python
# /tmp/sqlopt-test/test_patch.py
import sys
sys.path.insert(0, '/path/to/python')

from sqlopt.result.api import run, validate_input
from sqlopt.common.config import load_config
import json

# 验证输入
proposals_file = Path('/tmp/sqlopt-test/runs/test-run/optimize/proposals.json')
errors = validate_input(proposals_file)
if errors:
    print(f"Input errors: {errors}")
    sys.exit(1)

# 运行 Patch
config = load_config('/tmp/sqlopt-test/sqlopt.yml')
result = run(proposals_file, config)

# 检查结果
print(f"Success: {result.success}")
print(f"Patches: {result.patches_count}")
print(f"Applicable: {result.applicable_count}")
print(f"Errors: {result.errors}")

# 验证输出
with open(result.output_file) as f:
    patches = json.load(f)
    for p in patches:
        print(f"  {p['sqlKey']}: {p['status']}, {len(p['patchFiles'])} files")
```

### 4.3 运行测试

```bash
cd /tmp/sqlopt-test
python test_patch.py

# 检查输出
cat /tmp/sqlopt-test/runs/test-run/result/patches.json | python -m json.tool
```

### 4.4 预期输出

```json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "patchFiles": ["/tmp/sqlopt-test/runs/test-run/result/UserMapper.xml.patch"],
    "diffSummary": {
      "filesChanged": 1,
      "hunks": 1,
      "summary": "Replace LIKE '%' || #{name} with LIKE #{name} || '%'"
    },
    "applicable": true,
    "status": "ready"
  }
]
```

---

## 5. 修改指南

### 5.1 改补丁生成逻辑

**文件**：`patch_generator.py`

**原因**：需要修改生成补丁的方式

**修改**：编辑 `patch_generator.py`

```python
# patch_generator.py
def generate_patch(
    sql_key: str,
    original_sql: str,
    rewritten_sql: str,
    xml_path: str
) -> Patch:
    # 这里是补丁生成逻辑
    # 如果生成不对，改这里
    ...
```

### 5.2 改 diff 生成

**文件**：`diff_generator.py`

**原因**：需要修改 diff 格式

**修改**：编辑 `diff_generator.py`

```python
# diff_generator.py
def generate_diff(original: str, rewritten: str) -> Diff:
    # 这里是 diff 生成逻辑
    # 如果 diff 不对，改这里
    ...
```

### 5.3 改 XML 应用

**文件**：`xml_applier.py`

**原因**：需要修改 XML 应用方式

**修改**：编辑 `xml_applier.py`

```python
# xml_applier.py
def apply_xml_patch(xml_path: str, patch: Patch) -> bool:
    # 这里是 XML 应用逻辑
    # 如果应用不对，改这里
    ...
```

---

## 6. API 定义

### 6.1 validate_input()

```python
def validate_input(proposals_file: Path) -> list[str]:
    """
    验证输入文件是否有效
    
    Args:
        proposals_file: optimize/proposals.json 路径
    
    Returns:
        错误列表，空表示输入有效
    """
```

### 6.2 run()

```python
@dataclass
class PatchStageResult:
    success: bool
    output_file: Path          # result/patches.json
    patches_count: int
    applicable_count: int
    errors: list[str]

def run(
    optimize_output: Path,
    config: dict,
) -> PatchStageResult:
    """
    运行 Patch 阶段
    
    Args:
        optimize_output: optimize/proposals.json 路径
        config: 配置字典
    
    Returns:
        PatchStageResult: 包含输出文件路径和统计信息
    """
```

---

## 7. 依赖关系

```
Patch 阶段依赖：
├── common/contracts.py       # 契约验证
├── common/run_paths.py      # 路径管理
├── common/config.py         # 配置加载
├── common/errors.py         # 错误定义
│
├── optimize/proposals.json  # 输入（只读）
│
└── result/                  # 自有模块（禁止其他阶段 import）
    ├── patch_generator.py    # 补丁生成
    ├── xml_applier.py        # XML 应用
    └── diff_generator.py    # diff 生成
```

**关键约束**：`patch_generator.py` `xml_applier.py` `diff_generator.py` **只被 Result 使用**，禁止其他阶段 import。

---

## 8. 常见问题

### Q: 补丁生成失败？
**A**: 检查 `patch_generator.py` 中的生成逻辑

### Q: XML 应用失败？
**A**: 检查 `xml_applier.py` 中的应用逻辑

### Q: diff 格式不对？
**A**: 检查 `diff_generator.py` 中的 diff 生成逻辑
