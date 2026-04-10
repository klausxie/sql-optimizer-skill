# Release Gate Definition

## Purpose

Define the minimum merge/release gates that protect the current delivered optimizer boundary.

This gate is not a performance benchmark and not a capability expansion checklist.

It exists to prevent two bad regressions:

- breaking known supported lanes
- accidentally widening blocked or frozen boundaries

## Scope

These gates apply to future work that changes any of:

- candidate generation
- rewrite facts
- convergence / validation
- patch selection / patch generation
- replay / materialization
- report / summary output that changes blocker interpretation

## Gate Categories

### Gate 1: Ready Sentinel Protection

Known ready sentinels must stay ready.

Current representative ready set:

- `demo.user.countUser`
- `demo.test.complex.fromClauseSubquery`
- `demo.test.complex.wrapperCount`

Required condition:

- `ready_regressions = 0`

Failure means:

- the change broke current supported capability

### Gate 2: Blocked Boundary Protection

Known blocked boundary statements must not silently become patchable.

Required condition:

- `blocked_boundary_regressions = 0`

This includes:

- frozen non-goals
- deferred capability lanes that are still intentionally blocked
- semantic boundaries
- validate/security boundaries
- provider-limited lanes

Failure means:

- the change widened a boundary without an explicit product decision

### Gate 3: Replay Stability

Protected replay scopes must still run and preserve the current truth class.

Minimum protected scopes:

- `generalization-batch1`
- `generalization-batch9`
- `generalization-batch11`
- `generalization-batch12`
- `generalization-batch13`

Required condition:

- replay completes successfully for the protected scopes under current cassette expectations
- no unexpected patch files appear for currently blocked lanes

Failure means:

- replay/materialization/patch selection behavior drifted

### Gate 4: Boundary Category Stability

Product-facing boundary categories must remain truthful.

Required condition:

- no frozen lane is relabeled as deferred without a product decision
- no provider-limited lane is collapsed back into generic low-value messaging if the project has already frozen it explicitly
- no semantic or validate/security boundary is hidden under a generic catch-all

Failure means:

- product output became less honest even if raw engineering artifacts still exist

### Gate 5: No Silent Fallback Widening

Changes must not reintroduce broader fallback paths that bypass local or narrow safety contracts.

Examples:

- statement-level fallback for choose-local or collection-local lanes
- fragment-level fallback that bypasses local replay contracts
- generic recovery logic that leaks into frozen boundary families

Required condition:

- no new fallback path widens a currently blocked surface without an explicit spec and sentinel coverage

Failure means:

- a boundary was widened implicitly through implementation detail

## Minimum Verification Set

Every merge that touches protected areas should run the smallest set that can still catch boundary regressions.

### Always Required

- targeted unit tests for the touched subsystem
- targeted CI/harness tests if report/summary/boundary mapping changes

### Required When Convergence / Candidate / Patch Logic Changes

- relevant replay refresh for affected sentinel batches
- summary validation on those batches

### Required Before Declaring Stage Completion

- fresh full `python3 -m pytest -q`

## Protected Truths

The release gate protects these truths as first-class invariants:

### Supported Truths

- the ready set remains ready

### Boundary Truths

- `NO_SAFE_BASELINE_*` frozen/deferred lanes remain in the same truth class unless explicitly reopened
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_*` remain frozen non-goals
- `NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT` remains a low-value/no-op boundary
- semantic boundaries remain semantic
- validate/security boundaries remain validate/security
- choose-local provider-limited lane remains provider-limited unless an explicit new investment succeeds

## Failure Handling

If a release gate fails, the change must do one of the following:

1. restore the previous truth
2. add explicit spec and sentinel evidence showing that the boundary change is intentional
3. stop and request a product decision if the boundary is being reopened

The correct response is not:

- weakening the gate
- silently updating tests to fit accidental widening
- hiding the regression behind a broader category

## Expected Outcome

After this gate is adopted, future work should no longer rely on memory of past programs.

The merge criteria will explicitly protect the delivered scope and blocked-boundary honesty.
