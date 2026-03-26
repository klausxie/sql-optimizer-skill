# 数据契约总览

> 阶段间数据传递的唯一协议

---

## 1. 设计原则

### 1.1 契约优先

当代码行为与文档冲突时，按以下优先级：
1. `contracts/schemas/*.schema.json` (最高)
2. 各阶段 `api.py` 中的类型定义
3. 文档

### 1.2 阶段间不直接调用

阶段间**只通过 JSON 文件传递数据**，不直接 import 其他阶段的代码。

---

## 2. Schema 清单

```
contracts/
└── schemas/
    ├── sqlunit.schema.json         # SQL 单元
    ├── risks.schema.json           # 风险报告
    ├── baseline_result.schema.json # 性能基线
    ├── optimization_proposal.schema.json  # 优化提案
    └── patch_result.schema.json    # 补丁结果
```

---

## 3. 各契约说明

| Schema | 用途 | 主要字段 |
|--------|------|----------|
| `sqlunit.schema.json` | SQL 单元 | sqlKey, sql, branches, parameterMappings |
| `risks.schema.json` | 风险报告 | sqlKey, risks, severity |
| `baseline_result.schema.json` | 性能基线 | sqlKey, executionTimeMs, rowsScanned |
| `optimization_proposal.schema.json` | 优化提案 | sqlKey, originalSql, suggestions |
| `patch_result.schema.json` | 补丁结果 | sqlKey, patchFiles, applicable |

---

## 4. 契约验证

### 4.1 代码中使用

```python
from common.contracts import ContractValidator

validator = ContractValidator()

# 验证 Init 输出
errors = validator.validate_file(
    "init/sql_units.json",
    "sqlunit.schema.json"
)

# 验证 Parse 输出
errors = validator.validate_file(
    "parse/sql_units.json",
    "sqlunit.schema.json"  # 复用同一 Schema
)
```

### 4.2 命令行验证

```bash
# 验证单个文件
python scripts/schema_validate.py contracts/schemas/sqlunit.schema.json runs/test/init/sql_units.json

# 验证所有契约
python scripts/schema_validate_all.py runs/test/
```

---

## 5. 修改契约

### 5.1 修改流程

1. 编辑 `contracts/schemas/*.schema.json`
2. 更新对应阶段的 `api.py` 类型定义
3. 更新阶段文档 `STAGES/*.md`
4. 运行验证确保修改正确

### 5.2 注意事项

- **不破坏兼容性**：尽量添加可选字段，不删除已有字段
- **版本控制**：重大变更记录在 `contracts/CHANGELOG.md`
- **向后兼容**：考虑是否需要版本迁移

---

## 6. 契约与阶段的关系

```
契约                    生产阶段      消费阶段
─────────────────────────────────────────────────────
sqlunit.schema.json     Init, Parse   Parse, Recognition, Optimize
risks.schema.json       Parse         (内部使用)
baseline_result.schema.json  Recognition  Optimize
optimization_proposal.schema.json  Optimize  Patch
patch_result.schema.json   Patch         (最终输出)
```

详见 [data-flow.md](./data-flow.md)
