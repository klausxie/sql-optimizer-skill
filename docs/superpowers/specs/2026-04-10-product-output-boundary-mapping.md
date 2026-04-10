# Product Output Boundary Mapping

## Purpose

Map internal convergence and blocker truth into stable product-facing summary/diagnostics categories.

The system already has strong internal precision:

- `convergenceDecision`
- `conflictReason`
- blocker buckets
- `decision_focus`
- `recommended_next_step`

This spec defines how that internal truth should be surfaced in summary/diagnostics output without exposing users to raw engineering taxonomy unless useful.

It does not change the formal `report.json` contract in this stage.

## Current State

Today the project already exposes:

- `AUTO_PATCHABLE` vs `MANUAL_REVIEW`
- `conflictReason`
- batch-level `decision_focus`
- batch-level `recommended_next_step`

Source paths:

- [python/sqlopt/devtools/run_progress_summary.py](/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/run_progress_summary.py)
- [scripts/ci/generalization_summary.py](/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py)
- [python/sqlopt/application/diagnostics_summary.py](/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/application/diagnostics_summary.py)

This is enough for engineering, but still too raw for product-facing output.

## Product Output Layers

### Layer 1: Delivery Status

Keep the existing top-level delivery statuses:

- `AUTO_PATCHABLE`
- `MANUAL_REVIEW`
- `NOT_PATCHABLE`

These remain useful and should not be renamed.

### Layer 2: Product Boundary Category

Add a product-facing category derived from `conflictReason`.

Proposed field name:

- `boundaryCategory`

Allowed values:

- `SUPPORTED`
- `DEFERRED_CAPABILITY`
- `FROZEN_NON_GOAL`
- `SEMANTIC_BOUNDARY`
- `VALIDATE_SECURITY_BOUNDARY`
- `PROVIDER_LIMITED`
- `OTHER`

### Layer 3: Short User Message

Add a short stable explanation string.

Proposed field name:

- `boundarySummary`

Examples:

- "supported"
- "not supported yet"
- "not supported in current scope"
- "blocked by semantic safety"
- "blocked by validation/security"
- "blocked by current provider quality"

### Layer 4: Recommended Action

Reuse the idea already present in summary output, but make it product-facing.

Proposed field name:

- `recommendedAction`

Examples:

- `apply_patch`
- `review_candidate`
- `wait_for_future_capability`
- `do_not_retry_current_scope`
- `consider_provider_investment`

## Mapping Rules

### 1. Supported

When:

- `convergenceDecision = AUTO_PATCHABLE`

Output:

- `boundaryCategory = SUPPORTED`
- `boundarySummary = supported`
- `recommendedAction = apply_patch`

### 2. Deferred Capability

When `conflictReason` maps to an explicitly deferred future capability such as:

- `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`

Output:

- `boundaryCategory = DEFERRED_CAPABILITY`
- `boundarySummary = not supported yet`
- `recommendedAction = wait_for_future_capability`

### 3. Frozen Non-Goal

When `conflictReason` maps to frozen boundaries such as:

- `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
- `NO_SAFE_BASELINE_GROUP_BY`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_*`
- `NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT`
- generic low-value lanes with no future investment attached

Output:

- `boundaryCategory = FROZEN_NON_GOAL`
- `boundarySummary = not supported in current scope`
- `recommendedAction = do_not_retry_current_scope`

### 4. Semantic Boundary

When `conflictReason` starts with `SEMANTIC_`.

Output:

- `boundaryCategory = SEMANTIC_BOUNDARY`
- `boundarySummary = blocked by semantic safety`
- `recommendedAction = review_candidate`

### 5. Validate / Security Boundary

When `conflictReason` starts with `VALIDATE_`.

Output:

- `boundaryCategory = VALIDATE_SECURITY_BOUNDARY`
- `boundarySummary = blocked by validation/security`
- `recommendedAction = review_candidate`

### 6. Provider-Limited

When `conflictReason = NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` and the statement belongs to the explicit frozen choose-local provider lane:

- `demo.user.advanced.findUsersByKeyword`

Output:

- `boundaryCategory = PROVIDER_LIMITED`
- `boundarySummary = blocked by current provider quality`
- `recommendedAction = consider_provider_investment`

Important:

This mapping is intentionally narrow.

`NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` must not globally become `PROVIDER_LIMITED`.

### 7. Fallback

Everything else:

- `boundaryCategory = OTHER`
- `boundarySummary = requires manual review`
- `recommendedAction = review_candidate`

## Recommended Product Surface

### Summary / Diagnostics Example

Instead of only:

```text
MANUAL_REVIEW / NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE
```

show:

```text
Status: MANUAL_REVIEW
Boundary: FROZEN_NON_GOAL
Summary: not supported in current scope
Reason: NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE
Recommended action: do_not_retry_current_scope
```

### Why Keep Raw `conflictReason`

Raw reason should still be present for engineering and debugging.

The new fields are additive, not replacements.

## Guardrails

- Do not collapse multiple different engineering truths into one user message if that would hide important distinctions.
- Do not relabel frozen boundaries as deferred.
- Do not relabel provider-limited lanes as generic low-value noise.
- Do not use product messaging to make blocked outcomes sound temporary when they are intentionally frozen.

## Expected Outcome

After this mapping is implemented in summary/diagnostics layers, users should be able to understand blocked outcomes without reading planning documents, while engineering still retains the exact raw blocker taxonomy behind the scenes.

Any later `report.json` adoption should happen only after this mapping proves stable in those pre-report surfaces.
