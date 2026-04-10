# Surface-Specific Dynamic Rewrite Ops

## Purpose

Define the minimum internal rewrite-op contract for dynamic sub-statement template-preserving edits.

This spec is design-only.

It does **not** add implementation support yet.

Its job is to answer:

> Can the project define surface-local dynamic rewrite ops without silently falling back to statement-level or fragment-level replacement?

## Existing Limitation

Current template materialization and replay only understand:

- `replace_statement_body`
- `replace_fragment_body`

Those ops are too coarse for the two deferred dynamic review-only surfaces:

- `CHOOSE_BRANCH_BODY`
- `COLLECTION_PREDICATE_BODY`

Without narrower ops, any later "promotion" would be fake because it would still rely on whole-statement or whole-fragment replacement semantics.

## Design Goals

1. represent branch-local and collection-local edits explicitly
2. make the target envelope addressable
3. preserve sibling template structure outside the envelope
4. forbid statement/fragment fallback from being treated as equivalent

## New Ops

This spec introduces two candidate internal ops:

- `replace_choose_branch_body`
- `replace_collection_predicate_body`

These are internal artifact contracts first.

They are not yet user-visible patch families.

## Shared Contract Shape

Each surface-specific dynamic op must carry:

- `op`
- `targetRef`
- `targetSurface`
- `targetAnchor`
- `beforeTemplate`
- `afterTemplate`
- `preservedAnchors`
- `safetyChecks`

### `targetRef`

The owning statement or fragment reference already used by the current template-safe pipeline.

This keeps the new ops attached to an existing template container without claiming that the entire container is editable.

### `targetSurface`

A required enum:

- `CHOOSE_BRANCH_BODY`
- `COLLECTION_PREDICATE_BODY`

This must match rewrite facts capability profile exactly.

### `targetAnchor`

The surface-local identity object.

This is the critical new field.

It is what prevents these ops from degenerating into statement-level replacement.

`targetAnchor` must be structured data, not free text.

## `replace_choose_branch_body`

### Intended Meaning

Replace the inner body of one specific `<when>` or `<otherwise>` branch inside one top-level `<choose>` block, while preserving:

- the surrounding `<choose>`
- sibling branches
- the surrounding `<where>` envelope
- all structure outside the target branch body

### Required `targetAnchor`

`targetAnchor` for `replace_choose_branch_body` must include:

- `surfaceType = "CHOOSE_BRANCH_BODY"`
- `branchKind`
  - `WHEN`
  - `OTHERWISE`
- `branchOrdinal`
  - zero-based position among the immediate branches of the owned `<choose>`
- `chooseOrdinal`
  - zero-based position of the target `<choose>` within the owned statement or fragment
- `whereEnvelopeRequired`
  - boolean, currently expected to be `true`

Optional future fields may include:

- normalized `test` fingerprint for `WHEN`
- envelope fingerprint

### Safety Meaning

This op is only valid if:

- exactly one top-level target `<choose>` exists
- the target branch is uniquely identifiable
- sibling branches can be proven unchanged
- the surrounding `<where>` envelope can be proven unchanged

### Invalid Cases

This op must be rejected if:

- there are nested `<choose>` blocks within the target branch
- the target branch contains `<include>`, `<foreach>`, `<trim>`, `ORDER BY`, `GROUP BY`, `HAVING`, `JOIN`, `UNION`, `LIMIT`, or `OFFSET`
- target identity depends on statement-level text slicing rather than branch-local identity

## `replace_collection_predicate_body`

### Intended Meaning

Replace a guarded collection predicate zone that includes `<foreach>` plus its scalar guard logic, while preserving:

- the owning statement or fragment
- sibling predicates outside the collection zone
- the outer `<where>` or equivalent predicate envelope
- include structure outside the target collection zone

### Required `targetAnchor`

`targetAnchor` for `replace_collection_predicate_body` must include:

- `surfaceType = "COLLECTION_PREDICATE_BODY"`
- `foreachOrdinal`
  - zero-based position of the target `<foreach>` within the owned template surface
- `guardKind`
  - enum describing the scalar guard envelope
  - initially one of:
    - `IF_GUARD`
    - `IF_INCLUDE_GUARD`
    - `MIXED_SCALAR_GUARD`
- `whereEnvelopeRequired`
  - boolean
- `includeScoped`
  - boolean

Optional future fields may include:

- normalized `collection` / `item` / `open-close-separator` shape
- normalized guard-expression fingerprint

### Safety Meaning

This op is only valid if:

- one target collection predicate zone can be identified unambiguously
- the `<foreach>` envelope is preserved
- the scalar guard structure is preserved
- sibling predicate structure remains unchanged

### Invalid Cases

This op must be rejected if:

- multiple `<foreach>` predicates compete for the same anchor identity
- the guard envelope depends on multi-fragment include expansion that cannot be proven local
- promotion would require widening to a whole `WHERE_CLAUSE` or statement-level replacement

## `beforeTemplate` / `afterTemplate`

For these new ops, `beforeTemplate` and `afterTemplate` mean:

- the inner template body of the target surface only
- not the whole statement body
- not the whole fragment body

That is the main semantic difference from existing ops.

The stored template text must be scoped to the local editable surface.

## `preservedAnchors`

`preservedAnchors` remains required, but its meaning becomes surface-local:

- for `replace_choose_branch_body`, it should include preserved branch/envelope anchor ids
- for `replace_collection_predicate_body`, it should include preserved foreach/guard/envelope anchor ids

It must not be used as a substitute for `targetAnchor`.

## `safetyChecks`

The op must carry explicit surface-local safety checks.

Expected keys include:

- `surfaceLocalIdentityVerified`
- `siblingStructurePreserved`
- `envelopeStructurePreserved`
- `statementLevelFallbackUsed`
- `fragmentLevelFallbackUsed`

For this program:

- `statementLevelFallbackUsed` must always be `false`
- `fragmentLevelFallbackUsed` must always be `false`

If either becomes `true`, the op is invalid for promotion.

## Non-Equivalence Rule

These ops are **not** semantically equivalent to:

- `replace_statement_body`
- `replace_fragment_body`

The pipeline must treat them as different classes of edit.

It is invalid to "materialize" them by silently converting them into whole-container replacement while still claiming surface-local safety.

## Review-Only Phase Rule

Before replay and materialization support exists:

- the ops may be represented in artifacts or design docs
- the pipeline may thread them through review-only diagnostics
- patch generation must still stop at manual review

This allows substrate work without pretending the capability is already supported.

## Promotion Gate

These ops are promotable only if later tasks define all of:

1. replay contract that proves target-surface identity
2. materialization mode that can locate and rewrite only the local surface
3. patch family that requires these ops explicitly
4. replay evidence showing no guardrail widening

Without those, the ops remain review-only design constructs.

## Current Verdict

At this stage:

- `replace_choose_branch_body` is a valid candidate contract
- `replace_collection_predicate_body` is a valid candidate contract

Both are acceptable to carry forward into Task 3.

Neither is acceptable to implement with statement-level or fragment-level fallback semantics.
