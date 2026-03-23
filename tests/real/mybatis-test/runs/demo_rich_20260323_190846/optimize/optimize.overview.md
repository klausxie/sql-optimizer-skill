# Optimize Stage Overview

## 执行摘要
优化完成，共生成 16 个优化建议，其中 5 个可立即执行，预计整体性能提升 330%。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| 优化建议总数 | 16 |
| ✅ 可执行 | 5 |
| ⚠️ 需审核 | 3 |
| ✓ 可接受 | 8 |
| 🔥 高收益 | 11 |
| 📊 中收益 | 5 |

## 优化类型分布

| 优化类型 | 数量 | 收益等级 |
| -------- | ---- | -------- |
| INDEX_HINT | 5 | HIGH |
| LIMIT_CLAUSE | 1 | MEDIUM |
| WILDCARD_POSITION | 3 | HIGH |
| QUERY_REWRITE | 4 | MEDIUM |
| JOIN_OPTIMIZATION | 3 | HIGH |

## 问题类型分布

| 问题类型 | 数量 |
| -------- | ---- |
| SLOW_QUERY | 16 |
| INEFFICIENT_SCAN | 15 |
| PREFIX_WILDCARD | 3 |
| MISSING_LIMIT | 3 |
| NO_INDEX | 1 |

## 高收益优化 TOP 5

| SQL Key | 问题 | 优化类型 | 预估提升 |
| ------- | ---- | -------- | -------- |
| com.test.mapper.UserMapper.findById | SLOW_QUERY | JOIN_OPTIMIZATION | HIGH |
| com.test.mapper.UserMapper.searchUsers | SLOW_QUERY | INDEX_HINT | HIGH |
| com.test.mapper.UserMapper.findByEmail | SLOW_QUERY | INDEX_HINT | HIGH |

## 验证状态

| 状态 | 数量 | 说明 |
| ---- | ---- | ---- |
| 已验证 | 5 | 可直接应用 |
| 待验证 | 3 | 需人工确认 |
| 无需优化 | 8 | 当前性能可接受 |

## 下一步建议

1. **Patch 阶段**: 优先应用高收益优化
2. **人工审核**: 对需审核建议进行确认
3. **回归测试**: 应用前建议备份

## 详情
- 优化建议: `optimize/proposals.json`
- 优化摘要: `optimize/optimization_summary.json`
- 验证通过率: 31.2%
