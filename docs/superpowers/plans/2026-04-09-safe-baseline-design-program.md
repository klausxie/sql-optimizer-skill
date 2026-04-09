# Safe-Baseline Design Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans before implementation. This program starts from the completed generalization phase review and deliberately stops using new `batchN` expansion as the main planning primitive.

**Goal:** Turn the current `NO_SAFE_BASELINE_*` blocker surface from an observational bucket into explicit product decisions and bounded engineering tasks.

This program is not about discovering more samples. It is about deciding which safe-baseline subtypes should become supported capabilities, which should be frozen as boundaries, and what the minimum implementation path would be for the supported set.

## Why This Program Exists

The fresh `batch1..13` review is already clear:

- `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `NO_SAFE_BASELINE_RECOVERY = 21`
- `AUTO_PATCHABLE` has plateaued
- recent batches mostly improved blocker honesty, not ready count

That means the project is no longer blocked on classification work. It is blocked on **product decisions about safe baselines**.

## Fresh Baseline

Reference review:

- [2026-04-09-generalization-phase-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-generalization-phase-review.md)

Fresh blocker subtypes currently in scope:

1. `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
2. `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
3. `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
4. `NO_SAFE_BASELINE_FOREACH_INCLUDE_PREDICATE`
5. `NO_SAFE_BASELINE_GROUP_BY`

Primary sentinel statements already proving these lanes:

- `demo.user.advanced.findUsersByKeyword`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.multiFragmentLevel1`
- `demo.order.harness.findOrdersByUserIdsAndStatus`
- `demo.test.complex.staticGroupBy`

## Program Output

This program should produce four things:

1. A **safe-baseline decision table**
   - each subtype marked `promote`, `freeze`, or `defer`
2. A **minimal implementation verdict** for the deferred subtype(s)
3. A **boundary registry update** for the frozen subtype(s)
4. A **post-program replay review** proving the chosen direction did not regress existing ready or blocked sentinels

## Decision Rule

Each subtype must be evaluated against the same questions:

1. Can we define a template-aware rewrite that preserves semantics without widening current boundaries?
2. Can we verify that rewrite using existing validate / semantic checks?
3. Does it map onto an existing patch family, or would it require a brand-new family?
4. Does supporting it improve a shared lane, or only one isolated statement?

Decision outcomes:

- `promote`
  - there is a narrow, reusable, template-aware safe baseline
- `freeze`
  - there is no safe baseline worth automating in the current product scope
- `defer`
  - plausible future support exists, but not with the current validator/patch model

## Initial Recommendation By Subtype

These are the recommended starting hypotheses for the program, not final decisions:

### 1. `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`

Initial recommendation: `promote-candidate`

Status after Task 2 evidence review: `defer`

Why:

- it appears on a real dynamic-filter path
- but the sentinel still resolves to `capabilityTier = REVIEW_REQUIRED`, `baselineFamily = None`, blocker `DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE`
- current `SAFE_BASELINE_RECOVERY` only covers static families, so a real fix would require a new choose-aware template-preserving patch path rather than a small recovery tweak

Sentinel:

- `demo.user.advanced.findUsersByKeyword`

### 2. `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`

Initial recommendation: `freeze-candidate`

Why:

- current suggestions are speculative pagination-style rewrites
- this is exactly the kind of drift we have repeatedly refused to auto-patch
- supporting it would likely require semantic weakening rather than a true baseline

Sentinel:

- `demo.shipment.harness.findShipments`

### 3. `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`

Initial recommendation: `defer/freeze-candidate`

Why:

- multi-fragment include chains repeatedly show up as structure-heavy and hard to verify
- current patch model is not strong at fragment-chain preservation

Sentinel:

- `demo.test.complex.multiFragmentLevel1`

### 4. `NO_SAFE_BASELINE_FOREACH_INCLUDE_PREDICATE`

Initial recommendation: `defer-candidate`

Why:

- it is structurally important, but support would require clear template-aware handling of `foreach + include + where`
- this is more likely a future capability than a quick baseline add

Sentinel:

- `demo.order.harness.findOrdersByUserIdsAndStatus`

### 5. `NO_SAFE_BASELINE_GROUP_BY`

Initial recommendation: `freeze/defer-candidate`

Why:

- group-by safe baselines look closer to a dedicated aggregate capability than a small recovery rule
- current aggregate families are already precise; forcing this into “safe baseline” may blur product boundaries

Sentinel:

- `demo.test.complex.staticGroupBy`

## Task 1: Write the Decision Table

**Files:**

- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-09-safe-baseline-decision-table.md`
- Modify if helpful: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-safe-baseline-design-program.md`

Work:

- capture each subtype
- assign `promote / freeze / defer`
- write the reasoning and sentinel evidence

**Success standard:** every current `NO_SAFE_BASELINE_*` subtype has an explicit product disposition.

**Status:** complete

Decision table:

- [2026-04-09-safe-baseline-decision-table.md](/tmp/sqlopt-post-batch7/docs/superpowers/specs/2026-04-09-safe-baseline-decision-table.md)

## Task 2: Reassess the Best Promote Candidate

**Target subtype:**

- `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`

**Files likely involved:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- tests under:
  - `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/`
  - `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/`
  - `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/`

Work:

- determine whether a narrow choose-guarded filter safe baseline can be defined
- if yes, implement the smallest viable path
- if no, formally downgrade this subtype from promote-candidate to freeze/defer

**Outcome:** no viable narrow safe baseline exists in the current patch model; this subtype is now `DEFER`.

**Evidence:**

- sentinel `demo.user.advanced.findUsersByKeyword` passes semantic validation but still reports:
  - `capabilityTier = REVIEW_REQUIRED`
  - `baselineFamily = None`
  - blocker `DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE`
- `SAFE_BASELINE_RECOVERY` currently admits only static families, so this would require a new choose-aware template-preserving capability, not a small recovery extension

**Success standard:** either one safe-baseline path is proven viable, or the subtype is conclusively frozen with evidence.

**Status:** complete

## Task 3: Freeze the Unsafe Safe-Baseline Subtypes

**Targets:**

- `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
- `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `NO_SAFE_BASELINE_GROUP_BY`

**Files likely involved:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/convergence_registry.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-09-safe-baseline-decision-table.md`

Work:

- decide whether these are explicit non-goals or deferred capability lanes
- update registry/docs so they stop reading like “missing implementation detail”

**Status:** complete

Registry/source of truth:

- [convergence_registry.py](/tmp/sqlopt-post-batch7/python/sqlopt/stages/convergence_registry.py)

**Success standard:** these subtypes are no longer ambiguous backlog items.

## Task 4: Reassess `FOREACH_INCLUDE_PREDICATE`

**Target:**

- `NO_SAFE_BASELINE_FOREACH_INCLUDE_PREDICATE`

Work:

- decide whether this should stay in the safe-baseline program
- or move into a separate future capability program focused on template-aware collection predicates

**Status:** complete

**Success standard:** it is placed on the correct roadmap, not left in a limbo bucket.

## Task 5: Fresh Replay Review

**Files:**

- Modify or create:
  - `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-safe-baseline-design-program.md`
  - `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-safe-baseline-program-review.md`

Work:

- rerun the affected sentinel scopes in replay
- verify no ready regressions
- verify frozen subtypes are still blocked for the expected reasons
- record whether the promoted subtype actually improved anything

**Success standard:** the safe-baseline stage ends with a clear verdict, not another open-ended queue of subtypes.

**Status:** complete

Review:

- [2026-04-09-safe-baseline-program-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-safe-baseline-program-review.md)

## Non-Goals

This program must not:

- reopen generic family-by-family exploration
- auto-open `batch14`
- invent broad semantic relaxations for pagination, `EXISTS`, or join rewrites
- create patch families just to “make progress numbers move”
- blur `VALIDATE_SEMANTIC_ERROR` and `SEMANTIC_PREDICATE_CHANGED` into safe-baseline work

## Exit Criteria

This program is complete when:

1. every current `NO_SAFE_BASELINE_*` subtype has a product disposition
2. at least one subtype is either proven promotable or conclusively frozen
3. fresh replay review confirms no regression
4. the next stage can be named by capability, not by another exploratory batch number

## Final Result

Completed.

Outcome:

- no subtype was promoted in the current patch model
- frozen/deferred subtypes are now explicit in both docs and registry
- fresh replay review confirmed `ready_regressions = 0` and `blocked_boundary_regressions = 0`
- the next stage should be a capability program, not `batch14`
