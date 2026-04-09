# Template-Preserving Dynamic Capability Review

## Verdict

The foundation work was worth doing.

The promotion was not.

This stage should end with:

- `FOUNDATION = yes`
- `NARROW_PROMOTION = no`
- `CHOOSE_V2 = defer`
- `COLLECTION_V2 = defer`

## What This Stage Actually Added

### 1. Dynamic foundation truth is now explicit

The project now has a dedicated dynamic foundation inventory:

- primary prototype sentinel:
  - `demo.user.advanced.findUsersByKeyword`
- deferred second-wave sentinel:
  - `demo.order.harness.findOrdersByUserIdsAndStatus`
- explicit choose / collection guardrails

### 2. Review-only dynamic patch surfaces are now formalized

This stage established a narrow internal contract for dynamic sub-statement surfaces:

- `CHOOSE_BRANCH_BODY`
- `COLLECTION_PREDICATE_BODY`

The important change is not new patchability.

The important change is that the pipeline can now carry these surfaces honestly without pretending they are generic `WHERE_CLAUSE` or statement-body edits.

### 3. Patch-stage guardrails were tightened

This stage closed a real bug:

- `CHOOSE_BRANCH_BODY` review-only shapes could still fall through into template patch construction

Patch-stage behavior is now explicit:

- choose review-only -> `PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED`
- collection review-only -> `PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED`

No patch files are generated for either lane.

## What The Replay Evidence Still Says

Fresh replay runs:

- `generalization-batch9` -> `run_9c261f3eb3eb`
- `generalization-batch13` -> `run_16a5ae61564a`

Observed truth:

- `demo.user.advanced.findUsersByKeyword`
  - `MANUAL_REVIEW / NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
- `demo.order.harness.findOrdersByUserIdsAndStatus`
  - `MANUAL_REVIEW / NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`
- guardrails remained blocked:
  - `chooseBasic`
  - `chooseMultipleWhen`
  - `chooseWithLimit`
  - `selectWithFragmentChoose`
  - `findShipmentsByOrderIds`
  - `multiFragmentLevel1`
  - `findShipments`
  - `listOrdersWithUsersPaged`
  - `includeNested`
  - `findUsers`

No statement became `AUTO_PATCHABLE`.

No guardrail widened accidentally.

## Why Promotion Still Fails

The missing piece is still structural, not classificatory.

The system now has review-only surfaces for choose and collection, but it still lacks:

- a surface-specific materialization mode
- a surface-specific replay contract
- a surface-specific rewrite op
- a surface-specific patch family

Current patch materialization still only supports:

- `replace_statement_body`
- `replace_fragment_body`

That means the system can identify:

- where a dynamic branch-local edit would conceptually live
- where a collection predicate edit would conceptually live

But it still cannot apply either one without collapsing back to statement-level or fragment-level editing.

That is exactly the boundary this stage needed to prove.

## Final Recommendation

Do not keep pushing this stage in-place.

Treat this result as a successful capability assessment:

- the foundation contract is now better
- the patch-stage bug is closed
- the remaining gap is a larger future product investment

If product scope later wants to reopen dynamic support, it should start from this foundation and fund a new stage around:

- surface-specific rewrite ops
- surface-specific replay contracts
- surface-specific patch families

Until then:

- `CHOOSE_BRANCH_BODY` remains deferred
- `COLLECTION_PREDICATE_BODY` remains deferred
