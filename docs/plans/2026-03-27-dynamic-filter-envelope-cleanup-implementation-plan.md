# Dynamic Filter Envelope Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Onboard `DYNAMIC_FILTER_SELECT_LIST_CLEANUP` and `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP` through the patch family onboarding framework using one shared dynamic-envelope skeleton, without widening dynamic subtree rewrite scope.

**Architecture:** First promote the two dynamic cleanup families from thin frozen specs into explicit registered family specs with a shared skeleton contract. Then tighten dynamic shape classification, replay proof, and fixture obligations around that skeleton before onboarding the two families one at a time: select-list cleanup first, from-alias cleanup second. The implementation must preserve `<where>/<if>` behavior, block broader fallback paths explicitly, and keep `patch_generate` consuming persisted contracts rather than inventing dynamic rewrite behavior.

**Tech Stack:** Python 3, unittest/pytest, existing patch family registry, validate pipeline, dynamic candidate intent engine, template materializer/replay contract, fixture project harness

---

## File Map

- `python/sqlopt/patch_families/specs/dynamic_filter_select_list_cleanup.py`
  Explicit registered spec for the select-list dynamic envelope family with `HIGH` confidence gating and blocked-neighbor obligations.
- `python/sqlopt/patch_families/specs/dynamic_filter_from_alias_cleanup.py`
  Explicit registered spec for the from-alias dynamic envelope family with the same shared skeleton and explicit blocked-neighbor obligations.
- `python/sqlopt/patch_families/specs/frozen_baselines.py`
  Remove the two dynamic envelope families from the thin frozen-seed list once they have explicit specs.
- `python/sqlopt/patch_families/registry.py`
  Register the new explicit dynamic family specs and keep the registry authoritative.
- `python/sqlopt/platforms/sql/rewrite_facts.py`
  Tighten dynamic filter baseline derivation so the shared skeleton is explicit, mutually exclusive, and emits explicit blockers instead of falling through.
- `python/sqlopt/platforms/sql/dynamic_template_support.py`
  Add or refine helper functions for direct-statement and single-subquery-shell dynamic envelope cleanup, plus dynamic `<if>` fingerprint extraction helpers.
- `python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_select_list_cleanup.py`
  Bind select-list cleanup intent to the shared skeleton and block non-trivial aliases explicitly.
- `python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_from_alias_cleanup.py`
  Bind from-alias cleanup intent to the shared skeleton and block cases that would require predicate rewrites.
- `python/sqlopt/platforms/sql/template_materializer.py`
  Extend replay contract building so dynamic envelope families can require `<if test>` and `<if>` body identity in addition to anchors/placeholders.
- `python/sqlopt/verification/patch_replay.py`
  Enforce the new replay contract requirements for dynamic envelope families.
- `tests/test_patch_family_registry.py`
  Registry tests proving the two dynamic families moved from thin frozen specs into explicit family specs with the correct contract sections.
- `tests/test_rewrite_facts.py`
  Shared skeleton tests for accepted direct/select-shell shapes, explicit blocker paths, and mutual exclusivity.
- `tests/test_dynamic_candidate_intent.py`
  Intent tests proving template-preserving edits stay inside the shared skeleton and blocked neighbors do not.
- `tests/test_validate_candidate_selection.py`
  Validate tests proving family persistence happens only for in-scope dynamic cleanup cases and stays blocked for combined/non-trivial neighbors.
- `tests/test_patch_replay.py`
  Replay tests for `<if test>` / `<if>` body preservation and broader-family fallback prevention.
- `tests/fixture_project_harness_support.py`
  Shared fixture helper updates for dynamic registered families and blocked-neighbor assertions.
- `tests/fixtures/project/src/main/resources/com/example/mapper/user/advanced_user_mapper.xml`
  Add dynamic ready and blocked-neighbor statements for both families.
- `tests/fixtures/project/fixture_scenarios.json`
  Add ready and blocked-neighbor rows with explicit `targetDynamicBaselineFamily`, blocker expectations, and no-fallback expectations.
- `tests/test_fixture_project_validate_harness.py`
  Validate harness assertions for dynamic ready cases, blocked-neighbor obligations, and no broader-family fallback.
- `tests/test_fixture_project_patch_report_harness.py`
  Patch/report harness assertions for replay/syntax obligations and family-specific ready rows.

### Task 1: Promote The Two Dynamic Cleanup Families Into Explicit Registered Specs

**Files:**
- Create: `python/sqlopt/patch_families/specs/dynamic_filter_select_list_cleanup.py`
- Create: `python/sqlopt/patch_families/specs/dynamic_filter_from_alias_cleanup.py`
- Modify: `python/sqlopt/patch_families/specs/frozen_baselines.py`
- Modify: `python/sqlopt/patch_families/registry.py`
- Test: `tests/test_patch_family_registry.py`
- Test: `tests/test_patch_contracts.py`

- [ ] **Step 1: Write the failing registry tests**

```python
from sqlopt.patch_contracts import FROZEN_AUTO_PATCH_FAMILIES
from sqlopt.patch_families.registry import lookup_patch_family_spec


def test_dynamic_filter_cleanup_specs_are_explicit_registry_entries() -> None:
    select_spec = lookup_patch_family_spec("DYNAMIC_FILTER_SELECT_LIST_CLEANUP")
    from_spec = lookup_patch_family_spec("DYNAMIC_FILTER_FROM_ALIAS_CLEANUP")

    assert select_spec is not None
    assert from_spec is not None
    assert select_spec.status == "FROZEN_AUTO_PATCH"
    assert from_spec.status == "FROZEN_AUTO_PATCH"
    assert select_spec.acceptance.semantic_min_confidence == "HIGH"
    assert from_spec.acceptance.semantic_min_confidence == "HIGH"
    assert select_spec.fixture_obligations.blocked_neighbor_required is True
    assert from_spec.fixture_obligations.blocked_neighbor_required is True


def test_dynamic_filter_cleanup_frozen_scope_stays_registry_derived() -> None:
    assert "DYNAMIC_FILTER_SELECT_LIST_CLEANUP" in FROZEN_AUTO_PATCH_FAMILIES
    assert "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP" in FROZEN_AUTO_PATCH_FAMILIES
```

- [ ] **Step 2: Run the registry tests to verify they fail**

Run: `python3 -m pytest tests/test_patch_family_registry.py tests/test_patch_contracts.py -q`
Expected: FAIL because both dynamic families still come from the thin `frozen_baselines.py` seed with generic `MEDIUM` policy and no explicit spec modules.

- [ ] **Step 3: Add the explicit family specs and remove them from the thin frozen seed**

Use explicit modules instead of thin frozen placeholders:

```python
DYNAMIC_FILTER_SELECT_LIST_CLEANUP_SPEC = PatchFamilySpec(
    family="DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
    status="FROZEN_AUTO_PATCH",
    stage="MVP_ENVELOPE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        dynamic_shape_families=("IF_GUARDED_FILTER_STATEMENT",),
        forbid_features=("CHOOSE", "BIND", "FOREACH", "SET", "JOIN"),
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="DYNAMIC_STATEMENT_TEMPLATE_EDIT",
        requires_replay_contract=True,
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="EXISTING_PIPELINE",
    ),
    verification=PatchFamilyVerificationPolicy(
        require_replay_match=True,
        require_xml_parse=True,
        require_render_ok=True,
        require_sql_parse=True,
        require_apply_check=True,
    ),
    blockers=PatchFamilyBlockingPolicy(
        block_on_choose=True,
        block_on_bind=True,
        block_on_foreach=True,
    ),
    fixture_obligations=PatchFamilyFixtureObligations(
        ready_case_required=True,
        blocked_neighbor_required=True,
        replay_assertions_required=True,
        verification_assertions_required=True,
    ),
)
```

Mirror the same shape for `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`, then import both explicit spec modules from `registry.py` and remove the two families from `_FROZEN_BASELINE_FAMILIES`.

- [ ] **Step 4: Re-run the registry tests**

Run: `python3 -m pytest tests/test_patch_family_registry.py tests/test_patch_contracts.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/patch_families/specs/dynamic_filter_select_list_cleanup.py python/sqlopt/patch_families/specs/dynamic_filter_from_alias_cleanup.py python/sqlopt/patch_families/specs/frozen_baselines.py python/sqlopt/patch_families/registry.py tests/test_patch_family_registry.py tests/test_patch_contracts.py
git commit -m "feat: register dynamic filter cleanup family specs"
```

### Task 2: Add The Shared Dynamic Envelope Skeleton And Explicit Blockers

**Files:**
- Modify: `python/sqlopt/platforms/sql/rewrite_facts.py`
- Modify: `python/sqlopt/platforms/sql/dynamic_template_support.py`
- Test: `tests/test_rewrite_facts.py`
- Test: `tests/test_dynamic_candidate_intent.py`

- [ ] **Step 1: Write failing rewrite-facts and shared-shape tests**

Add focused tests for the shared skeleton:

```python
def test_build_rewrite_facts_marks_dynamic_filter_select_list_cleanup_direct_envelope() -> None:
    model = build_rewrite_facts_model(sql_unit, rewritten_sql, {}, semantic_evidence, semantic_gate)
    assert model.dynamic_template.capability_profile.baseline_family == "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"
    assert model.dynamic_template.capability_profile.patch_surface == "STATEMENT_BODY"


def test_build_rewrite_facts_marks_dynamic_filter_from_alias_cleanup_single_subquery_shell() -> None:
    model = build_rewrite_facts_model(sql_unit, rewritten_sql, {}, semantic_evidence, semantic_gate)
    assert model.dynamic_template.capability_profile.baseline_family == "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP"


def test_build_rewrite_facts_blocks_combined_dynamic_filter_cleanup_as_scope_mismatch() -> None:
    model = build_rewrite_facts_model(sql_unit, rewritten_sql, {}, semantic_evidence, semantic_gate)
    assert model.dynamic_template.capability_profile.baseline_family is None
    assert "DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH" in model.dynamic_template.capability_profile.blockers


def test_build_rewrite_facts_blocks_bind_foreach_and_set_from_dynamic_envelope_scope() -> None:
    bind_model = build_rewrite_facts_model(bind_sql_unit, bind_rewritten_sql, {}, semantic_evidence, semantic_gate)
    foreach_model = build_rewrite_facts_model(foreach_sql_unit, foreach_rewritten_sql, {}, semantic_evidence, semantic_gate)
    set_model = build_rewrite_facts_model(set_sql_unit, set_rewritten_sql, {}, semantic_evidence, semantic_gate)

    assert "DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH" in bind_model.dynamic_template.capability_profile.blockers
    assert "DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH" in foreach_model.dynamic_template.capability_profile.blockers
    assert "DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH" in set_model.dynamic_template.capability_profile.blockers
```

Add dynamic intent tests for the same shapes so the intent engine does not silently widen scope, including at least one `<bind>` or `<foreach>` case proving the shared blocker path survives through intent assessment.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python3 -m pytest tests/test_rewrite_facts.py tests/test_dynamic_candidate_intent.py -q`
Expected: FAIL because the current rewrite-facts logic still picks select-list first, then from-alias, and does not model the new shared skeleton blocker.

- [ ] **Step 3: Implement the shared skeleton in rewrite facts and helper utilities**

Add small helpers instead of scattering ad hoc checks:

```python
def classify_dynamic_filter_envelope_shape(template_sql: str, feature_set: set[str]) -> tuple[str | None, list[str]]:
    if feature_set & {"CHOOSE", "BIND", "FOREACH", "SET"}:
        return None, ["DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH"]
    if not _is_single_where_flat_if_shape(template_sql):
        return None, ["DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH"]
    if _matches_direct_dynamic_select_envelope(template_sql):
        return "DIRECT_ENVELOPE", []
    if _matches_single_subquery_shell_envelope(template_sql):
        return "SUBQUERY_SHELL_ENVELOPE", []
    return None, ["DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH"]
```

Use this before assigning `DYNAMIC_FILTER_SELECT_LIST_CLEANUP` or `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`. If both cleanups appear true on the same candidate, emit the explicit scope-mismatch blocker instead of choosing one family.

- [ ] **Step 4: Re-run the focused tests**

Run: `python3 -m pytest tests/test_rewrite_facts.py tests/test_dynamic_candidate_intent.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/rewrite_facts.py python/sqlopt/platforms/sql/dynamic_template_support.py tests/test_rewrite_facts.py tests/test_dynamic_candidate_intent.py
git commit -m "feat: add dynamic filter envelope skeleton"
```

### Task 3: Extend Replay Contract Proof For Dynamic `<if>` Preservation

**Files:**
- Modify: `python/sqlopt/platforms/sql/template_materializer.py`
- Modify: `python/sqlopt/verification/patch_replay.py`
- Modify: `tests/test_patch_replay.py`
- Modify: `tests/test_patch_verification.py`

- [ ] **Step 1: Write the failing replay-proof tests**

Add replay tests that lock the new proof requirements:

```python
def test_replay_patch_target_rejects_if_test_drift() -> None:
    patch_target = {
        "replayContract": {
            "requiredIfTestShape": ["status != null"],
            "requiredIfBodyShape": ["AND status = #{status}"],
        },
        ...
    }
    result = replay_patch_target(sql_unit=sql_unit, patch_target=patch_target, fragment_catalog={})
    assert result.matches_target is False
    assert result.drift_reason == "PATCH_DYNAMIC_IF_TEST_DRIFT"


def test_replay_patch_target_rejects_if_body_drift() -> None:
    ...
    assert result.drift_reason == "PATCH_DYNAMIC_IF_BODY_DRIFT"
```

Add one verification test proving these replay failures remain required for the two explicit dynamic families.

- [ ] **Step 2: Run the replay tests to verify they fail**

Run: `python3 -m pytest tests/test_patch_replay.py tests/test_patch_verification.py -q`
Expected: FAIL because replay contracts currently only enforce anchors/includes/placeholders/target SQL.

- [ ] **Step 3: Extend replay contract building and replay enforcement**

Add small replay-contract fields rather than a new verifier:

```python
replay_contract["requiredIfTestShape"] = collect_normalized_if_tests(after_template)
replay_contract["requiredIfBodyShape"] = collect_normalized_if_bodies(after_template)
```

Then enforce them in `patch_replay.py`:

```python
if replay_contract.get("requiredIfTestShape") != collect_normalized_if_tests(template_after):
    return ReplayResult(False, None, None, "PATCH_DYNAMIC_IF_TEST_DRIFT")
if replay_contract.get("requiredIfBodyShape") != collect_normalized_if_bodies(template_after):
    return ReplayResult(False, None, None, "PATCH_DYNAMIC_IF_BODY_DRIFT")
```

Keep this generic so future dynamic envelope families can reuse it.

- [ ] **Step 4: Re-run the replay tests**

Run: `python3 -m pytest tests/test_patch_replay.py tests/test_patch_verification.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/template_materializer.py python/sqlopt/verification/patch_replay.py tests/test_patch_replay.py tests/test_patch_verification.py
git commit -m "feat: enforce dynamic if replay proof"
```

### Task 4: Onboard `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`

**Files:**
- Modify: `python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_select_list_cleanup.py`
- Modify: `tests/test_validate_candidate_selection.py`
- Modify: `tests/fixtures/project/src/main/resources/com/example/mapper/user/advanced_user_mapper.xml`
- Modify: `tests/fixtures/project/fixture_scenarios.json`
- Modify: `tests/fixture_project_harness_support.py`
- Modify: `tests/test_fixture_project_validate_harness.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write failing onboarding tests for the select-list family**

Add validate tests:

```python
def test_validate_persists_dynamic_filter_select_list_cleanup_patch_target() -> None:
    result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))
    assert result.to_contract()["patchTarget"]["family"] == "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"


def test_validate_blocks_dynamic_filter_select_list_cleanup_for_qualified_projection_neighbor() -> None:
    result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))
    assert result.to_contract().get("patchTarget") is None
    assert (result.to_contract().get("patchability") or {}).get("blockingReason") == "DYNAMIC_FILTER_SELECT_LIST_NON_TRIVIAL_ALIAS"
```

Add fixture rows:

1. one ready dynamic case using same-name select aliases outside flat `<where>/<if>`
2. one semantic neighbor using qualified projection aliases
3. one template neighbor using `<choose>` or nested `<if>`

All three rows must carry `targetDynamicBaselineFamily: "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"` on the relevant family surface.

- [ ] **Step 2: Run the onboarding slice to verify it fails**

Run: `python3 -m pytest tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py -q`
Expected: FAIL because the current select-list cleanup path does not yet enforce the new narrow alias-only contract or the expanded blocked-neighbor fixture expectations.

- [ ] **Step 3: Tighten the select-list family implementation**

Keep it narrow:

```python
if not _dynamic_filter_envelope_ready(rewrite_facts):
    ...
if _contains_qualified_projection_alias(template_sql):
    return blocked("DYNAMIC_FILTER_SELECT_LIST_NON_TRIVIAL_ALIAS")
if not _cleanup_is_exact_same_name_projection_aliases(template_sql, rewritten_sql):
    return blocked("DYNAMIC_FILTER_SELECT_LIST_NON_TRIVIAL_ALIAS")
```

Update fixture helpers so blocked-neighbor assertions check:

1. the blocked row does not persist as another broader family
2. the blocked row emits the expected explicit blocker

- [ ] **Step 4: Re-run the onboarding slice**

Run: `python3 -m pytest tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_select_list_cleanup.py tests/test_validate_candidate_selection.py tests/fixtures/project/src/main/resources/com/example/mapper/user/advanced_user_mapper.xml tests/fixtures/project/fixture_scenarios.json tests/fixture_project_harness_support.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py
git commit -m "feat: onboard dynamic filter select list cleanup"
```

### Task 5: Onboard `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`

**Files:**
- Modify: `python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_from_alias_cleanup.py`
- Modify: `tests/test_validate_candidate_selection.py`
- Modify: `tests/fixtures/project/src/main/resources/com/example/mapper/user/advanced_user_mapper.xml`
- Modify: `tests/fixtures/project/fixture_scenarios.json`
- Modify: `tests/fixture_project_harness_support.py`
- Modify: `tests/test_fixture_project_validate_harness.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write failing onboarding tests for the from-alias family**

Add validate tests:

```python
def test_validate_persists_dynamic_filter_from_alias_cleanup_for_single_subquery_shell() -> None:
    result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))
    assert result.to_contract()["patchTarget"]["family"] == "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP"


def test_validate_blocks_dynamic_filter_from_alias_cleanup_when_predicate_rewrite_is_required() -> None:
    result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))
    assert result.to_contract().get("patchTarget") is None
    assert (result.to_contract().get("patchability") or {}).get("blockingReason") == "DYNAMIC_FILTER_FROM_ALIAS_REQUIRES_PREDICATE_REWRITE"
```

Add fixture rows:

1. one ready dynamic case using a single subquery shell or single-table alias cleanup
2. one semantic neighbor using join aliases
3. one template neighbor that would require `<if>` predicate reference rewrite

- [ ] **Step 2: Run the onboarding slice to verify it fails**

Run: `python3 -m pytest tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py -q -k "dynamic_filter_from_alias_cleanup"`
Expected: FAIL because the current from-alias path still accepts broader cases than the spec allows.

- [ ] **Step 3: Tighten the from-alias family implementation**

Keep the gate explicit:

```python
if _template_uses_join_aliases(template_sql):
    return blocked("DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH")
if _cleanup_requires_if_predicate_reference_changes(template_sql, rebuilt_template):
    return blocked("DYNAMIC_FILTER_FROM_ALIAS_REQUIRES_PREDICATE_REWRITE")
if not _matches_single_subquery_shell_or_single_table_alias(template_sql):
    return blocked("DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH")
```

Update fixture helper assertions so this family also proves:

1. blocked neighbors stay out of broader fallback families
2. ready rows satisfy replay + verification obligations from the registered family spec

- [ ] **Step 4: Re-run the onboarding slice**

Run: `python3 -m pytest tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py -q -k "dynamic_filter_from_alias_cleanup"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/dynamic_candidate_intent_rules/dynamic_filter_from_alias_cleanup.py tests/test_validate_candidate_selection.py tests/fixtures/project/src/main/resources/com/example/mapper/user/advanced_user_mapper.xml tests/fixtures/project/fixture_scenarios.json tests/fixture_project_harness_support.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py
git commit -m "feat: onboard dynamic filter from alias cleanup"
```

### Task 6: Run Regression For The Dynamic Envelope Cleanup Slice

**Files:**
- Modify: `docs/designs/patch/2026-03-27-dynamic-filter-envelope-cleanup-design.md` (only if implementation reveals a true spec mismatch)
- Test: `tests/test_patch_family_registry.py`
- Test: `tests/test_rewrite_facts.py`
- Test: `tests/test_dynamic_candidate_intent.py`
- Test: `tests/test_validate_candidate_selection.py`
- Test: `tests/test_patch_replay.py`
- Test: `tests/test_patch_verification.py`
- Test: `tests/test_fixture_project_validate_harness.py`
- Test: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Run the focused dynamic-envelope regression suite**

Run: `python3 -m pytest tests/test_patch_family_registry.py tests/test_rewrite_facts.py tests/test_dynamic_candidate_intent.py tests/test_validate_candidate_selection.py tests/test_patch_replay.py tests/test_patch_verification.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py -q`
Expected: PASS

- [ ] **Step 2: Run full project regression**

Run: `python3 -m pytest -q`
Expected: PASS

- [ ] **Step 3: If implementation exposed a real spec mismatch, update the spec**

Only edit [2026-03-27-dynamic-filter-envelope-cleanup-design.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/designs/patch/2026-03-27-dynamic-filter-envelope-cleanup-design.md) if shipped behavior must differ from:

1. shared direct-or-subquery envelope gate
2. mutual exclusivity between the two families
3. `<if test>` and `<if>` body proof requirements
4. explicit no-fallback blocked-neighbor obligations

- [ ] **Step 4: Re-run the smallest affected suite if the spec changed**

Run: `python3 -m pytest tests/test_patch_family_registry.py tests/test_validate_candidate_selection.py tests/test_patch_replay.py tests/test_patch_verification.py -q`
Expected: PASS

- [ ] **Step 5: Commit any spec sync, otherwise stop at the last feature commit**

```bash
git add docs/designs/patch/2026-03-27-dynamic-filter-envelope-cleanup-design.md
git commit -m "docs: sync dynamic filter envelope cleanup spec"
```

If no spec edits were needed, skip this commit and keep the last feature commit as the final implementation checkpoint.
