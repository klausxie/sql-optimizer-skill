# Patch Stage Overview

## 执行摘要
补丁生成完成，共生成 5 个补丁，其中 0 个已确认待应用。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| 补丁总数 | 5 |
| ✅ 已确认 | 0 |
| ⏳ 待确认 | 3 |
| ✅ 已应用 | 2 |
| 已验证 | 4 |

## 补丁状态分布

```
待确认: 3 ████░░░░░░ 60.0%
已确认: 0 ████████░░ 0.0%
已应用: 2 ██████░░░░ 40.0%
```

## 补丁清单

| ID | SQL Key | 类型 | 状态 | 预估提升 |
| -- | ------- | ---- | ---- | -------- |
| PATCH_0001 | UserMapper.testSingleIf | WILDCARD_POSITION | confirmed | 85% |
| PATCH_0002 | UserMapper.findByEmail | INDEX_HINT | pending | 70% |
| PATCH_0003 | UserMapper.searchUsers | QUERY_REWRITE | confirmed | 55% |

## 影响范围

| 影响类型 | 数量 |
| -------- | ---- |
| 性能提升 | 5 |
| 索引变更 | 0 |
| SQL 重写 | 5 |
| LIMIT 添加 | 0 |

## 应用建议

### 🔥 高优先级 (立即应用)
1. PATCH_0001 - 移除前导通配符，预计提升 85%
2. PATCH_0003 - 重写低效查询，预计提升 55%

### ⚠️ 中优先级 (审核后应用)
1. PATCH_0002 - 添加索引提示，需确认索引存在

## 下一步操作

1. **确认补丁**: 检查 `patches/` 目录下的 XML 文件
2. **备份数据**: 应用前建议备份原 Mapper XML
3. **应用补丁**: 使用 `sqlopt-cli apply --run-id demo_rich_20260323_190846` 应用

## 详情
- 补丁数据: `patch/patches.json`
- 补丁文件: `patch/patches/*.xml`
- 配置文件: `sqlopt.yml`
