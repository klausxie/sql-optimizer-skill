# Dynamic Filter Envelope Cleanup Design

## Status

- Date: 2026-03-27
- Scope: brainstorming-approved design
- Goal: onboard two dynamic safe-baseline families through the patch family onboarding framework without widening dynamic subtree rewrite scope

## Goal

Add a shared onboarding skeleton for dynamic filter envelope cleanup, then use it to onboard:

1. `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`
2. `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`

The target is not generic dynamic SQL rewriting. The target is a narrow, high-correctness path for dynamic statements whose dynamic behavior remains fully preserved while only the static envelope is cleaned up.

## Non-Goals

This design does not attempt to:

1. rewrite `<if>` predicates
2. reorder dynamic nodes
3. support `<choose>`, `<bind>`, `<foreach>`, or `<set>`
4. support join alias cleanup
5. expand into generic `DYNAMIC_FILTER_SUBTREE` rewriting

## Shared Skeleton

Both families must use one shared skeleton rather than two unrelated onboarding paths.

The shared skeleton is responsible for:

1. shared shape gate
2. shared blocked reasons
3. shared replay and verification obligations
4. shared fixture helper surface

This keeps future dynamic envelope families from reintroducing one-off logic across validate, verification, and fixture harnesses.

## Shared Shape Gate

The shared gate must accept only statements that satisfy all of the following:

1. statement type is `SELECT`
2. dynamic template is present
3. dynamic structure is a single `<where>` containing flat sibling `<if>` nodes
4. outer static envelope may be either:
   - a direct statement body with optional static `ORDER BY` and `LIMIT`
   - a single static subquery shell around the same dynamic `<where>/<if>` body, with optional static `ORDER BY` and `LIMIT`
5. patch surface stays `STATEMENT_BODY`
6. rewrite path remains template-preserving

The shared gate must reject any statement containing:

1. `<choose>`
2. `<bind>`
3. `<foreach>`
4. `<set>`
5. nested dynamic subtree rewrites
6. join-driven alias cleanup

## Family A: `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`

### Scope

This family only cleans static projection aliases outside the dynamic `<where>/<if>` tree.

Allowed:

1. `col AS col`

Blocked:

1. `u.col AS col`
2. expression aliases
3. constant aliases
4. aggregate aliases

### Ready Shape

The statement keeps the original `<where>` and all `<if>` nodes unchanged, while the outer static projection list normalizes from redundant same-name aliases into direct columns.

### Minimum Blocked Neighbors

Each onboarding slice must include at least:

1. one semantic neighbor using qualified projection aliases such as `u.id AS id`
2. one template neighbor that introduces disallowed dynamic structure such as `<choose>` or nested `<if>`

## Family B: `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`

### Scope

This family only cleans redundant aliases in the static `FROM` envelope while preserving the dynamic `<where>/<if>` tree.

Allowed:

1. single-table alias cleanup
2. alias cleanup around a single subquery shell that already passed the shared gate

Blocked:

1. join alias cleanup
2. any case that requires rewriting `<if>` predicate references
3. any case that requires reordering dynamic nodes

### Ready Shape

The statement keeps the original dynamic filter tree unchanged while removing only redundant static `FROM` aliases in the outer envelope or a single subquery shell.

### Minimum Blocked Neighbors

Each onboarding slice must include at least:

1. one semantic neighbor involving join aliases
2. one template neighbor where cleanup would require rewriting predicate references inside `<if>`

## Acceptance Policy

Both families stay conservative:

1. `semantic status = PASS`
2. `semantic confidence >= HIGH`
3. `patchability.eligible = True`
4. selected patch strategy must remain on the allowed dynamic envelope path
5. replay contract must exist

If a candidate only reaches `MEDIUM`, it must not enter frozen auto-patch scope in this iteration.

## Patch Family Derivation

The new onboarding flow must continue to use:

`rewrite facts -> validate acceptance -> patchTarget.family -> replay/verification -> fixture obligations`

The family must be derived during validate-side family classification, not guessed in `patch_generate`.

The derivation order is:

1. shared shape gate
2. mutually exclusive family-specific classifiers
3. patch target persistence

The classifier contract is:

1. `DYNAMIC_FILTER_SELECT_LIST_CLEANUP` and `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP` are mutually exclusive
2. if a candidate appears to require both select-list cleanup and from-alias cleanup in the same rewrite, it is out of scope for this iteration
3. such combined cases must block explicitly rather than choosing one family heuristically

If the shared gate passes but the family classifier fails, the system must not fall back to a broader generic dynamic rewrite family.

## Replay And Verification

Both families must preserve the same proof contract:

1. `<where>` node remains present
2. `<if>` node count remains unchanged
3. `<if>` node order remains unchanged
4. normalized `<if test="...">` expressions remain text-identical before and after rewrite
5. normalized `<if>` predicate bodies remain text-identical before and after rewrite
6. placeholder shape remains unchanged
7. replayed rendered SQL matches target rewritten SQL
8. XML parse passes
9. render passes
10. SQL parse passes
11. apply-check passes

This design does not introduce family-specific verifier engines. It binds these families to the existing proof chain through explicit shared obligations.

## Blocking Reasons

If the shared gate passes but a family still falls outside the narrow scope, the system must block explicitly rather than silently widening scope.

Expected reason-code families include:

1. `DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH`
2. `DYNAMIC_FILTER_SELECT_LIST_NON_TRIVIAL_ALIAS`
3. `DYNAMIC_FILTER_FROM_ALIAS_REQUIRES_PREDICATE_REWRITE`

The exact reason-code names may be adjusted during implementation if they align better with existing naming conventions, but the behavior must remain explicit and non-fallback.

## Fixture Obligations

This design requires non-empty fixture onboarding for both families.

Minimum requirement per family:

1. one ready case
2. two blocked neighbors
3. replay assertions for ready patch rows
4. syntax / verification assertions for ready patch rows
5. blocked-neighbor assertions that prove the case did not fall back to a broader family

This means the rollout is not complete if the family spec exists but the fixture harness cannot prove:

1. the ready case resolves to the registered family
2. the blocked-neighbor requirement is satisfied
3. the ready patch row meets replay and verification obligations
4. the blocked rows emit an explicit blocker and do not persist as another broader auto-patch family

## Recommended Implementation Order

Implementation should proceed in this order:

1. add the shared dynamic envelope skeleton
2. onboard `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`
3. onboard `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`
4. add aggregate regression coverage for the shared surface

The order is intentional. `SELECT_LIST_CLEANUP` is narrower and less likely to force the shared skeleton into serving alias-reference edge cases too early.

## Rationale

This design keeps the project aligned with the existing product goal:

1. high correctness
2. low coverage by choice
3. explicit proof before auto-patch

It expands family coverage without reopening the dangerous `dynamic subtree rewrite` problem.

## Harness Plan

### Proof Obligations

1. only the static envelope is cleaned up while dynamic `<if>` / `<where>` behavior remains preserved
2. `DYNAMIC_FILTER_SELECT_LIST_CLEANUP` and `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP` stay narrow and distinct
3. blocked neighbors remain blocked instead of widening to generic dynamic subtree rewrite
4. replay, verification, and report surfaces agree on the delivered family and outcome

### Harness Layers

#### L1 Unit Harness

- Goal: prove dynamic envelope classification and family-specific shape detection
- Scope: select-list cleanup vs from-alias cleanup boundaries, preserved dynamic structure, blocker logic
- Allowed Mocks: synthetic dynamic traces and family inputs are acceptable
- Artifacts Checked: in-memory shape and family classification payloads
- Budget: fast PR-safe runtime

#### L2 Fixture / Contract Harness

- Goal: prove fixture scenarios, family obligations, and downstream contracts stay aligned
- Scope: ready cases, blocked-neighbor cases, replay requirements, report summaries
- Allowed Mocks: synthetic validate evidence may be used when proving contract alignment
- Artifacts Checked: fixture matrix, acceptance artifacts, patch artifacts, verification artifacts, report aggregates
- Budget: moderate PR-safe runtime

#### L3 Scoped Workflow Harness

- Goal: prove one selected dynamic filter family through a real workflow slice
- Scope: one SQL key or one mapper slice per dynamic family
- Allowed Mocks: infrastructure-availability patches only
- Artifacts Checked: selected real run outputs across validate, patch, verification, and report
- Budget: targeted workflow runtime

#### L4 Full Workflow Harness

- Goal: prove dynamic envelope onboarding does not destabilize the broader patch portfolio
- Scope: full fixture-project regression
- Allowed Mocks: only workflow-stability patches that preserve patch semantics
- Artifacts Checked: full run outputs and report summaries
- Budget: separately governed broader regression lane

### Shared Classification Logic

1. dynamic baseline family and delivery class should reuse production semantics
2. blocked-neighbor classification should not drift into fixture-only logic

### Artifacts And Diagnostics

1. `tests/fixtures/project/fixture_scenarios.json`
2. `pipeline/validate/acceptance.results.jsonl`
3. `pipeline/patch_generate/patch.results.jsonl`
4. `pipeline/verification/ledger.jsonl`
5. `overview/report.json`

### Execution Budget

1. `L1` and `L2` are expected for family-onboarding edits
2. `L3` should be used before treating a dynamic family as stable
3. `L4` remains the broad-regression governance layer

### Regression Ownership

1. any expansion of dynamic safe-baseline scope
2. any change to dynamic envelope classification
3. any report field derived from dynamic family or delivery class
