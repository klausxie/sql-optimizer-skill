# Aggregation Baseline Family Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `patch` coverage by onboarding the next aggregation / wrapper / alias-cleanup baseline families through the fixture-driven family framework, without relaxing the current proof-first delivery bar.

**Architecture:** Use the existing patch-system and patch-family-onboarding specs as the governing design, then drive implementation from fixture obligations outward. Each family must land as one complete vertical slice: fixture scenarios, validate-family persistence, patch generation output, verification/report assertions, and no broader-family fallback. Roll out families one at a time in the order `REDUNDANT_GROUP_BY_WRAPPER`, `REDUNDANT_HAVING_WRAPPER`, `DISTINCT_FROM_ALIAS_CLEANUP`, `GROUP_BY_HAVING_FROM_ALIAS_CLEANUP`.

**Tech Stack:** Python 3, unittest/pytest, existing patch family registry, validate pipeline, patch generation pipeline, verification ledger, fixture project harness, report builder

---

## Governing Specs

- `docs/designs/patch/2026-03-25-patch-system-design.md`
- `docs/designs/patch/2026-03-26-patch-family-onboarding-framework-design.md`

## File Map

- `tests/fixtures/project/fixture_scenarios.json`
  Add ready and blocked-neighbor scenarios for each target family and keep the scenario matrix authoritative.
- `tests/fixtures/project/src/main/resources/com/example/mapper/**/*.xml`
  Add or adjust fixture mapper statements that exercise each ready case and its blocked neighbors.
- `tests/fixture_project_harness_support.py`
  Extend helpers that derive registered families, blocked-neighbor obligations, and patch/report assertions from the scenario matrix.
- `tests/test_fixture_project_validate_harness.py`
  Assert validate-side family persistence, dynamic/aggregation profile shape, and blocked-neighbor behavior.
- `tests/test_fixture_project_patch_report_harness.py`
  Assert patch generation, replay/syntax evidence presence, family-specific output snippets, and report aggregates.
- `tests/test_validate_candidate_selection.py`
  Focused validate regression tests for family derivation and `patchTarget` persistence.
- `tests/test_patch_generate_orchestration.py`
  Focused patch-generation tests for applicable family outputs and explicit blocked reasons.
- `tests/test_patch_verification.py`
  Family-policy regression tests for proof requirements and family-specific verdict behavior.
- `python/sqlopt/platforms/sql/aggregation_analysis.py`
  Detect safe-baseline aggregation families and keep shape/constraint/safe-baseline boundaries explicit.
- `python/sqlopt/platforms/sql/rewrite_facts.py`
  Surface aggregation capability profile data consistently into validate artifacts.
- `python/sqlopt/platforms/sql/patch_safety.py`
  Convert aggregation capability data into patchability gates and blocker families without widening unsafe scope.
- `python/sqlopt/platforms/sql/patch_strategy_planner.py`
  Produce the correct patch strategy only for ready baseline families.
- `python/sqlopt/platforms/sql/validator_sql.py`
  Persist `patchTarget.family`, replay contract, and family-specific selection decisions only for in-scope ready families.
- `python/sqlopt/stages/patch_decision_engine.py`
  Consume persisted family contracts cleanly and preserve family-specific skip reasons when a scenario is blocked.
- `python/sqlopt/stages/report_builder.py`
  Keep family counts and aggregation-ready stats aligned with scenario expectations.
- `python/sqlopt/patch_families/specs/frozen_baselines.py`
  Confirm the target families remain in the authoritative frozen auto-patch set until or unless they move to explicit specs.

### Task 1: Audit The Current Family Matrix And Encode Missing Fixture Obligations

**Files:**
- Modify: `tests/fixtures/project/fixture_scenarios.json`
- Modify: `tests/fixture_project_harness_support.py`
- Test: `tests/test_fixture_project_validate_harness.py`
- Test: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write the failing fixture expectations for the four target families**

Add or extend scenario rows so each target family has:

```json
{
  "sqlKey": "demo.order.harness.aggregateOrdersByStatusWrapped#v9",
  "scenarioClass": "PATCH_READY_STATEMENT",
  "targetPatchStrategy": "EXACT_TEMPLATE_EDIT",
  "targetRegisteredFamily": "REDUNDANT_GROUP_BY_WRAPPER",
  "targetBlockerFamily": "REDUNDANT_GROUP_BY_WRAPPER"
}
```

Also add one blocked-neighbor row per family with `targetPatchStrategy: null` and an explicit blocker reason proving the family does not over-match.

- [ ] **Step 2: Run the fixture harness tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: FAIL because one or more target families are missing ready rows, blocked-neighbor rows, or report expectations.

- [ ] **Step 3: Update fixture helpers so obligations are derived from the scenario matrix**

Make the helper layer reject silent drift:

```python
def fixture_registered_blocked_neighbor_families(scenarios: list[dict[str, object]]) -> set[str]:
    return {
        str(row["targetRegisteredFamily"])
        for row in scenarios
        if row.get("targetRegisteredFamily")
        and row.get("targetPatchStrategy") is None
    }
```

Ensure the helpers treat the four target families as mandatory for ready-case and blocked-neighbor coverage.

- [ ] **Step 4: Re-run the fixture harness tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: PASS for matrix completeness checks, even if downstream implementation assertions still fail later.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/project/fixture_scenarios.json tests/fixture_project_harness_support.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py
git commit -m "test: encode aggregation family fixture obligations"
```

### Task 2: Onboard `REDUNDANT_GROUP_BY_WRAPPER` As A Complete Vertical Slice

**Files:**
- Modify: `python/sqlopt/platforms/sql/aggregation_analysis.py`
- Modify: `python/sqlopt/platforms/sql/rewrite_facts.py`
- Modify: `python/sqlopt/platforms/sql/patch_safety.py`
- Modify: `python/sqlopt/platforms/sql/patch_strategy_planner.py`
- Modify: `python/sqlopt/platforms/sql/validator_sql.py`
- Modify: `tests/test_validate_candidate_selection.py`
- Modify: `tests/test_patch_generate_orchestration.py`
- Modify: `tests/test_fixture_project_validate_harness.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write the failing targeted tests**

Add focused tests:

```python
def test_validate_persists_redundant_group_by_wrapper_patch_target() -> None:
    contract = result.to_contract()
    assert contract["patchTarget"]["family"] == "REDUNDANT_GROUP_BY_WRAPPER"
    assert contract["selectedPatchStrategy"]["strategyType"] == "EXACT_TEMPLATE_EDIT"


def test_patch_generate_emits_group_by_wrapper_patch_for_ready_fixture() -> None:
    patch = patch_by_key["demo.order.harness.aggregateOrdersByStatusWrapped#v9"]
    assert patch["applicable"] is True
    assert patch["patchTarget"]["family"] == "REDUNDANT_GROUP_BY_WRAPPER"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_patch_generate_orchestration.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: FAIL because the family is not yet fully wired through validate, patch, and fixture assertions.

- [ ] **Step 3: Implement the family through the validate pipeline**

Keep the family narrow and explicit:

```python
if safe_baseline_family == "REDUNDANT_GROUP_BY_WRAPPER":
    return {
        "eligible": True,
        "allowedCapabilities": ["EXACT_TEMPLATE_EDIT"],
        "blockingReason": None,
    }
```

Only persist `patchTarget` when:
- aggregation analysis marks `safeBaselineFamily == "REDUNDANT_GROUP_BY_WRAPPER"`
- semantic gate is `PASS`
- confidence meets the frozen family threshold
- no broader aggregation blocker is active

- [ ] **Step 4: Re-run the targeted tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_patch_generate_orchestration.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/aggregation_analysis.py python/sqlopt/platforms/sql/rewrite_facts.py python/sqlopt/platforms/sql/patch_safety.py python/sqlopt/platforms/sql/patch_strategy_planner.py python/sqlopt/platforms/sql/validator_sql.py tests/test_validate_candidate_selection.py tests/test_patch_generate_orchestration.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py
git commit -m "feat: onboard redundant group by wrapper family"
```

### Task 3: Onboard `REDUNDANT_HAVING_WRAPPER` With A Protected Blocked Neighbor

**Files:**
- Modify: `python/sqlopt/platforms/sql/aggregation_analysis.py`
- Modify: `python/sqlopt/platforms/sql/rewrite_facts.py`
- Modify: `python/sqlopt/platforms/sql/patch_safety.py`
- Modify: `python/sqlopt/platforms/sql/patch_strategy_planner.py`
- Modify: `python/sqlopt/platforms/sql/validator_sql.py`
- Modify: `tests/test_validate_candidate_selection.py`
- Modify: `tests/test_patch_generate_orchestration.py`
- Modify: `tests/test_fixture_project_validate_harness.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write the failing tests for the ready and blocked-neighbor cases**

Add one ready-case assertion and one blocked-neighbor assertion:

```python
def test_validate_persists_redundant_having_wrapper_patch_target() -> None:
    assert contract["patchTarget"]["family"] == "REDUNDANT_HAVING_WRAPPER"


def test_validate_blocks_having_wrapper_neighbor_when_group_by_having_shape_is_not_safe_baseline() -> None:
    assert contract.get("patchTarget") is None
    assert contract["patchability"]["blockingReason"] == "HAVING_REVIEW_ONLY"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: FAIL because the family either does not persist or over-matches its blocked neighbor.

- [ ] **Step 3: Implement the family without broadening non-baseline HAVING support**

Only allow the exact baseline path and keep review-only fallbacks intact:

```python
if safe_baseline_family == "REDUNDANT_HAVING_WRAPPER":
    strategy = {"strategyType": "EXACT_TEMPLATE_EDIT"}
else:
    strategy = None
```

Preserve existing `HAVING` review-only classification for everything outside the ready baseline.

- [ ] **Step 4: Re-run the targeted tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/aggregation_analysis.py python/sqlopt/platforms/sql/rewrite_facts.py python/sqlopt/platforms/sql/patch_safety.py python/sqlopt/platforms/sql/patch_strategy_planner.py python/sqlopt/platforms/sql/validator_sql.py tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py
git commit -m "feat: onboard redundant having wrapper family"
```

### Task 4: Onboard `DISTINCT_FROM_ALIAS_CLEANUP` And Keep Scope Mismatch Explicit

**Files:**
- Modify: `python/sqlopt/platforms/sql/aggregation_analysis.py`
- Modify: `python/sqlopt/platforms/sql/patch_safety.py`
- Modify: `python/sqlopt/platforms/sql/validator_sql.py`
- Modify: `tests/test_validate_candidate_selection.py`
- Modify: `tests/test_fixture_project_validate_harness.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write the failing family-specific tests**

```python
def test_validate_persists_distinct_from_alias_cleanup_family() -> None:
    assert contract["patchTarget"]["family"] == "DISTINCT_FROM_ALIAS_CLEANUP"


def test_validate_blocks_distinct_alias_cleanup_scope_mismatch() -> None:
    assert contract.get("patchTarget") is None
    assert contract["patchability"]["blockingReason"] == "STATIC_ALIAS_PROJECTION_CLEANUP_SCOPE_MISMATCH"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: FAIL because the alias-cleanup baseline is either not persisted or is not protected from near-miss alias shapes.

- [ ] **Step 3: Implement the narrow alias-cleanup baseline**

Keep the family derivation tied to the exact safe-baseline signal from aggregation analysis. Do not let generic static alias cleanup absorb these rows implicitly.

- [ ] **Step 4: Re-run the focused tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/aggregation_analysis.py python/sqlopt/platforms/sql/patch_safety.py python/sqlopt/platforms/sql/validator_sql.py tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py
git commit -m "feat: onboard distinct from alias cleanup family"
```

### Task 5: Onboard `GROUP_BY_HAVING_FROM_ALIAS_CLEANUP` And Prove It Does Not Collapse Into Broader Families

**Files:**
- Modify: `python/sqlopt/platforms/sql/aggregation_analysis.py`
- Modify: `python/sqlopt/platforms/sql/patch_safety.py`
- Modify: `python/sqlopt/platforms/sql/validator_sql.py`
- Modify: `tests/test_validate_candidate_selection.py`
- Modify: `tests/test_fixture_project_validate_harness.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write the failing ready and blocked-neighbor tests**

```python
def test_validate_persists_group_by_having_from_alias_cleanup_family() -> None:
    assert contract["patchTarget"]["family"] == "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP"


def test_validate_blocks_group_by_having_alias_cleanup_neighbor_without_safe_baseline() -> None:
    assert contract.get("patchTarget") is None
    assert contract["patchability"]["blockingReason"] in {
        "GROUP_BY_REVIEW_ONLY",
        "HAVING_REVIEW_ONLY",
    }
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: FAIL because the family is not yet derived as a first-class ready baseline or because fallback behavior is not explicit enough.

- [ ] **Step 3: Implement the family and keep fallback boundaries explicit**

Only produce `patchTarget` for the combined alias-cleanup family when aggregation analysis marks the exact safe baseline. Do not fallback to `GROUP_BY_FROM_ALIAS_CLEANUP` or `REDUNDANT_HAVING_WRAPPER` on the same row.

- [ ] **Step 4: Re-run the focused tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/aggregation_analysis.py python/sqlopt/platforms/sql/patch_safety.py python/sqlopt/platforms/sql/validator_sql.py tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py
git commit -m "feat: onboard group by having alias cleanup family"
```

### Task 6: Tighten Verification And Report Coverage For The Expanded Family Set

**Files:**
- Modify: `python/sqlopt/stages/report_builder.py`
- Modify: `python/sqlopt/stages/patch_verification.py`
- Modify: `tests/test_patch_verification.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write the failing verification and report assertions**

Add tests that prove the new families:
- show up in report family counters
- require replay/syntax evidence when applicable
- remain `UNVERIFIED` if required family evidence is missing

```python
def test_patch_verification_marks_missing_required_group_by_wrapper_evidence_unverified() -> None:
    assert rows[0]["reason_code"] == "PATCH_DECISION_EVIDENCE_INCOMPLETE"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_verification.py tests/test_fixture_project_patch_report_harness.py`
Expected: FAIL because report aggregation or verification checks do not yet fully assert the newly onboarded families.

- [ ] **Step 3: Align report and verification outputs with the new family set**

Keep behavior registry-derived rather than hard-coding ad hoc family lists in multiple places.

- [ ] **Step 4: Re-run the focused tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_verification.py tests/test_fixture_project_patch_report_harness.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/stages/report_builder.py python/sqlopt/stages/patch_verification.py tests/test_patch_verification.py tests/test_fixture_project_patch_report_harness.py
git commit -m "test: align verification and report with aggregation families"
```

### Task 7: Final Regression Pass And Rollout Readiness

**Files:**
- Modify: `docs/project/10-sql-patchability-architecture.md`
- Modify: `docs/project/06-delivery-checklist.md`
- Test: `tests/test_fixture_project_validate_harness.py`
- Test: `tests/test_fixture_project_patch_report_harness.py`
- Test: `tests/test_validate_candidate_selection.py`
- Test: `tests/test_patch_generate_orchestration.py`
- Test: `tests/test_patch_verification.py`

- [ ] **Step 1: Update docs to reflect the expanded ready-family surface**

Document the newly delivered families and note that fixture obligations now gate onboarding.

- [ ] **Step 2: Run the focused regression suite**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py tests/test_validate_candidate_selection.py tests/test_patch_generate_orchestration.py tests/test_patch_verification.py`
Expected: PASS

- [ ] **Step 3: Run the broader acceptance checks**

Run: `env PYTHONPATH=python python3 -m pytest -q`
Expected: PASS, or documented unrelated failures only

Run: `env PYTHONPATH=python python3 scripts/schema_validate_all.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/project/10-sql-patchability-architecture.md docs/project/06-delivery-checklist.md
git commit -m "docs: update patch family expansion guidance"
```

- [ ] **Step 5: Prepare handoff notes**

Capture:
- which families are now fully onboarded
- which blocked neighbors remain intentionally review-only
- whether verification still has any family-specific gaps that should become the next plan
