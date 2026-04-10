# Provider Candidate Quality Program Review

## Verdict

This program improved the provider-side contract and the truthfulness of candidate diagnostics.

It did not move the primary sentinel out of the low-value lane.

Final status:

- `BASELINE_AUDIT = yes`
- `PROMPT_CONTRACT_TIGHTENED = yes`
- `CHOOSE_LOCAL_CONTRACT_DIAGNOSTICS = yes`
- `TARGETED_PROVIDER_RESEED = yes`
- `PRIMARY_SENTINEL_PROMOTED = no`
- `GUARDRAIL_WIDENING = no`
- `PROGRAM_RESULT = stop`

## What Changed

### 1. The choose-local optimize contract is stricter

Source:

- [optimizer_sql.py](/Users/klaus/.config/superpowers/worktrees/sql-optimizer-skill/codex-provider-candidate-quality-program/python/sqlopt/platforms/sql/optimizer_sql.py)

The `CHOOSE_BRANCH_BODY` contract now explicitly forbids:

- set operations
- branch merge
- whole-statement rewrite
- index-advisory-only output
- flattened predicate rewrites
- default-branch reduction

It also explicitly requires:

- return no candidate when the contract cannot be satisfied

### 2. The low-value lane is now more truthful

Source:

- [candidate_generation_support.py](/Users/klaus/.config/superpowers/worktrees/sql-optimizer-skill/codex-provider-candidate-quality-program/python/sqlopt/platforms/sql/candidate_generation_support.py)

For choose-local statements that carry branch identity, the system now distinguishes:

- `CHOOSE_LOCAL_CONTRACT_SET_OPERATION`
- `CHOOSE_LOCAL_CONTRACT_FLATTENED_PREDICATE_REWRITE`
- `CHOOSE_LOCAL_CONTRACT_DEFAULT_BRANCH_REDUCTION`

This does not widen patchability.

It only makes the provider failure mode more precise.

## Verification

Focused verification stayed green:

```bash
python3 -m pytest -q \
  tests/unit/sql/test_optimize_proposal.py \
  tests/unit/sql/test_llm_cassette.py \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/ci/test_generalization_summary_script.py \
  -k 'dynamic_surface_contract or choose_local_rewrite_constraints or find_users_by_keyword_candidate_pool_classification or keeps_choose_guarded_safe_baseline_gap_without_branch_identity or choose_guarded_low_value_only_after_identity_reseed or batch9_only_exposes_safe_baseline_focus_and_sentinels or batch13_returns_to_safe_baseline_focus'
```

Result:

- `8 passed`

## Provider Trial Evidence

### Record run

- `generalization-batch9` record:
  [run_833167277cef](/Users/klaus/.config/superpowers/worktrees/sql-optimizer-skill/codex-provider-candidate-quality-program/tests/fixtures/projects/sample_project/runs/run_833167277cef)

### Replay runs

- `generalization-batch9` replay:
  [run_3d7b94c1f790](/Users/klaus/.config/superpowers/worktrees/sql-optimizer-skill/codex-provider-candidate-quality-program/tests/fixtures/projects/sample_project/runs/run_3d7b94c1f790)
- `generalization-batch13` replay:
  [run_3e4eaf58fc8d](/Users/klaus/.config/superpowers/worktrees/sql-optimizer-skill/codex-provider-candidate-quality-program/tests/fixtures/projects/sample_project/runs/run_3e4eaf58fc8d)

### Replay truth

Primary sentinel:

- `demo.user.advanced.findUsersByKeyword`
  - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

Guardrails:

- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`

Batch summaries still show:

- `generalization-batch9`
  - one `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
  - four safe-baseline blockers
- `generalization-batch13`
  - one `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
  - no new auto-patchable statements

## Interpretation

The remaining bottleneck is still provider output quality.

What is now ruled out again:

- missing scan identity
- missing replay fingerprint separation
- missing patch substrate
- vague prompt contract

What remains true:

- even under a stricter choose-local contract, the provider does not emit a promotable branch-local cleanup candidate for the primary sentinel

## Recommendation

Stop this line here.

Do not keep iterating prompt wording inside the same engineering program.

If product wants to continue, the next investment should be explicitly framed as:

- model/provider-quality research
- provider-specific prompt experimentation
- or ranking / post-selection research

It should not be framed as more choose-local engineering work.
