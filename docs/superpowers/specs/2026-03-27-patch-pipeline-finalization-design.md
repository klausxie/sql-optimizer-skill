# Patch Pipeline Finalization Design

## Status

Draft validated through brainstorming on 2026-03-27.

## 1. Goal

Finalize the patch subsystem so it behaves as a single patch-owned pipeline instead of a mixed system with residual legacy compatibility paths.

This phase must:

1. remove patch-side legacy fallback that still reads validate-owned or historical patch-planning payloads
2. reduce `patch_result` to a thin external artifact centered on deliverable outcomes
3. demote `patchTarget` from a quasi-public contract to an internal patch-stage proof model
4. make downstream consumers rely on thin patch outputs plus verification artifacts instead of internal planning payloads

This phase must not:

1. expand patch family coverage
2. redesign report presentation semantics beyond consumer rewiring
3. reintroduce compatibility layers for historical acceptance artifacts
4. keep public escape hatches for internal patch planning details

## 2. Why This Phase Exists

The previous decoupling phase moved the main planning responsibility into `patch_generate`, but the subsystem still feels mixed because three kinds of legacy behavior remain:

1. some patch-stage modules still carry fallback logic for old acceptance-era patch fields
2. `patchTarget` still behaves like a half-public contract instead of a private proof model
3. downstream code still sometimes treats patch planning internals as externally consumable data

This leaves the architecture in an in-between state:

`validate` is no longer supposed to own patch planning, but parts of patch execution and reporting still act as if those old boundaries might come back.

That ambiguity is the next thing to remove.

## 3. Core Position

The patch system should now be treated as its own bounded pipeline:

`thin acceptance -> select -> build -> prove -> finalize -> thin patch_result`

There should be no public or semi-public contract in the middle of this pipeline.

In particular:

1. `patchTarget` is not a stage handoff contract
2. `rewriteMaterialization` is not an external patch artifact
3. `templateRewriteOps` are not downstream-facing data
4. replay-contract construction is not externally visible state

These are implementation details of patch generation and proof.

## 4. Recommended Approach

Use **strict internalization**.

This is preferred over:

1. keeping a debug envelope in `patch_result`
2. preserving old public patch-planning fields “just in case”
3. leaving hybrid fallback behavior in patch-stage modules

Strict internalization means:

1. only deliverable patch outcomes stay public
2. patch planning and proof models become patch-stage internals
3. downstream systems consume verdicts, not planning internals
4. compatibility branches are deleted instead of tolerated

## 5. External Patch Result Boundary

### 5.1 Patch Result Must Keep

The external patch artifact should remain focused on patch delivery outcomes:

1. `sqlKey`
2. `statementKey`
3. `patchFiles`
4. `applicable`
5. `selectionReason`
6. `deliveryOutcome`
7. verdict-level replay evidence
8. verdict-level syntax evidence

This is enough for:

1. delivery decisions
2. report summaries
3. verification summary linkage
4. debugging at the outcome level

### 5.2 Patch Result Must Drop

The external patch artifact should stop exporting internal planning and proof payloads:

1. `patchTarget`
2. `rewriteMaterialization`
3. `templateRewriteOps`
4. full replay contract payloads
5. other patch-internal planning structures used only to move data between internal steps

If a field exists only because one patch-stage helper needs to pass information to another helper, it should not live in the public result schema.

## 6. Internal Patch Pipeline Shape

The patch subsystem should be explicitly organized into these internal models:

1. `PatchSelection`
2. `PatchBuildPlan`
3. `PatchProof`
4. `PatchFinalization`

### 6.1 `PatchSelection`

Responsibilities:

1. enforce acceptance gates
2. recompute rewrite facts needed by patch planning
3. determine patch family and strategy
4. decide whether patch generation should proceed

### 6.2 `PatchBuildPlan`

Responsibilities:

1. derive materialization mode
2. compute template operations
3. determine patch artifact targets
4. generate patch text

### 6.3 `PatchProof`

Responsibilities:

1. construct proof-only internal target model
2. materialize artifact against XML
3. replay rendered SQL
4. compute syntax verdicts

### 6.4 `PatchFinalization`

Responsibilities:

1. convert internal pipeline state into thin `patch_result`
2. preserve only user-facing or downstream-required verdicts
3. downgrade failed proof/build cases to non-applicable outcomes without leaking internal models

## 7. PatchTarget Status Change

`patchTarget` should no longer be treated as a public patch artifact.

It may continue to exist temporarily as an internal proof model, but only under these rules:

1. it is created inside the patch stage
2. it is consumed only by internal proof logic
3. it is not persisted in public `patch_result`
4. downstream consumers do not read it

If a future refactor can eliminate the name entirely, that is acceptable. This phase only requires removing its public role.

## 8. Module Boundaries

### 8.1 Keep and Narrow

These modules should remain, but only within patch-owned boundaries:

1. `python/sqlopt/stages/patch_generate.py`
   Thin orchestrator only.
2. `python/sqlopt/stages/patch_select.py`
   Selection-only logic.
3. `python/sqlopt/stages/patch_build.py`
   Build-plan logic only.
4. `python/sqlopt/stages/patch_proof.py`
   Proof-only logic.
5. `python/sqlopt/stages/patch_finalize.py`
   Thin result assembly only.

### 8.2 Remove or Downgrade Legacy Roles

These modules need legacy compatibility removed or narrowed:

1. `python/sqlopt/stages/patch_decision_engine.py`
   Must stop assuming acceptance may still contain patch-planning payloads.
2. `python/sqlopt/stages/patch_decision.py`
   Must stop reading patch-owned data from acceptance.
3. `python/sqlopt/stages/patch_verification.py`
   Must stop falling back to acceptance for patch-owned proof inputs.
4. `python/sqlopt/patch_contracts.py`
   Must no longer define a public center-of-gravity contract for downstream consumers.

## 9. Downstream Consumer Rule

After finalization, downstream consumers may only rely on:

1. thin `patch_result`
2. verification artifacts
3. validate-owned acceptance fields

They must not rely on:

1. internal patch planning payloads
2. internal proof contracts
3. internal template operation details

This applies to:

1. report builder
2. report stats
3. fixture harnesses
4. contract tests
5. patch applicability tests

## 10. Testing Strategy

This phase should be implemented with tests that prove:

1. `patch_result` no longer exports internal planning payloads
2. patch-stage modules no longer require acceptance patch fallbacks
3. internal proof still works after `patchTarget` becomes internal-only
4. downstream reporting and fixture harnesses still function from thin patch outputs
5. full regression stays green

The most important test direction is negative:

If a consumer still expects `patchTarget` or another internal patch-planning structure to be public, that test should fail until the consumer is updated.

## 11. Completion Criteria

This phase is complete only when all of the following are true:

1. `patch_generate` behaves as a single patch-owned pipeline
2. `patch_result` is reduced to thin delivery-facing fields
3. `patchTarget` is internal-only or fully eliminated from public outputs
4. no patch-stage module carries legacy fallback for historical patch-planning fields
5. downstream consumers no longer depend on internal patch-planning payloads
6. full test regression remains green

## Harness Plan

### Proof Obligations

1. `patch_generate` owns patch planning end-to-end
2. public `patch_result` stays thin while internal proof still works
3. downstream report and fixture consumers function without public `patchTarget`
4. legacy patch-planning fallbacks are removed rather than silently preserved

### Harness Layers

#### L1 Unit Harness

- Goal: prove thin-result shaping and internal proof behavior remain compatible
- Scope: patch result fields, internal patch target use, fallback removal branches
- Allowed Mocks: synthetic patch payloads are acceptable
- Artifacts Checked: in-memory patch outputs and proof payloads
- Budget: fast PR-safe runtime

#### L2 Fixture / Contract Harness

- Goal: prove patch/report/fixture consumers still work from thin public outputs
- Scope: fixture patch rows, verification rows, report aggregates, downstream reader expectations
- Allowed Mocks: synthetic validate evidence is acceptable when proving patch-result contract shape
- Artifacts Checked: patch artifacts, verification artifacts, report outputs
- Budget: moderate PR-safe runtime

#### L3 Scoped Workflow Harness

- Goal: prove a selected real workflow slice survives the patch-owned pipeline finalization
- Scope: one selected SQL key or mapper slice
- Allowed Mocks: infrastructure-availability patches only
- Artifacts Checked: selected real run outputs
- Budget: targeted workflow runtime

#### L4 Full Workflow Harness

- Goal: prove the finalized patch pipeline remains stable across the broader fixture project
- Scope: full patch/report regression
- Allowed Mocks: only workflow-stability patches that preserve patch semantics
- Artifacts Checked: full run patch, verification, and report outputs
- Budget: separately governed broader regression lane

### Shared Classification Logic

1. thin public delivery-facing fields should reuse production patch semantics
2. downstream consumers should not rebuild hidden patch-planning meaning from tests alone

### Artifacts And Diagnostics

1. `pipeline/patch_generate/patch.results.jsonl`
2. `pipeline/verification/ledger.jsonl`
3. `overview/report.json`

### Execution Budget

1. `L1` and `L2` are expected for pipeline-finalization changes
2. `L3` should prove one real patch-owned workflow slice
3. `L4` remains the governed broad-regression layer

### Regression Ownership

1. any patch-result contract change
2. any internal/public boundary change around `patchTarget`
3. any downstream consumer rewiring for patch artifacts
