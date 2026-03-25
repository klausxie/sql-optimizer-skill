# Patch System Design

## Status

Draft validated through brainstorming on 2026-03-25.

## 1. Goal

Design the patch subsystem for the SQL optimizer project under a `high correctness, low coverage` strategy.

The subsystem must:

1. Generate patches only when the system can prove the patch implements the validated optimized SQL.
2. Prefer blocking or review-only outcomes over speculative auto-patching.
3. Keep patch generation deterministic, auditable, and bounded to explicitly supported safe baseline families.

The subsystem must not:

1. Maximize auto-patch coverage at the expense of correctness.
2. Let `patch_generate` invent rewrite logic that was not already validated and materialized upstream.
3. Treat `git apply --check` as proof of SQL or template correctness.

## 2. Core Position

The patch subsystem is not a generic "write optimized SQL back to XML" feature.

It is a constrained execution layer that:

1. Accepts a single validated target SQL.
2. Accepts a template-aware rewrite plan that is already aligned to that target.
3. Generates a patch only if the plan can be replayed back to the same target SQL with sufficient syntax and semantic evidence.

The intended product promise is:

`Only emit patches for safe baseline families whose template rewrite can be proven to replay to the validated target SQL.`

## 3. Design Principles

1. `validate` owns the persisted patch target contract; `patch_generate` only consumes it and does not re-choose the target.
2. Dynamic MyBatis templates are blocked by default.
3. Dynamic cases are auto-patchable only when they match an explicit safe baseline family.
4. Template-preserving rewrites are allowed; flattened-SQL overwrite of dynamic XML is not.
5. Every auto-patch decision must be backed by an explicit evidence chain.
6. If replay, syntax, or target consistency is incomplete, the result must degrade to `REVIEW_ONLY` or `BLOCKED`.

## 4. Outcome Classes

The patch subsystem must classify each validated statement into one of three delivery outcomes.

### 4.1 `AUTO_PATCH`

The system generates a patch file automatically.

This is allowed only when all hard gates pass.

### 4.2 `REVIEW_ONLY`

The optimization direction may be useful, but the system cannot prove a safe automatic template rewrite.

The system may output:

1. blocker reasons
2. replay failure reasons
3. repair hints
4. optional template-aware suggestions

No patch file is emitted.

### 4.3 `BLOCKED`

The system must refuse patch generation because:

1. the target SQL is not sufficiently validated
2. the source template is unsupported or ambiguous
3. the statement carries unacceptable security or semantic risk

No patch file is emitted.

## 5. Full-Scenario Decision Matrix

### 5.1 `AUTO_PATCH`

The following classes are in scope for automatic patch generation.

| Scenario | Conditions |
| --- | --- |
| Static statement rewrite | Unique PASS target, semantic gate PASS, confidence MEDIUM/HIGH, source locator stable, effective diff present |
| Static wrapper collapse | Same as above, plus fingerprint strength EXACT and wrapper proven collapsible |
| Simple static CTE/subquery inline | Static statement body only, no dynamic tags, target maps directly back to statement body |
| Static alias/projection cleanup | No template structure change, no placeholder binding change, statement-body rewrite only |
| Static aggregation safe baseline | Must match an explicit safe baseline family already declared ready |
| Static include wrapper collapse | Must match `STATIC_INCLUDE_WRAPPER_COLLAPSE`, with stable include chain, no property binding, no dynamic subtree, and replay closing cleanly |
| Dynamic count wrapper collapse | Must match `DYNAMIC_COUNT_WRAPPER_COLLAPSE`, template-preserving, replay verified |
| Dynamic filter wrapper collapse | Must match `DYNAMIC_FILTER_WRAPPER_COLLAPSE`, template-preserving, replay verified |
| Dynamic filter select-list cleanup | Must match `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`, template-preserving, replay verified |
| Dynamic filter from-alias cleanup | Must match `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`, template-preserving, replay verified |
| Aggregation ready families | Must match one of the authoritative in-scope ready families: `REDUNDANT_GROUP_BY_WRAPPER`, `REDUNDANT_HAVING_WRAPPER`, `REDUNDANT_DISTINCT_WRAPPER`, `GROUP_BY_FROM_ALIAS_CLEANUP`, `GROUP_BY_HAVING_FROM_ALIAS_CLEANUP`, `DISTINCT_FROM_ALIAS_CLEANUP` |

For the first implementation plan, the authoritative `AUTO_PATCH` family set is frozen to exactly:

1. static statement rewrite
2. static wrapper collapse
3. static CTE/simple subquery inline
4. static alias/projection cleanup
5. `STATIC_INCLUDE_WRAPPER_COLLAPSE`
6. `DYNAMIC_COUNT_WRAPPER_COLLAPSE`
7. `DYNAMIC_FILTER_WRAPPER_COLLAPSE`
8. `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`
9. `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`
10. `REDUNDANT_GROUP_BY_WRAPPER`
11. `REDUNDANT_HAVING_WRAPPER`
12. `REDUNDANT_DISTINCT_WRAPPER`
13. `GROUP_BY_FROM_ALIAS_CLEANUP`
14. `GROUP_BY_HAVING_FROM_ALIAS_CLEANUP`
15. `DISTINCT_FROM_ALIAS_CLEANUP`

Anything outside this list is out of scope for the first implementation plan and must remain `REVIEW_ONLY` or `BLOCKED`.

### 5.2 `REVIEW_ONLY`

These scenarios may be analyzable, but should not auto-patch under the target strategy.

| Scenario | Reason |
| --- | --- |
| Dynamic template that does not match a safe baseline | Source rewrite not uniquely determined |
| `FOREACH_IN_PREDICATE` | Collection rendering and empty-input semantics are hard to prove safely |
| `SET_SELECTIVE_UPDATE` | Dynamic comma trimming and conditional clause assembly are high-risk |
| Deep `if/choose` subtree rewrites | Branch-preserving rewrite is not yet reliable enough |
| Include with property bindings | Fragment meaning depends on call-site bindings |
| Aggregation optimization outside ready baseline families | Semantic intent may be plausible but source rewrite remains under-constrained |
| Replay partially works but cannot exactly close to target | Not acceptable for high-correctness auto-patch |

### 5.3 `BLOCKED`

These scenarios must be refused.

| Scenario | Reason |
| --- | --- |
| `${}` security risk | Unsafe pattern must not auto-patch |
| Semantic gate not PASS | Target SQL is not validated |
| Semantic confidence LOW | Evidence is insufficient |
| Multiple PASS candidates or no clear winner | Patch layer must not choose among validated variants |
| Missing locator/range | Source location is not stable enough for patching |
| Annotation mapper / non-XML SQL source | Outside current stable scan coverage |
| Unresolved include / partial scan evidence | Input evidence is incomplete |
| No effective change | Decorative or no-op patch must not be emitted |
| Dynamic subtree rewrite beyond statement-body preserving edits | No reliable deterministic mapping exists yet |
| `WINDOW`, `UNION`, or non-baselined aggregation constraints | No safe baseline exists yet |

## 6. Hard Gates For `AUTO_PATCH`

Every `AUTO_PATCH` decision must satisfy all of the following.

### 6.1 Target Uniqueness

`validate` must output exactly one selected target SQL for the statement.

Required properties:

1. unique PASS winner
2. stable `selectedCandidateId`
3. explicit `selectedPatchStrategy`
4. explicit target SQL fingerprint or normalized representation

### 6.2 Semantic Proof

The selected target must satisfy:

1. semantic gate `PASS`
2. confidence `MEDIUM` or `HIGH`
3. no hard conflicts

Additional stricter rule:

1. wrapper collapse requires exact fingerprint evidence

### 6.3 Patchability Proof

The statement must be allowed by patch safety and strategy planning.

This includes:

1. allowed capability
2. selected strategy
3. no active dynamic or aggregation blocker family

### 6.4 Template-Preserving Proof

The rewrite must preserve the source template structure required for correctness.

That means:

1. no flattened overwrite of dynamic XML
2. no uncontrolled branch removal
3. no loss of required include anchors
4. no placeholder semantics drift

### 6.5 Replay Proof

The template rewrite plan must replay to the target SQL.

Replay proof means:

1. apply `templateRewriteOps` to a template copy
2. rerender using the same template-expansion logic
3. compare replayed SQL against the selected target SQL
4. treat mismatch as non-auto-patchable

### 6.6 Syntax Proof

Patch generation must check:

1. XML still parses
2. template still renders
3. rendered SQL parses for the target dialect
4. when available, dialect-level `EXPLAIN` or equivalent syntax verification passes

### 6.7 Applicability Proof

Generated patch files must pass file-level applicability checks.

Current file-level proof:

1. `git apply --check`

This is necessary but not sufficient.

### 6.8 Artifact Proof

Patch results must record enough evidence for audit and later diagnosis.

Minimum evidence set:

1. selected target SQL
2. selected strategy and family
3. replay result
4. syntax-check result
5. patch applicability result

## 7. Architecture

The patch subsystem should be modeled as four layers.

### 7.1 `validate` Owns The Persisted Target Contract

`validate` is responsible for selecting the single patch target and persisting the full upstream contract consumed by `patch_generate`.

It should output a target contract, not just a free-form `rewrittenSql`.

The planner/materializer runs inside `validate` as an internal sublayer. It does not publish a separate external contract. Its outputs are persisted as part of the validate artifact.

The authoritative persisted schema is `PatchTargetContract` in Section 8.1. Section 7.1 defines ownership; Section 8.1 defines the contract fields.

### 7.2 Planner/Materializer Builds A Rewrite Plan Inside `validate`

This layer maps the selected target SQL back to source-template operations as an internal `validate` sublayer.

Ownership boundary:

1. planner/materializer computes rewrite-planning artifacts
2. `validate` persists those artifacts into the acceptance contract
3. `patch_generate` only consumes persisted artifacts and never recomputes them

It must answer:

1. whether the target is materializable
2. which family it belongs to
3. whether the rewrite is statement-body or fragment-body based
4. which anchors, includes, and dynamic structures must be preserved

`templateRewriteOps` should be treated as a formal IR for patch generation.

### 7.3 `patch_generate` Executes The Plan

`patch_generate` should be execution-only.

Its responsibilities:

1. load accepted target and template rewrite plan
2. verify uniqueness and consistency
3. apply template rewrite ops
4. produce diff/patch files
5. run patch-level checks
6. emit structured patch results

It must not:

1. choose a different candidate
2. invent new source rewrite logic
3. flatten dynamic mapper SQL back into XML

### 7.4 `patch_verification` Proves The Patch

`patch_verification` should become the final correctness gate for patch delivery.

It should record five groups of checks:

1. decision checks
2. template checks
3. replay checks
4. SQL checks
5. patch checks

## 8. Proposed Contracts

### 8.1 `PatchTargetContract`

Purpose:

Describe exactly which optimized SQL the patch must implement.

This is the authoritative persisted contract consumed by `patch_generate`.

Minimum required fields:

1. `sqlKey`
2. `selectedCandidateId`
3. `targetSql`
4. `targetSqlNormalized`
5. `targetSqlFingerprint`
6. `semanticGateStatus`
7. `semanticGateConfidence`
8. `selectedPatchStrategy`
9. `family`
10. `semanticEquivalence`
11. `patchability`
12. `rewriteMaterialization`
13. `templateRewriteOps`
14. `replayContract`
15. `evidenceRefs`

### 8.2 `PatchReplayContract`

Purpose:

Describe how to prove the template rewrite still produces the selected target SQL.

Minimum required fields:

1. `replayMode`
2. `requiredTemplateOps`
3. `expectedRenderedSql`
4. `expectedRenderedSqlNormalized`
5. `expectedFingerprint`
6. `requiredAnchors`
7. `requiredIncludes`
8. `requiredPlaceholderShape`
9. `dialectSyntaxCheckRequired`

## 9. Error Handling

Failures should be normalized into three buckets.

### 9.1 `AUTO_PATCH_FAILED -> REVIEW_ONLY`

Use when the optimization direction may still be useful, but auto-patching cannot be proven safe.

Examples:

1. replay mismatch
2. XML parse failure after rewrite
3. SQL syntax verification failure
4. patch applicability failure
5. missing template anchors after rewrite

### 9.2 `VALIDATION_INSUFFICIENT -> BLOCKED`

Use when patch generation should not even start because the target is not sufficiently validated.

Examples:

1. semantic gate not PASS
2. confidence LOW
3. multiple PASS candidates
4. partial scan evidence

### 9.3 `UNSUPPORTED_SHAPE -> BLOCKED`

Use when the statement shape is outside the declared safe baseline surface.

Examples:

1. `FOREACH_IN_PREDICATE`
2. `SET_SELECTIVE_UPDATE`
3. non-baselined dynamic subtree rewrites
4. `WINDOW`
5. `UNION`
6. include property-binding rewrites

## 10. Testing Strategy

Patch correctness must be tested at multiple layers.

### 10.1 Rule And Planner Unit Tests

Verify each family is classified correctly as:

1. `AUTO_PATCH`
2. `REVIEW_ONLY`
3. `BLOCKED`

### 10.2 Materialization Unit Tests

Verify `targetSql -> templateRewriteOps` remains deterministic and template-preserving.

Key assertions:

1. dynamic tags preserved
2. include anchors preserved
3. placeholders preserved
4. duplicate clauses rejected

### 10.3 Replay Unit Tests

For every auto-patchable family, assert:

`templateRewriteOps applied to template -> replayed SQL == targetSql`

This is the most important proof layer.

### 10.4 Patch Generation Integration Tests

Verify:

1. reason code
2. strategy type
3. patch contents
4. patch applicability result

### 10.5 Fixture And Full-Run Regression

Each new auto-patch family must add fixture coverage that locks:

1. target family
2. expected strategy
3. replay expectation
4. nearby blocked cases

### 10.6 Mandatory Hard Tests

The patch subsystem should explicitly test:

1. target drift between validated SQL and replayed SQL
2. anchor preservation failures
3. placeholder preservation failures
4. safe-baseline false positives
5. no-op patch suppression
6. `git apply --check` success combined with replay failure

## 11. Current Recommended Scope

The near-term implementation scope should focus on making existing safe baseline families provable and stable, not on broadening family coverage.

Recommended priority:

1. formalize target and replay contracts
2. strengthen replay verification from a boolean gate into explicit structured proof
3. expand patch verification to cover template and SQL correctness, not just patch applicability
4. lock the authoritative first-plan family set from Section 5.1 with stronger replay-oriented fixture tests
5. only then consider new safe baseline families

## 12. Non-Goals

This design does not aim to:

1. support all MyBatis dynamic constructs
2. auto-patch all semantically valid optimized SQL
3. use LLM output as final patch proof
4. make `patch_generate` responsible for candidate selection
5. eliminate manual review for under-constrained template shapes

## 13. Final Design Statement

The patch subsystem should be treated as a proof-driven delivery layer, not a best-effort rewrite layer.

The correct success criterion is:

`The system auto-generates a patch only when the chosen target SQL, the template rewrite plan, the replayed rendered SQL, and the emitted patch all agree.`
