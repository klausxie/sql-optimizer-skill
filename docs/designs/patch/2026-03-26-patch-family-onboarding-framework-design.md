# Patch Family Onboarding Framework Design

## Status

Draft validated through brainstorming on 2026-03-26.

## 1. Goal

Design a standard onboarding framework for adding new auto-patch families under the project's `high correctness, low coverage` strategy.

The framework must:

1. Turn "add a new patch family" into a fixed, auditable workflow.
2. Prevent family expansion from drifting across validate, patch generation, replay, verification, and fixtures.
3. Keep `AUTO_PATCH` gated by the same proof-driven standards already established by the patch system.

The framework must not:

1. Relax correctness gates for the sake of higher patch coverage.
2. Rebuild the entire patch subsystem into a generic DSL.
3. Migrate every existing family at once.

## 2. Core Position

The next scaling problem for patch generation is not "which family should be added next".

It is "how to add a family without changing five subsystems by hand and missing one of them".

The framework therefore treats each patch family as a first-class contract with one authoritative definition that all relevant stages can reference.

## 3. Why This Is Needed

Family expansion currently touches multiple layers at once:

1. shape recognition and rewrite facts
2. semantic acceptance and candidate selection
3. `patchTarget` derivation
4. replay contract generation
5. patch verification rules
6. fixture and regression coverage

Without a standard entry point, each new family becomes a distributed manual change set. That raises the risk of:

1. family names appearing in one layer but not another
2. `AUTO_PATCH` outcomes without matching proof rules
3. fixture drift from actual runtime family boundaries
4. dynamic cases expanding faster than their replay guarantees

## 4. Recommended Approach

The framework should use a **registration-based design**.

This is preferred over:

1. checklist-only/manual onboarding
2. fully declarative DSL/config-driven onboarding

### 4.1 Why Registration-Based

It gives the project:

1. one place to declare a family's intended scope
2. enough structure to prevent omission
3. enough code expressiveness to handle nuanced blockers and proof rules
4. a clean path to partial declarative evolution later if recurring patterns justify it

### 4.2 Relationship To Future DSL Work

Choosing registration now does **not** reject later declarative evolution.

The intended sequence is:

1. first stabilize family onboarding with registered specs
2. observe which spec fields are repetitive across families
3. only then consider extracting the repetitive subset into a more declarative form

## 5. Framework Objectives

The framework must solve four concrete problems.

### 5.1 Fixed Entry Points

Every family must enter the system through the same explicit surfaces.

### 5.2 Explicit Boundaries

Each family must declare what is in scope, what is blocked, and what proof it requires.

### 5.3 Shared Family Semantics

`rewrite_facts`, `validate`, `patchTarget`, replay, verification, and fixture harnesses must all align to the same family contract.

### 5.4 Predictable Expansion Cost

Adding a family should produce a predictable implementation checklist instead of an open-ended hunt across the codebase.

## 6. Non-Goals

The framework intentionally does not try to do the following in its first version.

1. define a universal SQL rewrite DSL
2. eliminate code-based family logic
3. auto-generate implementation code
4. auto-generate all tests
5. migrate all existing families immediately

## 7. Patch Family Spec Model

Each family must register a `PatchFamilySpec`.

The first version of the spec must carry the following categories.

### 7.1 Identity

Defines which family is being described.

Required fields:

1. `family`
2. `status`
3. `stage`

Optional fields:

1. `owner`
2. `notes`

### 7.2 Scope

Defines what shapes are eligible to be considered for the family.

Required fields:

1. `statement_types`
2. `requires_template_preserving`

Optional fields:

1. `dynamic_shape_families`
2. `aggregation_shape_families`
3. `forbid_features`
4. `patch_surface`

This answers:

`What input is allowed to be interpreted as this family candidate?`

### 7.3 Acceptance Policy

Defines validate-stage requirements.

Required fields:

1. `semantic_required_status`
2. `semantic_min_confidence`

Optional fields:

1. `fingerprint_requirement`
2. `known_equivalence_rule`
3. `requires_unique_pass_winner`

This answers:

`Under what evidence is the family allowed to become a persisted patch target?`

### 7.4 Patch Target Policy

Defines how the family becomes `patchTarget`.

Required fields:

1. `selected_patch_strategy`
2. `requires_replay_contract`

Optional fields:

1. `materialization_modes`
2. `target_type`
3. `target_ref_policy`

This answers:

`What must validate persist for this family before patch_generate is allowed to proceed?`

### 7.5 Replay Policy

Defines replay proof requirements.

Required fields:

1. `required_template_ops`
2. `render_mode`

Optional fields:

1. `required_anchors`
2. `required_includes`
3. `required_placeholder_shape`
4. `dialect_syntax_check_required`

This answers:

`What must remain true after the template rewrite for replay to count as valid?`

### 7.6 Verification Policy

Defines hard proof requirements for delivery.

Required fields:

1. `require_replay_match`
2. `require_xml_parse`
3. `require_render_ok`
4. `require_sql_parse`
5. `require_apply_check`

This answers:

`Which evidence is mandatory before this family can remain AUTO_PATCH?`

### 7.7 Blocking Policy

Defines adjacent shapes that must be rejected even if they look similar.

Optional fields:

1. `block_on_dynamic_subtree`
2. `block_on_choose`
3. `block_on_bind`
4. `block_on_foreach`
5. `block_on_expression_alias`
6. `custom_blockers`

This answers:

`Which near-miss shapes must be forced back to REVIEW_ONLY or BLOCKED?`

### 7.8 Fixture Obligations

Defines the minimum regression surface for the family.

Required fields:

1. `ready_case_required`
2. `blocked_neighbor_required`
3. `replay_assertions_required`
4. `verification_assertions_required`

This answers:

`What minimum test evidence must exist before the family is considered onboarded?`

## 8. Mapping To Existing Code

The framework is a contract layer. It does not replace current subsystem logic. It constrains and aligns it.

### 8.1 Scope -> Rewrite Facts / Shape Classification

Primary integration points:

1. `python/sqlopt/platforms/sql/rewrite_facts.py`
2. `python/sqlopt/platforms/sql/aggregation_analysis.py`
3. `python/sqlopt/platforms/sql/dynamic_candidate_intent_*`

Responsibility:

1. recognize family-compatible shape
2. produce shape labels that align with the registered family

### 8.2 Acceptance Policy -> Semantic / Validate

Primary integration points:

1. `python/sqlopt/platforms/sql/semantic_equivalence.py`
2. `python/sqlopt/platforms/sql/validator_sql.py`

Responsibility:

1. enforce family-specific semantic requirements
2. decide whether `patchTarget` may be emitted

### 8.3 Patch Target Policy -> Patch Target Construction

Primary integration points:

1. `python/sqlopt/platforms/sql/validator_sql.py`
2. `python/sqlopt/patch_contracts.py`

Responsibility:

1. derive `patchTarget.family`
2. choose strategy and materialization rules consistent with the family

### 8.4 Replay Policy -> Materialization / Replay

Primary integration points:

1. `python/sqlopt/platforms/sql/template_materializer.py`
2. `python/sqlopt/platforms/sql/patch_strategy_planner.py`
3. `python/sqlopt/verification/patch_replay.py`

Responsibility:

1. build the replay contract
2. enforce anchor/include/placeholder preservation

### 8.5 Verification Policy -> Patch Verification

Primary integration points:

1. `python/sqlopt/stages/patch_verification.py`
2. `python/sqlopt/verification/patch_syntax.py`

Responsibility:

1. decide whether proof is sufficient for `VERIFIED`
2. degrade incomplete proof to `UNVERIFIED`

### 8.6 Blocking Policy -> Patch Safety / Decision Engine

Primary integration points:

1. `python/sqlopt/platforms/sql/patch_safety.py`
2. `python/sqlopt/platforms/sql/patch_capability_rules/*`
3. `python/sqlopt/stages/patch_decision_engine.py`

Responsibility:

1. reject near-miss shapes
2. keep family boundaries narrow and explicit

### 8.7 Fixture Obligations -> Harnesses

Primary integration points:

1. `tests/fixtures/project/fixture_scenarios.json`
2. `tests/test_fixture_project_validate_harness.py`
3. `tests/test_fixture_project_patch_report_harness.py`

Responsibility:

1. ensure ready and blocked neighbors both exist
2. ensure proof fields are asserted at runtime

## 9. Recommended Code Organization

The framework should be implemented as Python spec objects with centralized registration.

Recommended structure:

1. `python/sqlopt/patch_families/models.py`
2. `python/sqlopt/patch_families/registry.py`
3. `python/sqlopt/patch_families/specs/*.py`

Examples:

1. `static_include_wrapper_collapse.py`
2. `static_alias_projection_cleanup.py`
3. `dynamic_filter_select_envelope_cleanup.py`
4. `redundant_group_by_wrapper.py`

This is preferred over:

1. placing all family metadata in `patch_contracts.py`
2. leaving family definitions scattered across unrelated modules
3. introducing a heavy config DSL too early

## 10. Standard Onboarding Workflow

Every new family must follow the same onboarding order.

### 10.1 Define Family Spec

Write the family contract first.

### 10.2 Add Shape Recognition

Make rewrite facts classify the family reliably.

### 10.3 Add Acceptance Rules

Make validate decide when the family can produce a target.

### 10.4 Add Replay / Materialization Rules

Make planner and replay enforce the family proof contract.

### 10.5 Add Verification Rules

Make patch verification degrade missing proof appropriately.

### 10.6 Add Fixture Coverage

Provide at least:

1. one ready case
2. one blocked-neighbor case

### 10.7 Only Then Add To Frozen Auto-Patch Scope

A family must not enter the authoritative frozen `AUTO_PATCH` set before the previous six steps are complete.

### 10.8 Complete Harness Review Handoff

Before review closes, the onboarding change should include:

1. a completed `Harness Plan` in the family-facing spec or design note
2. a completed copy of `docs/governance/harness/templates/patch-harness-review-checklist.md` in the review summary or PR description
3. an explicit statement of which `L1` through `L4` layers changed

## 11. Minimum Viable Framework

The first implementation must stay small.

### 11.1 Required MVP Pieces

1. introduce `PatchFamilySpec`
2. introduce registry lookup
3. integrate registry reads in `validator_sql.py`
4. integrate registry reads in `patch_verification.py`
5. add fixture consistency assertions against the registry

### 11.1.1 MVP Authority Boundary

The registry is the long-term shared family contract, but **it is not fully authoritative across every stage in MVP**.

For the first implementation:

1. `identity`, `acceptance`, and `verification` sections are authoritative in MVP
2. `fixture obligations` are authoritative in MVP for consistency checks
3. `scope`, `patch target policy`, `replay policy`, and `blocking policy` are present in the spec model in MVP, but may remain partly hand-wired in existing subsystem code for the first pass

This means the MVP is intentionally a **registry seed**, not yet a full cross-subsystem replacement.

### 11.1.2 What Remains Hand-Wired In MVP

For the first implementation, the following logic is allowed to stay in existing subsystem code:

1. detailed shape recognition in rewrite-facts and dynamic intent analyzers
2. replay/materialization construction in planner/materializer code
3. blocker enforcement in patch safety and decision engine

The framework must still document these concerns, but the MVP does not require all of them to become registry-driven on day one.

### 11.2 MVP Migration Scope

The first version should not migrate the entire family catalog.

It should onboard exactly:

1. one already-stable family as the template
2. one newly expanded family as the first true onboarding use case

Recommended pair:

1. `STATIC_INCLUDE_WRAPPER_COLLAPSE` as the stable template family
2. `STATIC_ALIAS_PROJECTION_CLEANUP` as the first onboarding-driven expansion family

### 11.3 MVP Success Interpretation

The MVP succeeds if it proves that:

1. a family can be registered once and referenced by validate and verification consistently
2. frozen-family and fixture assertions can be checked against registry state
3. a new family such as `STATIC_ALIAS_PROJECTION_CLEANUP` can be onboarded without requiring a simultaneous rewrite of replay/materialization and blocker logic

The MVP does **not** require `STATIC_ALIAS_PROJECTION_CLEANUP` to be fully driven by registry-owned replay/materialization or blocker enforcement in the first pass.

## 12. Recommended Rollout Order

The rollout should happen in this order.

### 12.1 Step 1: Build Framework MVP

Do not optimize for coverage yet. Optimize for a stable onboarding method.

### 12.2 Step 2: Register A Mature Existing Family

Use `STATIC_INCLUDE_WRAPPER_COLLAPSE` as the reference family to prove the framework can describe an already-correct path.

### 12.3 Step 3: Onboard `STATIC_ALIAS_PROJECTION_CLEANUP`

Use the framework to bring in the first new family with low proof complexity.

### 12.4 Step 4: Revisit Dynamic Expansion

Only after the first new family is successfully onboarded should the project move to a narrow dynamic family such as the proposed dynamic filter select-envelope cleanup shape.

### 12.5 Step 5: Re-evaluate Partial Declarative Evolution

Once several families are stabilized in the registry, reassess whether a subset of spec fields should become more declarative.

## 13. Candidate Families After Framework MVP

Under the stated priority of "high-frequency first, but never by lowering proof standards", the next family sequence should be:

1. `STATIC_ALIAS_PROJECTION_CLEANUP`
2. a narrow dynamic select-envelope cleanup family for plain `<where><if>...</if></where>` shapes

The dynamic family is intentionally not part of the framework MVP because it still carries wider boundary risk than the static alias cleanup case.

## 14. Success Criteria

The framework is successful when:

1. a new family can be onboarded through a predictable checklist
2. family scope is declared once and referenced consistently across stages
3. `AUTO_PATCH` cannot be expanded without explicit replay and verification policy
4. fixture and runtime proof assertions stay aligned with family registration
5. review handoff stays concrete rather than relying on ad-hoc prose

## 15. Design Outcome

The recommended next step after this spec is not immediate family expansion.

It is:

`Build the patch family onboarding framework MVP, register one stable family, then onboard STATIC_ALIAS_PROJECTION_CLEANUP through that framework.`

## Harness Plan

### Proof Obligations

1. family scope is declared once and consumed consistently across validate, patch, replay, verification, and fixture layers
2. onboarding a new family cannot silently widen `AUTO_PATCH`
3. fixture obligations stay aligned with registry state
4. representative ready and blocked-neighbor cases exist for each onboarded family

### Harness Layers

#### L1 Unit Harness

- Goal: prove registry construction, family model invariants, and family-scope validation rules
- Scope: family identity, acceptance policy, replay policy, fixture obligation invariants
- Allowed Mocks: synthetic family specs are acceptable
- Artifacts Checked: in-memory family models and registry payloads
- Budget: fast PR-safe runtime

#### L2 Fixture / Contract Harness

- Goal: prove family registration stays aligned with fixture scenarios and downstream contracts
- Scope: `fixture_scenarios.json`, validate/patch/report family expectations, blocked-neighbor coverage
- Allowed Mocks: synthetic validate evidence is acceptable when the goal is family contract alignment
- Artifacts Checked: fixture matrix, acceptance artifacts, patch artifacts, verification artifacts, report aggregates
- Budget: moderate PR-safe runtime

#### L3 Scoped Workflow Harness

- Goal: prove a newly onboarded family works through a real selected workflow slice
- Scope: one family or one representative SQL key per family
- Allowed Mocks: infrastructure-availability patches only
- Artifacts Checked: selected run outputs across validate, patch, verification, and report
- Budget: targeted workflow runtime

#### L4 Full Workflow Harness

- Goal: prove family onboarding does not destabilize the broader fixture portfolio
- Scope: full fixture-project regression after family onboarding
- Allowed Mocks: only workflow-stability patches that preserve patch semantics
- Artifacts Checked: full run artifacts and report summaries
- Budget: separately governed broader regression lane

### Shared Classification Logic

1. family readiness and frozen-scope checks should reuse registry-derived semantics
2. fixture obligations should not become an untracked parallel taxonomy

### Artifacts And Diagnostics

1. `tests/fixtures/project/fixture_scenarios.json`
2. `pipeline/validate/acceptance.results.jsonl`
3. `pipeline/patch_generate/patch.results.jsonl`
4. `pipeline/verification/ledger.jsonl`
5. `overview/report.json`

### Execution Budget

1. `L1` and `L2` should run for framework and family-onboarding changes
2. `L3` should run for each newly onboarded family before widening scope
3. `L4` should remain the governed broad-regression layer

### Regression Ownership

1. every new patch family
2. every change to family registry semantics
3. every change to fixture obligation interpretation
4. every validate/patch/report field that encodes family identity
