# Low-Value/No-Op Boundary Design

## Goal

Define the next cleanup stage around one bounded product question:

> are the remaining low-value/no-op tails final reporting boundaries that should be frozen explicitly, or are any of them still mislabeled?

This stage is not a capability program.

It is a boundary-cleanup stage for proposals that are already correctly blocked because they do not produce a meaningful patch.

## Why This Stage Comes Next

The project has already frozen:

- safe-baseline deferred/frozen lanes
- semantic/validation clarified lanes
- unsupported-strategy tails

That leaves the smallest remaining ambiguous cleanup surface:

- `NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT`
- generic `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` where it still remains

These statements are not asking for new SQL capability. They are asking for cleaner product truth.

## Primary Sentinels

- `demo.test.complex.staticSimpleSelect`
  - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT`
- `demo.test.complex.staticOrderBy`
  - low-value/no-op canary already used in prior batches

## Guardrail Sentinels

- `demo.test.complex.existsSubquery`
- `demo.test.complex.inSubquery`
- `demo.test.complex.leftJoinWithNull`
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.test.complex.includeNested`
- `demo.user.findUsers`

These must remain in unsupported, semantic, or validate lanes; low-value cleanup must not absorb them.

## Recommended Output

At the end of this stage:

- low-value/no-op tails are explicitly frozen as non-deliverable
- neighboring semantic, validate, and unsupported lanes stay untouched
- the project is ready for a final delivery/boundary summary instead of more exploratory cleanup
