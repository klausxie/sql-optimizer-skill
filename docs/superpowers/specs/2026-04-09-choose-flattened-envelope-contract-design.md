# Choose Flattened Envelope Contract Design

## Purpose

The project now has a real narrow choose-local family:

- `DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP`

That family is valid for statements whose `original_sql` can be localized to one concrete `<choose>` branch.

The real sample-project sentinel:

- `demo.user.advanced.findUsersByKeyword`

still cannot use that family, because the current scan/original-sql contract gives downstream stages a flattened statement-level SQL:

- `WHERE (name ILIKE ... OR status = ... OR status != 'DELETED')`

That SQL proves the statement result, but it does **not** preserve which `<choose>` branch was rendered.

This design defines the next capability investment:

> add a branch-local choose render contract so supported choose statements can be reasoned about at the same surface level that patching and replay already use.

## Problem Statement

Current state:

- `rewrite_facts` can recognize structural choose support
- `dynamic_surface_locator` can localize a branch when the original SQL already matches one branch body
- `template_materializer`, `patching_templates`, and `patch_replay` can execute a narrow choose-local patch

But for the real sentinel:

- scan used to produce only a flattened OR-based `sql`
- downstream stages now also carry `dynamicRenderIdentity`
- `findUsersByKeyword` still remains
  - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

So the real gap is no longer patch substrate.

It is the absence of a **branch-local dynamic render identity** in the scan/original-sql contract.

## Design Goal

Add the smallest contract extension that lets downstream stages answer this question honestly:

> For one supported `<where><choose>` statement, which branch was actually rendered when the current `sql` was produced?

This is not a broad dynamic rendering redesign.

It is a narrow contract addition for top-level choose envelopes only.

## Non-Goals

This design does not:

- support nested choose
- support choose under join / union / group / having / limit
- support fragment choose chains
- support collection / foreach local surfaces
- replace statement-level `sql`
- promote `findUsersByKeyword` by itself

The current truth is narrower than the original problem statement:

- the missing branch identity contract has now been added
- optimize and replay now see that branch-local context
- but the provider still emits only speculative or low-value candidates

So the next remaining gap is candidate quality, not scan identity.

## Supported Scope

The contract only applies when all of the following are true:

- exactly one top-level `<choose>` exists
- it is directly under `<where>`
- branch bodies are predicate-only
- no `<include>` inside the choose body
- no outer unsupported clauses around the choose envelope

This is the same narrow shape already used by `CHOOSE_BRANCH_BODY`.

## Recommended Approach

### Approach A: Infer branch-local identity from flattened SQL every time

Pros:

- no scan contract change

Cons:

- brittle
- ambiguous for OR-merged predicates
- duplicates guesswork across optimize / validate / replay

Recommendation:

- reject

### Approach B: Add branch-local render evidence to scan/sql-unit

Pros:

- explicit
- reusable by optimize, validate, patch selection, and replay
- aligns runtime truth with local patch surface

Cons:

- requires a scan contract extension
- requires fresh fixture / artifact updates

Recommendation:

- **recommended**

### Approach C: Replace statement-level `sql` with branch-local rendered SQL

Pros:

- simplifies narrow choose lane

Cons:

- breaks the current meaning of `sql`
- dangerous for non-choose dynamic statements
- too invasive

Recommendation:

- reject

## Proposed Contract

Keep existing statement-level `sql` unchanged.

Add a new optional structure on the scan/sql-unit side:

```json
{
  "dynamicRenderIdentity": {
    "surfaceType": "CHOOSE_BRANCH_BODY",
    "renderMode": "CHOOSE_BRANCH_RENDERED",
    "chooseOrdinal": 0,
    "branchOrdinal": 0,
    "branchKind": "WHEN",
    "branchTestFingerprint": "keyword != null and keyword != ''",
    "renderedBranchSql": "name ILIKE #{keywordPattern}",
    "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
    "requiredSiblingShape": {
      "branchCount": 3
    }
  }
}
```

Key rule:

- `sql` remains the statement-level rendered SQL
- `dynamicRenderIdentity` carries the local branch-level proof

## Data Flow

### Scan

When a statement matches the narrow choose shape, scan records:

- which branch was rendered
- the local rendered branch SQL
- stable branch identity metadata

### Optimize / Candidate Recovery

Use `dynamicRenderIdentity` instead of guessing from flattened `sql`.

This allows:

- `safe_baseline_recovery_family(...)`
- low-value choose classification
- future choose-local recovery

to distinguish:

- localizable branch cleanup
- from flattened OR-only statement rewrites

### Rewrite Facts / Patch Selection

`rewrite_facts` may promote choose-local only when:

- structural shape is supported
- `dynamicRenderIdentity.surfaceType == CHOOSE_BRANCH_BODY`
- local branch SQL aligns with the rewritten SQL

### Replay

Replay keeps using local surface anchors, but now the original statement also carries a truthful local render identity instead of requiring inference from flattened SQL.

## Guardrails

The following must remain blocked under this contract work:

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`

## Success Criteria

The contract work is successful when:

1. scan/sql-unit can carry branch-local choose identity for supported shapes
2. synthetic choose-local tests still pass
3. unsupported choose guardrails stay blocked
4. the real sentinel can be evaluated against a truthful local branch contract

This design still does **not** require immediate auto-promotion.

It only requires that the system stop guessing from flattened OR SQL.

## Expected Outcomes

Best case:

- `findUsersByKeyword` becomes eligible for a future narrow choose-local recovery/promotion

Acceptable case:

- the system proves the real sentinel still should remain deferred, but now for a precise branch-local reason rather than because flattened SQL erased the branch boundary

Either result is valuable.
