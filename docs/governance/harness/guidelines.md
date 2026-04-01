# Harness Engineering Guidelines Design

## Status

Draft validated through brainstorming on 2026-03-29.

## 1. Goal

Define a repository-level harness engineering guideline that starts from the `patch` subsystem and can later scale to the full `sql-optimizer` codebase.

This guideline exists to answer one question consistently:

`How should a capability be proven, regressed, budgeted, and diagnosed across staged workflow boundaries?`

The guideline is intended to be used by:

1. engineers changing runtime behavior
2. engineers writing specs and implementation plans
3. reviewers evaluating whether a change has adequate proof and regression coverage

The immediate target is not "better tests" in the abstract.

The immediate target is:

1. a shared language for harness layers
2. explicit proof obligations at spec time
3. consistent artifact- and workflow-aware regression expectations
4. a reviewable adoption path that does not require immediate repo-wide hard gating

## 2. Non-Goals

This guideline does not attempt to:

1. replace all existing testing guidance with a universal unit-test style guide
2. force every subsystem into the same runtime cost profile
3. require historical code to immediately conform retroactively
4. treat all tests as harnesses
5. make full-workflow tests the only trusted proof layer

It also does not define CI hard gates in the first version.

The first version is a `readiness and review standard`, not yet a repository-wide enforcement mechanism.

## 3. Core Principles

### 3.1 Harness Is A First-Class Design Concern

Harness design is part of capability design.

If a feature cannot explain:

1. what must be proven
2. which layer proves it
3. which artifacts carry the evidence
4. how failures are diagnosed

then the feature design is incomplete.

### 3.2 Prove Boundary Contracts, Not Only Local Functions

Unit tests remain necessary, but they are insufficient when correctness depends on:

1. stage handoff
2. persisted contracts
3. replay or proof artifacts
4. report aggregation
5. workflow state transitions

Harness engineering must prioritize the proof of boundary contracts, not only helper-level behavior.

### 3.3 Shared Production Logic Beats Duplicated Test Semantics

When a concept already exists in production semantics, harnesses should reuse that logic or a shared helper surface whenever practical.

Examples include:

1. blocker family classification
2. delivery tier or delivery class mapping
3. applicability-ready classification
4. semantic readiness buckets

Test-only parallel logic is acceptable only when:

1. production logic cannot be safely imported
2. the duplication is explicitly documented
3. the duplicated mapping is itself treated as a short-term exception

### 3.4 Harnesses Must Be Layered

Every substantial capability must describe its harness stack explicitly.

The default repository model is:

1. `L1 Unit Harness`
2. `L2 Fixture / Contract Harness`
3. `L3 Scoped Workflow Harness`
4. `L4 Full Workflow Harness`

Not every capability needs all four layers immediately, but every missing layer must be explained.

### 3.5 Scoped Realism Comes Before Expensive Realism

The preferred build order for high-correctness verification is:

1. prove local rules
2. prove fixed contracts and scenario matrices
3. prove real workflow behavior on a scoped slice
4. prove system-wide regression on the full baseline

This avoids forcing all trust into slow, unstable, hard-to-diagnose full runs.

### 3.6 Artifacts Are Part Of The Harness

In this repository, persisted artifacts are not byproducts.

They are part of the proof system.

For staged capabilities, harnesses are expected to inspect and compare artifacts such as:

1. `artifacts/acceptance.jsonl`
2. `artifacts/patches.jsonl`
3. embedded verification records inside stage artifacts
4. `report.json`
5. per-SQL evidence files under `sql/<sql-key>/...`

### 3.7 Harnesses Must Be Budgeted And Diagnosable

A harness is not considered healthy if it is realistic but:

1. cannot be run predictably within its intended trigger context
2. times out without clear failure ownership
3. lacks artifact breadcrumbs for diagnosis
4. couples many proof responsibilities into one opaque failure

Each harness layer must therefore define:

1. expected runtime budget
2. allowed scope
3. primary diagnostics on failure

### 3.8 Specs Must Trace To Harness Ownership

Any spec that adds or changes a capability must identify:

1. which proof obligations are new
2. which harness layers will cover them
3. which existing harnesses must be updated
4. which gaps remain deferred

No meaningful feature, family onboarding, or boundary refactor should be considered complete without this traceability.

## 4. Harness Stack

### 4.1 `L1 Unit Harness`

Purpose:

1. prove local rule logic
2. prove engine ordering and branch behavior
3. prove mapper / formatter / replay edge handling
4. lock small, fast regression boundaries

Typical examples:

1. patch decision gate ordering
2. replay drift rejection
3. reason-code mapping
4. family registry invariants

Allowed mocks:

1. liberal mocking is acceptable
2. inputs may be synthetic
3. persisted runtime artifacts are optional

This layer does not prove:

1. cross-stage contract alignment
2. real workflow state progression
3. report aggregation correctness across runtime artifacts

### 4.2 `L2 Fixture / Contract Harness`

Purpose:

1. prove fixed scenario matrices
2. prove cross-module contract alignment
3. lock artifact fields and aggregation semantics
4. prevent family and fixture drift

Typical examples:

1. fixture scenario matrices
2. registry-derived family obligations
3. patch/report aggregate assertions
4. validate-to-patch contract assertions

Allowed mocks:

1. selected synthetic evidence is allowed
2. expensive or unstable DB compare layers may be mocked if the harness goal is contract proof rather than DB realism

This layer must clearly document where it is synthetic and what remains to be proven in workflow harnesses.

### 4.3 `L3 Scoped Workflow Harness`

Purpose:

1. prove real staged workflow behavior
2. prove real artifact production across multiple phases
3. preserve diagnosability and runtime budget by constraining scope

Typical scope:

1. one SQL key
2. one mapper
3. one family
4. one reduced selection slice

Allowed mocks:

1. infrastructure availability patches may be allowed
2. semantic or patch proof logic should remain as real as possible

This layer is the preferred first workflow-level target for new capabilities.

### 4.4 `L4 Full Workflow Harness`

Purpose:

1. prove broad integration and regression closure
2. detect cross-slice drift
3. validate system-level behavior under representative fixture baselines

Typical scope:

1. full fixture project
2. full run plans across all active statements in scope
3. report and verification summary integrity

This layer should be treated as a separately governed system harness, not merely a slow test.

It must define:

1. trigger policy
2. runtime budget
3. failure triage path
4. ownership when it becomes unstable

## 5. Required Spec Sections

Any future spec that materially changes a staged capability should include a `Harness Plan` section with the following required subsections.

### 5.1 Proof Obligations

List exactly what must be proven for the capability to be considered complete.

Examples:

1. boundary contract shape
2. replay proof
3. report aggregation correctness
4. readiness classification
5. state transition integrity

### 5.2 Harness Layers

Map each proof obligation onto one or more harness layers:

1. `L1`
2. `L2`
3. `L3`
4. `L4`

For each layer, specify:

1. `Goal`
2. `Scope`
3. `Allowed Mocks`
4. `Artifacts Checked`
5. `Budget`

### 5.3 Shared Classification Logic

Call out any semantic mappings that must be shared between runtime and harnesses.

Examples:

1. blocker family
2. delivery class
3. applicability-ready
4. semantic gate bucket

### 5.4 Artifacts And Diagnostics

List the authoritative or required artifact reads for the capability.

Also list which diagnostics are expected when a harness fails.

### 5.5 Execution Budget

Describe how the harness stack should be run in practice.

At minimum:

1. which layers are expected on normal PR validation
2. which layers are expected on broader integration validation
3. which layers are allowed to be slower or less frequent

### 5.6 Regression Ownership

State which future changes must update this harness surface.

Examples:

1. new family onboarding
2. new report field aggregation
3. workflow-state refactor
4. new patch strategy

Patch-facing specs should start from:

1. `docs/governance/harness/templates/patch-harness-plan-template.md`
2. `docs/governance/harness/templates/patch-harness-review-checklist.md`
3. `docs/governance/harness/templates/patch-harness-session-prompt-templates.md`

Patch-facing reviews should pair the spec's `Harness Plan` with a completed copy of the patch harness review checklist.

A bare link to the checklist is weaker than explicit answers.

When starting a fresh session, authors should prefer the reusable prompts in `docs/governance/harness/templates/patch-harness-session-prompt-templates.md` rather than relying on memory or shorthand references to "do harness engineering".

## 6. Review Checklist

Reviews should use a short, explicit checklist rather than vague statements such as "tests look good".

For patch-facing work, the default reusable review surface is `docs/governance/harness/templates/patch-harness-review-checklist.md`.

Authors or reviewers should answer it directly in the review summary, PR description, or review comment.

Reference sample:

1. `docs/governance/harness/reviews/2026-03-30-exists-rewrite-harness-review.md`

For any staged capability change, reviewers should ask:

1. What boundary contract changed?
2. Which harness layer proves that boundary now?
3. Does the harness reuse production semantics where required, or has it recreated logic in tests?
4. Which artifacts should be inspected when this fails?
5. Is the proof responsibility placed at the right layer, or was it pushed into either too-local unit tests or too-expensive full-workflow tests?
6. If a new capability or family was added, which harness layer was explicitly extended?

If these questions cannot be answered crisply, the harness plan is incomplete.

## 7. Patch Adoption Surface

Version 1 rollout should update the patch documentation surface first.

The initial adoption surface is:

1. `docs/designs/patch/2026-03-25-patch-system-design.md`
2. `docs/project/10-sql-patchability-architecture.md`
3. future patch-family onboarding specs
4. future patch workflow and report refactor specs

The first patch rollout should standardize:

1. explicit `Harness Plan` sections in patch-facing specs
2. shared terminology for `L1` through `L4`
3. explicit artifact comparison surfaces
4. an explicit patch review checklist with completed answers during review

## 8. Patch Subsystem Initial Adoption

The `patch` subsystem is the first adoption target because it already has:

1. staged handoff across scan / validate / patch / verification / report
2. explicit persisted artifacts
3. proof-driven delivery rules
4. fixture family onboarding
5. report aggregation and blocker classification

The first adoption wave should standardize the following:

### 8.1 Explicit Patch Harness Stack

The patch subsystem should explicitly document:

1. `L1`: engine, replay, formatting, family registry, verification unit harnesses
2. `L2`: fixture scenario matrix and patch/report contract harnesses
3. `L3`: scoped real workflow harnesses for selected SQL keys or families
4. `L4`: full fixture-project workflow baselines

### 8.2 Shared Classification Requirements

The patch subsystem should not allow duplicate harness-only semantics for:

1. blocker family
2. delivery class
3. applicability-ready
4. dynamic delivery classification when already represented in production logic

Any remaining duplicated logic should be treated as a temporary exception and documented as such.

### 8.3 Artifact-Centric Regression

Patch harnesses should treat the following as primary comparison surfaces:

1. `artifacts/acceptance.jsonl`
2. `artifacts/patches.jsonl`
3. embedded verification records in `artifacts/acceptance.jsonl` / `artifacts/patches.jsonl`
4. `report.json`

### 8.4 Scoped Workflow Must Be A Formal Layer

Patch should not rely only on:

1. unit harnesses
2. fixture harnesses
3. full fixture-project goldens

There must be an intermediate, explicitly budgeted workflow harness for one-SQL or one-family slices.

### 8.5 Full Workflow Must Be Governed

Patch full-workflow baselines must be treated as a governed harness layer with:

1. explicit runtime expectations
2. explicit selection or fixture size assumptions
3. explicit failure triage expectations

If a full-workflow harness becomes unstable or consistently exceeds budget, the correct response is not to ignore it.

The correct response is to either:

1. repair its budget and triage model
2. narrow scope and preserve it as `L3`
3. move broader coverage to a separately governed slower lane

## 9. Rollout Strategy

Version 1 rollout is `admission-oriented`, not yet hard-gated.

That means:

1. new relevant specs should include a `Harness Plan`
2. new patch family onboarding work should explicitly map to harness layers
3. patch-facing reviews should complete the patch harness review checklist during design and implementation review
4. historical code is not required to be rewritten immediately to comply

Recommended rollout order:

1. adopt in new patch-related specs
2. adopt in patch family onboarding and patch-report related changes
3. adopt in adjacent staged subsystems such as validate/report workflow refactors
4. only after repeated use, identify which checklist items are mature enough for CI or explicit review gates

## 10. Open Questions And Deferred Hard Gates

The following are intentionally deferred from version 1:

1. exact CI mapping for each harness layer
2. exact required runtime budgets for every layer
3. whether all report aggregate classifications must always be computed from shared helpers
4. whether full-workflow harnesses should be mandatory for every staged subsystem
5. whether a repository-wide harness manifest should exist

These are deferred because the repository first needs one successful reference adoption in `patch`.

Version 1 should therefore be judged by:

1. whether future specs can use it cleanly
2. whether patch-related reviews become more concrete
3. whether harness ownership becomes easier to discuss and enforce

## 11. Summary Position

The repository should treat harness engineering as a design discipline for staged correctness, not as a synonym for "more tests".

The working rule is:

`Every staged capability must explain how it is proven locally, how its contracts are proven across artifacts, how real workflow behavior is proven in a scoped slice, and how system-wide regression is governed under budget.`
