# Template-Preserving Dynamic Capability Design

## Purpose

Define the minimum internal contract for dynamic template-safe patch surfaces below `STATEMENT_BODY`.

This design is intentionally narrow and review-first.

It does **not** promise automatic patch generation for dynamic branches or collection predicates.

## Problem

Current dynamic support has two review-only lanes that are now clearly classified:

- `CHOOSE_BRANCH_BODY`
- `FOREACH_COLLECTION_PREDICATE`

But the system still treats them inconsistently:

- `CHOOSE_BRANCH_BODY` exists in rewrite facts, but had no explicit patch-stage guardrail
- collection predicates were still represented as generic `WHERE_CLAUSE`
- patch materialization only knows:
  - `replace_statement_body`
  - `replace_fragment_body`

So the pipeline could describe some dynamic review-only shapes, but it did not yet expose a consistent contract for them.

## Design Goals

1. Represent narrow dynamic sub-statement surfaces explicitly
2. Carry those surfaces through rewrite facts, patchability, convergence, reporting, and patch gating
3. Keep the surfaces review-only until a dedicated template-preserving patch family exists
4. Avoid flattening dynamic templates into executable SQL patch targets

## New Contract

### Dynamic patch surfaces

The design recognizes these dynamic patch surfaces:

- `STATEMENT_BODY`
  - existing safe-baseline statement-level template edit
- `CHOOSE_BRANCH_BODY`
  - branch-local review-only surface for one top-level `<choose>` inside `<where>`
- `COLLECTION_PREDICATE_BODY`
  - review-only surface for guarded `<foreach>` collection predicates
- `WHERE_CLAUSE`
  - legacy dynamic predicate surface for generic review-only cases
- `SET_CLAUSE`
  - existing review-only dynamic set surface

### Semantics

#### `CHOOSE_BRANCH_BODY`

- describes a candidate patch surface that is smaller than the statement body
- means the system can identify the relevant branch-local editing zone
- does **not** mean patch generation is allowed
- current required blocker family:
  - `DYNAMIC_FILTER_CHOOSE_GUARDED_REVIEW_ONLY`

#### `COLLECTION_PREDICATE_BODY`

- describes a guarded collection predicate zone containing `<foreach>` plus scalar guard logic
- replaces the older over-broad use of `WHERE_CLAUSE` for this lane
- does **not** mean patch generation is allowed
- current required blocker family:
  - `FOREACH_COLLECTION_GUARDED_PREDICATE`

## Review-Only Rule

Any dynamic patch surface below `STATEMENT_BODY` is review-only unless all of the following become true:

1. a dedicated baseline family exists
2. materialization can target that surface directly
3. replay contract can verify the surface-specific rewrite ops
4. patch generation can apply the resulting op without replacing the whole statement

Until then:

- convergence may classify the shape
- patchability may expose the surface
- reporting may display the surface
- patch generation must stop at manual-review

## Current Supported Plumbing

After this stage, the contract is expected to be visible in:

- rewrite facts capability profile
- patchability assessment
- dynamic template summary
- convergence/report summaries
- patch-stage review-only selection reasons

It is **not** expected to be visible as a new materialized rewrite op yet.

## Explicit Non-Goals

This design does not add:

- `replace_choose_branch_body`
- `replace_collection_predicate_body`
- new dynamic patch families
- dynamic patch replay beyond existing statement/fragment modes

Those would belong to a later promotion stage if the review-only foundation proves valuable.

## Promotion Criteria

Promotion from review-only to supported requires:

- a dedicated patch family
- a surface-specific materialization mode
- a replay contract for that mode
- sentinel replay proving no guardrail widening

Without those, the surface stays an honest review-only contract.
