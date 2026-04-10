# Choose Flattened Envelope Contract Program

## Goal

Extend the scan/original-sql contract so supported top-level `<where><choose>` statements can carry a truthful branch-local render identity alongside the existing flattened statement SQL.

The primary target remains:

- `demo.user.advanced.findUsersByKeyword`

## Recommendation

Do not change patch substrate again.

Do not try more choose recovery heuristics on flattened OR SQL.

Instead:

1. add branch-local choose render identity at scan/sql-unit level
2. thread that contract through optimize and rewrite facts
3. reassess `findUsersByKeyword` only after the new identity is available

## Scope

In scope:

- top-level `<where><choose>` only
- one choose per statement
- branch-local render identity
- optimize/rewrite-facts consumption of that identity

Out of scope:

- nested choose
- collection / foreach
- multi-fragment include
- generic dynamic semantic redesign

## Primary Sentinel

- `demo.user.advanced.findUsersByKeyword`

## Guardrails

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`

## Task 1: Freeze Current Flattened-Choose Truth

Capture and lock:

- the real `findUsersByKeyword` flattened `sql`
- the branch-local template shape
- the current review result:
  - `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

Add focused tests proving:

- synthetic choose-local shapes still promote
- flattened real sentinel still does not

## Task 2: Define Scan-Level `dynamicRenderIdentity`

Add a narrow contract for supported choose statements:

- `surfaceType`
- `renderMode`
- `chooseOrdinal`
- `branchOrdinal`
- `branchKind`
- `branchTestFingerprint`
- `renderedBranchSql`
- `requiredEnvelopeShape`
- `requiredSiblingShape`

This task is contract-first:

- model
- artifact shape
- fixture truth

## Task 3: Populate Choose Branch Identity In Scan Output

Teach scan/template rendering to emit `dynamicRenderIdentity` for supported choose shapes only.

Rules:

- `sql` must remain unchanged
- no identity should be emitted for unsupported choose shapes
- no fallback guesses for ambiguous choose envelopes

## Task 4: Consume The Contract In Optimize / Rewrite Facts

Use `dynamicRenderIdentity` to:

- decide whether choose-local safe baseline is truly available
- stop inferring locality from flattened OR SQL
- keep unsupported or ambiguous choose statements blocked

This task should touch:

- `safe_baseline_recovery_family(...)`
- choose low-value / no-safe-baseline classification
- `rewrite_facts` choose-local promotion checks

## Task 5: Reassess The Primary Sentinel

Fresh replay:

- `generalization-batch9`
- `generalization-batch13`

Possible outcomes:

### Outcome A

`findUsersByKeyword` becomes a valid member of:

- `DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP`

Then write a follow-up narrow promotion task.

### Outcome B

`findUsersByKeyword` still remains deferred, but now with branch-local truth proving why.

That is also acceptable and should close the lane honestly.

## Exit Rule

Stop this program after one of these is proven:

1. the primary sentinel can now be reasoned about branch-locally
2. even with branch-local render identity, the primary sentinel should remain deferred

Do not expand into broader dynamic support during this program.
