# Parse 第二阶段设计与下一步建议

> 适用范围：MyBatis XML 分支展开与慢 SQL 候选提取  
> 所属阶段：`Parse`  
> 文档定位：V2 设计稿 + 当前实现状态 + 后续推进建议

---

## 1. 背景

Parse 阶段的目标不应该是“尽量枚举所有动态 SQL 分支”，而应该是：

1. 正确还原 MyBatis XML 的可执行分支。
2. 在分支预算内，尽量精准提取更可能成为慢 SQL 的分支。
3. 为 Recognition / Optimize 阶段提供可解释、可排序、可追踪的候选结果。

在初始实现里，存在几个关键问题：

| 问题 | 影响 |
| --- | --- |
| `include` / 跨文件片段没有接入 Parse 展开链路 | 真实 mapper 容易直接失败 |
| `ladder` 先全量枚举再采样 | 条件数稍大时仍然指数爆炸 |
| 风险排序基于 OGNL `test` 字符串 | 无法准确命中真正高风险 SQL 分支 |
| `active_conditions` / `risk_flags` 丢失 | 后续阶段缺少解释性和优先级依据 |
| `foreach` 通过字符串替换造边界分支 | 容易生成 `IN ()` 或嵌套失真 |

因此，Parse V2 的核心转向是：

> 从“条件组合展开器”升级为“慢 SQL 候选提取器”。

---

## 2. 第二阶段目标

### 2.1 正确性

- 正确解析本地和跨文件 `include`
- 正确处理 `choose / when / otherwise` 的互斥语义
- 正确处理 `bind` 的风险传播，但不把 `bind` 自身当作独立慢 SQL 分支
- 正确处理 `foreach` 的代表性基数场景
- 忽略 `selectKey` 等不属于主 SQL 执行体的标签

### 2.2 精准度

- 优先提取真正高风险的 SQL 分支，而不是仅仅“参数非空”的分支
- 风险评分基于“激活后的 SQL 片段 / 完整分支 SQL”
- 输出带解释的优先级信息，供后续阶段消费

### 2.3 性能

- 不再走“先全量枚举，再采样”的路径
- 在 `max_branches` 预算内稳定工作
- 对 `10+` 个独立 `<if>` 的场景保持可接受的耗时

---

## 3. 当前 V2 已落地能力

下面这些能力已经在当前代码中落地：

### 3.1 Parse 已接通 Init 上下文

ParseStage 现在不仅读取 `sql_units.json`，也会读取：

- `sql_fragments.json`
- `table_schemas.json`
- `xml_mappings.json`

并在 Parse 入口完成：

- `FragmentRegistry` 重建
- `table_metadata` 构建
- 默认 `namespace` 推断

### 3.2 `include` / 跨文件片段可展开

- 本地 `include` 已可稳定展开
- 跨 mapper 的 `include` 已可通过 registry 查找
- Parse 展开不再只适用于 demo 级 XML

### 3.3 分支元数据会透传

Parse 输出已保留：

- `active_conditions`
- `risk_flags`
- `risk_score`
- `score_reasons`

这让后续阶段可以真正基于分支优先级做处理。

### 3.4 `selectKey` 已从主 SQL 渲染中剔除

避免将 `selectKey` 误拼进主 SQL，导致产生错误的混合语句。

### 3.5 `ladder` 已切到预算优先的规划路径

当前不再执行：

```text
枚举所有合法条件组合
  -> 再从中做采样
```

而是改成：

```text
提取分支维度
  -> 按 SQL 风险评分
  -> 在预算内规划代表性候选组合
```

### 3.6 风险评分已切换到 SQL 视角

评分不再基于 `name != null`、`status != null` 这类 OGNL 条件，而是基于：

- `LIKE`
- `IN`
- `JOIN`
- `GROUP BY`
- `ORDER BY`
- 函数包裹列
- 表规模 / 索引等表元数据

### 3.7 `foreach` 已升级为代表性基数桶

当前已覆盖：

- base: small list
- `singleton`
- `large`

同时避免了 `IN ()` 这样的无效 SQL。

### 3.8 分支校验与去重已加入

- 无效 SQL 会在 Parse 阶段过滤
- 相同 SQL 会去重
- 去重时优先保留 `risk_score` 更高、信息更完整的分支

---

## 4. V2 总体架构

```text
InitOutput
  |- sql_units
  |- sql_fragments
  |- xml_mappings
  |- table_schemas
      |
      v
ParseStage
  |- FragmentRegistry Builder
  |- TableMetadata Loader
  |- BranchExpander
      |
      v
BranchGenerator (Facade)
  |- DimensionExtractor
  |- LadderBranchPlanner
  |- BranchRenderer
  |- SQLDeltaRiskScorer
  |- BranchValidator
      |
      v
ParseOutput
  |- SQLBranch(path_id, expanded_sql, active_conditions, risk_flags, risk_score, score_reasons, ...)
```

---

## 5. 核心模块设计

### 5.1 ParseStage

职责：

- 读取 Init 阶段产物
- 重建 `FragmentRegistry`
- 加载并归一化表元数据
- 为每条 `sql_unit` 推断默认 `namespace`
- 调用 `BranchExpander`
- 组装 `ParseOutput`

设计原则：

- Parse 入口必须知道 fragment / schema / namespace
- 不再允许只拿一段 `sql_text` 就尝试做真实 MyBatis 展开

### 5.2 BranchExpander

职责：

- 作为 Parse 与 Branching 核心能力之间的适配层
- 接收完整上下文：
  - `fragments`
  - `table_metadata`
  - `default_namespace`
- 调用 `XMLLanguageDriver + BranchGenerator`
- 输出带解释信息的 `ExpandedBranch`

### 5.3 DimensionExtractor

职责：

- 从 `SqlNode` 树中提取“分支维度”
- 每个维度不是简单的 test 字符串，而是一个可规划、可评分、可约束的对象

当前维度模型：

```python
BranchDimension(
    condition,
    required_conditions,
    sql_fragment,
    depth,
    mutex_group,
)
```

设计价值：

- 可表达“子条件依赖父条件”
- 可表达 `choose` 的互斥组
- 可基于 SQL 片段而不是 OGNL 文本做风险评分

### 5.4 LadderBranchPlanner

职责：

- 在预算内生成“值得展开”的条件组合

当前策略：

1. baseline
2. 高风险单因子
3. Top pair
4. Top triple
5. 少量更高阶补充组合

约束：

- 同一 `mutex_group` 不允许同时取多个维度
- 自动补齐 `required_conditions`
- 不依赖全量枚举

设计目标：

- 在 `max_branches` 有限时，优先覆盖更可能触发慢 SQL 的组合

### 5.5 BranchRenderer

当前仍由 `BranchGenerator` 内部承担主要渲染逻辑，但长期建议拆出为独立模块。

职责：

- 根据 `active_conditions` 过滤 `SqlNode`
- 重新渲染整棵树
- 对 `foreach` 的代表性基数桶做再次渲染

设计原则：

- 一律“重新渲染整棵树”
- 不再使用字符串替换来修补动态 SQL 结构

### 5.6 SQLDeltaRiskScorer

职责：

- 给维度和最终分支打分
- 同时产出 `score_reasons`

当前评分来源：

- SQL 文本特征：
  - `JOIN`
  - `SELECT *`
  - `GROUP BY`
  - `ORDER BY`
  - `DISTINCT`
  - `UNION`
  - 子查询
  - `IN / NOT IN`
  - `LIKE` 前缀通配
  - 函数包裹列
- 表元数据：
  - `large / medium` table
  - 索引覆盖情况
- 分支元数据：
  - `active_conditions`
  - `risk_flags`

输出示例：

```json
{
  "risk_score": 8.0,
  "score_reasons": [
    "select_star",
    "in_clause",
    "table:users:large",
    "active:foreach_0_large"
  ]
}
```

### 5.7 BranchValidator

职责：

- 过滤无效 SQL
- 去重
- 保留更高价值的分支

当前规则：

- 过滤空 SQL
- 过滤 `IN ()`
- 对相同 SQL，仅保留：
  - `risk_score` 更高的分支
  - 或 `active_conditions` 更丰富的分支

---

## 6. ParseOutput V2 契约

当前 Parse 输出至少应稳定保留以下字段：

```python
SQLBranch(
    path_id,
    condition,
    expanded_sql,
    is_valid,
    risk_flags,
    active_conditions,
    risk_score,
    score_reasons,
)
```

建议后续继续补充但不必立即落地的字段：

- `sql_signature`
- `lineage`
- `dimension_state`
- `source_mapper`
- `source_fragment_ids`

这些字段会显著提升：

- 结果解释能力
- 分支去重稳定性
- 从结果回溯到 XML 源头的能力

---

## 7. 当前方案的价值

### 7.1 对真实 MyBatis 更友好

- 不再只适配简单 `<if>` 场景
- 能覆盖 `include / choose / bind / foreach / selectKey` 等关键边界

### 7.2 对慢 SQL 提取更精准

- 评分对象从 OGNL 条件切换到了 SQL 片段 / 分支 SQL
- 更接近“这条 SQL 是否可能慢”的真实目标

### 7.3 对大条件数场景更稳定

- 避免了全量组合爆炸
- `ladder` 变成预算前置生效的规划器

### 7.4 对后续阶段更可解释

Parse 输出现在不仅告诉下游“有哪些分支”，还告诉下游：

- 为什么这个分支被优先选中
- 风险来自哪些 SQL 特征

---

## 8. 仍未完全完成的部分

### 8.1 Recognition 尚未真正消费 `risk_score`

现状：

- Recognition 仍然更像“遍历 Parse 分支”

问题：

- Parse 已经具备优先级能力，但还没有形成全链路收益

### 8.2 `choose default` 还不是完整状态建模

现状：

- `otherwise` 目前可以影响评分
- 但还不是 planner 中的显式选择项

建议：

- 引入显式 `ChooseOptionDimension`
- 让 `when / otherwise` 都成为完整候选状态

### 8.3 `foreach` 基数桶还可以更细

现状：

- 已有 `singleton / large`

建议：

- 细化为：
  - `singleton`
  - `small_list`
  - `medium_list`
  - `large_list`

### 8.4 BranchRenderer 还未完全独立

现状：

- 主要渲染逻辑仍在 `BranchGenerator`

建议：

- 拆出独立 `renderer.py`
- 明确 `planner / scorer / renderer / validator` 的边界

### 8.5 lineage / signature 还未落地

现状：

- 目前只能看到 `active_conditions`

建议：

- 输出分支来源：
  - 哪个 `if`
  - 哪个 `choose`
  - 哪个 `include`
  - 哪个 `foreach`

这样会更利于：

- debug
- 结果解释
- Patch 归因

---

## 9. 下一步建议

### 9.1 第一优先级：让 Recognition 消费 Parse 的优先级

建议改造：

1. Recognition 按 `risk_score` 降序处理分支
2. 增加 Recognition 侧预算配置，例如：

```yaml
recognition:
  max_branches_per_sql: 10
  min_risk_score: 3.0
  high_priority_first: true
```

3. 对低风险分支允许跳过、延后，或只做轻量检查

收益：

- 直接降低 EXPLAIN / 分析开销
- 让 Parse 的“智能提取”真正传导到后续阶段

### 9.2 第二优先级：补齐 `choose` 的显式状态建模

建议：

- 新增 `ChooseOptionDimension`
- 让：
  - `when_a`
  - `when_b`
  - `otherwise`
  都成为 planner 中的一等候选项

收益：

- 互斥分支建模更完整
- `otherwise` 不再只是被动存在

### 9.3 第三优先级：拆出独立 BranchRenderer

建议：

- 从 `BranchGenerator` 中抽出：
  - 条件过滤
  - 树重渲染
  - `foreach` bucket 渲染

收益：

- 模块边界清晰
- 便于后续扩展数据库方言差异

### 9.4 第四优先级：补齐 lineage / signature

建议新增：

- `sql_signature`
- `lineage`
- `source_fragment_ids`

收益：

- 去重更稳
- 解释更强
- 更容易从结果回溯 XML 来源

### 9.5 第五优先级：引入执行计划反馈闭环

建议：

- Recognition/Optimize 对 Top-N 高风险分支优先做 `EXPLAIN`
- 将执行计划结果回流到后续评分策略

方向：

- 先静态规则筛选
- 再动态计划验证
- 后续逐步形成“静态提取 + 动态校正”的闭环

---

## 10. 推荐实施顺序

### Phase 1：已完成

- 接通 Init -> Parse fragment/schema 上下文
- 透传 `risk_flags / active_conditions`
- 修复 `include / selectKey / foreach` 边界
- 去掉 `ladder` 的全量枚举
- 引入 SQL 片段风险评分
- 引入分支去重与校验
- 输出 `risk_score / score_reasons`

### Phase 2：建议立即推进

- Recognition 消费 `risk_score`
- 引入分支预算配置
- 优先处理高风险分支

### Phase 3：结构性优化

- 拆出独立 BranchRenderer
- 补齐 `choose default` 显式状态
- 输出 `lineage / signature`

### Phase 4：进一步智能化

- 增加数据库方言感知评分
- 引入执行计划反馈回流
- 做自适应补采样

---

## 11. 验收指标建议

建议以以下指标判断第二阶段是否达标：

### 11.1 正确性指标

- `include` / 跨文件 `include` 可稳定展开
- Parse 不再生成 `IN ()`
- `selectKey` 不进入主 SQL
- `active_conditions / risk_flags / risk_score / score_reasons` 全链路保留

### 11.2 性能指标

- `10+` 个独立 `<if>` 场景不再出现指数级退化
- `max_branches` 生效时，Parse 耗时可控

### 11.3 精准度指标

Top-N 分支能优先命中这些高风险模式：

- 前缀通配 `LIKE`
- 深分页
- 大 `IN`
- 子查询
- 动态排序
- 函数包裹列
- 大表非索引过滤

---

## 12. 总结

Parse 第二阶段的关键变化不是“再多加几条规则”，而是角色切换：

```text
从 动态 SQL 分支展开器
升级为 慢 SQL 候选分支提取器
```

当前实现已经具备三项关键能力：

1. 能更真实地理解 MyBatis XML。
2. 能在预算内提取更有价值的分支。
3. 能为每个分支输出风险分数与解释理由。

下一步最值得做的不是继续堆规则，而是让 Recognition / Optimize 真正消费这些优先级信息。只有这一步打通，Parse 第二阶段的价值才会完整释放。

---

*文档版本：v2.0*  
*更新日期：2026-03-25*  
*作者：Codex*
