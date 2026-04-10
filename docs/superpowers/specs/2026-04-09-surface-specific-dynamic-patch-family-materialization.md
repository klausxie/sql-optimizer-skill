# Surface-Specific Dynamic Patch Family And Materialization Contract

## Purpose

Define the minimum patch-family and materialization model needed for surface-specific dynamic edits.

This spec answers:

> What must change in patch family modeling and template materialization so that surface-local dynamic rewrites are real, instead of disguised whole-statement edits?

## Existing Limitation

Current patch family and materialization support are tied to whole-container semantics:

- patch families mostly require `replace_statement_body` or `replace_fragment_body`
- template materialization only produces statement-level or fragment-level ops
- patch build and replay only know how to apply those two op classes

That is incompatible with:

- `CHOOSE_BRANCH_BODY`
- `COLLECTION_PREDICATE_BODY`

because those surfaces are smaller than the owning statement or fragment.

## Design Goals

1. make dynamic surface-local families explicit
2. forbid promotion through statement/fragment fallback
3. allow review-only plumbing before full implementation
4. make materialization target the local surface, not the whole container

## Candidate Patch Families

This spec introduces two candidate future family lanes:

- `DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP`
- `DYNAMIC_COLLECTION_PREDICATE_LOCAL_CLEANUP`

These names are intentionally narrow.

They do **not** imply broad dynamic support.

## Patch Family Scope

### `DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP`

Scope requirements:

- statement type is dynamic template statement
- dynamic shape family must be `IF_GUARDED_FILTER_STATEMENT`
- patch surface must be `CHOOSE_BRANCH_BODY`
- top-level `<where><choose>` only
- no include/foreach/order/group/having/join/union/limit widening

### `DYNAMIC_COLLECTION_PREDICATE_LOCAL_CLEANUP`

Scope requirements:

- statement type is dynamic template statement
- dynamic shape family must be `FOREACH_COLLECTION_PREDICATE`
- patch surface must be `COLLECTION_PREDICATE_BODY`
- one collection predicate zone only
- no multi-fragment ambiguous envelope

## Patch Target Policy

Neither family may reuse generic template-edit semantics.

Required patch target policy:

- `requires_replay_contract = true`
- `materialization_modes` must be surface-specific
- `target_ref_policy` must stay attached to the owning statement/fragment
- the local surface must be identified through `targetSurface + targetAnchor`

Statement-level or fragment-level replacement is not an acceptable substitute.

## Candidate Materialization Modes

This spec introduces two candidate future materialization modes:

- `DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE`
- `DYNAMIC_COLLECTION_PREDICATE_TEMPLATE_SAFE`

These modes are distinct from:

- `STATEMENT_TEMPLATE_SAFE`
- `FRAGMENT_TEMPLATE_SAFE`

### `DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE`

Must mean:

- locate one owned statement or fragment
- locate one top-level choose branch within it
- rewrite only that branch body
- preserve sibling branches and outer envelope

### `DYNAMIC_COLLECTION_PREDICATE_TEMPLATE_SAFE`

Must mean:

- locate one owned statement or fragment
- locate one collection predicate zone within it
- rewrite only that local zone
- preserve sibling predicates and outer envelope

## Required Template Ops

These families must require the new ops explicitly:

- `replace_choose_branch_body`
- `replace_collection_predicate_body`

It is invalid for these families to accept:

- `replace_statement_body`
- `replace_fragment_body`

as their sole materialized op.

## Materialization Requirements

Materialization must produce:

- local-surface `beforeTemplate`
- local-surface `afterTemplate`
- `targetSurface`
- `targetAnchor`
- surface-local `preservedAnchors`
- surface-local `safetyChecks`

Materialization must also prove:

- the owning template container exists
- the local surface can be found uniquely
- sibling structure outside the target surface is preserved

## Patch Build Rule

Patch building must apply the resulting op to the owning XML node without widening the edit range beyond the local surface.

If the only available implementation strategy is:

- replace whole statement body
- replace whole fragment body

then the family is not truly implemented and must remain review-only.

## Review-Only Plumbing Rule

Before the local patch builder exists:

- these families may be declared as future families in design docs
- review-only materialization modes may be represented in diagnostics
- patch generation must still stop with explicit manual-review blocking reasons

This keeps the system honest while the substrate is incomplete.

## Promotion Gate

Either family is promotable only if:

1. materialization can locate the local surface deterministically
2. replay can prove local-surface identity
3. patch build can rewrite only that local surface
4. targeted sentinel replay shows no guardrail widening

Without all four, the family remains review-only or nonexistent.

## Current Verdict

At this stage:

- the family model is definable
- the materialization-mode split is definable

But neither family should be implemented through current statement/fragment machinery.

That would be false promotion.
