# Verification Closure Design

## Status

Draft validated through brainstorming on 2026-03-27.

## 1. Goal

Close the remaining correctness gaps in the patch verification path so that `AUTO_PATCH` means the generated patch artifact itself has been proven against the persisted patch contract.

This phase must:

1. Verify real patch artifacts instead of trusting `patchTarget` intent alone.
2. Unify statement and fragment verification semantics.
3. Make syntax evidence contract-driven instead of partially placeholder-driven.
4. Stabilize a regression matrix for the main verification failure modes.

This phase must not:

1. Expand patch family coverage.
2. Rework report or ledger presentation.
3. Introduce external SQL parser dependencies.
4. Redesign apply mode or patch delivery workflow.

## 2. Core Position

The current patch system is only trustworthy if the verification chain answers one question:

`Does the generated patch artifact, when replayed against the source XML, still produce the exact validated target under the required proof policy?`

Anything weaker is not a closed verification system.

The design therefore treats verification as a strict pipeline:

`patch text -> patched XML artifact -> replayed SQL -> syntax evidence -> verification verdict`

No stage in this pipeline should silently fall back to validating only the intended template rewrite if the patch artifact is available.

## 3. Why This Phase Exists

Recent work already tightened several important gaps:

1. patch family specs are now explicit contracts
2. statement artifact replay exists
3. fragment artifact replay now resolves by `fragmentKey`
4. rendered SQL syntax evidence is no longer a pure placeholder
5. `dialectSyntaxCheckRequired` now affects SQL syntax enforcement

What remains is not broad feature work. It is closure work.

The remaining risk is that verification still depends on a few simplified assumptions, especially in the patch artifact materialization layer. That means a patch may be judged by a model of the artifact that is not yet strict enough to be the project's final proof boundary.

## 4. Recommended Approach

Use a **vertical closure** approach.

This is preferred over:

1. matrix-first expansion before the artifact base is stable
2. exhaustive infrastructure work before reconnecting replay and syntax to real runtime flows

The vertical sequence is:

1. stabilize `patch_artifact` as the verification base
2. ensure replay and syntax consume that base consistently
3. lock the main regression matrix around the resulting semantics

This ordering minimizes churn because each higher layer depends on the semantics of the lower layer.

## 5. Scope Boundaries

### 5.1 In Scope

1. patch artifact parsing and materialization
2. target file recognition for artifact replay
3. hunk application semantics required by current patch builders
4. statement and fragment replay convergence
5. syntax evidence behavior under replay contract policy
6. verification-focused regression coverage

### 5.2 Out of Scope

1. new patch families
2. report reason-code phrasing improvements
3. broader SQL parser integration
4. UI or markdown output changes
5. apply-stage redesign

## 6. Architecture Boundaries

### 6.1 `patch_artifact`

File:
`python/sqlopt/verification/patch_artifact.py`

Responsibility:

1. accept patch text plus source XML path
2. validate the artifact target file
3. apply the supported unified diff shape
4. return either patched XML or a precise artifact failure

It must not:

1. compare against target SQL
2. decide replay success
3. decide verification policy

### 6.2 `patch_replay`

File:
`python/sqlopt/verification/patch_replay.py`

Responsibility:

1. render replay output from patched XML
2. compare rendered SQL to persisted target SQL
3. enforce replay-contract invariants such as anchors, includes, placeholders, and dynamic shapes

It must not:

1. implement patch diff parsing
2. invent fallback target SQL

### 6.3 `patch_syntax`

File:
`python/sqlopt/verification/patch_syntax.py`

Responsibility:

1. derive `xmlParseOk`, `renderOk`, and `sqlParseOk`
2. obey replay-contract-driven SQL syntax strength
3. report syntax-specific failures without overriding upstream replay failures

It must not:

1. own artifact application rules
2. choose whether replay drift is acceptable

### 6.4 `patch_generate`

File:
`python/sqlopt/stages/patch_generate.py`

Responsibility:

1. orchestrate artifact materialization, replay, and syntax checks
2. degrade selected patches to non-applicable results when proof does not close

It must not:

1. re-derive proof logic inline
2. split statement and fragment verification into different semantics

## 7. Milestones

### 7.1 `M1.1 Artifact Base`

The artifact layer is complete when:

1. supported patch shape is explicit
2. target file mismatch is detected deterministically
3. malformed unified diff input produces an artifact failure, not silent replay drift
4. XML parse failure is emitted as an artifact-derived failure

Primary focus:

1. target-path strictness
2. supported hunk semantics
3. precise failure classification

### 7.2 `M1.2 Replay/Syntax Convergence`

This milestone is complete when:

1. statement and fragment replay both read from the artifact path
2. syntax evidence is computed against the same artifact-backed replay result
3. `dialectSyntaxCheckRequired` fully controls SQL syntax strictness
4. no remaining mainline path validates only `afterTemplate` when patch text is available

### 7.3 `M1.3 Verification Matrix`

This milestone is complete when the main regression suite covers:

1. statement artifact drift
2. fragment artifact drift
3. artifact target mismatch
4. malformed artifact
5. patched XML parse failure
6. SQL syntax required and failing
7. SQL syntax not required and tolerated

## 8. Non-Goals During Implementation

To keep the phase closed, implementation must reject opportunistic side work:

1. no family onboarding changes
2. no report wording cleanup
3. no new verification UI fields unless required by existing contracts
4. no general-purpose diff engine beyond current project needs

## 9. Acceptance Criteria

`M1 Verification Closure` is considered complete only if all of the following are true:

1. every applicable patch is verified against the actual generated artifact
2. statement and fragment proof paths produce consistent replay semantics
3. syntax evidence is contract-driven rather than placeholder-driven
4. verification failures are attributable to artifact, replay, or syntax layers with stable regression tests
5. full repository test suite remains green

## 10. Preferred Execution Order

1. tighten `patch_artifact` behavior and tests first
2. reconnect any remaining replay and syntax branches to the artifact output
3. fill the verification regression matrix last

This ordering keeps the base semantics stable before expanding the matrix built on top of it.

## Harness Plan

### Proof Obligations

1. verification operates on the real generated patch artifact
2. statement and fragment proof paths share consistent replay semantics
3. syntax evidence is contract-driven rather than placeholder-driven
4. verification failures are attributable to artifact, replay, or syntax layers

### Harness Layers

#### L1 Unit Harness

- Goal: prove patch artifact loading, replay checks, syntax checks, and verification verdict mapping
- Scope: artifact mismatch, replay drift, syntax failures, verdict composition
- Allowed Mocks: synthetic patch and proof payloads are acceptable
- Artifacts Checked: in-memory verification records and patch proof payloads
- Budget: fast PR-safe runtime

#### L2 Fixture / Contract Harness

- Goal: prove verification ledger and summary semantics align with patch and report artifacts
- Scope: fixture patch verification outcomes, ledger fields, report summary expectations
- Allowed Mocks: synthetic validate evidence is acceptable when the goal is verification contract proof
- Artifacts Checked: verification ledger, verification summary, patch artifacts, report outputs
- Budget: moderate PR-safe runtime

#### L3 Scoped Workflow Harness

- Goal: prove one selected real workflow slice produces correct verification artifacts
- Scope: one selected SQL key or mapper slice
- Allowed Mocks: infrastructure-availability patches only
- Artifacts Checked: selected real run verification and patch outputs
- Budget: targeted workflow runtime

#### L4 Full Workflow Harness

- Goal: prove verification closure remains stable across the broader fixture project
- Scope: full verification and report regression
- Allowed Mocks: only workflow-stability patches that preserve patch semantics
- Artifacts Checked: full run verification summaries and related report outputs
- Budget: separately governed broader regression lane

### Shared Classification Logic

1. verification status mapping
2. reason-code attribution
3. artifact, replay, and syntax layer failure classification

### Artifacts And Diagnostics

1. `pipeline/verification/ledger.jsonl`
2. `pipeline/verification/summary.json`
3. `pipeline/patch_generate/patch.results.jsonl`
4. `overview/report.json`

### Execution Budget

1. `L1` and `L2` are expected for verification-path changes
2. `L3` should prove at least one real verification workflow slice
3. `L4` remains the broader governance layer

### Regression Ownership

1. patch verification logic
2. verification ledger or summary contract changes
3. report readers that consume verification outcomes
