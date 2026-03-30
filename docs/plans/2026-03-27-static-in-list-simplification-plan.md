# STATIC_IN_LIST_SIMPLIFICATION Implementation Plan

**Goal:** Add a new patch family that simplifies `IN (single_value)` to equality comparisons.

**Examples:**
- `WHERE id IN (1)` → `WHERE id = 1`
- `WHERE id NOT IN (1)` → `WHERE id <> 1`
- `WHERE name IN ('test')` → `WHERE name = 'test'`

**Architecture:** Register as a static patch family with high confidence gating, requiring semantic equivalence to prove the transformation is safe.

---

## Task 1: Register the Patch Family Spec

**Files:**
- Create: `python/sqlopt/patch_families/specs/static_in_list_simplification.py`
- Modify: `python/sqlopt/patch_families/registry.py`
- Test: `tests/test_patch_family_registry.py`

- [ ] **Step 1: Add family spec module**

```python
from ..models import (
    PatchFamilySpec, PatchFamilyStatus, PatchFamilyScope,
    PatchFamilyAcceptancePolicy, PatchFamilyPatchTargetPolicy,
    PatchFamilyReplayPolicy, PatchFamilyVerificationPolicy,
    PatchFamilyBlockingPolicy, PatchFamilyFixtureObligations,
)

STATIC_IN_LIST_SIMPLIFICATION_SPEC = PatchFamilySpec(
    family="STATIC_IN_LIST_SIMPLIFICATION",
    status="FROZEN_AUTO_PATCH",
    stage="MVP",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        forbid_features=("SUBQUERY", "JOIN"),
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="EXACT_TEMPLATE_EDIT",
        requires_replay_contract=False,
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=(),
        render_mode="NONE",
    ),
    verification=PatchFamilyVerificationPolicy(
        require_replay_match=False,
        require_xml_parse=True,
        require_render_ok=True,
        require_sql_parse=False,
        require_apply_check=False,
    ),
    blockers=PatchFamilyBlockingPolicy(
        block_on_choose=True,
        block_on_foreach=True,
    ),
    fixture_obligations=PatchFamilyFixtureObligations(
        ready_case_required=True,
        blocked_neighbor_required=False,
        replay_assertions_required=False,
        verification_assertions_required=True,
    ),
)
```

- [ ] **Step 2: Register in registry.py**

- [ ] **Step 3: Run registry tests**

---

## Task 2: Implement Family Classification in Validator

**Files:**
- Modify: `python/sqlopt/platforms/sql/validator_sql.py`
- Test: `tests/test_validate_candidate_selection.py`

- [ ] **Step 1: Add classification logic**

```python
def _classify_static_in_list_simplification(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    # Check if transformation is IN(single) -> = or NOT IN(single) -> <>
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False
    # ... pattern matching logic
```

- [ ] **Step 2: Integrate into _derive_patch_target_family**

- [ ] **Step 3: Run validate tests**

---

## Task 3: Add Fixture Coverage

**Files:**
- Modify: `tests/fixtures/project/fixture_scenarios.json`
- Test: `tests/test_fixture_project_validate_harness.py`

- [ ] **Step 1: Add scenario rows**

- [ ] **Step 2: Run fixture tests**

---

## Task 4: Regression

- [ ] **Step 1: Run focused tests**

- [ ] **Step 2: Run full test suite**