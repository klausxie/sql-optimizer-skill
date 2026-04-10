# Surface-Specific Dynamic Replay Contract

## Purpose

Define what replay must prove before any surface-specific dynamic rewrite op can move beyond review-only.

This spec extends the existing template replay contract model that currently relies on:

- `rewriteMaterialization.replayContract`
- `templateRewriteOps`

It does **not** implement new replay logic yet.

## Existing Limitation

Current replay semantics are built around whole-container edits:

- `replace_statement_body`
- `replace_fragment_body`

Current replay checks are good at proving:

- rendered SQL matches expected SQL
- include anchors were preserved
- placeholder shape stayed stable
- `<if>` test/body shape stayed stable

They are **not** good at proving:

- which exact choose branch was edited
- which exact collection predicate zone was edited
- whether sibling template structure outside the target surface remained unchanged

That is the missing contract this spec defines.

## Replay Contract Placement

Surface-specific replay still lives under:

- `rewriteMaterialization.replayContract`

and still references:

- `templateRewriteOps`

The difference is that replay now needs surface-local identity evidence in addition to rendered SQL equivalence.

## Shared Contract Additions

The replay contract for any surface-specific dynamic op must include these extra fields:

- `targetSurface`
- `targetAnchor`
- `requiredSurfaceIdentity`
- `requiredSiblingShape`
- `requiredEnvelopeShape`
- `surfaceFallbackAllowed`

### `targetSurface`

Required enum:

- `CHOOSE_BRANCH_BODY`
- `COLLECTION_PREDICATE_BODY`

### `targetAnchor`

Must be copied from the matching rewrite op.

Replay must treat this as the primary identity claim for the local editable surface.

### `requiredSurfaceIdentity`

Structured proof requirements for the target surface itself.

### `requiredSiblingShape`

Structured proof requirements for siblings outside the edited surface.

### `requiredEnvelopeShape`

Structured proof requirements for the containing envelope, such as the outer `<where>` or scalar guard shell.

### `surfaceFallbackAllowed`

Must be `false` for this program.

If replay can only succeed by treating the edit as statement-level or fragment-level replacement, replay must fail.

## `CHOOSE_BRANCH_BODY` Replay Contract

### Required Fields

For `targetSurface = CHOOSE_BRANCH_BODY`, replay contract must include:

- `targetSurface = "CHOOSE_BRANCH_BODY"`
- `targetAnchor`
  - `surfaceType`
  - `chooseOrdinal`
  - `branchKind`
  - `branchOrdinal`
  - `whereEnvelopeRequired`
- `requiredSurfaceIdentity`
  - `branchCount`
  - `targetBranchTestFingerprint` for `WHEN`
  - `targetBranchKind`
- `requiredSiblingShape`
  - `siblingBranchCount`
  - `siblingBranchFingerprints`
- `requiredEnvelopeShape`
  - `whereEnvelopePresent`
  - `outerChooseCount`
  - `outerUnsupportedTagsAbsent`

### Replay Must Prove

Replay is successful only if:

1. the same top-level `<choose>` is present
2. the same target branch is identifiable
3. sibling branches remain structurally unchanged
4. the surrounding `<where>` envelope remains structurally unchanged
5. rendered SQL still matches the expected rewritten SQL

### Replay Must Reject

Replay must fail if:

- branch ordinal becomes ambiguous
- `WHEN` test fingerprint changes unexpectedly
- sibling branches disappear, merge, or reorder
- outer `<where>` structure changes
- the system can only prove the change by comparing whole statement bodies

## `COLLECTION_PREDICATE_BODY` Replay Contract

### Required Fields

For `targetSurface = COLLECTION_PREDICATE_BODY`, replay contract must include:

- `targetSurface = "COLLECTION_PREDICATE_BODY"`
- `targetAnchor`
  - `surfaceType`
  - `foreachOrdinal`
  - `guardKind`
  - `whereEnvelopeRequired`
  - `includeScoped`
- `requiredSurfaceIdentity`
  - `foreachCount`
  - `targetForeachShape`
  - `guardFingerprint`
- `requiredSiblingShape`
  - `siblingPredicateFingerprints`
  - `outerForeachCount`
- `requiredEnvelopeShape`
  - `whereEnvelopePresent`
  - `includeEnvelopeFingerprint`
  - `multiFragmentExpansionAbsent`

### Replay Must Prove

Replay is successful only if:

1. the same collection predicate zone is identifiable
2. the same `<foreach>` envelope survives
3. the scalar guard shell survives
4. sibling predicates outside the target zone remain structurally unchanged
5. rendered SQL still matches the expected rewritten SQL

### Replay Must Reject

Replay must fail if:

- multiple foreach candidates can satisfy the same anchor
- scalar guard identity becomes ambiguous
- include expansion changes the local boundary
- replay can only prove correctness by widening to generic `WHERE_CLAUSE`

## Relationship To Existing Fields

Existing fields still matter:

- `requiredTemplateOps`
- `expectedRenderedSql`
- `expectedFingerprint`
- `requiredAnchors`
- `requiredIncludes`
- `requiredPlaceholderShape`
- `requiredIfTestShape`
- `requiredIfBodyShape`

The new rule is:

these are necessary but not sufficient for surface-specific replay.

Rendered SQL equivalence alone cannot prove surface-local safety.

## Review-Only Phase Rule

Before materialization exists, the replay contract may still be emitted in review-only diagnostics.

At that stage:

- replay evidence may describe what must be proven
- actual replay verification may remain `false`
- patch generation must stay blocked

This is acceptable because the substrate is still being designed.

## Promotion Gate

Surface-specific replay is promotable only if:

1. all required surface-local fields can be produced deterministically
2. replay can reject statement/fragment fallback
3. guardrails remain blocked in targeted replay runs
4. the primary sentinel can be replayed without ambiguity

If any of those fail, the surface remains review-only.

## Current Verdict

At this stage:

- the replay contract shape for `CHOOSE_BRANCH_BODY` is definable
- the replay contract shape for `COLLECTION_PREDICATE_BODY` is definable

This is enough to move to materialization and patch-family design.

It is not enough to promote either lane yet.
