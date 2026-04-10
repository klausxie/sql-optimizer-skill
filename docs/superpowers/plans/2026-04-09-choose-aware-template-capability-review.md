# Choose-Aware Template Capability Review

## Verdict

No narrow branch-local safe path exists in current code for `CHOOSE_BRANCH_BODY`.

The stage is complete and the choose-aware lane is re-deferred.

## Why It Was Ruled Out

- `rewrite_facts` can now recognize the primary sentinel as a choose-aware review-only capability lane:
  - `shapeFamily = IF_GUARDED_FILTER_STATEMENT`
  - `patchSurface = CHOOSE_BRANCH_BODY`
  - `blockerFamily = DYNAMIC_FILTER_CHOOSE_GUARDED_REVIEW_ONLY`
- `safe_baseline_recovery_family(...)` still returns no family for that shape.
- all existing dynamic intent rules require:
  - `capabilityTier = SAFE_BASELINE`
  - `patchSurface = STATEMENT_BODY`
  - a known safe-baseline family
- there is no consumer for `CHOOSE_BRANCH_BODY`, so there is no template-preserving path to patch generation.

## Code Evidence

- [python/sqlopt/platforms/sql/rewrite_facts.py](/tmp/sqlopt-post-batch7/python/sqlopt/platforms/sql/rewrite_facts.py)
- [python/sqlopt/platforms/sql/candidate_generation_engine.py](/tmp/sqlopt-post-batch7/python/sqlopt/platforms/sql/candidate_generation_engine.py)
- [python/sqlopt/platforms/sql/candidate_generation_support.py](/tmp/sqlopt-post-batch7/python/sqlopt/platforms/sql/candidate_generation_support.py)
- [python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_select_list_cleanup.py](/tmp/sqlopt-post-batch7/python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_select_list_cleanup.py)
- [python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_from_alias_cleanup.py](/tmp/sqlopt-post-batch7/python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_from_alias_cleanup.py)
- [python/sqlopt/stages/validate_convergence.py](/tmp/sqlopt-post-batch7/python/sqlopt/stages/validate_convergence.py)

## Fresh Replay Review

Fresh replay runs:

- `generalization-batch5` -> [run_7eb066571c1d](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_7eb066571c1d)
- `generalization-batch13` -> [run_f862952bca4c](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_f862952bca4c)

Observed truth:

- `demo.user.advanced.findUsersByKeyword` -> `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.test.complex.chooseBasic` -> `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.chooseMultipleWhen` -> `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.chooseWithLimit` -> `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.selectWithFragmentChoose` -> `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.order.harness.listOrdersWithUsersPaged` -> `MANUAL_REVIEW / SEMANTIC_PREDICATE_CHANGED`

No statement became `AUTO_PATCHABLE`. No non-goal choose sentinel was widened.

## Recommendation

Do not continue exploratory choose batches.

Only reopen this lane if there is a product decision to build a dedicated choose-aware safe-baseline family that:

- edits branch-local template bodies directly
- preserves `<choose>` structure end-to-end
- keeps semantic guardrails at least as strict as the current replay truth
