# 使用热门值替换 SQL 占位符设计文档

**日期**: 2026-04-06
**状态**: Draft

---

## 1. 目标

增强 Recognition 阶段，使用 `field_distributions` 中的热门值（top_values）替换 MyBatis 占位符，获取更真实的执行计划作为慢 SQL 基线。

## 2. 背景

当前 `_resolve_mybatis_params_for_explain()` 函数使用静态样本值（`1`, `'test'`, `'2024-01-01'`）替换 `#{}` 占位符，无法反映真实数据分布。

`init` 阶段已从数据库获取 `field_distributions.json`，包含每个字段的热门值，但 Recognition 阶段未使用。

## 3. 设计方案

### 3.1 数据流

```
init 阶段输出:
├── sql_units.json
├── table_schemas.json
└── field_distributions.json

recognition 阶段 (增强):
├── 加载 parse 输出
├── 加载 table_schemas
├── 加载 field_distributions  ← 新增
└── 执行 EXPLAIN（使用热门值替换参数）
```

### 3.2 改动点

| 文件 | 改动 |
|------|------|
| `recognition/stage.py` | 新增加载 `field_distributions.json` |
| `recognition/stage.py` | `_resolve_mybatis_params_for_explain()` 新增 `field_distributions` 参数 |
| `recognition/stage.py` | 实现热门值查询和替换逻辑 |

### 3.3 参数匹配逻辑

```python
def get_value_for_param(param_name, sql_lower, field_distributions, table_schemas):
    # 1. 优先从热门值获取 top-1
    hot_value = lookup_hot_value(param_name, sql_lower, field_distributions)
    if hot_value:
        return format_value(hot_value)

    # 2. fallback 到现有静态样本值逻辑
    return get_static_sample_value(param_name, sql_lower, table_schemas)
```

#### 3.3.1 热门值查询

```python
def lookup_hot_value(param_name: str, sql_lower: str, field_distributions: dict) -> str | None:
    """从 field_distributions 中查找参数的热门值"""
    param_lower = param_name.lower()
    param_snake = camel_to_snake(param_name)

    for table_name, dists in field_distributions.items():
        if table_name not in sql_lower:
            continue
        for dist in dists:
            col_name = dist.column_name.lower()
            if col_name in (param_lower, param_snake):
                # 取 top-1 热门值
                if dist.top_values and len(dist.top_values) > 0:
                    return str(dist.top_values[0].get("value"))
    return None
```

#### 3.3.2 值格式化

```python
def format_value(value: str, col_type: str | None = None) -> str:
    """根据列类型格式化热门值"""
    if value is None:
        return None

    # 数字类型不需要引号
    if col_type and any(t in col_type.upper() for t in ["INT", "BIGINT", "DECIMAL", "FLOAT", "DOUBLE"]):
        return value

    # 已经是数字字符串
    if value.lstrip("-").isdigit():
        return value

    # 其他类型加引号
    return f"'{value}'"
```

### 3.4 配置

- 无需新增配置项
- 默认行为：始终启用热门值替换
- 无热门值时 fallback 到静态样本值

## 4. 向后兼容

- 不改变现有 `table_schemas` 参数的作用
- 无 `field_distributions` 数据时，使用原有静态样本值逻辑
- 不影响现有的 Mock 模式

## 5. 错误处理

| 场景 | 处理 |
|------|------|
| `field_distributions.json` 不存在 | 使用静态样本值，记录 debug 日志 |
| 热门值为 NULL | 使用静态样本值 |
| 热门值格式化失败 | 使用静态样本值，记录警告日志 |

## 6. 测试场景

| 场景 | 预期 |
|------|------|
| 参数有热门值 | 使用 top-1 热门值 |
| 参数无热门值 | 使用静态样本值 |
| 热门值为数字 | 不加引号 |
| 热门值为字符串 | 加引号 |
| 嵌套参数 `#{user.id}` | 取 `user` 部分匹配 |

## 7. 风险

- 热门值可能不是典型查询值，但这是可接受的（作为最常见场景的基线）
- 不需要开关控制，始终启用简化实现