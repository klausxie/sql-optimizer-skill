# Patch Applicability Closure Design

## Status

Draft validated through brainstorming on 2026-03-27.

## 1. Goal

Close the next patch phase by making patch delivery more reliable across statement, fragment, and template artifacts.

This phase must:

1. unify delivery semantics across statement, fragment, and template patch artifacts
2. define a single notion of `apply-ready` for all artifact kinds
3. distinguish build failure, applicability failure, and proof failure consistently
4. make artifact-kind differences matter only during build, not during delivery verdicts

This phase must not:

1. expand patch family coverage
2. redesign report presentation semantics
3. re-open validate/patch planning boundaries
4. turn `patch_generate` back into a mixed orchestration and policy file

## 2. Why This Phase Exists

The previous phases solved architecture and proof integrity:

1. patch planning moved fully into the patch stage
2. proof was bound to real patch artifacts instead of validate-era intent
3. public patch outputs were reduced to thinner, more explicit delivery-facing data

That work made the subsystem clearer, but not yet fully delivery-oriented.

The remaining gap is that statement, fragment, and template artifacts still risk being understood through slightly different notions of success:

1. some outcomes feel proof-driven
2. some outcomes feel apply-check-driven
3. some failures are classified more by artifact-specific mechanics than by delivery stage

This phase exists to remove that inconsistency.

## 3. Core Position

All patch artifacts should go through the same delivery lifecycle:

`build -> applicability -> proof -> finalize`

Artifact kind may affect how a patch is built, but it must not affect the meaning of delivery verdicts.

In particular:

1. every patch artifact must first exist as a materialized artifact
2. every patch artifact must pass the same class of apply-readiness gate
3. every patch artifact must separately satisfy proof requirements
4. `apply-ready` must mean the same thing regardless of artifact kind

## 4. Recommended Approach

Use **delivery-semantics-first unification**.

This is preferred over:

1. starting with more preflight checks while artifact semantics stay mixed
2. starting by normalizing patch file shape before the lifecycle is defined
3. adding reliability checks directly into `patch_generate.py` without a distinct delivery model

Delivery-semantics-first unification means:

1. define the lifecycle first
2. hang readiness checks on that lifecycle
3. only then tighten artifact-shape consistency where it improves delivery reliability

## 5. Delivery Lifecycle

Every patch artifact should be assessed in three explicit stages.

### 5.1 Materialized

`materialized` means:

1. patch text exists
2. target file identity is known
3. target kind is known
4. target-specific addressing data is known well enough for downstream applicability checks

This stage answers:

`Did the patch stage produce a concrete artifact aimed at a concrete target?`

### 5.2 Applicability Checked

`applicability_checked` means:

1. the artifact passed unified apply-readiness checks
2. the target file matches the artifact target assumptions
3. the artifact shape is internally consistent enough to attempt delivery

This stage answers:

`Can this artifact be responsibly treated as deliverable to the current workspace state?`

### 5.3 Proof Verified

`proof_verified` means:

1. the artifact re-materializes against the intended XML
2. replay matches the expected rendered SQL contract
3. syntax evidence satisfies the proof contract

This stage answers:

`Assuming this artifact is applied, does it still prove the intended change?`

## 6. Apply-Ready Definition

An artifact is `apply-ready` only if:

1. it is materialized
2. it passes applicability checks
3. it passes proof verification

This phase rejects weaker interpretations such as:

1. `git apply --check` passed, so it is ready
2. replay matched, so it is ready
3. artifact exists, so it is ready pending manual interpretation

Those conditions can each be necessary, but none of them are sufficient alone.

## 7. Failure Taxonomy

Delivery failures should be normalized into three classes.

### 7.1 Build Failure

`BUILD_FAILURE` means the stage never produced a valid artifact for delivery assessment.

Examples:

1. missing target locator
2. missing template materialization
3. missing required template ops
4. unresolved fragment target

### 7.2 Applicability Failure

`APPLICABILITY_FAILURE` means the artifact exists, but cannot yet be treated as safely deliverable.

Examples:

1. target-file mismatch
2. invalid or non-replayable hunk structure
3. apply-check failure
4. artifact-target addressing mismatch

### 7.3 Proof Failure

`PROOF_FAILURE` means the artifact is materially present, but does not prove the intended change.

Examples:

1. replay drift
2. XML parse failure after artifact application
3. rendered SQL mismatch
4. required syntax evidence failure

## 8. Artifact-Kind Rule

Statement, fragment, and template patches may continue to differ in build mechanics.

They must not differ in:

1. delivery lifecycle stages
2. readiness terminology
3. failure-class meanings
4. final applicability semantics

The acceptable difference is:

`artifact kind changes how build computes the artifact, not how delivery quality is judged`

## 9. Module Boundaries

### 9.1 Build Layer

`python/sqlopt/stages/patch_build.py`

Responsibilities:

1. compute artifact kind
2. compute target identity
3. produce patch text and target metadata

It should not decide final delivery readiness.

### 9.2 Applicability Layer

This phase should introduce or consolidate a delivery-focused applicability module, for example:

`python/sqlopt/stages/patch_applicability.py`

Responsibilities:

1. run unified apply-readiness checks
2. classify applicability failures
3. return a patch-owned applicability verdict independent of proof

It should not do replay or syntax proof work.

### 9.3 Proof Layer

`python/sqlopt/stages/patch_proof.py`

Responsibilities:

1. build proof-only internal target state
2. run artifact materialization, replay, and syntax verification
3. classify proof failures

It should not act as the only delivery gate.

### 9.4 Orchestration Layer

`python/sqlopt/stages/patch_generate.py`

Responsibilities:

1. run `build -> applicability -> proof -> finalize`
2. combine applicability and proof verdicts into final patch outcomes
3. avoid mixing artifact-kind-specific policy into top-level flow

## 10. External Patch Result Boundary

This phase should preserve the thin public result shape.

Public patch outputs may expose:

1. patch files
2. delivery-facing reason codes
3. replay and syntax verdict summaries
4. thin artifact identity that is useful externally, such as `patchFamily`

Public patch outputs should still not expose:

1. internal proof target payloads
2. template op lists used only internally
3. replay-contract internals that only patch-stage helpers need

## 11. Testing Strategy

This phase should be validated through a delivery matrix rather than only isolated helper tests.

Minimum matrix:

1. statement artifact
   build success + applicability success + proof success
   build success + applicability failure
   build success + applicability success + proof failure
2. fragment artifact
   build success + applicability success + proof success
   build success + applicability failure
   build success + applicability success + proof failure
3. template artifact
   build success + applicability success + proof success
   build success + applicability failure
   build success + applicability success + proof failure

The key test question is:

`Does this artifact kind land in the correct delivery stage and failure class?`

not:

`Does this artifact kind happen to emit a particular legacy field?`

## 12. Completion Criteria

This phase is complete only when all of the following are true:

1. statement, fragment, and template artifacts all pass through the same delivery lifecycle
2. `apply-ready` has one consistent meaning across artifact kinds
3. failure outcomes are normalized into build, applicability, or proof classes
4. patch applicability decisions no longer depend on artifact-kind-specific hidden semantics
5. thin public patch results remain intact while still exposing necessary delivery-facing identity
6. full regression remains green
