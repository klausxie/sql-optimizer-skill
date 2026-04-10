# Productization / Boundary Hardening Program

## Goal

Turn the current optimizer state from an internally-clear engineering system into a productized, user-visible delivery surface.

This program does **not** try to add a new capability.

It converts the already-completed boundary work into:

- a supported capability matrix
- user-visible blocked-boundary explanations
- release gates that protect the delivered scope

This stage is intentionally pre-`report.json` contract.

## Starting Point

The project has already finished the exploratory and cleanup phases.

Key completed outcomes:

- [2026-04-09-project-boundary-delivery-summary.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-project-boundary-delivery-summary.md)
- [2026-04-09-generalization-phase-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-phase-review.md)
- [2026-04-09-safe-baseline-program-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-safe-baseline-program-review.md)
- [2026-04-09-semantic-validation-boundary-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-semantic-validation-boundary-review.md)
- [2026-04-09-unsupported-strategy-boundary-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-unsupported-strategy-boundary-review.md)
- [2026-04-09-low-value-boundary-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-low-value-boundary-review.md)
- [2026-04-10-provider-strategy-decision.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-strategy-decision.md)

Current truth:

- supported ready set exists and is stable
- major blocked lanes are explicitly classified
- no more exploratory batch work is needed
- choose-local provider work is frozen unless a future model-side investment is approved

## Why This Program Exists

Right now, the project has strong internal truth but weaker product-facing expression.

Engineering can answer:

- why a statement is blocked
- whether a boundary is frozen, deferred, semantic, or validate/security
- whether a lane is provider-limited

But the product surface still needs to make those truths obvious without requiring someone to read planning documents.

## Non-Goals

- Do not open a new capability track.
- Do not reopen `choose`, `collection`, or fragment/include work.
- Do not change patchability rules to create more green results.
- Do not rerun exploratory generalization batches.
- Do not weaken blocked boundaries to simplify output.

## Program Outputs

This stage should produce three concrete delivery artifacts:

1. **Supported Capability Matrix**
   - what is supported now
   - what is deferred
   - what is frozen
   - what is blocked by semantic/validate boundaries

2. **User-Visible Blocked Reason Surface**
   - stable reason classes in summary/diagnostics output first
   - concise recommended next action per reason class

3. **Release Gate Definition**
   - required replay and boundary checks for future changes
   - explicit no-regression conditions for ready and blocked sets

## Task 1: Publish The Supported Capability Matrix

Create a compact matrix that product and engineering can both use.

Suggested categories:

- `SUPPORTED`
- `DEFERRED_CAPABILITY`
- `FROZEN_NON_GOAL`
- `SEMANTIC_BOUNDARY`
- `VALIDATE_SECURITY_BOUNDARY`
- `PROVIDER_LIMITED`

The matrix should name representative sentinels, not every historical statement.

Primary source inputs:

- ready set from [2026-04-09-project-boundary-delivery-summary.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-project-boundary-delivery-summary.md)
- frozen/deferred decisions from the boundary reviews
- provider freeze from [2026-04-10-provider-strategy-decision.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-strategy-decision.md)

Deliverable:

- `docs/superpowers/specs/2026-04-10-supported-capability-matrix.md`

## Task 2: Promote Boundary Truth Into Product Output

Audit the current summary/diagnostics surface and identify where the product still exposes:

- generic `MANUAL_REVIEW`
- generic blocked language
- missing or unclear next-step guidance

Then design a small mapping from internal reason classes to product-facing output classes.

Important constraint:

- land this in summary/diagnostics layers first
- do not change the formal `report.json` contract in this stage

This task should not invent new blocker types.

It should reuse the truth already established by the project:

- safe-baseline boundary
- semantic boundary
- validate/security boundary
- unsupported current non-goal
- low-value/no-op
- provider-limited

Deliverables:

- a summary/diagnostics mapping spec
- a short recommended wording table

Suggested file:

- `docs/superpowers/specs/2026-04-10-product-output-boundary-mapping.md`

## Task 3: Define Release Gates

Freeze the rules that future capability work must pass before merge.

Minimum release gates should include:

- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- replay/cassette stability for the protected sentinel scopes
- no silent widening of deferred or frozen lanes

This should become the standard for future capability programs.

Deliverable:

- `docs/superpowers/specs/2026-04-10-release-gate-definition.md`

## Task 4: Convert Into A Small Implementation Plan

After Tasks 1-3 are written, convert them into a narrow implementation plan focused on:

- docs surface updates
- summary/diagnostics output shaping
- CI/release gate assertions

This keeps the next execution stage small and concrete.

Deliverable:

- `docs/superpowers/plans/2026-04-10-productization-boundary-hardening-implementation-plan.md`

## Success Criteria

This program is successful when:

- the current supported scope is readable without replay archaeology
- blocked outcomes map cleanly to stable product-facing categories
- future contributors have explicit release gates for boundary safety
- the project can stop saying “the architecture is clear internally” and instead say “the product boundary is now documented and enforceable”

## Hard Stop

Stop and re-evaluate if this program drifts into:

- a new capability implementation
- generalized UX redesign
- prompt/model experimentation
- exploratory batch reopening

That would mean the project is leaving productization and falling back into capability chasing.

## Expected Outcome

By the end of this stage, the project should be able to present itself as:

> a SQL optimizer with a documented supported scope, explicit blocked boundaries, and merge gates that protect those boundaries

That is a stronger product position than “we have a lot of internal planning documents explaining why things are blocked.”
