# Fragment/Include Preservation Review

## Verdict

`fragment/include preservation` remains **frozen**.

This stage did not uncover a narrow, reusable, template-preserving safe path for multi-fragment include statements. The lane is now better classified, but it is still review-only and should not be promoted.

## What Changed

### 1. Multi-fragment include is now a first-class review-only shape

The system no longer collapses repeated include chains into generic `STATIC_INCLUDE_ONLY`.

Current review-only profile:

- `shapeFamily = MULTI_FRAGMENT_INCLUDE`
- `capabilityTier = REVIEW_REQUIRED`
- `blockerFamily = MULTI_FRAGMENT_INCLUDE_REVIEW_ONLY`

### 2. Convergence can no longer auto-promote this lane

The earlier gap was real: because `MULTI_FRAGMENT_INCLUDE` was inside the supported static shape registry, a future selected candidate plus patch-family hint could have bypassed the intended review-only posture.

That promotion hole is now closed.

Current convergence behavior:

- `MULTI_FRAGMENT_INCLUDE` remains a supported reporting lane
- but it is explicitly blocked at convergence with
  - `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- even when a selected candidate and patch-family hint are present

### 3. There is still no latent recovery path

Fresh proposal diagnostics across the primary sentinel and guardrails all show the same truth:

- `degradationKind = EMPTY_CANDIDATES`
- `recoveryReason = NO_SAFE_BASELINE_SHAPE_MATCH`
- `recoveredCandidateCount = 0`
- `acceptedCandidateCount = 0`
- `finalCandidateCount = 0`

This means the current system does not contain a hidden fragment/include-preserving recovery path waiting to be wired up.

## Fresh Replay Evidence

### Primary sentinel

- [run_7661c779896e](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_7661c779896e)
  - `demo.test.complex.multiFragmentLevel1`
  - `MANUAL_REVIEW / NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`

### Guardrails

- [run_4536c5f83232](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_4536c5f83232)
  - `demo.test.complex.fragmentInJoin`
  - `MANUAL_REVIEW / NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- [run_3df15250d9a6](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_3df15250d9a6)
  - `demo.test.complex.includeWithWhere`
  - `MANUAL_REVIEW / NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- [run_7661c779896e](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_7661c779896e)
  - `demo.test.complex.includeNested`
  - `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
  - `demo.order.harness.listOrdersWithUsersPaged`
  - `MANUAL_REVIEW / SEMANTIC_PREDICATE_CHANGED`

## Why This Lane Stays Frozen

Promotion would require all three of these to exist at once:

1. a stable, reusable shape-specific recovery path
2. a template-preserving patch surface that keeps include refs intact
3. a semantic guard strong enough to distinguish fragment-only preservation from join/filter/order drift

The current system has none of the three.

What it has today:

- review-only shape classification
- honest blocker reporting
- regression guards preventing accidental widening

That is enough to freeze the lane intentionally, but not enough to promote it.

## Exit Decision

The fragment/include stage is complete with:

- `PROMOTE = no`
- `FREEZE = yes`
- `new patch family = no`
- `patch surface work = no`

The next stage should remain capability-driven and move on to a different product gap, rather than opening `batch14` or continuing fragment/include experiments.
