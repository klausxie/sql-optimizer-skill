# Provider Quality Research Program

## Goal

理解 provider 在 `CHOOSE_BRANCH_BODY` contract 下的失败模式，并判断这是不是 prompt 可解问题。

不是"让 sentinel 变绿"，而是"产出可复用的 insight"。

## Research Questions

1. 模型是否理解 `CHOOSE_BRANCH_BODY` 概念？
2. strict contract 是否降低有效候选率？
3. few-shot 是否提高 `branch_local_valid` 命中率？
4. 不同模型在 choose-local contract 下的失败模式是否不同？

## Scope

- 只研究 `demo.user.advanced.findUsersByKeyword`
- 不改任何工程 substrate
- 不追求 sentinel promotion
- 只允许 prompt / model / few-shot 变量变化

## Success Criteria: 4-Bucket Rubric

每次 provider 输出必须归类到以下 4 个桶之一：

| Bucket | 定义 | 判定规则 |
|--------|------|---------|
| `branch_local_valid` | 符合 contract 的有效候选 | rewrite 只涉及单个 branch 内的 predicate 简化 |
| `low_value` | 无实际优化价值 | INDEX_SEEK / PREDICATE_SIMPLIFICATION / PREDICATE_REDUCTION |
| `unsupported` | 策略不支持 | 用了 set operations / branch merge / whole-statement rewrite |
| `semantic_risk` | 语义风险高 | 改变了参数语义或逻辑等价性 |

**核心指标**:
```
branch_local_valid_rate = branch_local_valid / total_candidates
low_value_rate = low_value / total_candidates
```

## Experiment Matrix

| 变量 | 取值 | 说明 |
|-----|------|------|
| **prompt** | baseline / strict-v1 / strict-v2 | baseline = 当前最松, strict = 当前最严 |
| **few-shot** | none / 1-shot / 2-shot | 0/1/2 个 branch-local cleanup 示例 |
| **model** | current / model-b / model-c | 主模型 + 1-2 个对照 |

**实验设计**:
- baseline prompt + current model = **控制组 A**
- strict prompt + current model = **控制组 B**
- 其余组合 = **实验组**

## Control Groups (必须保留)

```
A: baseline prompt + current model
B: strict prompt (当前最严) + current model
```

只有对比 A vs B，才能证明其他变量变化的真实效果。

## Stop Conditions (写死)

- **max 6 轮 prompt 变体**
- **max 3 个模型**
- **连续 2 轮无提升** (`branch_local_valid_rate` 持平或下降) → 立即停止

## Deliverables (规定产物)

| 产物 | 格式 | 说明 |
|-----|------|------|
| `experiment_matrix.csv` | CSV | 所有实验配置的输入输出汇总 |
| `per_run_classification.jsonl` | JSONL | 每次 run 的 4 桶分类结果 |
| `top_failure_patterns.md` | Markdown | 最常见的失败模式总结 |
| `recommendation.md` | Markdown | 最终建议：prompt-fixable / model-limited / not-worth-continuing |

## Candidate Classification Rules

### branch_local_valid (有效)

- 只修改单个 branch 内的 predicate
- 不引入新 table / join / set operation
- 不改变其他 branch 的内容
- 保留参数占位符

### low_value (无价值)

- `INDEX_SEEK` / `INDEX_SCAN`
- `PREDICATE_SIMPLIFICATION` (整个 WHERE 重写)
- `PREDICATE_REDUCTION` (删除 branch，降级到 default)
- 任何不改变 branch 内容的优化

### unsupported (不支持)

- `UNION` / `UNION ALL` / `INTERSECT` / `EXCEPT`
- 多 branch merge
- whole-statement rewrite (替换整个 WHERE)
- 跨 branch 的条件重排

### semantic_risk (高风险)

- 改变参数语义 (如 `#{keyword}` → `#{keywordPattern}`)
- 移除必要的 null check
- 改变 AND/OR 逻辑

## Program Stages

### Phase 1: Baseline Capture

- [ ] 运行控制组 A (baseline prompt)
- [ ] 运行控制组 B (strict prompt)
- [ ] 建立 baseline 分类数据

### Phase 2: Prompt Experiments

- [ ] 尝试 strict + 1-shot
- [ ] 尝试 strict + 2-shot
- [ ] 尝试其他 prompt 变体 (最多 6 轮)

### Phase 3: Model Comparison

- [ ] 用 baseline prompt 测试 model-b
- [ ] 用 baseline prompt 测试 model-c

### Phase 4: Analysis & Deliverables

- [ ] 汇总 experiment_matrix.csv
- [ ] 汇总 per_run_classification.jsonl
- [ ] 编写 top_failure_patterns.md
- [ ] 编写 recommendation.md

## Expected Outcome

这个 program 会回答：

```
Q: 模型不遵循 contract 是 prompt 问题还是模型问题？
A: (基于实验数据)
   - 如果 few-shot 显著提升 → prompt 可解
   - 如果所有模型表现一致差 → 模型限制
   - 如果无论怎么改都没用 → not worth continuing
```

## Hard Stop

如果遇到以下情况，立即停止并产出当前结论：

- guardrail 开始移动
- 需要改 substrate 才能继续
- 连续 2 轮实验无任何改善

---

## Related Artifacts

- Primary sentinel: `demo.user.advanced.findUsersByKeyword`
- Current baseline cassette: `f2378d949f6dff98af8cb746d090b03a913528d3f0f610e9cf986ff1c8dbcced`
- Previous program review: `2026-04-10-provider-candidate-quality-review.md`