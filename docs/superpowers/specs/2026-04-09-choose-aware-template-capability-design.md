# Choose-Aware Template Capability Design

## Goal

Define a narrow, template-preserving capability for `choose`-guarded dynamic filters.

This stage is not about making all `CHOOSE` statements patchable. It is about deciding whether the product can support a small, defensible subset of `<where><choose>...</choose></where>` statements without weakening current semantic boundaries.

## Why This Exists

The safe-baseline review already proved:

- `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER` is real
- the sentinel `demo.user.advanced.findUsersByKeyword` is structurally close to the existing `IF_GUARDED_FILTER_STATEMENT` lane
- but current `rewrite_facts` still report:
  - `capabilityTier = REVIEW_REQUIRED`
  - `baselineFamily = None`
  - blocker `DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE`
- current `SAFE_BASELINE_RECOVERY` only admits static-family baselines

So the remaining question is no longer “is there a small recovery rule?” The question is:

> Can we introduce a branch-preserving choose-aware patch capability without turning `CHOOSE` into a generic statement-rewrite escape hatch?

## Sentinel Set

### Primary capability sentinel

- `demo.user.advanced.findUsersByKeyword`

### Semantic-risk / non-goal sentinels

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`

These four statements exist to prove what must stay blocked.

## Supported Shape

Only the following shape is even eligible for this capability:

1. statement shape remains `IF_GUARDED_FILTER_STATEMENT`
2. exactly one top-level `<choose>` exists
3. the `<choose>` lives directly inside `<where>`
4. branch bodies are predicate-only
5. branch bodies do not contain:
   - `<include>`
   - `ORDER BY`
   - `GROUP BY`
   - `HAVING`
   - `JOIN`
   - `UNION`
   - `LIMIT/OFFSET/FETCH`
6. no outer `foreach`
7. no nested `choose`

This is intentionally narrower than “supported choose.”

## Non-Goals

This capability must not:

- support top-level bare `choose`
- support choose-driven ordering or pagination
- support fragment-driven choose branches
- merge choose branches into flat SQL predicates
- auto-patch semantic-risk rewrites such as `union_or_elimination`
- auto-patch unsupported strategy tails such as union/index or join-style rewrites

## Recommended Capability Shape

The recommended design is **branch-preserving choose-aware patching**.

That means:

- the `<choose>` structure remains intact
- each branch body is treated as its own predicate rewrite surface
- a patch is only allowed when every touched branch can be rewritten by a known, semantics-preserving branch-local operation

The capability should not invent a flat replacement SQL statement. It should operate at template level.

## Minimal First Scope

The first implementation scope should be deliberately smaller than the full sentinel set:

1. recognize a choose-aware capability profile in `rewrite_facts`
2. allow a branch-local patch only when the chosen rewrite is a **known template-preserving branch-local transformation**
3. if no branch-local transformation exists, keep the statement blocked with the explicit subtype

That means `demo.user.advanced.findUsersByKeyword` is allowed to remain blocked even in the first program pass. The success condition is not “make it green at any cost.” The success condition is:

- either prove one real branch-local path exists
- or prove the whole lane should remain deferred

## Patch Model

This design assumes the current patch model needs a new capability boundary, not a generic recovery tweak.

Recommended direction:

- add a choose-aware capability/profile marker
- add a dedicated template patch surface for choose branch bodies
- keep convergence and patch selection conservative unless branch-local proof exists

This may become a new patch family or a new template patch mode. The decision should be made in implementation after checking how much reuse is possible from existing dynamic filter families.

## Validation Requirements

Any promoted choose-aware path must satisfy all of these:

1. semantic equivalence stays `PASS`
2. the `<choose>` branch structure is preserved
3. patch generation does not flatten branches into one executable predicate string
4. unsupported sentinels remain blocked for their current reasons

## Success Criteria

This capability program is successful if it ends with one of these two outcomes:

1. **Promote**
   - at least one narrow choose-aware branch-preserving path is implemented and proven safe
2. **Freeze/Defer with evidence**
   - the capability is shown to require a broader patch model than is justified right now

Either result is valid. “More green” is not the primary metric.
