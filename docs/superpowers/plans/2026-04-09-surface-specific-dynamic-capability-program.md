# Surface-Specific Dynamic Capability Program

## Goal

Turn the current dynamic review-only foundation into a concrete capability investment decision.

This program does **not** assume that `CHOOSE_BRANCH_BODY` or `COLLECTION_PREDICATE_BODY` will become patchable.

It exists to answer a narrower question:

> Is the project willing to fund the missing dynamic substrate needed to support sub-statement template-preserving rewrites?

That substrate is now known to require all of:

- a surface-specific rewrite op
- a surface-specific replay contract
- a surface-specific patch family
- a surface-specific materialization mode

## Why This Program Exists

The previous stage proved two things:

1. the current review-only foundation is useful
2. promotion fails for structural reasons, not classification reasons

The project now has honest review-only surfaces:

- `CHOOSE_BRANCH_BODY`
- `COLLECTION_PREDICATE_BODY`

But patch materialization still only supports:

- `replace_statement_body`
- `replace_fragment_body`

So the next useful step is no longer another batch or another boundary cleanup.

The next useful step is to design and prototype the missing substrate directly.

## Scope

### In Scope

- dynamic sub-statement patch surface contract
- rewrite-op shape for branch-local and collection-local edits
- replay contract for those ops
- patch-family modeling for those ops
- review-only plumbing upgrades needed to carry those contracts honestly
- one narrow prototype lane, only after the substrate exists

### Out Of Scope

- broad `choose` support
- broad `foreach/include` support
- new exploratory generalization batches
- weakening semantic or validation guardrails
- flattening dynamic templates into statement-level SQL patches

## Primary Prototype Sequence

The program should proceed in this order:

1. define surface-specific rewrite-op contracts
2. define replay evidence contract for those ops
3. define surface-specific patch family contract
4. add materialization plumbing in review-only mode
5. only then prototype one narrow promoted lane

The prototype order should remain:

1. `CHOOSE_BRANCH_BODY`
2. `COLLECTION_PREDICATE_BODY`

Collection should stay second-wave because its shape envelope is broader.

## Sentinels

### Primary Prototype Sentinel

- `demo.user.advanced.findUsersByKeyword`

### Second-Wave Sentinel

- `demo.order.harness.findOrdersByUserIdsAndStatus`

### Guardrails

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentLevel1`
- `demo.shipment.harness.findShipments`
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.test.complex.includeNested`
- `demo.user.findUsers`

## Task 1. Freeze The Investment Decision Table

Write a decision table that spells out:

- which dynamic surfaces exist
- which are review-only
- what promotion would require
- which sentinel owns each surface
- which guardrails must remain blocked

Expected outputs:

- a new spec under `docs/superpowers/specs/`
- matching inventory constants if the current naming is insufficient

## Task 2. Define Surface-Specific Rewrite Ops

Design candidate internal ops such as:

- `replace_choose_branch_body`
- `replace_collection_predicate_body`

This is design work first.

The task is successful only if the ops can be specified without:

- statement-level replacement fallback
- fragment-level replacement fallback
- ambiguity about target anchors

If that cannot be done cleanly, stop and mark the program as blocked before implementation.

Likely files:

- `python/sqlopt/platforms/sql/rewrite_facts_models.py`
- `python/sqlopt/platforms/sql/rewrite_facts.py`
- `python/sqlopt/stages/proposal_models.py`

## Task 3. Define Replay Contract

Specify what replay must prove for a surface-specific op:

- target anchor identity
- branch-local or collection-local envelope identity
- preserved sibling template structure
- preserved guard expressions outside the target surface

Success means the replay contract is strong enough to reject accidental widening.

Likely files:

- `python/sqlopt/stages/validation_models.py`
- `python/sqlopt/stages/validate.py`
- `python/sqlopt/stages/validate_convergence.py`
- docs/specs for replay semantics

## Task 4. Define Patch Family And Materialization Contract

Design explicit dynamic patch families for surface-specific edits.

Examples:

- choose-branch-local cleanup family
- collection-predicate-local cleanup family

This task must also define:

- how materialization locates the exact template surface
- how patch generation refuses to widen to statement/fragment replacement

Likely files:

- `python/sqlopt/patch_families/models.py`
- `python/sqlopt/stages/patch_decision/*`
- `python/sqlopt/patching_templates.py`
- `python/sqlopt/template_materializer.py`

## Task 5. Review-Only Plumbing First

Before any promotion attempt:

- thread the new op and replay contract through artifacts
- keep the final decision review-only
- prove no guardrails regress

This is a red/green step for the substrate only.

Success criteria:

- new contracts appear in rewrite facts / validate artifacts
- patch generation still stops with explicit manual-review reasons
- no patch files are emitted

## Task 6. Narrow Prototype: Choose Only

Only after Tasks 1 through 5 succeed:

- try a single narrow prototype for `demo.user.advanced.findUsersByKeyword`

Strict constraints:

- top-level `<where><choose>`
- one branch-local target
- no include / order / limit / group / join / union widening
- no collection predicate mixing

Success criteria:

- either one honest `AUTO_PATCHABLE` promotion for the primary sentinel
- or a precise proof that even with the new substrate, the lane should remain deferred

If this step fails, do **not** continue to collection.

## Task 7. Reassess Collection Second-Wave

Only if Task 6 succeeds cleanly:

- reassess `demo.order.harness.findOrdersByUserIdsAndStatus`

Do not implement collection promotion by analogy.

Collection reopens only if the choose prototype shows the new substrate is sound.

## Verification Strategy

Use the fast cadence already established:

- unit tests for new contracts and guardrails
- targeted replay refresh for `generalization-batch9` and `generalization-batch13`
- no full-suite rerun until the end of a coherent delivery slice

Required replay checks:

- primary sentinel truth does not drift accidentally
- guardrails remain blocked
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`

## Stop Conditions

Stop the program early if any of the following becomes true:

- the rewrite op cannot be specified without statement-level fallback
- the replay contract cannot prove surface-local identity
- the patch family must reuse statement/fragment replacement semantics
- guardrails start passing only because the target surface became ambiguous

These are not "implementation details."

They mean the current product should not fund this capability yet.

## Deliverables

At program end, one of these must be true:

1. the project has a credible surface-specific dynamic substrate and one narrow choose prototype
2. the project has a documented no-go verdict with explicit missing prerequisites

Both outcomes are acceptable.

The unacceptable outcome is drifting halfway into a pseudo-support lane that still relies on statement-level fallback.
