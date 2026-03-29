# Patch Harness Session Prompt Templates

Use these prompts when starting a new session for patch-facing work under the repository's harness engineering guideline.

Primary references:

1. `docs/superpowers/specs/2026-03-29-harness-engineering-guidelines-design.md`
2. `docs/superpowers/specs/templates/patch-harness-plan-template.md`
3. `docs/superpowers/specs/templates/patch-harness-review-checklist.md`
4. `docs/superpowers/specs/2026-03-26-patch-family-onboarding-framework-design.md`

## Standard Prompt: Spec Work

Use this when the session should start from design or spec work.

```text
这次 patch 相关工作按 harness engineering guideline 执行。
要求：
1. 先对照 docs/superpowers/specs/2026-03-29-harness-engineering-guidelines-design.md 建立 Harness Plan
2. 采用 L1/L2/L3/L4 分层说明 proof obligations、shared classification logic、artifacts、execution budget、regression ownership
3. patch spec 用 docs/superpowers/specs/templates/patch-harness-plan-template.md
4. review 输出必须填写 docs/superpowers/specs/templates/patch-harness-review-checklist.md
5. 先做 spec / plan，对齐后再实现
```

## Standard Prompt: Implementation Work

Use this when the design already exists and the session should execute against it.

```text
这次 patch 实现按现有 Harness Plan 执行。
要求：
1. 先说明这次改动对应哪些 proof obligations 和 L1/L2/L3/L4 harness
2. 实现过程中不要脱离 docs/superpowers/specs/2026-03-29-harness-engineering-guidelines-design.md 的分层模型
3. 改动后说明哪些 shared classification logic、artifacts、execution budget 受影响
4. 最终 review 输出按 docs/superpowers/specs/templates/patch-harness-review-checklist.md 收口
```

## Standard Prompt: Review Work

Use this when the main task is design review, PR review, or patch readiness review.

```text
按 patch harness review checklist 做 review，不要只说 tests look good。
要求：
1. 对照 docs/superpowers/specs/templates/patch-harness-review-checklist.md 逐项给出结论
2. 先看 boundary contract、harness layer、shared classification logic、artifact diagnostics
3. 明确指出 proof burden 是否放在正确的层级
4. 如果缺 Harness Plan 或 checklist handoff，直接指出
```

## Standard Prompt: Family Onboarding Work

Use this when a new patch family is being added or widened.

```text
这次 patch family onboarding 按 harness engineering guideline 和 family onboarding framework 执行。
要求：
1. 对照 docs/superpowers/specs/2026-03-26-patch-family-onboarding-framework-design.md 的标准流程推进
2. 明确 family scope、acceptance policy、replay policy、verification policy、fixture obligations
3. 补完整 Harness Plan，并说明新增或变更了哪些 L1/L2/L3/L4 harness
4. review summary 或 PR description 必须附上 docs/superpowers/specs/templates/patch-harness-review-checklist.md 的完成版
5. 没有 spec / harness 对齐前，不进入实现
```

## Short Prompt

Use this when you only need a compact reminder.

```text
按 patch harness engineering 流程做：先写或对齐 Harness Plan，再实现，最后用 patch harness review checklist 收口。
```

## Expected Responses

When these prompts are used well, the session should usually do the following:

1. name the governing harness guideline explicitly
2. identify which layer or layers are in scope
3. point to the required template or checklist file
4. distinguish spec-time work from implementation-time work
5. avoid skipping directly from idea to code when the harness surface is still undefined
