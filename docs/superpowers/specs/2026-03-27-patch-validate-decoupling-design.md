# Patch Validate Decoupling Design

## Status

Draft validated through brainstorming on 2026-03-27.

## 1. Goal

Strongly decouple `validate` from `patch_generate` so that patch planning is owned by the patch stage instead of being precomputed upstream.

This phase must:

1. make `validate` responsible only for candidate acceptance and rewrite gates
2. make `patch_generate` independently derive patch family, strategy, materialization, template operations, and proof plan
3. remove patch-specific planning fields from the acceptance contract
4. keep the patch proof path compatible with the verification-closure work already completed

This phase must not:

1. expand patch family coverage
2. redesign report output
3. preserve backward compatibility for old acceptance artifacts
4. avoid repeated analysis when repetition is the cleanest way to separate stage ownership

## 2. Core Position

The current patch flow is over-coupled because `validate` does two jobs:

1. decide whether a rewritten SQL candidate is acceptable
2. partially execute patch planning on behalf of `patch_generate`

That boundary is wrong.

`validate` should answer:

`Is this rewritten SQL safe and worthwhile enough to hand to the patch stage?`

`patch_generate` should answer:

`Given this validated rewritten SQL and the original mapper template, what patch should be built and how is it proven correct?`

Any design where `validate` freezes patch strategy, materialization, template operations, or replay proof is still leaking patch-stage responsibility upstream.

## 3. Why This Refactor Exists

Today, the acceptance contract carries patch-owned data such as:

1. `patchTarget`
2. `selectedPatchStrategy`
3. `patchability`
4. `rewriteMaterialization`
5. `templateRewriteOps`
6. `patchStrategyCandidates`
7. `dynamicTemplate`
8. `deliveryReadiness`

This creates three problems:

1. `validate` must know too much about mapper patch internals
2. `patch_generate` consumes a pre-shaped patch plan instead of owning its own pipeline
3. any patch-system refactor keeps dragging the acceptance schema with it

The refactor exists to turn patch generation back into a real subsystem with a clear entry contract and internal ownership.

## 4. Recommended Approach

Use **strong decoupling**.

This is preferred over:

1. partial decoupling where acceptance still carries most patch planning fields
2. compatibility-first designs that keep reading old `patchTarget` artifacts indefinitely

Strong decoupling means:

1. acceptance artifacts become thinner and patch-agnostic
2. `patch_generate` repeats any template analysis it needs
3. patch planning becomes an internal patch-stage concern
4. any persisted patch plan is written by the patch stage, not by validation

The team explicitly accepts duplicated analysis if that is the price of a cleaner stage boundary.

## 5. Acceptance Contract Boundary

### 5.1 Acceptance Must Keep

The acceptance artifact should remain focused on validated rewrite facts:

1. `sqlKey`
2. `status`
3. `selectedCandidateId`
4. `rewrittenSql`
5. `semanticEquivalence`
6. `equivalence`
7. `perfComparison`
8. `securityChecks`
9. `feedback`, `warnings`, `riskFlags`
10. other validate-owned rationale and gating fields

These fields describe whether the rewritten SQL passed acceptance and why.

### 5.2 Acceptance Must Drop

The acceptance artifact should stop persisting patch-stage planning fields:

1. `patchTarget`
2. `selectedPatchStrategy`
3. `patchability`
4. `rewriteMaterialization`
5. `templateRewriteOps`
6. `patchStrategyCandidates`
7. `dynamicTemplate`
8. `deliveryReadiness`

If a field exists only to help patch generation decide how to edit XML, it belongs to the patch stage.

### 5.3 Acceptance Does Not Preserve Old Artifact Compatibility

This refactor targets new runs only.

New code does not need a backward-compatibility layer for historical acceptance artifacts that still contain patch-planning payloads.

## 6. Patch Generate Ownership

After decoupling, `patch_generate` consumes:

1. `sql_unit`
2. acceptance status and gates
3. `rewrittenSql`
4. selected candidate identity

From that input, `patch_generate` must derive all patch-owned decisions itself:

1. patch family
2. patchability assessment
3. strategy candidates and selected strategy
4. materialization mode
5. template rewrite operations
6. replay contract
7. artifact proof inputs

This means `patch_generate` becomes the single owner of:

1. patch planning
2. patch artifact construction
3. patch proof construction
4. patch-result degradation when proof does not close

## 7. Patch Pipeline Shape

`patch_generate` should be reorganized into a linear internal pipeline:

`acceptance gates -> select -> build -> prove -> finalize`

### 7.1 `select`

Responsibilities:

1. enforce acceptance gates before any patch work starts
2. recompute rewrite and template analysis needed for patch planning
3. derive patch family and patchability
4. rank strategy candidates and choose one

Outputs:

1. a patch-selection context owned by the patch stage

### 7.2 `build`

Responsibilities:

1. derive materialization mode from the selected strategy
2. generate template rewrite operations
3. produce the unified diff artifact

Outputs:

1. a patch-build result containing artifact text plus patch-plan metadata

### 7.3 `prove`

Responsibilities:

1. derive the replay contract from the build result
2. materialize the artifact against source XML
3. replay rendered SQL from the patched XML
4. compute syntax evidence under the replay contract

Outputs:

1. proof evidence and a pass/fail verdict for the generated patch

### 7.4 `finalize`

Responsibilities:

1. assemble the final `patch_result`
2. persist patch-owned metadata needed by downstream stages
3. degrade to non-applicable when build or proof does not close

Outputs:

1. the only persisted patch-plan payload that downstream consumers should read

## 8. Module Boundaries

### 8.1 Keep and Narrow

These modules should stay, but with tighter responsibilities:

1. `python/sqlopt/stages/patch_generate.py`
   Orchestrator only.
2. `python/sqlopt/verification/patch_artifact.py`
   Artifact materialization only.
3. `python/sqlopt/verification/patch_replay.py`
   Replay comparison only.
4. `python/sqlopt/verification/patch_syntax.py`
   Syntax evidence only.
5. `python/sqlopt/stages/patch_finalize.py`
   Final patch-result assembly only.

### 8.2 Move Ownership Out of Validate

Patch-owned logic currently hanging off validation should move behind patch-stage entry points:

1. strategy planning
2. template materialization planning
3. patch family derivation for auto-patch delivery
4. replay-contract construction

The refactor does not require moving every helper file physically at once, but ownership must become patch-stage-owned even if some helper modules are temporarily shared.

### 8.3 Add Internal Patch Modules

Introduce focused patch-stage modules:

1. `python/sqlopt/stages/patch_select.py`
2. `python/sqlopt/stages/patch_build.py`
3. `python/sqlopt/stages/patch_proof.py`

These modules are internal pipeline units, not cross-stage contracts.

## 9. Data Model Direction

### 9.1 Acceptance Result

`ValidationResult` and `contracts/acceptance_result.schema.json` should be reduced to validate-owned fields only.

The acceptance schema should stop defining patch-owned contracts such as `PatchTargetContract` and `PatchReplayContract`.

### 9.2 Patch Result

Any persisted patch-planning payload should move to `patch_result`, because that is the stage that actually owns:

1. selected strategy
2. materialization mode
3. template ops
4. replay contract
5. proof evidence

If a `patchTarget`-like object remains useful, it should be generated inside `patch_generate` and persisted as patch-stage output rather than acceptance-stage output.

## 10. Migration Strategy

Use a two-step migration.

### 10.1 Step 1

Make `patch_generate` capable of computing the full patch plan from thin acceptance input while the old acceptance fields still exist in code.

The purpose of this step is behavioral validation, not compatibility preservation.

### 10.2 Step 2

After the new path is stable:

1. remove patch-owned fields from `ValidationResult`
2. remove patch-owned fields from `acceptance_result.schema.json`
3. delete validation-side assembly code for `patchTarget` and related payloads
4. switch tests and fixtures to the new thin acceptance contract

The transition is complete only when `patch_generate` no longer depends on acceptance patch fields at runtime.

## 11. Risks

### 11.1 Analysis Drift

Repeated analysis between validate and patch stages may diverge.

Mitigation:

1. prefer patch-stage recomputation over hidden sharing
2. add tests that assert patch_generate can rebuild the same patch plan from thin acceptance input

### 11.2 Harness Coupling

Some fixture and harness tests currently expect patch-related fields in acceptance artifacts.

Mitigation:

1. update harness expectations to read patch-owned fields from patch artifacts instead
2. keep validate harness focused on validate semantics only

### 11.3 Report Coupling

Report logic may still read patch fields from acceptance rows.

Mitigation:

1. patch only the minimum report dependencies needed for correctness in this refactor
2. avoid broader report redesign in this phase

## 12. Test Strategy

The refactor is complete only if these layers stay green:

1. acceptance contract tests for the thinner schema
2. patch orchestration tests proving `patch_generate` no longer needs acceptance patch fields
3. fixture harness tests covering validate, patch, and report handoff
4. verification matrix tests from the completed `M1 Verification Closure` work
5. full repository test suite

New targeted regressions should explicitly cover:

1. acceptance rows without `patchTarget`
2. acceptance rows without `selectedPatchStrategy`
3. acceptance rows without `rewriteMaterialization` and `templateRewriteOps`
4. patch-stage recomputation for both statement and fragment paths

## 13. Acceptance Criteria

This refactor is complete only if all of the following are true:

1. `validate` no longer persists patch-planning payloads
2. `patch_generate` derives patch family, strategy, materialization, template ops, and replay proof from thin acceptance input
3. `patch_result` becomes the single persisted source of patch-planning truth
4. the verification-closure behavior remains intact after decoupling
5. new runs pass the full test suite without backward-compatibility shims for old acceptance artifacts
