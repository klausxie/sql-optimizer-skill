# Family Convergence Abstraction Design

## Goal

Formally consolidate the family convergence logic that has grown during the first three delivery batches, without changing the run/artifact model or widening product behavior.

The purpose of this abstraction is not to add new optimization capability. It is to reduce repeated case-by-case logic across convergence, patch-family derivation, and `sample_project` family scope selection, while keeping already-proven family behavior stable.

## Current Context

The project has already proven a growing set of patch families against real `sample_project` statements. That progress is real, but the code that supports it is now spread across a few hotspots:

- `python/sqlopt/stages/validate_convergence.py`
- `python/sqlopt/platforms/sql/patch_utils.py`
- `python/sqlopt/patch_families/registry.py`
- `scripts/run_sample_project.py`

These files now contain repeated patterns:

- shape-family constants and detection rules
- strategy-to-family mappings
- special-case normalization overrides
- sample-project family scope registries

This is the correct time for a formal consolidation because recent family additions have become structurally similar rather than fundamentally new.

## Non-Goals

This work will not:

- introduce new patch families
- expand blocked families such as broad `JOIN`, `WINDOW`, or `UNION` into auto-patch support
- change `statement_convergence.jsonl` contract shape
- change run directory layout
- add a new stage
- redesign harness/runtime architecture

If a proposed change requires any of the above, it is out of scope for this abstraction pass.

## Design Summary

The abstraction will stay intentionally small and table-driven.

Three things will be formalized:

1. A convergence registry layer for shape families and strategy mappings.
2. A stricter split between one-to-one strategy mappings and generic strategy mappings.
3. A normalized registry for `sample_project` family scopes.

The implementation will preserve current family outcomes. Existing ready statements must remain ready. Existing blocked boundaries must remain blocked unless they were already intentionally proven ready in prior batches.

## Architecture

### 1. Convergence Registry

The convergence logic in `validate_convergence.py` currently mixes four responsibilities:

- shape-family constants
- shape inference
- strategy-to-family mappings
- decision assembly

This design does not fully split those responsibilities into separate modules yet. Instead, it introduces an explicit registry-oriented organization inside the convergence layer so future changes become append-only rather than branch-heavy.

The target internal structure is:

- shape family declarations
- supported family set
- normalized family overrides
- shape-specific strategy-family tables

The expected outcome is that adding a future family becomes:

1. add a shape family constant
2. add a shape detection rule if needed
3. add one registry entry for strategy mapping
4. add sample-project scope entries

and not “change conditionals in multiple files until tests pass.”

### 2. Strategy Mapping Rules

Current behavior has shown that not all strategy types are equal.

There are two categories:

#### A. One-to-one strategy mappings

These are safe to derive automatically from patch family specs because they are specific and unique. Examples:

- `SAFE_EXISTS_REWRITE -> STATIC_EXISTS_REWRITE`
- `SAFE_UNION_COLLAPSE -> STATIC_UNION_COLLAPSE`

These mappings can live in a registry-generated table.

#### B. Generic strategy mappings

These must remain explicit because the same strategy can correspond to different families depending on shape or context. The clearest example is:

- `SAFE_WRAPPER_COLLAPSE`

This strategy must not be blindly auto-mapped from patch family specs, because it can correspond to multiple wrapper-oriented families. It must continue to be resolved through explicit logic using surrounding shape or rewrite facts.

This separation is a key design rule for the abstraction:

> Only one-to-one mappings may be registry-generated. Generic strategies must remain explicitly resolved.

### 3. Sample Project Family Registry

`scripts/run_sample_project.py` is now a real product-progress tool, not just a convenience script.

It should keep a single clear family scope registry, but the data section must become more maintainable. The abstraction pass will keep the current behavior while making the family grouping easier to extend and audit.

The script must continue to support:

- `project`
- `mapper`
- `sql`
- named family scopes

But named family scopes must remain declarative and easy to inspect in one place.

## Detailed Design

### Convergence Layer Boundaries

The convergence layer remains responsible for:

- inferring statement shape family
- determining whether a shape is currently supported
- resolving patch family hints from proposal/strategy
- producing the final statement-level convergence row

The convergence layer should not:

- decide new optimization strategies
- invent new rewrite candidates
- inspect project-level run orchestration

### Shape Inference Rules

Shape inference should remain conservative.

A family must only be inferred when the SQL shape proves the intended structure, not when a broad keyword merely appears.

For example:

- plain presence of `JOIN` must not imply a join-optimization family
- plain presence of `UNION` must not imply a wrapper-collapse family

This means shape inference should continue preferring narrow structural signatures over broad keyword checks.

### Supported vs Blocked Families

The abstraction must preserve the current distinction:

- supported families: already proven through real `sample_project` statements
- blocked families: intentionally recognized but not yet auto-patched
- generic/static fallback: statements that should remain in broad static handling

This distinction must remain data-driven enough that later family work extends the registry rather than rewrites core control flow.

## Files in Scope

### Primary Code

- `python/sqlopt/stages/validate_convergence.py`
- `python/sqlopt/platforms/sql/patch_utils.py`
- `python/sqlopt/patch_families/registry.py`
- `scripts/run_sample_project.py`

### Tests

- `tests/unit/verification/test_validate_convergence.py`
- `tests/unit/patch/test_patch_selection.py`
- `tests/ci/test_run_sample_project_script.py`

Additional targeted tests may be updated if the refactor exposes repeated assumptions.

## Migration Strategy

The abstraction will be done in three safe steps.

### Step 1: Freeze Current Behavior

Add or tighten targeted tests for:

- one-to-one strategy-family mappings
- generic strategy explicit handling
- shape inference boundaries
- family-scope lookup behavior

This prevents accidental widening during refactor.

### Step 2: Consolidate Registries

Move repeated mapping knowledge into explicit registry data structures while keeping existing public behavior unchanged.

Key rule:

- registry-generated mapping may only be used for unambiguous strategy-family pairs

### Step 3: Re-verify Real Sample Outcomes

Re-run a small set of sentinel `sample_project` family scopes and confirm:

- already-ready families stay ready
- blocked boundary families stay blocked
- no generic wrapper or static statement regresses into the wrong family

## Sentinel Real-Run Set

The abstraction must be validated against a small, representative real-run set:

- `IF_GUARDED_FILTER_STATEMENT`
- `STATIC_SUBQUERY_WRAPPER`
- `GROUP_BY_WRAPPER`
- `HAVING_WRAPPER`
- `GROUP_BY_HAVING_ALIAS`
- `STATIC_UNION_COLLAPSE`

These cover:

- dynamic filter convergence
- wrapper families
- alias cleanup families
- union-specific family behavior

## Risks

### Risk 1: Over-generalized strategy mapping

If generic strategies are auto-mapped, families will silently drift. This already showed up with `SAFE_WRAPPER_COLLAPSE`.

Mitigation:

- keep generic strategies out of generated maps
- test them explicitly

### Risk 2: Over-broad shape detection

If broad keywords imply families, large classes of statements will be mislabeled.

Mitigation:

- use structural signatures
- keep regression tests for plain static `JOIN` and plain `UNION`

### Risk 3: “Refactor-only” hidden behavior drift

Because this task is abstraction work, silent behavioral drift is the main danger.

Mitigation:

- require targeted unit tests
- require sentinel real-run verification

## Success Criteria

This abstraction pass is successful when:

1. `validate_convergence.py` has less ad hoc branching for already-proven families.
2. generic strategies remain explicitly resolved rather than auto-derived.
3. `run_sample_project.py` family scope definitions stay declarative and stable.
4. sentinel real-run families preserve current ready/blocked outcomes.
5. full test suite passes without new regressions.

## Recommendation

Proceed with the abstraction as a behavior-preserving refactor, not as a capability expansion.

The implementation should stay disciplined:

- consolidate data
- preserve logic boundaries
- verify with real sample runs

This keeps the project moving toward a maintainable convergence model without prematurely building a large general-purpose framework.
